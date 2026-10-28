import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, GUID


class GroupModel(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class GroupMemberModel(Base):
    __tablename__ = "group_members"

    group_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="MEMBER", nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class GroupInvitationModel(Base):
    __tablename__ = "group_invitations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inviter_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invitee_email: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="MEMBER", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class MemoryGroupAccessModel(Base):
    __tablename__ = "memory_group_access"

    memory_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"), primary_key=True, index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    granted_by: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_reshare: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class MemoryUserAccessModel(Base):
    __tablename__ = "memory_user_access"

    memory_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"), primary_key=True, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    granted_by: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class GroupFeedReferenceModel(Base):
    __tablename__ = "group_feed_references"
    __table_args__ = (
        UniqueConstraint("group_id", "memory_id", name="uq_group_feed_ref"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    shared_by: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class GroupActivityModel(Base):
    __tablename__ = "group_activities"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
