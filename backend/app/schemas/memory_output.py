from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import MediaType, Privacy, Sentiment
from app.schemas.extraction_output import AdditionalAttribute


class SystemFields(BaseModel):
    owner_id: str
    group_id: str | None = None
    media_type: MediaType
    created_at: str
    privacy: Privacy
    allowed_users: list[str] = Field(default_factory=list)


class ContentFields(BaseModel):
    raw_text: str | None = None
    clean_text: str
    description: str
    summary: str


class EntityFields(BaseModel):
    people: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)


class SemanticFields(BaseModel):
    topics: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    sentiment: Sentiment = Sentiment.UNKNOWN
    mood: list[str] = Field(default_factory=list)


class TemporalFields(BaseModel):
    mentioned_dates: list[str] = Field(default_factory=list)
    inferred_time: str | None = None
    time_of_day: Literal["morning", "afternoon", "evening", "night", "unknown"] | None = None


class ProcessingFields(BaseModel):
    status: Literal["completed", "failed", "partial"]
    source_modality: MediaType
    transcription_required: bool
    image_understanding_required: bool
    llm_provider: str
    llm_model: str
    errors: list[str] = Field(default_factory=list)


class MemoryV1(BaseModel):
    memory_id: str
    schema_version: Literal["1.0"] = "1.0"
    system: SystemFields
    content: ContentFields
    entities: EntityFields
    semantics: SemanticFields
    temporal: TemporalFields
    additional_attributes: list[AdditionalAttribute] = Field(default_factory=list)
    processing: ProcessingFields
