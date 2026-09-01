from pydantic import BaseModel

from app.core.enums import MediaType, Privacy


class SystemContext(BaseModel):
    owner_id: str
    group_id: str | None = None
    media_type: MediaType
    privacy: Privacy
    allowed_users: list[str]


class ProcessedInput(BaseModel):
    media_type: MediaType
    raw_text: str | None = None
    clean_text: str


class CanonicalInput(BaseModel):
    media_type: MediaType
    source_text: str
    raw_text: str | None = None
    source_context: SystemContext
