import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, UserDefinedType

from app.database.models.base import Base, GUID

if TYPE_CHECKING:
    from app.database.models.phase1_output import Phase1OutputModel


class PGVectorType(UserDefinedType):
    """PostgreSQL pgvector column type."""
    def __init__(self, dim: int = 1024):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"


class VectorType(TypeDecorator):
    """Platform-independent 1024-dim vector type.
    Uses PostgreSQL pgvector 'vector(1024)' on PostgreSQL, and Text (JSON) on SQLite.
    """
    impl = Text
    cache_ok = True

    def __init__(self, dim: int = 1024, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PGVectorType(self.dim))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, (list, tuple)):
            if dialect.name == "postgresql":
                return "[" + ",".join(str(float(x)) for x in value) + "]"
            return json.dumps([float(x) for x in value])
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            clean = value.strip("[]() ")
            if not clean:
                return []
            return [float(x.strip()) for x in clean.split(",") if x.strip()]
        return list(value)


class Phase2EmbeddingModel(Base):
    """Stores Phase 2 dual 1024-dim vector representations linked to Phase 1 MemoryV1.
    
    Contains content_vector (what happened) and context_vector (entities, topics, mood, time)
    without duplicating the canonical MemoryV1 JSONB payload.
    """
    __tablename__ = "phase2_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    phase1_output_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("phase1_outputs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    memory_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("phase1_outputs.memory_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="MindMesh unique memory ID e.g. M_<uuid>",
    )
    content_vector: Mapped[list[float]] = mapped_column(
        VectorType(1024),
        nullable=False,
        comment="1024-dim BAAI/bge-m3 content embedding",
    )
    context_vector: Mapped[list[float]] = mapped_column(
        VectorType(1024),
        nullable=False,
        comment="1024-dim BAAI/bge-m3 context embedding",
    )
    embedding_model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="BAAI/bge-m3",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationship back to the canonical Phase 1 output record
    phase1_output: Mapped["Phase1OutputModel"] = relationship(
        "Phase1OutputModel",
        back_populates="phase2_embedding",
        foreign_keys=[phase1_output_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Phase2EmbeddingModel(id={self.id}, memory_id={self.memory_id}, phase1_output_id={self.phase1_output_id})>"
