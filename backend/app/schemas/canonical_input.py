from pydantic import BaseModel

from app.core.enums import MediaType, Privacy
from app.schemas.memory_output import MediaReference


class SystemContext(BaseModel):
    owner_id: str
    group_id: str | None = None
    media_type: MediaType
    privacy: Privacy
    allowed_users: list[str]
    media_reference: MediaReference | None = None
    user_context: str | None = None


class ProcessedInput(BaseModel):
    media_type: MediaType
    raw_text: str | None = None
    clean_text: str
    detected_language: str | None = None
    language_probability: float | None = None
    normalized_language: str | None = None
    display_script: str | None = "latin"


class CanonicalInput(BaseModel):
    media_type: MediaType
    source_text: str
    raw_text: str | None = None
    source_context: SystemContext
    media_reference: MediaReference | None = None
    user_context: str | None = None
    detected_language: str | None = None
    normalized_language: str | None = None
    display_script: str | None = "latin"
