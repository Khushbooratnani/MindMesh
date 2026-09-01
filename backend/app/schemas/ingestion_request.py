from pydantic import BaseModel, Field

from app.core.enums import MediaType, Privacy


class CurrentUser(BaseModel):
    id: str


class BaseIngestionRequest(BaseModel):
    media_type: MediaType
    group_id: str | None = None
    privacy: Privacy = Privacy.ONLY_ME
    allowed_users: list[str] = Field(default_factory=list)


class TextIngestionRequest(BaseIngestionRequest):
    media_type: MediaType = MediaType.TEXT
    text: str
