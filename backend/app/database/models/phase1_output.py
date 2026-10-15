import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.models.base import Base, GUID

if TYPE_CHECKING:
    from app.database.models.phase2_embedding import Phase2EmbeddingModel
    from app.database.models.raw_input import RawInputModel


class Phase1OutputModel(Base):
    """Stores complete validated MemoryV1 JSON produced by Phase 1.
    
    Contains unflattened JSONB payload preserving all system, content,
    entities, semantics, temporal, additional_attributes, and processing fields.
    """
    __tablename__ = "phase1_outputs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    raw_input_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("raw_inputs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    memory_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="MindMesh unique memory ID e.g. M_<uuid>",
    )
    schema_version: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="1.0",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        comment="Complete validated MemoryV1 structure as JSONB",
    )
    processing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="completed",
        index=True,
    )
    extractor_model: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationship back to the generating raw input
    raw_input: Mapped["RawInputModel"] = relationship(
        "RawInputModel",
        back_populates="phase1_outputs",
        lazy="selectin",
    )

    # Relationship to downstream Phase 2 vector embeddings
    phase2_embedding: Mapped["Phase2EmbeddingModel | None"] = relationship(
        "Phase2EmbeddingModel",
        back_populates="phase1_output",
        foreign_keys="[Phase2EmbeddingModel.phase1_output_id]",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Phase1OutputModel(id={self.id}, memory_id={self.memory_id}, raw_input_id={self.raw_input_id})>"
