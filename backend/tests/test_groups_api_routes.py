import uuid
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.enums import GroupRole, Privacy
from app.api.routes.memories import get_ingestion_service
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService


@pytest.mark.asyncio
async def test_groups_api_routes_full_flow():
    """Full HTTP API integration test for Groups, Members, Sharing, Feed, and Comments."""
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        llm_service=LLMService(model_name="mock-memory-extractor")
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as api_client:
            tokens = {}
            for uname in ["alice_owner", "bob_member", "eve_stranger"]:
                pwd = "TestPassword123!"
                reg = await api_client.post("/api/v1/auth/register", json={"username": uname, "password": pwd})
                login = await api_client.post("/api/v1/auth/login", data={"username": uname, "password": pwd})
                assert login.status_code == 200, f"Login failed for {uname}: {login.text}"
                tokens[uname] = {
                    "token": login.json()["access_token"],
                    "headers": {"Authorization": f"Bearer {login.json()['access_token']}"},
                    "user_id": reg.json()["id"],
                }

            alice = tokens["alice_owner"]
            bob = tokens["bob_member"]
            eve = tokens["eve_stranger"]

            # 1. Alice creates group
            resp = await api_client.post(
                "/api/v1/groups",
                json={"name": "Engineering Team", "description": "Backend & AI team"},
                headers=alice["headers"],
            )
            assert resp.status_code == 201, resp.text
            group_data = resp.json()
            group_id = group_data["id"]
            assert group_data["name"] == "Engineering Team"
            assert group_data["my_role"] == GroupRole.OWNER.value

            # 2. Alice lists groups -> Contains Engineering Team
            resp = await api_client.get("/api/v1/groups", headers=alice["headers"])
            assert resp.status_code == 200
            my_groups = resp.json()
            assert any(g["id"] == group_id for g in my_groups)

            # 3. Eve lists groups -> Empty (Eve is not a member)
            resp = await api_client.get("/api/v1/groups", headers=eve["headers"])
            assert resp.status_code == 200
            assert not any(g["id"] == group_id for g in resp.json())

            # 4. Eve attempts to view group details -> 403 Forbidden
            resp = await api_client.get(f"/api/v1/groups/{group_id}", headers=eve["headers"])
            assert resp.status_code == 403

            # 5. Alice invites Bob via invitation token
            resp = await api_client.post(
                f"/api/v1/groups/{group_id}/invitations",
                json={"invitee_email": "bob@example.com", "role": GroupRole.CONTRIBUTOR.value},
                headers=alice["headers"],
            )
            assert resp.status_code == 201
            inv_data = resp.json()
            raw_token = inv_data["invitation_token"]
            assert raw_token is not None

            # 6. Bob accepts invitation
            resp = await api_client.post(
                "/api/v1/groups/invitations/accept",
                json={"token": raw_token},
                headers=bob["headers"],
            )
            assert resp.status_code == 200
            assert resp.json()["role"] == GroupRole.CONTRIBUTOR.value

            # 7. Bob now sees group in his list
            resp = await api_client.get("/api/v1/groups", headers=bob["headers"])
            assert resp.status_code == 200
            assert any(g["id"] == group_id for g in resp.json())

            # 8. Alice ingests memory targeted at group
            resp = await api_client.post(
                "/api/v1/memories/ingest",
                json={
                    "media_type": "text",
                    "text": "Quarterly architecture review for MindMesh pgvector and groups",
                    "group_id": group_id,
                    "privacy": Privacy.SHARED.value,
                },
                headers=alice["headers"],
            )
            assert resp.status_code == 200
            memory_id = resp.json()["memory_id"]

            # 9. Bob views group feed -> Contains the memory
            resp = await api_client.get(f"/api/v1/memories/feed?group_id={group_id}", headers=bob["headers"])
            assert resp.status_code == 200
            feed = resp.json()
            assert feed["total_count"] >= 1
            assert any(item["memory_id"] == memory_id for item in feed["items"])

            # 10. Eve attempts to view group feed -> 403 Forbidden
            resp = await api_client.get(f"/api/v1/memories/feed?group_id={group_id}", headers=eve["headers"])
            assert resp.status_code == 403

            # 11. Bob adds comment to the memory
            resp = await api_client.post(
                f"/api/v1/memories/{memory_id}/comments",
                json={"content": "Reviewed the dual vectors; 1024-dim BGE-M3 performs great."},
                headers=bob["headers"],
            )
            assert resp.status_code == 201
            comment_data = resp.json()
            comment_id = comment_data["id"]
            assert comment_data["is_knowledge_eligible"] is True

            # 12. Eve attempts to view comments on group memory -> 403 Forbidden
            resp = await api_client.get(f"/api/v1/memories/{memory_id}/comments", headers=eve["headers"])
            assert resp.status_code == 403

            # 13. Alice views comments -> Sees Bob's comment
            resp = await api_client.get(f"/api/v1/memories/{memory_id}/comments", headers=alice["headers"])
            assert resp.status_code == 200
            assert any(c["id"] == comment_id for c in resp.json())

            # 14. Alice views memory shares
            resp = await api_client.get(f"/api/v1/memories/{memory_id}/shares", headers=alice["headers"])
            assert resp.status_code == 200
            shares = resp.json()
            assert any(str(gs["group_id"]) == group_id for gs in shares["group_shares"])

            # 15. Alice updates Bob's role to MEMBER
            resp = await api_client.patch(
                f"/api/v1/groups/{group_id}/members/{bob['user_id']}",
                json={"role": GroupRole.MEMBER.value},
                headers=alice["headers"],
            )
            assert resp.status_code == 200
            assert resp.json()["role"] == GroupRole.MEMBER.value

            # 16. User search
            resp = await api_client.get("/api/v1/groups/users/search?q=alice", headers=bob["headers"])
            assert resp.status_code == 200
            assert any("alice" in u["username"] for u in resp.json())

            # 17. Bob deletes his own comment
            resp = await api_client.delete(f"/api/v1/memories/comments/{comment_id}", headers=bob["headers"])
            assert resp.status_code == 200

            # 18. Bob leaves the group
            resp = await api_client.post(f"/api/v1/groups/{group_id}/leave", headers=bob["headers"])
            assert resp.status_code == 200

            # 19. Bob now receives 403 when requesting group feed
            resp = await api_client.get(f"/api/v1/memories/feed?group_id={group_id}", headers=bob["headers"])
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.clear()
