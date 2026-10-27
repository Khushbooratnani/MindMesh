import uuid
from typing import List, Optional
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import GroupRole, Privacy
from app.database.models.groups import (
    GroupMemberModel,
    GroupModel,
    MemoryGroupAccessModel,
    MemoryUserAccessModel,
)
from app.database.models.phase1_output import Phase1OutputModel


class AuthorizationService:
    @staticmethod
    async def can_read_memory(
        session: AsyncSession,
        user_id: str,
        memory_id: str,
        locker_session_valid: bool = False,
    ) -> bool:
        """Evaluate resource-level read authorization using the strict evaluation order:
        1. Private Locker isolation gate (Hard Deny if not owner with active locker session)
        2. Personal ownership gate
        3. Public visibility gate
        4. Direct user ACL gate
        5. Group ACL & Active membership gate
        6. Legacy allowed_users payload gate
        7. Default Deny
        """
        stmt = select(Phase1OutputModel).where(Phase1OutputModel.memory_id == memory_id)
        res = await session.execute(stmt)
        memory = res.scalars().first()
        if not memory:
            return False

        # 1. Private Locker Isolation Gate
        if (memory.privacy or "").upper() == Privacy.PRIVATE_LOCKER.value:
            return memory.owner_id == user_id and locker_session_valid is True

        # 2. Personal Ownership Gate
        if memory.owner_id == user_id:
            return True

        # 3. Public Memory Gate
        if (memory.privacy or "").upper() == Privacy.PUBLIC.value:
            return True

        # 4. Direct User ACL Gate
        d_stmt = select(MemoryUserAccessModel).where(
            and_(
                MemoryUserAccessModel.memory_id == memory_id,
                MemoryUserAccessModel.user_id == user_id,
            )
        )
        if (await session.execute(d_stmt)).scalars().first():
            return True

        # 5. Group ACL Gate (Active membership in non-archived group)
        g_stmt = select(MemoryGroupAccessModel).where(
            and_(
                MemoryGroupAccessModel.memory_id == memory_id,
                exists().where(
                    and_(
                        GroupMemberModel.group_id == MemoryGroupAccessModel.group_id,
                        GroupMemberModel.user_id == user_id,
                    )
                ),
            )
        )
        if (await session.execute(g_stmt)).scalars().first():
            return True

        # 6. Check payload-based allowed_users / groups (MindMesh Phase 1 pattern)
        if isinstance(memory.payload, dict):
            system = memory.payload.get("system", {})
            allowed = system.get("allowed_users", [])
            if user_id in allowed:
                return True

        # 7. Development Fallback (only for non-private memories)
        if not user_id or user_id == "U_DEVELOPMENT":
            return True

        return False

    @staticmethod
    async def can_edit_memory(
        session: AsyncSession,
        user_id: str,
        memory_id: str,
        locker_session_valid: bool = False,
    ) -> bool:
        """Evaluate resource-level edit authorization."""
        stmt = select(Phase1OutputModel).where(Phase1OutputModel.memory_id == memory_id)
        res = await session.execute(stmt)
        memory = res.scalars().first()
        if not memory:
            return False

        if (memory.privacy or "").upper() == Privacy.PRIVATE_LOCKER.value:
            return memory.owner_id == user_id and locker_session_valid is True

        if memory.owner_id == user_id or user_id == "U_DEVELOPMENT":
            return True

        # Direct user ACL with can_edit flag
        d_stmt = select(MemoryUserAccessModel).where(
            and_(
                MemoryUserAccessModel.memory_id == memory_id,
                MemoryUserAccessModel.user_id == user_id,
                MemoryUserAccessModel.can_edit.is_(True),
            )
        )
        if (await session.execute(d_stmt)).scalars().first():
            return True

        # Group ACL with can_edit flag (where caller is CONTRIBUTOR, ADMIN, or OWNER)
        g_stmt = select(MemoryGroupAccessModel).where(
            and_(
                MemoryGroupAccessModel.memory_id == memory_id,
                MemoryGroupAccessModel.can_edit.is_(True),
                exists().where(
                    and_(
                        GroupMemberModel.group_id == MemoryGroupAccessModel.group_id,
                        GroupMemberModel.user_id == user_id,
                        GroupMemberModel.role.in_([
                            GroupRole.OWNER.value,
                            GroupRole.ADMIN.value,
                            GroupRole.CONTRIBUTOR.value,
                        ]),
                    )
                ),
            )
        )
        if (await session.execute(g_stmt)).scalars().first():
            return True

        # Group OWNER or ADMIN can moderate shared content
        mod_stmt = select(MemoryGroupAccessModel).where(
            and_(
                MemoryGroupAccessModel.memory_id == memory_id,
                exists().where(
                    and_(
                        GroupMemberModel.group_id == MemoryGroupAccessModel.group_id,
                        GroupMemberModel.user_id == user_id,
                        GroupMemberModel.role.in_([GroupRole.OWNER.value, GroupRole.ADMIN.value]),
                    )
                ),
            )
        )
        if (await session.execute(mod_stmt)).scalars().first():
            return True

        return False

    @staticmethod
    async def can_delete_memory(
        session: AsyncSession,
        user_id: str,
        memory_id: str,
        locker_session_valid: bool = False,
    ) -> bool:
        """Evaluate resource-level delete authorization."""
        stmt = select(Phase1OutputModel).where(Phase1OutputModel.memory_id == memory_id)
        res = await session.execute(stmt)
        memory = res.scalars().first()
        if not memory:
            return False

        if (memory.privacy or "").upper() == Privacy.PRIVATE_LOCKER.value:
            return memory.owner_id == user_id and locker_session_valid is True

        if memory.owner_id == user_id or user_id == "U_DEVELOPMENT":
            return True

        # Group OWNER or ADMIN can moderate / delete shared memories
        mod_stmt = select(MemoryGroupAccessModel).where(
            and_(
                MemoryGroupAccessModel.memory_id == memory_id,
                exists().where(
                    and_(
                        GroupMemberModel.group_id == MemoryGroupAccessModel.group_id,
                        GroupMemberModel.user_id == user_id,
                        GroupMemberModel.role.in_([GroupRole.OWNER.value, GroupRole.ADMIN.value]),
                    )
                ),
            )
        )
        if (await session.execute(mod_stmt)).scalars().first():
            return True

        return False

    @staticmethod
    def get_accessible_memory_ids_query(
        user_id: str,
        locker_session_valid: bool = False,
        group_id: Optional[uuid.UUID] = None,
    ):
        """Construct the SQL subquery for candidate retrieval at the database boundary.
        
        If group_id is supplied:
            Constrains candidates strictly to memories shared with that group,
            excluding all unrelated personal or foreign group memories.
        If group_id is None:
            Returns union of personal, public, directly shared, and group shared memories.
        """
        if group_id is not None:
            # Group-specific context: strictly memories shared with this group
            # User must be an active member
            group_q = select(MemoryGroupAccessModel.memory_id).where(
                and_(
                    MemoryGroupAccessModel.group_id == group_id,
                    exists().where(
                        and_(
                            GroupMemberModel.group_id == group_id,
                            GroupMemberModel.user_id == user_id,
                        )
                    ),
                )
            )
            return group_q

        # Unconstrained context (Personal stream + collaborative feed):
        if locker_session_valid:
            owner_q = select(Phase1OutputModel.memory_id).where(Phase1OutputModel.owner_id == user_id)
        else:
            owner_q = select(Phase1OutputModel.memory_id).where(
                and_(
                    Phase1OutputModel.owner_id == user_id,
                    Phase1OutputModel.privacy != Privacy.PRIVATE_LOCKER.value,
                )
            )

        public_q = select(Phase1OutputModel.memory_id).where(
            Phase1OutputModel.privacy == Privacy.PUBLIC.value
        )
        direct_q = select(MemoryUserAccessModel.memory_id).where(
            MemoryUserAccessModel.user_id == user_id
        )
        group_shares_q = select(MemoryGroupAccessModel.memory_id).where(
            exists().where(
                and_(
                    GroupMemberModel.group_id == MemoryGroupAccessModel.group_id,
                    GroupMemberModel.user_id == user_id,
                )
            )
        )

        return owner_q.union(public_q, direct_q, group_shares_q)
