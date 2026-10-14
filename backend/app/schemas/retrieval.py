from typing import Literal

from pydantic import BaseModel, Field


class EmbeddingRunRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=500)
    memory_ids: list[str] = Field(default_factory=list)


class EmbeddingRunResponse(BaseModel):
    processed: int
    failed: int
    embedding_model: str
    errors: list[str] = Field(default_factory=list)


class GraphSyncRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=500)
    memory_ids: list[str] = Field(default_factory=list)


class GraphSyncResponse(BaseModel):
    processed: int
    failed: int
    neo4j_database: str
    errors: list[str] = Field(default_factory=list)


class SearchRequest(BaseModel):
    query: str
    mode: Literal["vector", "graph", "hybrid"] = "hybrid"
    limit: int = Field(default=5, ge=1, le=100)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_km: float | None = Field(default=None, gt=0, le=200)
    location_query: str | None = Field(default=None, min_length=2, max_length=200)


class NearbySearchRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(default=10, gt=0, le=200)
    limit: int = Field(default=5, ge=1, le=100)


class SearchResult(BaseModel):
    memory_id: str
    summary: str
    score: float
    matched_by: list[Literal["vector", "graph", "postgis"]]
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    distance_meters: float | None = None
    location_confidence: float | None = None
    location_match_type: Literal["within_requested_radius", "expanded_nearby"] | None = None
    search_radius_km: float | None = None


class SearchResponse(BaseModel):
    mode: Literal["vector", "graph", "hybrid"]
    results: list[SearchResult]
