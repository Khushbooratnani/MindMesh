import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, GUID


class CommentModel(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"), index=True, nullable=False
    )
    author_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_knowledge_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    derived_memory_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("phase1_outputs.memory_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="If knowledge eligible, this links to the derived phase1_output memory_id",
    )
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
