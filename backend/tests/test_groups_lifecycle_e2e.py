import json
import uuid
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient, ASGITransport

from app.core.enums import GroupRole, Privacy
from app.database.models.comments import CommentModel
from app.database.models.groups import (
    GroupFeedReferenceModel,
    GroupMemberModel,
    GroupModel,
    MemoryGroupAccessModel,
    MemoryUserAccessModel,
)
from app.database.models.phase1_output import Phase1OutputModel
from app.database.models.raw_input import RawInputModel
from app.database.models.user import UserModel
from app.main import app
from app.schemas.search_schemas import MemorySearchRequest
from app.services.authz_service import AuthorizationService
from app.services.comment_service import CommentService
from app.services.group_service import GroupService
from app.services.memory_search_service import MemorySearchService
from app.services.share_service import ShareService
from app.services.embedding_service import EmbeddingService


async def get_or_create_users(session: AsyncSession) -> dict[str, str]:
    """Helper to seed or fetch test users."""
    users = {}
    for uname in ["owner_u", "admin_u", "contrib_u", "member_u", "guest_u", "stranger_u"]:
        uid = f"U_{uname}"
        u = await session.get(UserModel, uid)
        if not u:
            u = UserModel(
                id=uid,
                username=uname,
                password_hash="argon2id$mocked",
            )
            session.add(u)
        users[uname] = uid
    await session.commit()
    return users


@pytest.mark.asyncio
async def test_scenario_a_group_lifecycle_and_invitations(db_session):
    """Scenario A: Create group, invite member, accept invitation, change roles, leave group."""
    async with db_session() as session:
        sample_users = await get_or_create_users(session)
        owner_id = sample_users["owner_u"]
        admin_id = sample_users["admin_u"]
        member_id = sample_users["member_u"]

        # 1. Create Group
        group = await GroupService.create_group(
            session=session,
            name="MindMesh Core Architects",
            description="Collaborative AI engineering team",
            avatar_url="https://example.com/avatar.png",
            creator_id=owner_id,
        )
        assert group.name == "MindMesh Core Architects"
        assert group.created_by == owner_id

        # Verify Owner membership was atomically created
        role = await GroupService.get_user_role(session, group.id, owner_id)
        assert role == GroupRole.OWNER.value

        # 2. Invite User as ADMIN
        invitation, raw_token = await GroupService.create_invitation(
            session=session,
            group_id=group.id,
            inviter_id=owner_id,
            invitee_email="admin@example.com",
            role=GroupRole.ADMIN.value,
        )
        assert invitation.status == "PENDING"
        assert raw_token is not None

        # 3. Accept Invitation
        new_member = await GroupService.accept_invitation(
            session=session,
            raw_token=raw_token,
            current_user_id=admin_id,
        )
        assert new_member.user_id == admin_id
        assert new_member.role == GroupRole.ADMIN.value

        # Replay attempt fails
        with pytest.raises(HTTPException) as exc:
            await GroupService.accept_invitation(session, raw_token, sample_users["stranger_u"])
        assert exc.value.status_code == 400

        # 4. Admin adds Contributor
        contrib_id = sample_users["contrib_u"]
        c_member = await GroupService.add_member(
            session=session,
            group_id=group.id,
            requester_id=admin_id,
            target_user_id=contrib_id,
            role=GroupRole.CONTRIBUTOR.value,
        )
        assert c_member.role == GroupRole.CONTRIBUTOR.value

        # 5. Admin attempts to appoint another ADMIN -> Fails (Only OWNER can create ADMIN)
        with pytest.raises(HTTPException) as exc:
            await GroupService.add_member(
                session=session,
                group_id=group.id,
                requester_id=admin_id,
                target_user_id=member_id,
                role=GroupRole.ADMIN.value,
            )
        assert exc.value.status_code == 403

        # 6. Admin adds MEMBER
        m_member = await GroupService.add_member(
            session=session,
            group_id=group.id,
            requester_id=admin_id,
            target_user_id=member_id,
            role=GroupRole.MEMBER.value,
        )
        assert m_member.role == GroupRole.MEMBER.value

        # 7. List user groups
        owner_groups = await GroupService.list_user_groups(session, owner_id)
        assert len(owner_groups) >= 1
        assert owner_groups[0]["my_role"] == GroupRole.OWNER.value
        assert owner_groups[0]["member_count"] == 4


