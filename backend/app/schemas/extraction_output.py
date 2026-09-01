from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.enums import Sentiment


class ExtractedEntities(BaseModel):
    people: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)


class ExtractedSemantics(BaseModel):
    topics: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    sentiment: Sentiment = Sentiment.UNKNOWN
    mood: list[str] = Field(default_factory=list)


class ExtractedTemporal(BaseModel):
    mentioned_dates: list[str] = Field(default_factory=list)
    inferred_time: str | None = None
    time_of_day: Literal["morning", "afternoon", "evening", "night", "unknown"] | None = None


class AdditionalAttribute(BaseModel):
    key: str
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["llm", "system", "user"]


class ExtractionOutput(BaseModel):
    description: str
    summary: str
    entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    semantics: ExtractedSemantics = Field(default_factory=ExtractedSemantics)
    temporal: ExtractedTemporal = Field(default_factory=ExtractedTemporal)
    additional_attributes: list[AdditionalAttribute] = Field(default_factory=list)
