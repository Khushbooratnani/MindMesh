import pytest
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.group_service import GroupService
from app.services.share_service import ShareService
from app.services.authz_service import AuthorizationService
from app.database.models.raw_input import RawInputModel
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.phase2_embedding import Phase2EmbeddingModel

@pytest.mark.asyncio
async def test_e2e_group_boundary(db_session):
    async with db_session() as session:
        # Setup
        g = await GroupService.create_group(session, "College", "Friends", "A")
        await GroupService.add_member(session, g.id, "A", "B")
        
        # Fake memory
        mem_id = "M_X"
        r = RawInputModel(media_type="text", raw_payload="hello", owner_id="A", privacy="ONLY_ME")
        session.add(r)
        await session.flush()
        p1 = Phase1OutputModel(raw_input_id=r.id, memory_id=mem_id, owner_id="A", privacy="ONLY_ME", payload={"text":"hello"})
        session.add(p1)
        await session.commit()
        
        # Share
        await ShareService.share_memory(session, mem_id, "A", [g.id], [])
        
        # Check Authz
        assert await AuthorizationService.can_read_memory(session, "A", mem_id)
        assert await AuthorizationService.can_read_memory(session, "B", mem_id)
        assert not await AuthorizationService.can_read_memory(session, "P", mem_id)
