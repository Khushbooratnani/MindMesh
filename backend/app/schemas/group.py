import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import GroupRole


class GroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    avatar_url: Optional[str] = None


class GroupUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None
    avatar_url: Optional[str] = None


class GroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_id: uuid.UUID
    user_id: str
    username: Optional[str] = None
    role: str
    joined_at: datetime


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    created_by: Optional[str] = None
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime
    member_count: Optional[int] = None
    my_role: Optional[str] = None


class GroupDetailResponse(GroupResponse):
    members: List[GroupMemberResponse] = []
    can_manage: bool = False


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = GroupRole.MEMBER.value


class UpdateMemberRoleRequest(BaseModel):
    role: str


class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: str


class CreateInvitationRequest(BaseModel):
    invitee_email: str
    role: str = GroupRole.MEMBER.value


class GroupInvitationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    group_name: Optional[str] = None
    inviter_id: str
    invitee_email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    invitation_token: Optional[str] = None


class AcceptInvitationRequest(BaseModel):
    token: str


class ShareMemoryRequest(BaseModel):
    group_ids: List[uuid.UUID] = Field(default_factory=list)
    user_ids: List[str] = Field(default_factory=list)
    can_edit: bool = False
    can_reshare: bool = False


class RevokeMemoryShareRequest(BaseModel):
    group_ids: List[uuid.UUID] = Field(default_factory=list)
    user_ids: List[str] = Field(default_factory=list)


class MemoryShareDetail(BaseModel):
    group_id: Optional[uuid.UUID] = None
    user_id: Optional[str] = None
    can_edit: bool = False
    created_at: datetime


class MemorySharesResponse(BaseModel):
    memory_id: str
    owner_id: str
    privacy: str
    group_shares: List[MemoryShareDetail] = []
    user_shares: List[MemoryShareDetail] = []


class UserSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
