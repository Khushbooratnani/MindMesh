import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database.connection.session import get_db_session
from app.api.dependencies.auth import get_current_user
from app.database.models.user import UserModel
from app.database.models.groups import GroupModel, GroupMemberModel
from app.services.group_service import GroupService
from app.schemas.group import GroupCreateRequest, GroupResponse, AddMemberRequest, GroupMemberResponse

router = APIRouter(prefix="/api/v1/groups", tags=["groups"])

@router.post("", response_model=GroupResponse)
async def create_group(
    request: GroupCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    group = await GroupService.create_group(db, request.name, request.description or "", current_user.id)
    return group

@router.get("", response_model=List[GroupResponse])
async def list_groups(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    stmt = select(GroupModel).join(GroupMemberModel).where(GroupMemberModel.user_id == current_user.id)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/{group_id}/members", response_model=GroupMemberResponse)
async def add_member(
    group_id: uuid.UUID,
    request: AddMemberRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    member = await GroupService.add_member(db, group_id, current_user.id, request.user_id, request.role)
    return member

@router.delete("/{group_id}/members/{user_id}")
async def remove_member(
    group_id: uuid.UUID,
    user_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    await GroupService.remove_member(db, group_id, current_user.id, user_id)
    return {"message": "Member removed successfully"}
