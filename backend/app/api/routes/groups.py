import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_strictly_authenticated_user as get_current_user
from app.core.enums import GroupRole
from app.database.connection.session import get_db_session
from app.database.models.user import UserModel
from app.schemas.group import (
    AcceptInvitationRequest,
    AddMemberRequest,
    CreateInvitationRequest,
    GroupCreateRequest,
    GroupDetailResponse,
    GroupInvitationResponse,
    GroupMemberResponse,
    GroupResponse,
    GroupUpdateRequest,
    TransferOwnershipRequest,
    UpdateMemberRoleRequest,
    UserSummaryResponse,
)
from app.services.group_service import GroupService

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    request: GroupCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new collaborative group and assign the creator as OWNER."""
    group = await GroupService.create_group(
        session=db,
        name=request.name,
        description=request.description,
        avatar_url=request.avatar_url,
        creator_id=current_user.id,
    )
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        avatar_url=group.avatar_url,
        created_by=group.created_by,
        is_archived=group.is_archived,
        created_at=group.created_at,
        updated_at=group.updated_at,
        member_count=1,
        my_role=GroupRole.OWNER.value,
    )


@router.get("", response_model=List[GroupResponse])
async def list_groups(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List all active groups that the authenticated user is a member of."""
    groups = await GroupService.list_user_groups(session=db, user_id=current_user.id)
    return [GroupResponse(**g) for g in groups]


@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group_details(
    group_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """View details and members of a specific group. Requires membership."""
    return await GroupService.get_group_details(
        session=db, group_id=group_id, user_id=current_user.id
    )


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group_details(
    group_id: uuid.UUID,
    request: GroupUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update group name or description. Requires OWNER or ADMIN role."""
    group = await GroupService.update_group(
        session=db,
        group_id=group_id,
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        avatar_url=request.avatar_url,
    )
    my_role = await GroupService.get_user_role(db, group_id, current_user.id)
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        avatar_url=group.avatar_url,
        created_by=group.created_by,
        is_archived=group.is_archived,
        created_at=group.created_at,
        updated_at=group.updated_at,
        my_role=my_role,
    )


@router.delete("/{group_id}")
async def delete_group(
    group_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Archive / delete a group. Strictly requires OWNER role."""
    await GroupService.delete_group(session=db, group_id=group_id, user_id=current_user.id)
    return {"message": "Group deleted successfully", "group_id": str(group_id)}


@router.post("/{group_id}/transfer-ownership")
async def transfer_ownership(
    group_id: uuid.UUID,
    request: TransferOwnershipRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Transfer group ownership to another active member. Strictly requires OWNER."""
    await GroupService.transfer_ownership(
        session=db,
        group_id=group_id,
        current_owner_id=current_user.id,
        new_owner_id=request.new_owner_user_id,
    )
    return {
        "message": "Group ownership successfully transferred.",
        "new_owner_id": request.new_owner_user_id,
    }


@router.get("/{group_id}/members", response_model=List[GroupMemberResponse])
async def list_group_members(
    group_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List members of a group. Requires membership."""
    details = await GroupService.get_group_details(
        session=db, group_id=group_id, user_id=current_user.id
    )
    return details.members


@router.post("/{group_id}/members", response_model=GroupMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    group_id: uuid.UUID,
    request: AddMemberRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Add a member directly to a group. Requires OWNER or ADMIN role."""
    member = await GroupService.add_member(
        session=db,
        group_id=group_id,
        requester_id=current_user.id,
        target_user_id=request.user_id,
        role=request.role,
    )
    return GroupMemberResponse(
        group_id=member.group_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.patch("/{group_id}/members/{user_id}", response_model=GroupMemberResponse)
async def change_member_role(
    group_id: uuid.UUID,
    user_id: str,
    request: UpdateMemberRoleRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Change a member's role. Enforces RBAC boundaries."""
    member = await GroupService.update_member_role(
        session=db,
        group_id=group_id,
        requester_id=current_user.id,
        target_user_id=user_id,
        new_role=request.role,
    )
    return GroupMemberResponse(
        group_id=member.group_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: uuid.UUID,
    user_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Remove a member from the group or self-leave."""
    await GroupService.remove_member(
        session=db,
        group_id=group_id,
        requester_id=current_user.id,
        target_user_id=user_id,
    )
    return {"message": "Member removed successfully", "user_id": user_id}


@router.post("/{group_id}/leave")
async def leave_group(
    group_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Leave a group. Non-owner members can leave anytime."""
    await GroupService.remove_member(
        session=db,
        group_id=group_id,
        requester_id=current_user.id,
        target_user_id=current_user.id,
    )
    return {"message": "You have left the group.", "group_id": str(group_id)}


@router.post("/{group_id}/invitations", response_model=GroupInvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    group_id: uuid.UUID,
    request: CreateInvitationRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a secure invitation token. Requires OWNER or ADMIN role."""
    invitation, raw_token = await GroupService.create_invitation(
        session=db,
        group_id=group_id,
        inviter_id=current_user.id,
        invitee_email=request.invitee_email,
        role=request.role,
    )
    return GroupInvitationResponse(
        id=invitation.id,
        group_id=invitation.group_id,
        inviter_id=invitation.inviter_id,
        invitee_email=invitation.invitee_email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        invitation_token=raw_token,
    )


@router.get("/{group_id}/invitations", response_model=List[GroupInvitationResponse])
async def list_pending_invitations(
    group_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List pending invitations for a group. Requires OWNER or ADMIN role."""
    return await GroupService.list_pending_invitations(
        session=db, group_id=group_id, requester_id=current_user.id
    )


@router.delete("/invitations/{invitation_id}")
async def revoke_invitation(
    invitation_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke a pending invitation. Requires OWNER or ADMIN role."""
    await GroupService.revoke_invitation(
        session=db, invitation_id=invitation_id, requester_id=current_user.id
    )
    return {"message": "Invitation revoked successfully."}


@router.post("/invitations/accept", response_model=GroupMemberResponse)
async def accept_invitation(
    request: AcceptInvitationRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Accept an invitation using the raw token received in invite link."""
    member = await GroupService.accept_invitation(
        session=db,
        raw_token=request.token,
        current_user_id=current_user.id,
    )
    return GroupMemberResponse(
        group_id=member.group_id,
        user_id=member.user_id,
        role=member.role,
        joined_at=member.joined_at,
    )


@router.post("/invitations/reject")
async def reject_invitation(
    request: AcceptInvitationRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Reject an invitation token."""
    await GroupService.reject_invitation(
        session=db,
        raw_token=request.token,
    )
    return {"message": "Invitation rejected successfully."}


@router.get("/invitations/validate/{token}")
async def validate_invitation(
    token: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Validate an invitation token and return preview metadata for deep-link / web joining."""
    return await GroupService.validate_invitation(
        session=db,
        raw_token=token,
    )


@router.get("/users/search", response_model=List[UserSummaryResponse])
async def search_users_for_invitation(
    q: str = Query(..., min_length=2, description="Username search query"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Search registered users by username for invitations with privacy limits."""
    users = await GroupService.search_users(session=db, query_str=q, limit=10)
    return [UserSummaryResponse(id=u.id, username=u.username) for u in users]
