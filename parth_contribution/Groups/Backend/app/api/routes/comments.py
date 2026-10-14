import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database.connection.session import get_db_session
from app.api.dependencies.auth import get_current_user
from app.database.models.user import UserModel
from app.database.models.comments import CommentModel
from app.services.comment_service import CommentService
from app.schemas.comment import CommentCreateRequest, CommentResponse

router = APIRouter(prefix="/api/v1/memories/{memory_id}/comments", tags=["comments"])

@router.post("", response_model=CommentResponse)
async def create_comment(
    memory_id: str,
    request: CommentCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    comment = await CommentService.add_comment(db, memory_id, current_user.id, request.content)
    return comment

@router.get("", response_model=List[CommentResponse])
async def list_comments(
    memory_id: str,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    from app.services.authz_service import AuthorizationService
    if not await AuthorizationService.can_read_memory(db, current_user.id, memory_id):
        raise HTTPException(status_code=403, detail="Not authorized to read comments for this memory")
        
    stmt = select(CommentModel).where(CommentModel.memory_id == memory_id).order_by(CommentModel.created_at.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.delete("/{comment_id}")
async def delete_comment(
    memory_id: str,
    comment_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    await CommentService.delete_comment(db, comment_id, current_user.id)
    return {"message": "Comment deleted successfully"}
