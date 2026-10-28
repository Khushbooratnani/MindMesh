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
    group_id: Optional[Any] = Field(default=None, description="Optional group context to filter semantic search")

    # Phase 3: Location-Aware Search
    location_query: Optional[str] = Field(
        default=None,
        description="Natural language place description to geocode (e.g. 'Dehradun, India')",
    )
    latitude: Optional[float] = Field(default=None, description="Explicit latitude coordinate")
    longitude: Optional[float] = Field(default=None, description="Explicit longitude coordinate")
    radius_km: Optional[float] = Field(default=None, ge=0.1, le=200.0, description="Search radius in km (optional)")
    mode: str = Field(
        default="hybrid",
        description="Search mode: 'hybrid' (vector+graph+location) | 'nearby' | 'graph' | 'vector'",
    )


class NearbySearchRequest(BaseModel):
    """Pure coordinate-based proximity search request."""
    model_config = ConfigDict(extra="ignore")

    latitude: float = Field(..., description="Latitude of search origin")
    longitude: float = Field(..., description="Longitude of search origin")
    radius_km: float = Field(default=10.0, ge=0.1, le=200.0, description="Search radius in km")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results to return")


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
    memory: dict[str, Any] = Field(default_factory=dict, description="Canonical MemoryV1 payload from phase1_outputs")

    # Phase 3: Location & Graph enrichment (all optional for backward compatibility)
    matched_by: Optional[list[str]] = Field(default=None, description="Which search modes matched: vector, graph, postgis, haversine")
    location: Optional[str] = Field(default=None, description="Nearest location display name")
    latitude: Optional[float] = Field(default=None)
    longitude: Optional[float] = Field(default=None)
    distance_meters: Optional[float] = Field(default=None, description="Distance from search origin in metres")
    location_match_type: Optional[str] = Field(default=None, description="within_requested_radius | expanded_nearby")
    search_radius_km: Optional[float] = Field(default=None, description="Effective radius used for this result")


class MemorySearchResponse(BaseModel):
    """Complete semantic retrieval response including grounded LLM answer."""
    model_config = ConfigDict(extra="ignore")

    query: str
    answer: Optional[str] = None
    grounded: bool = True
    results: list[MemorySearchResult] = Field(default_factory=list)
    total_results: int = 0
