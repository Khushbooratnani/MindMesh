import uuid
from typing import List
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.groups import MemoryGroupAccessModel, MemoryUserAccessModel, GroupFeedReferenceModel

class ShareService:
    @staticmethod
    async def share_memory(session: AsyncSession, memory_id: str, owner_id: str, group_ids: List[uuid.UUID], user_ids: List[str]):
        stmt = select(Phase1OutputModel).where(and_(Phase1OutputModel.memory_id == memory_id, Phase1OutputModel.owner_id == owner_id))
        memory = (await session.execute(stmt)).scalars().first()
        if not memory: raise HTTPException(status_code=404)
        if memory.privacy == "PRIVATE_LOCKER": raise HTTPException(status_code=400)
            
        if memory.privacy == "ONLY_ME":
            memory.privacy = "SHARED"
            
        for gid in group_ids:
            if memory.privacy == "PUBLIC":
                # Create feed reference instead of ACL
                session.add(GroupFeedReferenceModel(memory_id=memory_id, group_id=gid, shared_by=owner_id))
            else:
                session.add(MemoryGroupAccessModel(memory_id=memory_id, group_id=gid, granted_by=owner_id))
            
        for uid in user_ids:
            if memory.privacy != "PUBLIC":
                session.add(MemoryUserAccessModel(memory_id=memory_id, user_id=uid, granted_by=owner_id))
            
        await session.commit()
        return True

    @staticmethod
    async def revoke_access(session: AsyncSession, memory_id: str, owner_id: str, group_ids: List[uuid.UUID] = None, user_ids: List[str] = None):
        group_ids = group_ids or []
        user_ids = user_ids or []
        if group_ids:
            await session.execute(delete(MemoryGroupAccessModel).where(and_(MemoryGroupAccessModel.memory_id == memory_id, MemoryGroupAccessModel.group_id.in_(group_ids))))
        if user_ids:
            await session.execute(delete(MemoryUserAccessModel).where(and_(MemoryUserAccessModel.memory_id == memory_id, MemoryUserAccessModel.user_id.in_(user_ids))))
        await session.commit()
