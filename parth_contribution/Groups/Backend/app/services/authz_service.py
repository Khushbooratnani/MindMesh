import uuid
from typing import List
from sqlalchemy import select, and_, exists
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models.raw_input import RawInputModel
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.groups import GroupMemberModel, MemoryGroupAccessModel, MemoryUserAccessModel

class AuthorizationService:
    @staticmethod
    async def can_read_memory(session: AsyncSession, user_id: str, memory_id: str, locker_session_valid: bool = False) -> bool:
        stmt = select(Phase1OutputModel).where(Phase1OutputModel.memory_id == memory_id)
        res = await session.execute(stmt)
        memory = res.scalars().first()
        if not memory:
            return False
            
        if memory.privacy == "PRIVATE_LOCKER":
            return memory.owner_id == user_id and locker_session_valid
            
        if memory.privacy == "PUBLIC":
            return True
            
        if memory.owner_id == user_id:
            return True
            
        if memory.privacy == "SHARED":
            d_stmt = select(MemoryUserAccessModel).where(and_(MemoryUserAccessModel.memory_id == memory_id, MemoryUserAccessModel.user_id == user_id))
            if (await session.execute(d_stmt)).scalars().first():
                return True
                
            g_stmt = select(MemoryGroupAccessModel).where(
                and_(
                    MemoryGroupAccessModel.memory_id == memory_id,
                    exists().where(and_(GroupMemberModel.group_id == MemoryGroupAccessModel.group_id, GroupMemberModel.user_id == user_id))
                )
            )
            if (await session.execute(g_stmt)).scalars().first():
                return True
                
        return False
        
    @staticmethod
    def get_accessible_memory_ids_query(user_id: str, locker_session_valid: bool = False):
        if locker_session_valid:
            owner_q = select(Phase1OutputModel.memory_id).where(Phase1OutputModel.owner_id == user_id)
        else:
            owner_q = select(Phase1OutputModel.memory_id).where(and_(Phase1OutputModel.owner_id == user_id, Phase1OutputModel.privacy != "PRIVATE_LOCKER"))
        public_q = select(Phase1OutputModel.memory_id).where(Phase1OutputModel.privacy == "PUBLIC")
        direct_q = select(MemoryUserAccessModel.memory_id).where(MemoryUserAccessModel.user_id == user_id)
        group_q = select(MemoryGroupAccessModel.memory_id).where(
            exists().where(and_(GroupMemberModel.group_id == MemoryGroupAccessModel.group_id, GroupMemberModel.user_id == user_id))
        )
        return owner_q.union(public_q, direct_q, group_q)
