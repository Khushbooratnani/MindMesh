from datetime import datetime
from typing import Any
import uuid
from pydantic import BaseModel, ConfigDict, Field


class VectorPreview(BaseModel):
    """Preview metadata for generated embedding vectors."""
    model_config = ConfigDict(extra="ignore")

    created: bool = True
    dimension: int = 1024
    input_text: str
    vector_preview: list[float] = Field(default_factory=list)


class Phase2EmbeddingMetadata(BaseModel):
    """Encapsulates content and context vector previews and model info."""
    model_config = ConfigDict(extra="ignore")

    model: str = "BAAI/bge-m3"
    content: VectorPreview
    context: VectorPreview


class Phase2ProcessResponse(BaseModel):
    """Response returned after processing a Phase 1 output into Phase 2 vector embeddings."""
    model_config = ConfigDict(extra="ignore")

    embedding_id: uuid.UUID
    phase1_output_id: uuid.UUID
    memory_id: str
    schema_version: str = "1.0"
    status: str = "processed"
    stored: bool = True
    embeddings: Phase2EmbeddingMetadata
    created_at: datetime
