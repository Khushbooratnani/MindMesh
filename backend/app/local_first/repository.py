"""
Repository layer for isolated Locker Authentication Database operations.
Strictly handles verifiers and sessions; zero private data touchpoints.
"""
from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.local_first.models import LockerAuthIdentityModel, LockerAuthSessionModel


class LockerAuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_identity_by_user_ref(self, user_reference: str) -> Optional[LockerAuthIdentityModel]:
        stmt = select(LockerAuthIdentityModel).where(LockerAuthIdentityModel.user_reference == user_reference)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_identity_by_id(self, identity_id: str) -> Optional[LockerAuthIdentityModel]:
        stmt = select(LockerAuthIdentityModel).where(LockerAuthIdentityModel.id == identity_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_identity(
        self,
        user_reference: str,
        argon2_hash: str,
        recovery_hash: str,
    ) -> LockerAuthIdentityModel:
        identity = LockerAuthIdentityModel(
            id=str(uuid.uuid4()),
            user_reference=user_reference,
            argon2_hash=argon2_hash,
            recovery_hash=recovery_hash,
            failed_attempts=0,
            lockout_until=None,
        )
        self.session.add(identity)
        await self.session.flush()
        return identity

    async def update_credentials(
        self,
        identity_id: str,
        argon2_hash: str,
        recovery_hash: Optional[str] = None,
    ) -> None:
        vals = {"argon2_hash": argon2_hash, "failed_attempts": 0, "lockout_until": None}
        if recovery_hash:
            vals["recovery_hash"] = recovery_hash
        stmt = update(LockerAuthIdentityModel).where(LockerAuthIdentityModel.id == identity_id).values(**vals)
        await self.session.execute(stmt)
        await self.session.flush()

    async def record_failed_attempt(
        self,
        identity_id: str,
        failed_attempts: int,
        lockout_until: Optional[datetime],
    ) -> None:
        stmt = (
            update(LockerAuthIdentityModel)
            .where(LockerAuthIdentityModel.id == identity_id)
            .values(failed_attempts=failed_attempts, lockout_until=lockout_until)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def reset_failed_attempts(self, identity_id: str) -> None:
        stmt = (
            update(LockerAuthIdentityModel)
            .where(LockerAuthIdentityModel.id == identity_id)
            .values(failed_attempts=0, lockout_until=None)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def create_session(
        self,
        identity_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> LockerAuthSessionModel:
        session = LockerAuthSessionModel(
            id=str(uuid.uuid4()),
            identity_id=identity_id,
            token_hash=token_hash,
            expires_at=expires_at,
            last_activity_at=datetime.now(timezone.utc),
            revoked=False,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_session_by_token_hash(self, token_hash: str) -> Optional[LockerAuthSessionModel]:
        stmt = (
            select(LockerAuthSessionModel)
            .where(LockerAuthSessionModel.token_hash == token_hash)
            .where(LockerAuthSessionModel.revoked == False)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def revoke_session_by_token_hash(self, token_hash: str) -> None:
        stmt = (
            update(LockerAuthSessionModel)
            .where(LockerAuthSessionModel.token_hash == token_hash)
            .values(revoked=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke_all_sessions(self, identity_id: str) -> None:
        stmt = (
            update(LockerAuthSessionModel)
            .where(LockerAuthSessionModel.identity_id == identity_id)
            .values(revoked=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()
