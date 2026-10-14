import uuid
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.database.models.comments import CommentModel
from app.database.models.raw_input import RawInputModel
from app.database.models.phase1_output import Phase1OutputModel
from app.services.authz_service import AuthorizationService

class CommentService:
    @staticmethod
    async def add_comment(session: AsyncSession, memory_id: str, author_id: str, content: str) -> CommentModel:
        if not await AuthorizationService.can_read_memory(session, author_id, memory_id):
            raise HTTPException(status_code=403)
            
        c = CommentModel(memory_id=memory_id, author_id=author_id, content=content)
        # Mock NLP logic
        if len(content.split()) > 4:
            c.is_knowledge_eligible = True
            c.derived_memory_id = f"M_COM_{uuid.uuid4().hex[:8]}"
            # Generate RawInput & Phase1 derived logic dynamically inheriting parent ACL
            raw = RawInputModel(media_type="text", raw_payload=content, owner_id=author_id, source_type="COMMENT", parent_memory_id=memory_id)
            session.add(raw)
            await session.flush()
            p1 = Phase1OutputModel(raw_input_id=raw.id, memory_id=c.derived_memory_id, owner_id=author_id, source_type="COMMENT", parent_memory_id=memory_id, privacy="SHARED", payload={"text": content})
            session.add(p1)
            
        session.add(c)
        await session.commit()
        return c

    @staticmethod
    async def delete_comment(session: AsyncSession, comment_id: uuid.UUID, user_id: str):
        stmt = select(CommentModel).where(and_(CommentModel.id == comment_id, CommentModel.author_id == user_id))
        c = (await session.execute(stmt)).scalars().first()
        if not c: raise HTTPException(status_code=403)
        if c.derived_memory_id:
            await session.execute(delete(Phase1OutputModel).where(Phase1OutputModel.memory_id == c.derived_memory_id))
        await session.delete(c)
        await session.commit()
