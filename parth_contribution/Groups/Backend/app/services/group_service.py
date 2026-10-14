import uuid
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.database.models.groups import GroupModel, GroupMemberModel

class GroupService:
    @staticmethod
    async def create_group(session: AsyncSession, name: str, description: str, user_id: str) -> GroupModel:
        group = GroupModel(name=name, description=description, created_by=user_id)
        session.add(group)
        await session.flush()
        member = GroupMemberModel(group_id=group.id, user_id=user_id, role="OWNER")
        session.add(member)
        await session.commit()
        return group
        
    @staticmethod
    async def add_member(session: AsyncSession, group_id: uuid.UUID, adder_id: str, target_user_id: str, role: str = "MEMBER"):
        stmt = select(GroupMemberModel).where(and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == adder_id))
        adder = (await session.execute(stmt)).scalars().first()
        if not adder or adder.role not in ["OWNER", "ADMIN"]:
            raise HTTPException(status_code=403, detail="Not authorized")
            
        member = GroupMemberModel(group_id=group_id, user_id=target_user_id, role=role)
        session.add(member)
        await session.commit()
        return member

    @staticmethod
    async def remove_member(session: AsyncSession, group_id: uuid.UUID, remover_id: str, target_user_id: str):
        if remover_id != target_user_id:
            stmt = select(GroupMemberModel).where(and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == remover_id))
            remover = (await session.execute(stmt)).scalars().first()
            if not remover or remover.role not in ["OWNER", "ADMIN"]:
                raise HTTPException(status_code=403, detail="Not authorized")
                
        stmt = delete(GroupMemberModel).where(and_(GroupMemberModel.group_id == group_id, GroupMemberModel.user_id == target_user_id))
        await session.execute(stmt)
        await session.commit()
