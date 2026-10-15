import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base, GUID

class CommentModel(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    memory_id: Mapped[str] = mapped_column(String(64), ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"), index=True)
    author_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_knowledge_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    derived_memory_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="If knowledge eligible, this links to the derived phase1_output memory_id")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
