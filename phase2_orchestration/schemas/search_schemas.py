from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator

class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20_000)
    top_k: int = Field(default=5, ge=1, le=50)
    user_id: Optional[str] = Field(default="U_DEVELOPMENT")
    content_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    context_weight: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value

class MemorySearchResult(BaseModel):
    memory_id: str
    similarity_score: float
    score: float = Field(default=0.0)
    content_score: Optional[float] = None
    context_score: Optional[float] = None
    summary: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None
    semantics: Optional[Dict[str, Any]] = None
    memory: Optional[Dict[str, Any]] = None

    @model_validator(mode="before")
    @classmethod
    def sync_scores(cls, values: Any) -> Any:
        if isinstance(values, dict):
            if "similarity_score" in values and ("score" not in values or values["score"] == 0.0):
                values["score"] = values["similarity_score"]
            elif "score" in values and "similarity_score" not in values:
                values["similarity_score"] = values["score"]
            
            # Extract summary, entities, semantics if nested inside memory_json
            mem = values.get("memory") or values.get("memory_json") or {}
            if isinstance(mem, dict):
                if not values.get("summary"):
                    values["summary"] = mem.get("content", {}).get("summary") or mem.get("content", {}).get("clean_text")
                if not values.get("entities"):
                    values["entities"] = mem.get("entities")
                if not values.get("semantics"):
                    values["semantics"] = mem.get("semantics")
        return values

class MemorySearchResponse(BaseModel):
    query: str
    answer: str
    results: List[MemorySearchResult]
    total_results: int = 0

    @model_validator(mode="before")
    @classmethod
    def set_total(cls, values: Any) -> Any:
        if isinstance(values, dict) and "results" in values:
            values["total_results"] = len(values.get("results", []))
        return values
