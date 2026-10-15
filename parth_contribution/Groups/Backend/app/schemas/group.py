from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

class GroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None

class GroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    created_by: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class AddMemberRequest(BaseModel):
    user_id: str
    role: str = "MEMBER"

class GroupMemberResponse(BaseModel):
    group_id: uuid.UUID
    user_id: str
    role: str
    joined_at: datetime
    
    class Config:
        from_attributes = True

class GroupListResponse(BaseModel):
    groups: List[GroupResponse]
