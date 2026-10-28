import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from app.main import app
from app.config import settings

settings.embedding_force_mock = True
settings.memory_extraction_model = "mock-memory-extractor"


@pytest.mark.asyncio
async def test_private_locker_flow():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as async_client:
        with patch("app.services.embedding_service.EmbeddingService.generate_embedding") as mock_gen_embed, \
             patch("app.services.embedding_service.EmbeddingService.generate_content_and_context_vectors") as mock_gen_dual:

            # Mock embeddings
            mock_gen_embed.return_value = [0.1] * 1024
            mock_gen_dual.return_value = ([0.1] * 1024, [0.1] * 1024)

            # 1. Register User A
            resp = await async_client.post("/api/v1/auth/register", json={
                "username": "user_a",
                "password": "password123"
            })
            assert resp.status_code in (200, 201), resp.text

            # Login User A
            resp = await async_client.post("/api/v1/auth/login", data={
                "username": "user_a",
                "password": "password123"
            })
            assert resp.status_code == 200, resp.text
            token_a = resp.json()["access_token"]
            headers_a = {"Authorization": f"Bearer {token_a}"}

            # Register User B
            resp = await async_client.post("/api/v1/auth/register", json={
                "username": "user_b",
                "password": "password123"
            })
            assert resp.status_code in (200, 201), resp.text

            # Login User B
            resp = await async_client.post("/api/v1/auth/login", data={
                "username": "user_b",
                "password": "password123"
            })
            assert resp.status_code == 200, resp.text
            token_b = resp.json()["access_token"]
            headers_b = {"Authorization": f"Bearer {token_b}"}

            # 2. Create Locker for User A
            resp = await async_client.post("/api/v1/locker/create", json={
                "password": "lockerpassword"
            }, headers=headers_a)
            assert resp.status_code in (200, 201), resp.text

            # 3. Unlock Locker for User A
            resp = await async_client.post("/api/v1/locker/unlock", json={
                "password": "lockerpassword"
            }, headers=headers_a)
            assert resp.status_code == 200, resp.text
            locker_token_a = resp.json()["locker_token"]

            headers_a_unlocked = headers_a.copy()
            headers_a_unlocked["X-Locker-Token"] = locker_token_a

            # 4. Ingest normal memory for A
            resp = await async_client.post("/api/v1/memories/ingest", json={
                "text": "User A normal public memory about going to Cafe Goa",
                "privacy": "ONLY_ME"
            }, headers=headers_a)
            assert resp.status_code == 200, resp.text

            # 5. Ingest private locker memory for A
            resp = await async_client.post("/api/v1/memories/ingest", json={
                "text": "User A secret private memory about a hidden treasure in Cafe Goa",
                "privacy": "PRIVATE_LOCKER"
            }, headers=headers_a_unlocked)
            assert resp.status_code == 200, resp.text
            private_memory_id = resp.json()["memory_id"]

            # Ingest normal memory for B
            resp = await async_client.post("/api/v1/memories/ingest", json={
                "text": "User B normal public memory",
                "privacy": "ONLY_ME"
            }, headers=headers_b)
            assert resp.status_code == 200, resp.text

            # 6. Test User A unlocked -> A's Private Locker memory searchable
            resp = await async_client.post("/api/v1/memories/search", json={
                "query": "hidden treasure in Cafe Goa",
                "top_k": 5
            }, headers=headers_a_unlocked)
            assert resp.status_code == 200, resp.text
            assert "hidden treasure" in resp.text

            # 7. Test User A locked -> A's Private Locker memory inaccessible
            await async_client.post("/api/v1/locker/lock", headers=headers_a_unlocked)

            resp = await async_client.post("/api/v1/memories/search", json={
                "query": "hidden treasure in Cafe Goa",
                "top_k": 5
            }, headers=headers_a_unlocked)  # Token is now invalid
            assert resp.status_code == 200
            assert private_memory_id not in [r["memory_id"] for r in resp.json()["results"]]

            # 8. Test User B cannot retrieve it through vector search
            with patch("app.services.llm_service.LLMService.answer_from_memories") as mock_llm:
                mock_llm.return_value = "Mocked answer"
                resp = await async_client.post("/api/v1/memories/search", json={
                    "query": "hidden treasure in Cafe Goa",
                    "top_k": 5
                }, headers=headers_b)
                assert resp.status_code == 200
                results = resp.json()["results"]
                for r in results:
                    assert r["memory_id"] != private_memory_id

                # 9. Verify actual LLM context isolation
                if mock_llm.called:
                    called_memories = mock_llm.call_args.kwargs.get("memories", [])
                    for mem in called_memories:
                        assert mem["system"]["owner_id"] != "user_a" or mem["system"]["privacy"] != "PRIVATE_LOCKER"

            # 10. User A's Private Locker memories never appear in the locked /feed
            resp = await async_client.get("/api/v1/memories/feed", headers=headers_a)
            assert resp.status_code == 200
            feed_items = resp.json()["items"]
            for item in feed_items:
                assert item["privacy"] != "PRIVATE_LOCKER"