@pytest.mark.asyncio
async def test_scenario_b_cross_group_isolation(db_session):
    """Scenario B: Stranger cannot access private group details, feed, media, or comments."""
    async with db_session() as session:
        sample_users = await get_or_create_users(session)
        owner_id = sample_users["owner_u"]
        stranger_id = sample_users["stranger_u"]

        group = await GroupService.create_group(session, "Top Secret Team", "Confidential", None, owner_id)

        # 1. Stranger attempts to view group details -> 403 Forbidden
        with pytest.raises(HTTPException) as exc:
            await GroupService.get_group_details(session, group.id, stranger_id)
        assert exc.value.status_code == 403

        # 2. Setup memory in group
        mem_id = f"M_sec_{uuid.uuid4().hex[:8]}"
        p1 = Phase1OutputModel(
            raw_input_id=uuid.uuid4(),
            memory_id=mem_id,
            owner_id=owner_id,
            privacy=Privacy.ONLY_ME.value,
            payload={"system": {"owner_id": owner_id, "privacy": "ONLY_ME"}},
        )
        session.add(p1)
        await session.commit()

        # Share to group
        await ShareService.share_memory(session, mem_id, owner_id, group_ids=[group.id])

        # Owner can read
        assert await AuthorizationService.can_read_memory(session, owner_id, mem_id)
        # Stranger CANNOT read
        assert not await AuthorizationService.can_read_memory(session, stranger_id, mem_id)

        # Stranger cannot comment
        with pytest.raises(HTTPException) as exc:
            await CommentService.add_comment(session, mem_id, stranger_id, "Sneaking in")
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_scenario_c_rbac_permission_boundaries(db_session):
    """Scenario C: Test full role boundary matrix (OWNER, ADMIN, CONTRIBUTOR, MEMBER, GUEST)."""
    async with db_session() as session:
        sample_users = await get_or_create_users(session)
        owner_id = sample_users["owner_u"]
        admin_id = sample_users["admin_u"]
        contrib_id = sample_users["contrib_u"]
        member_id = sample_users["member_u"]
        guest_id = sample_users["guest_u"]

        group = await GroupService.create_group(session, "Permissions Matrix Test", "RBAC", None, owner_id)
        await GroupService.add_member(session, group.id, owner_id, admin_id, GroupRole.ADMIN.value)
        await GroupService.add_member(session, group.id, owner_id, contrib_id, GroupRole.CONTRIBUTOR.value)
        await GroupService.add_member(session, group.id, owner_id, member_id, GroupRole.MEMBER.value)
        await GroupService.add_member(session, group.id, owner_id, guest_id, GroupRole.GUEST.value)

        # 1. Admin cannot remove OWNER
        with pytest.raises(HTTPException) as exc:
            await GroupService.remove_member(session, group.id, admin_id, owner_id)
        assert exc.value.status_code == 403

        # 2. Admin cannot delete group
        with pytest.raises(HTTPException) as exc:
            await GroupService.delete_group(session, group.id, admin_id)
        assert exc.value.status_code == 403

        # 3. Admin cannot transfer ownership
        with pytest.raises(HTTPException) as exc:
            await GroupService.transfer_ownership(session, group.id, admin_id, contrib_id)
        assert exc.value.status_code == 403

        # 4. Contributor cannot add or remove members
        with pytest.raises(HTTPException) as exc:
            await GroupService.remove_member(session, group.id, contrib_id, member_id)
        assert exc.value.status_code == 403

        # 5. Guest cannot share memories to group
        fake_mem = f"M_guest_{uuid.uuid4().hex[:8]}"
        p1 = Phase1OutputModel(
            raw_input_id=uuid.uuid4(),
            memory_id=fake_mem,
            owner_id=guest_id,
            privacy="ONLY_ME",
            payload={},
        )
        session.add(p1)
        await session.commit()

        with pytest.raises(HTTPException) as exc:
            await ShareService.share_memory(session, fake_mem, guest_id, group_ids=[group.id])
        assert exc.value.status_code == 403

        # 6. Guest cannot comment on group memories
        mem_owner = f"M_owner_{uuid.uuid4().hex[:8]}"
        p_owner = Phase1OutputModel(
            raw_input_id=uuid.uuid4(),
            memory_id=mem_owner,
            owner_id=owner_id,
            privacy="ONLY_ME",
            payload={},
        )
        session.add(p_owner)
        await session.commit()
        await ShareService.share_memory(session, mem_owner, owner_id, group_ids=[group.id])

        with pytest.raises(HTTPException) as exc:
            await CommentService.add_comment(session, mem_owner, guest_id, "Guest comment")
        assert exc.value.status_code == 403

        # 7. Member can view, and Contributor can comment
        comment = await CommentService.add_comment(
            session, mem_owner, contrib_id, "Substantive engineering architecture insight regarding dual vectors"
        )
        assert comment.is_knowledge_eligible is True


