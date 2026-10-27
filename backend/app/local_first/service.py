"""
Service layer for the isolated Private Locker Authentication Database.
Manages Argon2id credentials, recovery verification, lockout policies, and session tokens.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from typing import Optional, Tuple

from passlib.hash import argon2
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.local_first.models import LockerAuthIdentityModel, LockerAuthSessionModel
from app.local_first.repository import LockerAuthRepository


class LockerAuthService:
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    IDLE_TIMEOUT_SECONDS = 120

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = LockerAuthRepository(session)

    @classmethod
    def derive_pseudonymous_ref(cls, user_id: str) -> str:
        """Derives a one-way pseudonymous identifier for the user reference."""
        salt = settings.auth_secret_key + ":locker-auth-pseudonym-salt"
        return hashlib.sha256(f"{user_id}:{salt}".encode("utf-8")).hexdigest()

    @classmethod
    def hash_verifier(cls, secret_value: str) -> str:
        return argon2.hash(secret_value)

    @classmethod
    def verify_verifier(cls, secret_value: str, hash_value: str) -> bool:
        try:
            return argon2.verify(secret_value, hash_value)
        except Exception:
            return False

    @classmethod
    def hash_token(cls, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def register_locker(
        self,
        user_id: str,
        password: str,
    ) -> Tuple[LockerAuthIdentityModel, str]:
        user_ref = self.derive_pseudonymous_ref(user_id)
        existing = await self.repo.get_identity_by_user_ref(user_ref)
        if existing:
            raise ValueError("Locker identity already exists for this user")

        if len(password) < 8:
            raise ValueError("Locker password must be at least 8 characters")

        argon2_hash = self.hash_verifier(password)
        recovery_key = "rcv_" + secrets.token_urlsafe(24)
        recovery_hash = self.hash_verifier(recovery_key)

        identity = await self.repo.create_identity(
            user_reference=user_ref,
            argon2_hash=argon2_hash,
            recovery_hash=recovery_hash,
        )
        return identity, recovery_key

    async def authenticate_and_create_session(
        self,
        user_id: str,
        password: str,
    ) -> str:
        user_ref = self.derive_pseudonymous_ref(user_id)
        identity = await self.repo.get_identity_by_user_ref(user_ref)
        if not identity:
            raise PermissionError("Locker does not exist")

        now = datetime.now(timezone.utc)
        if identity.lockout_until is not None:
            lockout = identity.lockout_until
            if lockout.tzinfo is None:
                lockout = lockout.replace(tzinfo=timezone.utc)
            if lockout > now:
                remaining = int((lockout - now).total_seconds())
                raise PermissionError(f"Locker locked out due to multiple failed attempts. Retry in {remaining}s")

        if not self.verify_verifier(password, identity.argon2_hash):
            new_attempts = identity.failed_attempts + 1
            lockout_time = None
            if new_attempts >= self.MAX_FAILED_ATTEMPTS:
                lockout_time = now + timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
            await self.repo.record_failed_attempt(identity.id, new_attempts, lockout_time)
            await self.session.commit()
            raise ValueError("Incorrect locker password")

        # Success - reset attempts
        await self.repo.reset_failed_attempts(identity.id)

        raw_token = secrets.token_urlsafe(32)
        token_hash = self.hash_token(raw_token)
        expires_at = now + timedelta(days=1)

        await self.repo.create_session(identity.id, token_hash, expires_at)
        return raw_token

    async def validate_session(self, user_id: str, raw_token: str) -> Optional[LockerAuthSessionModel]:
        token_hash = self.hash_token(raw_token)
        session = await self.repo.get_session_by_token_hash(token_hash)
        if not session:
            return None

        user_ref = self.derive_pseudonymous_ref(user_id)
        identity = await self.repo.get_identity_by_id(session.identity_id)
        if not identity or identity.user_reference != user_ref:
            return None

        now = datetime.now(timezone.utc)
        last_activity = session.last_activity_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)

        # Enforce idle timeout (120 seconds)
        if (now - last_activity).total_seconds() > self.IDLE_TIMEOUT_SECONDS:
            await self.repo.revoke_session_by_token_hash(token_hash)
            return None

        session.last_activity_at = now
        await self.session.commit()
        return session

    async def revoke_session(self, raw_token: str) -> None:
        token_hash = self.hash_token(raw_token)
        await self.repo.revoke_session_by_token_hash(token_hash)

    async def revoke_all_user_sessions(self, user_id: str) -> None:
        user_ref = self.derive_pseudonymous_ref(user_id)
        identity = await self.repo.get_identity_by_user_ref(user_ref)
        if identity:
            await self.repo.revoke_all_sessions(identity.id)

    async def recover_locker(
        self,
        user_id: str,
        recovery_key: str,
        new_password: str,
    ) -> str:
        user_ref = self.derive_pseudonymous_ref(user_id)
        identity = await self.repo.get_identity_by_user_ref(user_ref)
        if not identity:
            raise PermissionError("Locker does not exist")

        if not self.verify_verifier(recovery_key, identity.recovery_hash):
            raise ValueError("Invalid recovery key")

        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")

        new_argon2 = self.hash_verifier(new_password)
        new_recovery = "rcv_" + secrets.token_urlsafe(24)
        new_rec_hash = self.hash_verifier(new_recovery)

        await self.repo.update_credentials(identity.id, new_argon2, new_rec_hash)
        await self.repo.revoke_all_sessions(identity.id)
        return new_recovery

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str,
    ) -> None:
        user_ref = self.derive_pseudonymous_ref(user_id)
        identity = await self.repo.get_identity_by_user_ref(user_ref)
        if not identity:
            raise PermissionError("Locker does not exist")

        if not self.verify_verifier(old_password, identity.argon2_hash):
            raise ValueError("Incorrect old password")

        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters")

        new_argon2 = self.hash_verifier(new_password)
        await self.repo.update_credentials(identity.id, new_argon2)
        await self.repo.revoke_all_sessions(identity.id)

    async def get_status(self, user_id: str) -> dict:
        user_ref = self.derive_pseudonymous_ref(user_id)
        identity = await self.repo.get_identity_by_user_ref(user_ref)
        if not identity:
            return {"has_locker": False, "exists": False, "locked_out": False, "status": "locked"}

        now = datetime.now(timezone.utc)
        is_locked_out = False
        if identity.lockout_until is not None:
            lockout = identity.lockout_until
            if lockout.tzinfo is None:
                lockout = lockout.replace(tzinfo=timezone.utc)
            is_locked_out = lockout > now

        return {
            "has_locker": True,
            "exists": True,
            "locked_out": is_locked_out,
            "status": "locked",
        }
