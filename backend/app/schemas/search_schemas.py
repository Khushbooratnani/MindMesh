from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.memory_output import MemoryV1


class MemorySearchRequest(BaseModel):
    """Natural language semantic search request."""
    model_config = ConfigDict(extra="ignore")

    query: str = Field(..., min_length=1, description="Natural language search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Max number of candidate memories to retrieve")
    content_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Weight for content vector similarity")
    context_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Weight for context vector similarity")
    generate_answer: bool = Field(default=True, description="Whether to generate grounded LLM answer")


class MemorySearchResult(BaseModel):
    """Individual ranked memory candidate matching the search query."""
    model_config = ConfigDict(extra="ignore")

    memory_id: str
    similarity_score: float
    score: float
    source_modality: Optional[str] = None
    user_context: Optional[str] = None
    clean_text: Optional[str] = None
    media: Optional[dict[str, Any]] = None
    content_score: Optional[float] = None
    context_score: Optional[float] = None
    summary: Optional[str] = None
    entities: Optional[dict[str, Any]] = None
    semantics: Optional[dict[str, Any]] = None
    memory: dict[str, Any] = Field(..., description="Canonical MemoryV1 payload from phase1_outputs")


class MemorySearchResponse(BaseModel):
    """Complete semantic retrieval response including grounded LLM answer."""
    model_config = ConfigDict(extra="ignore")

    query: str
    answer: Optional[str] = None
    grounded: bool = True
    results: list[MemorySearchResult] = Field(default_factory=list)
    total_results: int = 0
