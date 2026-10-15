import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, GUID

class GroupModel(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

class GroupMemberModel(Base):
    __tablename__ = "group_members"

    group_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="MEMBER")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class MemoryGroupAccessModel(Base):
    __tablename__ = "memory_group_access"

    memory_id: Mapped[str] = mapped_column(String(64), ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"), primary_key=True)
    group_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    granted_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class MemoryUserAccessModel(Base):
    __tablename__ = "memory_user_access"

    memory_id: Mapped[str] = mapped_column(String(64), ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    granted_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

class GroupFeedReferenceModel(Base):
    __tablename__ = "group_feed_references"
    
    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[str] = mapped_column(String(64), ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"), index=True)
    group_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    shared_by: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
