import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import get_current_user
from app.database.connection.session import get_db_session
from app.database.models.user import UserModel
from app.schemas.comment import CommentCreateRequest, CommentResponse
from app.services.comment_service import CommentService
from app.services.locker_service import LockerService

router = APIRouter(prefix="/api/v1/memories", tags=["comments"])


async def _resolve_locker_valid(request: Request, user_id: str, db: AsyncSession) -> bool:
    token = request.headers.get("X-Locker-Token")
    if not token:
        return False
    try:
        sess = await LockerService(db).get_active_locker_session(user_id, token)
        return sess is not None
    except Exception:
        return False


@router.post("/{memory_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    memory_id: str,
    request: CommentCreateRequest,
    fastapi_req: Request,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Add a collaborative discussion comment to an authorized memory."""
    locker_valid = await _resolve_locker_valid(fastapi_req, current_user.id, db)
    comment = await CommentService.add_comment(
        session=db,
        memory_id=memory_id,
        author_id=current_user.id,
        content=request.content,
        locker_session_valid=locker_valid,
    )
    return CommentResponse(
        id=comment.id,
        memory_id=comment.memory_id,
        author_id=comment.author_id,
        author_username=current_user.username,
        content=comment.content,
        is_knowledge_eligible=comment.is_knowledge_eligible,
        derived_memory_id=comment.derived_memory_id,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.get("/{memory_id}/comments", response_model=List[CommentResponse])
async def list_comments(
    memory_id: str,
    fastapi_req: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List comments on an authorized memory."""
    locker_valid = await _resolve_locker_valid(fastapi_req, current_user.id, db)
    return await CommentService.get_comments_for_memory(
        session=db,
        memory_id=memory_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
        locker_session_valid=locker_valid,
    )


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: uuid.UUID,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a comment. Permitted for comment author or group moderators."""
    await CommentService.delete_comment(
        session=db,
        comment_id=comment_id,
        user_id=current_user.id,
    )
    return {"message": "Comment deleted successfully", "comment_id": str(comment_id)}