@pytest.mark.asyncio
async def test_scenario_d_instant_revocation(db_session):
    """Scenario D: When member is removed, subsequent access is immediately denied."""
    async with db_session() as session:
        sample_users = await get_or_create_users(session)
        owner_id = sample_users["owner_u"]
        member_id = sample_users["member_u"]

        group = await GroupService.create_group(session, "Revocation Group", "Revoke test", None, owner_id)
        await GroupService.add_member(session, group.id, owner_id, member_id, GroupRole.MEMBER.value)

        mem_id = f"M_rev_{uuid.uuid4().hex[:8]}"
        p = Phase1OutputModel(
            raw_input_id=uuid.uuid4(),
            memory_id=mem_id,
            owner_id=owner_id,
            privacy="ONLY_ME",
            payload={},
        )
        session.add(p)
        await session.commit()

        await ShareService.share_memory(session, mem_id, owner_id, group_ids=[group.id])

        # Member can read initially
        assert await AuthorizationService.can_read_memory(session, member_id, mem_id) is True

        # Owner removes member
        await GroupService.remove_member(session, group.id, owner_id, member_id)

        # Member is IMMEDIATELY denied
        assert await AuthorizationService.can_read_memory(session, member_id, mem_id) is False


@pytest.mark.asyncio
async def test_scenario_e_private_locker_firewall(db_session):
    """Scenario E: Private Locker memories can NEVER be shared with groups or users."""
    async with db_session() as session:
        sample_users = await get_or_create_users(session)
        owner_id = sample_users["owner_u"]
        admin_id = sample_users["admin_u"]

        group = await GroupService.create_group(session, "Firewall Group", "Locker test", None, owner_id)
        await GroupService.add_member(session, group.id, owner_id, admin_id, GroupRole.ADMIN.value)

        # Create private locker memory
        vault_mem = f"M_vault_{uuid.uuid4().hex[:8]}"
        p = Phase1OutputModel(
            raw_input_id=uuid.uuid4(),
            memory_id=vault_mem,
            owner_id=owner_id,
            privacy=Privacy.PRIVATE_LOCKER.value,
            payload={"system": {"owner_id": owner_id, "privacy": "PRIVATE_LOCKER"}},
        )
        session.add(p)
        await session.commit()

        # Attempt to share Private Locker memory to group -> Strictly rejected (400)
        with pytest.raises(HTTPException) as exc:
            await ShareService.share_memory(session, vault_mem, owner_id, group_ids=[group.id])
        assert exc.value.status_code == 400

        # Attempt to share directly with user -> Strictly rejected (400)
        with pytest.raises(HTTPException) as exc:
            await ShareService.share_memory(session, vault_mem, owner_id, user_ids=[admin_id])
        assert exc.value.status_code == 400

        # Verify access rules:
        # Admin can NEVER read
        assert not await AuthorizationService.can_read_memory(session, admin_id, vault_mem)
        # Owner cannot read without active locker session
        assert not await AuthorizationService.can_read_memory(session, owner_id, vault_mem, locker_session_valid=False)
        # Owner can read ONLY with active locker session
        assert await AuthorizationService.can_read_memory(session, owner_id, vault_mem, locker_session_valid=True)


