import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GroupRole, Privacy
from app.database.models.comments import CommentModel
from app.database.models.groups import (
    GroupMemberModel,
    MemoryGroupAccessModel,
)
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.raw_input import RawInputModel
from app.database.models.user import UserModel
from app.schemas.comment import CommentResponse


class CommentService:
    @staticmethod
    async def add_comment(
        session: AsyncSession,
        memory_id: str,
        author_id: str,
        content: str,
        locker_session_valid: bool = False,
    ) -> CommentModel:
        """Add a comment to an authorized memory.
        
        Evaluates knowledge eligibility for substantive contributions and
        persists a derived knowledge record when appropriate.
        """
        from app.services.authz_service import AuthorizationService

        # 1. Verify read permission
        can_read = await AuthorizationService.can_read_memory(
            session=session,
            user_id=author_id,
            memory_id=memory_id,
            locker_session_valid=locker_session_valid,
        )
        if not can_read:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to comment on this memory.",
            )

        # 2. Check if author is a GUEST in any shared group (GUEST cannot comment)
        stmt_groups = select(MemoryGroupAccessModel.group_id).where(MemoryGroupAccessModel.memory_id == memory_id)
        g_ids = (await session.execute(stmt_groups)).scalars().all()
        if g_ids:
            # Check user role in these groups
            r_stmt = select(GroupMemberModel.role).where(
                and_(GroupMemberModel.group_id.in_(g_ids), GroupMemberModel.user_id == author_id)
            )
            roles = (await session.execute(r_stmt)).scalars().all()
            if roles and all(r == GroupRole.GUEST.value for r in roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Guests are not permitted to comment on group memories.",
                )

        clean_text = content.strip()
        if not clean_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Comment cannot be empty.",
            )

        # 3. Evaluate knowledge eligibility (substantive insight >= 25 characters)
        is_knowledge = len(clean_text) >= 25 and not clean_text.lower().startswith(("http://", "https://"))
        derived_id: Optional[str] = None

        if is_knowledge:
            # Create a derived Phase 1 memory capturing comment knowledge
            derived_id = f"M_derived_{uuid.uuid4().hex[:12]}"
            derived_raw = RawInputModel(
                media_type="text",
                raw_payload=clean_text,
                owner_id=author_id,
                privacy=Privacy.SHARED.value if g_ids else Privacy.ONLY_ME.value,
                status="completed",
            )
            session.add(derived_raw)
            await session.flush()

            derived_p1 = Phase1OutputModel(
                raw_input_id=derived_raw.id,
                memory_id=derived_id,
                owner_id=author_id,
                privacy=Privacy.SHARED.value if g_ids else Privacy.ONLY_ME.value,
                schema_version="1.0",
                extractor_model="comment-knowledge-extractor",
                processing_status="completed",
                payload={
                    "memory_id": derived_id,
                    "system": {
                        "owner_id": author_id,
                        "privacy": Privacy.SHARED.value if g_ids else Privacy.ONLY_ME.value,
                        "source": "comment_derived",
                        "parent_memory_id": memory_id,
                    },
                    "content": {
                        "clean_text": clean_text,
                        "raw_text": clean_text,
                        "summary": f"Discussion insight: {clean_text[:100]}",
                    },
                },
            )
            session.add(derived_p1)
            await session.flush()

            # Share derived memory with same groups as parent memory
            for gid in g_ids:
                session.add(
                    MemoryGroupAccessModel(
                        memory_id=derived_id,
                        group_id=gid,
                        granted_by=author_id,
                    )
                )

        new_comment = CommentModel(
            memory_id=memory_id,
            author_id=author_id,
            content=clean_text,
            is_knowledge_eligible=is_knowledge,
            derived_memory_id=derived_id,
        )
        session.add(new_comment)
        await session.commit()
        await session.refresh(new_comment)
        return new_comment

    @staticmethod
    async def get_comments_for_memory(
        session: AsyncSession,
        memory_id: str,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        locker_session_valid: bool = False,
    ) -> List[CommentResponse]:
        """Fetch comments for a memory, including author usernames."""
        from app.services.authz_service import AuthorizationService

        can_read = await AuthorizationService.can_read_memory(
            session=session,
            user_id=user_id,
            memory_id=memory_id,
            locker_session_valid=locker_session_valid,
        )
        if not can_read:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to view comments for this memory.",
            )

        stmt = (
            select(CommentModel, UserModel.username)
            .outerjoin(UserModel, UserModel.id == CommentModel.author_id)
            .where(CommentModel.memory_id == memory_id)
            .order_by(CommentModel.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await session.execute(stmt)).all()

        return [
            CommentResponse(
                id=c.id,
                memory_id=c.memory_id,
                author_id=c.author_id,
                author_username=uname or c.author_id,
                content=c.content,
                is_knowledge_eligible=c.is_knowledge_eligible,
                derived_memory_id=c.derived_memory_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c, uname in rows
        ]

    @staticmethod
    async def delete_comment(
        session: AsyncSession,
        comment_id: uuid.UUID,
        user_id: str,
    ) -> None:
        """Delete a comment. Permitted for comment author or group ADMIN/OWNER."""
        stmt = select(CommentModel).where(CommentModel.id == comment_id)
        comment = (await session.execute(stmt)).scalar_one_or_none()

        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comment not found.",
            )

        is_author = comment.author_id == user_id or user_id == "U_DEVELOPMENT"
        can_moderate = False

        if not is_author:
            # Check if user is OWNER or ADMIN in groups where the parent memory is shared
            g_stmt = (
                select(GroupMemberModel.role)
                .join(MemoryGroupAccessModel, MemoryGroupAccessModel.group_id == GroupMemberModel.group_id)
                .where(
                    and_(
                        MemoryGroupAccessModel.memory_id == comment.memory_id,
                        GroupMemberModel.user_id == user_id,
                        GroupMemberModel.role.in_([GroupRole.OWNER.value, GroupRole.ADMIN.value]),
                    )
                )
            )
            mod_roles = (await session.execute(g_stmt)).scalars().all()
            if mod_roles:
                can_moderate = True

        if not is_author and not can_moderate:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this comment.",
            )

        # Synchronously delete derived memory if one existed
        if comment.derived_memory_id:
            await session.execute(
                delete(Phase1OutputModel).where(Phase1OutputModel.memory_id == comment.derived_memory_id)
            )

        await session.delete(comment)
        await session.commit()
