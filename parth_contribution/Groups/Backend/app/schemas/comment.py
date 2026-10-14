from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class CommentCreateRequest(BaseModel):
    content: str

class CommentResponse(BaseModel):
    id: uuid.UUID
    memory_id: str
    author_id: str
    content: str
    is_knowledge_eligible: bool
    derived_memory_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
