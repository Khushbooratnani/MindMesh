import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class PrivateLockerModel(Base):
    """Stores user private locker configuration and authentication state."""
    __tablename__ = "private_lockers"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Argon2id hash of the locker password",
    )
    recovery_key_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Hash of the recovery key",
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    lockout_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class LockerSessionModel(Base):
    """Stores active private locker sessions with idle timeout tracking."""
    __tablename__ = "locker_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    token_hash: Mapped[str] = mapped_column(
        String(256),
        unique=True,
        nullable=False,
        index=True,
    )
    locker_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("private_lockers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
