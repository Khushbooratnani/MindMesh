from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field

class EmbeddingDetail(BaseModel):
    created: bool = True
    dimension: int = 1024
    input_text: str = ""
    vector_preview: List[float] = Field(default_factory=list)
    vector_full: List[float] = Field(default_factory=list)

class EmbeddingSummary(BaseModel):
    model: str = "BAAI/bge-m3"
    content: EmbeddingDetail = Field(default_factory=EmbeddingDetail)
    context: EmbeddingDetail = Field(default_factory=EmbeddingDetail)

class Phase2ProcessResponse(BaseModel):
    memory_id: str
    schema_version: str = "1.0"
    status: str = "processed"
    stored: bool = True
    embeddings: EmbeddingSummary = Field(default_factory=EmbeddingSummary)
    stored_memory: Optional[Dict[str, Any]] = None
