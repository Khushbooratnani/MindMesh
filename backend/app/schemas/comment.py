import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    memory_id: str
    author_id: str
    author_username: Optional[str] = None
    content: str
    is_knowledge_eligible: bool = False
    derived_memory_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
