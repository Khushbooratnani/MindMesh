import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.services.group_service import GroupService
from app.services.share_service import ShareService
from app.services.authz_service import AuthorizationService
from app.services.comment_service import CommentService
from app.database.models.raw_input import RawInputModel
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.groups import GroupFeedReferenceModel
from sqlalchemy import select

@pytest.mark.asyncio
async def test_all_requirements_e2e(db_session):
    async with db_session() as session:
        # 1. Group CRUD & Roles
        g1 = await GroupService.create_group(session, "College", "Friends", "A")
        assert g1.name == "College"
        
        await GroupService.add_member(session, g1.id, "A", "B", "ADMIN")
        await GroupService.add_member(session, g1.id, "A", "C", "MEMBER")
        await GroupService.add_member(session, g1.id, "A", "D", "MEMBER")
        
        # Unauthorized admin
        with pytest.raises(HTTPException) as exc:
            await GroupService.add_member(session, g1.id, "C", "P")
        assert exc.value.status_code == 403

        # Fake memory setup
        mem_x = "M_X"
        p1 = Phase1OutputModel(raw_input_id=uuid.uuid4(), memory_id=mem_x, owner_id="A", privacy="ONLY_ME", payload={})
        session.add(p1)
        
        mem_y = "M_Y"
        p2 = Phase1OutputModel(raw_input_id=uuid.uuid4(), memory_id=mem_y, owner_id="A", privacy="ONLY_ME", payload={})
        session.add(p2)
        
        mem_pub = "M_PUB"
        p3 = Phase1OutputModel(raw_input_id=uuid.uuid4(), memory_id=mem_pub, owner_id="A", privacy="PUBLIC", payload={})
        session.add(p3)
        
        mem_priv = "M_PRIV"
        p4 = Phase1OutputModel(raw_input_id=uuid.uuid4(), memory_id=mem_priv, owner_id="A", privacy="PRIVATE_LOCKER", payload={})
        session.add(p4)
        await session.commit()
        
        # Single group sharing (College)
        await ShareService.share_memory(session, mem_x, "A", [g1.id], [])
        assert await AuthorizationService.can_read_memory(session, "B", mem_x)
        assert await AuthorizationService.can_read_memory(session, "C", mem_x)
        assert not await AuthorizationService.can_read_memory(session, "P", mem_x)
        
        # Multi group + Direct (Combined)
        g2 = await GroupService.create_group(session, "Project", "Team", "A")
        await GroupService.add_member(session, g2.id, "A", "P")
        await ShareService.share_memory(session, mem_y, "A", [g1.id, g2.id], ["Q"])
        
        assert await AuthorizationService.can_read_memory(session, "C", mem_y) # College
        assert await AuthorizationService.can_read_memory(session, "P", mem_y) # Project
        assert await AuthorizationService.can_read_memory(session, "Q", mem_y) # Direct
        assert not await AuthorizationService.can_read_memory(session, "R", mem_y)
        
        # Revocation
        await ShareService.revoke_access(session, mem_y, "A", group_ids=[g2.id])
        assert not await AuthorizationService.can_read_memory(session, "P", mem_y) # Lost Project access
        assert await AuthorizationService.can_read_memory(session, "C", mem_y) # Still College
        assert await AuthorizationService.can_read_memory(session, "Q", mem_y) # Still Direct
        
        # Membership Revocation
        await ShareService.share_memory(session, mem_y, "A", [], ["B"]) # B has direct AND group
        await GroupService.remove_member(session, g1.id, "A", "B")
        # B lost College but keeps direct
        assert await AuthorizationService.can_read_memory(session, "B", mem_y) 
        
        # Public
        assert await AuthorizationService.can_read_memory(session, "Z", mem_pub)
        
        # Public -> Group Reference
        await ShareService.share_memory(session, mem_pub, "A", [g1.id], [])
        ref = (await session.execute(select(GroupFeedReferenceModel).where(GroupFeedReferenceModel.memory_id == mem_pub))).scalars().first()
        assert ref is not None
        
        # Private Locker Protection
        with pytest.raises(HTTPException):
            await ShareService.share_memory(session, mem_priv, "A", [g1.id], [])
        assert not await AuthorizationService.can_read_memory(session, "Z", mem_priv)
        assert not await AuthorizationService.can_read_memory(session, "A", mem_priv, locker_session_valid=False)
        assert await AuthorizationService.can_read_memory(session, "A", mem_priv, locker_session_valid=True)
        
        # Comments & Meaningful Knowledge
        c_short = await CommentService.add_comment(session, mem_x, "C", "Nice")
        assert not c_short.is_knowledge_eligible
        
        c_long = await CommentService.add_comment(session, mem_x, "C", "The starters were excellent yesterday")
        assert c_long.is_knowledge_eligible
        assert c_long.derived_memory_id is not None
        
        # Delete Sync
        await CommentService.delete_comment(session, c_long.id, "C")
        assert (await session.execute(select(Phase1OutputModel).where(Phase1OutputModel.memory_id == c_long.derived_memory_id))).scalars().first() is None
