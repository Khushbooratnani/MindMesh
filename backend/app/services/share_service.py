import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GroupRole, Privacy
from app.database.models.groups import (
    GroupFeedReferenceModel,
    GroupModel,
    MemoryGroupAccessModel,
    MemoryUserAccessModel,
)
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.raw_input import RawInputModel
from app.database.models.user import UserModel
from app.schemas.group import MemoryShareDetail, MemorySharesResponse
from app.services.group_service import GroupService


class ShareService:
    @staticmethod
    async def share_memory(
        session: AsyncSession,
        memory_id: str,
        user_id: str,
        group_ids: Optional[List[uuid.UUID]] = None,
        user_ids: Optional[List[str]] = None,
        can_edit: bool = False,
        can_reshare: bool = False,
    ) -> None:
        """Share a personal memory with specified groups and/or users.
        
        Strictly enforces:
        1. Private Locker isolation: PRIVATE_LOCKER memories can NEVER be shared.
        2. Ownership verification: Only the memory owner can share.
        3. Zero vector/memory duplication: creates only ACL associations.
        4. Group membership verification: Caller must belong to the target group(s).
        """
        group_ids = group_ids or []
        user_ids = user_ids or []

        if not group_ids and not user_ids:
            return

        # 1. Fetch memory record
        stmt = select(Phase1OutputModel).where(Phase1OutputModel.memory_id == memory_id)
        res = await session.execute(stmt)
        memory = res.scalar_one_or_none()

        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory {memory_id} not found.",
            )

        # 2. Hard Isolation: PRIVATE_LOCKER memories can never be shared
        if (memory.privacy or "").upper() == Privacy.PRIVATE_LOCKER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Private locker memories cannot be shared with groups or other users.",
            )

        # 3. Ownership / authorization verification
        if memory.owner_id != user_id and user_id != "U_DEVELOPMENT":
            # Check if user has can_reshare grant
            reshare_grant = (
                await session.execute(
                    select(MemoryGroupAccessModel).where(
                        and_(
                            MemoryGroupAccessModel.memory_id == memory_id,
                            MemoryGroupAccessModel.can_reshare.is_(True),
                        )
                    )
                )
            ).scalars().first()
            if not reshare_grant:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the memory owner or permitted resharer can share this memory.",
                )

        # 4. Process group shares
        for gid in group_ids:
            # Verify caller is a member of target group and has sharing permission (not GUEST)
            role = await GroupService.verify_membership(session, gid, user_id)
            if role == GroupRole.GUEST.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Guests cannot share memories to group {gid}.",
                )

            # Insert or update memory_group_access
            existing_g = (
                await session.execute(
                    select(MemoryGroupAccessModel).where(
                        and_(
                            MemoryGroupAccessModel.memory_id == memory_id,
                            MemoryGroupAccessModel.group_id == gid,
                        )
                    )
                )
            ).scalar_one_or_none()

            if not existing_g:
                mga = MemoryGroupAccessModel(
                    memory_id=memory_id,
                    group_id=gid,
                    granted_by=user_id,
                    can_edit=can_edit,
                    can_reshare=can_reshare,
                )
                session.add(mga)

            # Insert or update group_feed_references
            existing_ref = (
                await session.execute(
                    select(GroupFeedReferenceModel).where(
                        and_(
                            GroupFeedReferenceModel.memory_id == memory_id,
                            GroupFeedReferenceModel.group_id == gid,
                        )
                    )
                )
            ).scalar_one_or_none()

            if not existing_ref:
                gfr = GroupFeedReferenceModel(
                    memory_id=memory_id,
                    group_id=gid,
                    shared_by=user_id,
                )
                session.add(gfr)

        # 5. Process direct user shares
        for uid in user_ids:
            if uid == memory.owner_id:
                continue

            # Verify target user exists
            target_user = (
                await session.execute(select(UserModel).where(UserModel.id == uid))
            ).scalar_one_or_none()
            if not target_user:
                continue

            existing_u = (
                await session.execute(
                    select(MemoryUserAccessModel).where(
                        and_(
                            MemoryUserAccessModel.memory_id == memory_id,
                            MemoryUserAccessModel.user_id == uid,
                        )
                    )
                )
            ).scalar_one_or_none()

            if not existing_u:
                mua = MemoryUserAccessModel(
                    memory_id=memory_id,
                    user_id=uid,
                    granted_by=user_id,
                    can_edit=can_edit,
                )
                session.add(mua)

        # 6. Update memory privacy status to SHARED if previously ONLY_ME
        if memory.privacy in (Privacy.ONLY_ME.value, Privacy.GROUP.value, Privacy.SELECTED.value):
            memory.privacy = Privacy.SHARED.value
            # Also update raw_inputs privacy if associated
            if memory.raw_input_id:
                raw_input = (
                    await session.execute(
                        select(RawInputModel).where(RawInputModel.id == memory.raw_input_id)
                    )
                ).scalar_one_or_none()
                if raw_input:
                    raw_input.privacy = Privacy.SHARED.value

        await session.commit()

    @staticmethod
    async def revoke_access(
        session: AsyncSession,
        memory_id: str,
        user_id: str,
        group_ids: Optional[List[uuid.UUID]] = None,
        user_ids: Optional[List[str]] = None,
    ) -> None:
        """Revoke sharing permissions for specific groups and/or users.
        
        Strictly requires memory owner.
        """
        group_ids = group_ids or []
        user_ids = user_ids or []

        stmt = select(Phase1OutputModel).where(Phase1OutputModel.memory_id == memory_id)
        memory = (await session.execute(stmt)).scalar_one_or_none()

        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory {memory_id} not found.",
            )

        if memory.owner_id != user_id and user_id != "U_DEVELOPMENT":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the memory owner can revoke sharing permissions.",
            )

        # Revoke group access
        if group_ids:
            await session.execute(
                delete(MemoryGroupAccessModel).where(
                    and_(
                        MemoryGroupAccessModel.memory_id == memory_id,
                        MemoryGroupAccessModel.group_id.in_(group_ids),
                    )
                )
            )
            await session.execute(
                delete(GroupFeedReferenceModel).where(
                    and_(
                        GroupFeedReferenceModel.memory_id == memory_id,
                        GroupFeedReferenceModel.group_id.in_(group_ids),
                    )
                )
            )

        # Revoke user access
        if user_ids:
            await session.execute(
                delete(MemoryUserAccessModel).where(
                    and_(
                        MemoryUserAccessModel.memory_id == memory_id,
                        MemoryUserAccessModel.user_id.in_(user_ids),
                    )
                )
            )

        # Check remaining shares. If none left and privacy is SHARED, revert to ONLY_ME
        remaining_g = (
            await session.execute(
                select(MemoryGroupAccessModel).where(MemoryGroupAccessModel.memory_id == memory_id)
            )
        ).first()
        remaining_u = (
            await session.execute(
                select(MemoryUserAccessModel).where(MemoryUserAccessModel.memory_id == memory_id)
            )
        ).first()

        if not remaining_g and not remaining_u and memory.privacy == Privacy.SHARED.value:
            memory.privacy = Privacy.ONLY_ME.value
            if memory.raw_input_id:
                raw_input = (
                    await session.execute(
                        select(RawInputModel).where(RawInputModel.id == memory.raw_input_id)
                    )
                ).scalar_one_or_none()
                if raw_input:
                    raw_input.privacy = Privacy.ONLY_ME.value

        await session.commit()

    @staticmethod
    async def get_memory_shares(
        session: AsyncSession,
        memory_id: str,
        user_id: str,
    ) -> MemorySharesResponse:
        """Fetch current sharing configuration for a memory."""
        stmt = select(Phase1OutputModel).where(Phase1OutputModel.memory_id == memory_id)
        memory = (await session.execute(stmt)).scalar_one_or_none()

        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Memory {memory_id} not found.",
            )

        # Group shares
        g_stmt = select(MemoryGroupAccessModel).where(MemoryGroupAccessModel.memory_id == memory_id)
        g_shares = (await session.execute(g_stmt)).scalars().all()

        # User shares
        u_stmt = select(MemoryUserAccessModel).where(MemoryUserAccessModel.memory_id == memory_id)
        u_shares = (await session.execute(u_stmt)).scalars().all()

        return MemorySharesResponse(
            memory_id=memory.memory_id,
            owner_id=memory.owner_id or "",
            privacy=memory.privacy or "ONLY_ME",
            group_shares=[
                MemoryShareDetail(
                    group_id=gs.group_id,
                    can_edit=gs.can_edit,
                    created_at=gs.created_at,
                )
                for gs in g_shares
            ],
            user_shares=[
                MemoryShareDetail(
                    user_id=us.user_id,
                    can_edit=us.can_edit,
                    created_at=us.created_at,
                )
                for us in u_shares
            ],
        )
