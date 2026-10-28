"""
SQLAlchemy models for the separate MindMesh Private Locker Authentication Database.

SECURITY INVARIANT:
This database stores ONLY authentication verifiers and session state.
It MUST NEVER store:
- Plaintext passwords or encryption keys
- Private memories, media, or transcripts
- Embeddings or AI results
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class LockerAuthBase(DeclarativeBase):
    """Isolated declarative base for the separate authentication database."""
    pass


class LockerAuthIdentityModel(LockerAuthBase):
    """
    Stores pseudonymous locker authentication verifiers.
    Decoupled from application user identities for cryptographic isolation.
    """
    __tablename__ = "locker_auth_identities"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_reference: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="Pseudonymous reference hash derived from user_id without exposing primary account identity",
    )
    argon2_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Argon2id verifier of the locker unlock password",
    )
    recovery_hash: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="Argon2id verifier of the recovery credential",
    )
    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    lockout_until: Mapped[Optional[datetime]] = mapped_column(
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

    sessions: Mapped[list["LockerAuthSessionModel"]] = relationship(
        "LockerAuthSessionModel",
        back_populates="identity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class LockerAuthSessionModel(LockerAuthBase):
    """
    Stores active sessions for local-first locker verification tokens.
    Tokens expire after 120 seconds of inactivity.
    """
    __tablename__ = "locker_auth_sessions"

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
    identity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("locker_auth_identities.id", ondelete="CASCADE"),
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
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    identity: Mapped[LockerAuthIdentityModel] = relationship(
        "LockerAuthIdentityModel",
        back_populates="sessions",
    )
