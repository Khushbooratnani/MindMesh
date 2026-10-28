import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.user import UserModel, UserSessionModel

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_token_hash(token: str) -> str:
    """Hashes a raw token for storage/lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    hash_password = staticmethod(get_password_hash)
    verify_password = staticmethod(verify_password)

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_user(self, username: str, password: str) -> UserModel:
        """Register a new user."""
        stmt = select(UserModel).where(UserModel.username == username)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError(f"User {username} already exists")

        new_user = UserModel(
            id=str(uuid.uuid4()),
            username=username,
            password_hash=get_password_hash(password)
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)
        return new_user

    async def authenticate_user(self, username: str, password: str) -> UserModel | None:
        """Verify username and password."""
        stmt = select(UserModel).where(UserModel.username == username)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def create_session(self, user_id: str) -> tuple[str, UserSessionModel]:
        """Creates a session and returns (raw_token, session_model)."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = get_token_hash(raw_token)

        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.user_session_timeout_days)
        
        session = UserSessionModel(
            token_hash=token_hash,
            user_id=user_id,
            expires_at=expires_at,
            revoked=False
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return raw_token, session

    async def get_active_user_from_token(self, raw_token: str) -> UserModel | None:
        """Validates a raw token and returns the user if valid."""
        token_hash = get_token_hash(raw_token)
        
        stmt = select(UserSessionModel).where(
            UserSessionModel.token_hash == token_hash,
            UserSessionModel.revoked == False,
            UserSessionModel.expires_at > datetime.now(timezone.utc)
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if not session:
            return None
            
        user_stmt = select(UserModel).where(UserModel.id == session.user_id)
        user_res = await self.db.execute(user_stmt)
        return user_res.scalar_one_or_none()

    async def revoke_session(self, raw_token: str) -> None:
        """Revokes a session given the raw token."""
        token_hash = get_token_hash(raw_token)
        stmt = select(UserSessionModel).where(UserSessionModel.token_hash == token_hash)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        
        if session:
            session.revoked = True
            await self.db.commit()