@pytest.mark.asyncio
async def test_scenario_f_group_semantic_search_isolation(db_session):
    """Scenario F: Semantic search within Group A strictly isolates candidates and LLM context."""
    async with db_session() as session:
        sample_users = await get_or_create_users(session)
        owner_id = sample_users["owner_u"]
        member_id = sample_users["member_u"]
        stranger_id = sample_users["stranger_u"]

        group = await GroupService.create_group(session, "Alpha Team", "Isolated group", None, owner_id)
        await GroupService.add_member(session, group.id, owner_id, member_id, GroupRole.MEMBER.value)

        # Create memory in Group Alpha
        mem_alpha = f"M_alpha_{uuid.uuid4().hex[:8]}"
        raw_alpha = RawInputModel(
            media_type="text",
            raw_payload="Project Chimera deployment schedule for next Friday",
            group_id=str(group.id),
            owner_id=owner_id,
            privacy=Privacy.SHARED.value,
            status="completed",
        )
        session.add(raw_alpha)
        await session.flush()

        p1_alpha = Phase1OutputModel(
            raw_input_id=raw_alpha.id,
            memory_id=mem_alpha,
            owner_id=owner_id,
            privacy=Privacy.SHARED.value,
            schema_version="1.0",
            processing_status="completed",
            payload={
                "memory_id": mem_alpha,
                "system": {"owner_id": owner_id, "privacy": "SHARED"},
                "content": {
                    "clean_text": "Project Chimera deployment schedule for next Friday",
                    "raw_text": "Project Chimera deployment schedule for next Friday",
                    "summary": "Project Chimera deployment schedule",
                },
            },
        )
        session.add(p1_alpha)
        await session.flush()

        # Insert Group access
        session.add(MemoryGroupAccessModel(memory_id=mem_alpha, group_id=group.id, granted_by=owner_id))
        session.add(GroupFeedReferenceModel(memory_id=mem_alpha, group_id=group.id, shared_by=owner_id))

        # Insert dual-vector embedding record for semantic search
        from app.database.models.phase2_embedding import Phase2EmbeddingModel
        emb = Phase2EmbeddingModel(
            id=uuid.uuid4(),
            phase1_output_id=p1_alpha.id,
            memory_id=mem_alpha,
            content_vector=[0.1] * 1024,
            context_vector=[0.1] * 1024,
            embedding_model="mock-embedding",
        )
        session.add(emb)
        await session.commit()

        search_service = MemorySearchService(
            embedding_service=EmbeddingService(force_mock=True)
        )

        # 1. Member searches with group_id -> Finds memory
        member_search = await search_service.search(
            session=session,
            query="When is Project Chimera deployment?",
            user_id=member_id,
            group_id=group.id,
        )
        assert member_search.total_results >= 1
        assert any(r.memory_id == mem_alpha for r in member_search.results)

        # 2. Stranger searches with group_id -> Safely denied (0 results, no leak)
        stranger_search = await search_service.search(
            session=session,
            query="When is Project Chimera deployment?",
            user_id=stranger_id,
            group_id=group.id,
        )
        assert stranger_search.total_results == 0
        assert len(stranger_search.results) == 0


