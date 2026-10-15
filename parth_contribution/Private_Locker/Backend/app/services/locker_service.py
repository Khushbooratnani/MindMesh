import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.locker import PrivateLockerModel, LockerSessionModel
from app.services.auth_service import get_password_hash, verify_password, get_token_hash

class LockerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_locker(self, user_id: str, password: str) -> tuple[PrivateLockerModel, str]:
        """Creates a private locker and returns the locker model and plaintext recovery key."""
        stmt = select(PrivateLockerModel).where(PrivateLockerModel.user_id == user_id)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("Locker already exists for this user")

        recovery_key = secrets.token_hex(16)
        
        new_locker = PrivateLockerModel(
            user_id=user_id,
            password_hash=get_password_hash(password),
            recovery_key_hash=get_password_hash(recovery_key) # Use argon2 for recovery key hash too
        )
        self.db.add(new_locker)
        await self.db.commit()
        await self.db.refresh(new_locker)
        return new_locker, recovery_key

    async def unlock(self, user_id: str, password: str) -> str | None:
        """Verifies locker password and returns a raw session token if valid."""
        stmt = select(PrivateLockerModel).where(PrivateLockerModel.user_id == user_id)
        result = await self.db.execute(stmt)
        locker = result.scalar_one_or_none()
        
        if not locker:
            return None
            
        # Check lockout
        now = datetime.now(timezone.utc)
        lockout = locker.lockout_until
        if lockout:
            if lockout.tzinfo is None:
                lockout = lockout.replace(tzinfo=timezone.utc)
            if lockout > now:
                raise PermissionError("Locker is temporarily locked due to too many failed attempts")

        if not verify_password(password, locker.password_hash):
            locker.failed_attempts += 1
            if locker.failed_attempts >= 5:
                locker.lockout_until = now + timedelta(minutes=5)
            await self.db.commit()
            return None

        # Reset failed attempts
        if locker.failed_attempts > 0:
            locker.failed_attempts = 0
            locker.lockout_until = None
        
        raw_token = secrets.token_urlsafe(32)
        token_hash = get_token_hash(raw_token)
        
        session = LockerSessionModel(
            token_hash=token_hash,
            locker_id=locker.id,
            expires_at=now + timedelta(days=1), # Long max lifetime, but activity checked
            last_activity_at=now,
            revoked=False
        )
        self.db.add(session)
        await self.db.commit()
        
        return raw_token

    async def get_active_locker_session(self, user_id: str, raw_token: str) -> LockerSessionModel | None:
        """Validates locker session token, checks inactivity, and resets timer."""
        token_hash = get_token_hash(raw_token)
        
        stmt = select(LockerSessionModel).join(PrivateLockerModel).where(
            LockerSessionModel.token_hash == token_hash,
            LockerSessionModel.revoked == False,
            PrivateLockerModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return None
            
        now = datetime.now(timezone.utc)
        last_activity = session.last_activity_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        
        # Check 120s inactivity
        timeout_seconds = settings.private_locker_idle_timeout_seconds
        if (now - last_activity).total_seconds() > timeout_seconds:
            session.revoked = True
            await self.db.commit()
            return None
            
        # Reset activity timer
        session.last_activity_at = now
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def lock(self, user_id: str, raw_token: str) -> None:
        """Manually revokes a locker session."""
        token_hash = get_token_hash(raw_token)
        
        stmt = select(LockerSessionModel).join(PrivateLockerModel).where(
            LockerSessionModel.token_hash == token_hash,
            PrivateLockerModel.user_id == user_id
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            session.revoked = True
            await self.db.commit()

    async def get_locker_status(self, user_id: str) -> dict:
        """Returns locker setup status without returning secret state."""
        stmt = select(PrivateLockerModel).where(PrivateLockerModel.user_id == user_id)
        result = await self.db.execute(stmt)
        locker = result.scalar_one_or_none()
        
        now = datetime.now(timezone.utc)
        is_locked_out = False
        if locker is not None and locker.lockout_until is not None:
            lockout = locker.lockout_until
            if lockout.tzinfo is None:
                lockout = lockout.replace(tzinfo=timezone.utc)
            is_locked_out = lockout > now

        return {
            "has_locker": locker is not None,
            "locked_out": is_locked_out
        }

    async def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        stmt = select(PrivateLockerModel).where(PrivateLockerModel.user_id == user_id)
        result = await self.db.execute(stmt)
        locker = result.scalar_one_or_none()
        
        if not locker or not verify_password(old_password, locker.password_hash):
            return False
            
        locker.password_hash = get_password_hash(new_password)
        await self.db.commit()
        return True

    async def recover_password(self, user_id: str, recovery_key: str, new_password: str) -> bool:
        stmt = select(PrivateLockerModel).where(PrivateLockerModel.user_id == user_id)
        result = await self.db.execute(stmt)
        locker = result.scalar_one_or_none()
        
        if not locker or not verify_password(recovery_key, locker.recovery_key_hash):
            return False
            
        locker.password_hash = get_password_hash(new_password)
        locker.failed_attempts = 0
        locker.lockout_until = None
        await self.db.commit()
        return True