@pytest.mark.asyncio
async def test_scenario_g_comments_and_knowledge_capture(db_session):
    """Scenario G: Adding substantive comment captures derived knowledge; deleting cleans it up."""
    async with db_session() as session:
        sample_users = await get_or_create_users(session)
        owner_id = sample_users["owner_u"]
        contrib_id = sample_users["contrib_u"]

        group = await GroupService.create_group(session, "Knowledge Group", "Comments test", None, owner_id)
        await GroupService.add_member(session, group.id, owner_id, contrib_id, GroupRole.CONTRIBUTOR.value)

        mem_id = f"M_disc_{uuid.uuid4().hex[:8]}"
        p1 = Phase1OutputModel(
            raw_input_id=uuid.uuid4(),
            memory_id=mem_id,
            owner_id=owner_id,
            privacy=Privacy.ONLY_ME.value,
            payload={"system": {"owner_id": owner_id, "privacy": "ONLY_ME"}},
        )
        session.add(p1)
        await session.commit()
        await ShareService.share_memory(session, mem_id, owner_id, group_ids=[group.id])

        # Short trivial comment (< 25 chars) -> Not knowledge eligible
        c_short = await CommentService.add_comment(session, mem_id, contrib_id, "Looks good!")
        assert c_short.is_knowledge_eligible is False
        assert c_short.derived_memory_id is None

        # Substantive comment (>= 25 chars) -> Knowledge eligible + creates derived memory
        insight_text = "We should implement HNSW M=16 efConstruction=64 for pgvector indexing."
        c_insight = await CommentService.add_comment(session, mem_id, contrib_id, insight_text)
        assert c_insight.is_knowledge_eligible is True
        assert c_insight.derived_memory_id is not None

        # Verify derived memory exists in phase1_outputs
        derived_p1 = (
            await session.execute(
                select(Phase1OutputModel).where(Phase1OutputModel.memory_id == c_insight.derived_memory_id)
            )
        ).scalar_one_or_none()
        assert derived_p1 is not None

        # Delete comment -> Cleans up derived memory synchronously
        await CommentService.delete_comment(session, c_insight.id, contrib_id)

        # Verify derived memory was cleaned up
        derived_check = (
            await session.execute(
                select(Phase1OutputModel).where(Phase1OutputModel.memory_id == c_insight.derived_memory_id)
            )
        ).scalar_one_or_none()
        assert derived_check is None


@pytest.mark.asyncio
async def test_scenario_h_multi_group_and_direct_user_sharing(db_session):
    """Scenario H: Share single memory to multiple groups and individual users, then revoke selectively."""
    async with db_session() as session:
        sample_users = await get_or_create_users(session)
        owner_id = sample_users["owner_u"]
        user_b = sample_users["member_u"]
        user_c = sample_users["guest_u"]
        user_d = sample_users["stranger_u"]

        g1 = await GroupService.create_group(session, "Engineering", "Tech", None, owner_id)
        g2 = await GroupService.create_group(session, "Product", "Design", None, owner_id)

        await GroupService.add_member(session, g1.id, owner_id, user_b, GroupRole.MEMBER.value)
        await GroupService.add_member(session, g2.id, owner_id, user_c, GroupRole.MEMBER.value)

        mem_id = f"M_multi_{uuid.uuid4().hex[:8]}"
        p1 = Phase1OutputModel(
            raw_input_id=uuid.uuid4(),
            memory_id=mem_id,
            owner_id=owner_id,
            privacy=Privacy.ONLY_ME.value,
            payload={},
        )
        session.add(p1)
        await session.commit()

        # Share to g1, g2, and user_d directly
        await ShareService.share_memory(
            session=session,
            memory_id=mem_id,
            user_id=owner_id,
            group_ids=[g1.id, g2.id],
            user_ids=[user_d],
        )

        assert await AuthorizationService.can_read_memory(session, user_b, mem_id) is True
        assert await AuthorizationService.can_read_memory(session, user_c, mem_id) is True
        assert await AuthorizationService.can_read_memory(session, user_d, mem_id) is True

        # Revoke access for g2 only
        await ShareService.revoke_access(session, mem_id, owner_id, group_ids=[g2.id])

        assert await AuthorizationService.can_read_memory(session, user_b, mem_id) is True
        assert await AuthorizationService.can_read_memory(session, user_c, mem_id) is False  # g2 revoked
        assert await AuthorizationService.can_read_memory(session, user_d, mem_id) is True   # Direct kept
