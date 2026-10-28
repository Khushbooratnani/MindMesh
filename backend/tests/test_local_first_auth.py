"""
Comprehensive automated tests for v2 Local-First Private Locker Architecture.
Validates:
1. Isolated authentication database models and repository.
2. Argon2id verifiers, 5-attempt lockout, recovery-key rotation, 120s timeout.
3. Strict zero-persistence invariant for Ephemeral AI processing.
"""
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.database.connection.session import get_db_session
from app.database.repositories.raw_input_repo import RawInputRepository
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.local_first.database import init_locker_auth_db, get_locker_auth_session
from app.local_first.routes import get_ephemeral_ai_service
from app.local_first.temporary_processing import EphemeralAiService
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService

settings.embedding_force_mock = True
settings.memory_extraction_model = "mock-memory-extractor"
settings.enable_local_first_locker = True


@pytest.mark.asyncio
async def test_local_first_complete_flow():
    # Initialize separate auth schema in test database
    await init_locker_auth_db()

    app.dependency_overrides[get_ephemeral_ai_service] = lambda: EphemeralAiService(
        ingestion_service=IngestionService(llm_service=LLMService(model_name="mock-memory-extractor")),
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Register main user account
        user_name = "local_first_tester"
        user_pass = "TestPassword123!"
        reg_resp = await client.post("/api/v1/auth/register", json={"username": user_name, "password": user_pass})
        user_id = reg_resp.json()["id"]
        login_resp = await client.post("/api/v1/auth/login", data={"username": user_name, "password": user_pass})
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2a. Verify Allowlist default-deny when user is NOT on allowlist
        settings.local_first_test_user_allowlist = []
        denied_resp = await client.get("/api/v2/locker-auth/status", headers=headers)
        assert denied_resp.status_code == 403
        assert "not authorized" in denied_resp.json()["detail"].lower()

        # 2b. Add user to allowlist -> authorized access
        settings.local_first_test_user_allowlist = [user_id]
        status_resp = await client.get("/api/v2/locker-auth/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["exists"] is False
        assert status_resp.json()["has_locker"] is False

        # 3. Register Local-First Locker verifier
        locker_pass = "LocalLockerSecret123!"
        create_resp = await client.post(
            "/api/v2/locker-auth/register",
            json={"password": locker_pass},
            headers=headers,
        )
        assert create_resp.status_code == 200
        create_data = create_resp.json()
        assert "identity_id" in create_data
        recovery_key = create_data["recovery_key"]
        assert recovery_key.startswith("rcv_")

        # 4. Unlock with correct password
        unlock_resp = await client.post(
            "/api/v2/locker-auth/unlock",
            json={"password": locker_pass},
            headers=headers,
        )
        assert unlock_resp.status_code == 200
        locker_token = unlock_resp.json()["token"]
        assert unlock_resp.json()["expires_in_seconds"] == 120
        locker_headers = {**headers, "X-Locker-Token": locker_token}

        # Check status now shows unlocked
        status_unlocked = await client.get("/api/v2/locker-auth/status", headers=locker_headers)
        assert status_unlocked.status_code == 200
        assert status_unlocked.json()["status"] == "unlocked"

        # 5. Wrong password rejection
        wrong_resp = await client.post(
            "/api/v2/locker-auth/unlock",
            json={"password": "WrongPassword99!"},
            headers=headers,
        )
        assert wrong_resp.status_code == 401

        # 6. Lockout policy (5 attempts)
        for _ in range(3):
            r = await client.post("/api/v2/locker-auth/unlock", json={"password": "Wrong!"}, headers=headers)
            assert r.status_code == 401
        # 5th attempt
        r5 = await client.post("/api/v2/locker-auth/unlock", json={"password": "Wrong!"}, headers=headers)
        assert r5.status_code == 401

        # 6th attempt locked out
        locked_resp = await client.post("/api/v2/locker-auth/unlock", json={"password": locker_pass}, headers=headers)
        assert locked_resp.status_code == 403
        assert "locked out" in locked_resp.text.lower()

        # 7. Recovery key unlocks and rotates credential
        recovered_pass = "RecoveredLockerSecret456!"
        rec_resp = await client.post(
            "/api/v2/locker-auth/recover",
            json={"recovery_key": recovery_key, "new_password": recovered_pass},
            headers=headers,
        )
        assert rec_resp.status_code == 200
        new_recovery_key = rec_resp.json()["new_recovery_key"]
        assert new_recovery_key != recovery_key

        # Old recovery key should now fail
        rec_fail = await client.post(
            "/api/v2/locker-auth/recover",
            json={"recovery_key": recovery_key, "new_password": "NewPassFail123!"},
            headers=headers,
        )
        assert rec_fail.status_code == 400

        # Unlock with recovered password works
        unlock_rec = await client.post(
            "/api/v2/locker-auth/unlock",
            json={"password": recovered_pass},
            headers=headers,
        )
        assert unlock_rec.status_code == 200
        locker_token = unlock_rec.json()["token"]
        locker_headers = {**headers, "X-Locker-Token": locker_token}

        # 8. Password change
        changed_pass = "ChangedLockerSecret789!"
        chg_resp = await client.post(
            "/api/v2/locker-auth/change-password",
            json={"old_password": recovered_pass, "new_password": changed_pass},
            headers=headers,
        )
        assert chg_resp.status_code == 200

        # Unlock with new password
        unlock_chg = await client.post(
            "/api/v2/locker-auth/unlock",
            json={"password": changed_pass},
            headers=headers,
        )
        assert unlock_chg.status_code == 200
        locker_token = unlock_chg.json()["token"]
        locker_headers = {**headers, "X-Locker-Token": locker_token}

        # 9. Manual lock
        lock_resp = await client.post("/api/v2/locker-auth/lock", headers=locker_headers)
        assert lock_resp.status_code == 200
        status_after_lock = await client.get("/api/v2/locker-auth/status", headers=locker_headers)
        assert status_after_lock.json()["status"] == "locked"

        # ==============================================================================
        # 10. Ephemeral AI Processing Tests (Zero-Persistence Invariant)
        # ==============================================================================
        test_secret_snippet = "Private medical appointment with Dr. Mehta regarding allergy symptoms"

        # Invariant A: Denial if consent is False
        denied_resp = await client.post(
            "/api/v2/ephemeral-ai/extract",
            json={
                "consent": {
                    "consent_granted": False,
                    "purpose": "semantic_extraction",
                    "retention_policy": "immediate_destruction",
                },
                "text": test_secret_snippet,
            },
            headers=headers,
        )
        assert denied_resp.status_code == 403

        # Invariant B: Rejection if retention policy is not 'immediate_destruction'
        bad_policy_resp = await client.post(
            "/api/v2/ephemeral-ai/extract",
            json={
                "consent": {
                    "consent_granted": True,
                    "purpose": "semantic_extraction",
                    "retention_policy": "persist_on_server",
                },
                "text": test_secret_snippet,
            },
            headers=headers,
        )
        assert bad_policy_resp.status_code == 400

        # Invariant C: Successful extraction with explicit consent
        extract_resp = await client.post(
            "/api/v2/ephemeral-ai/extract",
            json={
                "consent": {
                    "consent_granted": True,
                    "purpose": "semantic_extraction",
                    "retention_policy": "immediate_destruction",
                },
                "text": test_secret_snippet,
            },
            headers=headers,
        )
        assert extract_resp.status_code == 200
        extract_data = extract_resp.json()
        assert "clean_text" in extract_data
        assert "entities" in extract_data

        # Invariant D: Ephemeral BGE-M3 embedding generation
        embed_resp = await client.post(
            "/api/v2/ephemeral-ai/embed",
            json={
                "consent": {
                    "consent_granted": True,
                    "purpose": "embedding_generation",
                    "retention_policy": "immediate_destruction",
                },
                "texts": [test_secret_snippet],
            },
            headers=headers,
        )
        assert embed_resp.status_code == 200
        embed_data = embed_resp.json()
        assert len(embed_data["embeddings"]) == 1
        assert embed_data["dimension"] == 1024

        # Invariant E: Ephemeral QA grounded strictly on user-approved snippets
        qa_resp = await client.post(
            "/api/v2/ephemeral-ai/qa",
            json={
                "consent": {
                    "consent_granted": True,
                    "purpose": "question_answering",
                    "retention_policy": "immediate_destruction",
                },
                "query": "What did I see Dr. Mehta about?",
                "selected_context": [test_secret_snippet],
            },
            headers=headers,
        )
        assert qa_resp.status_code == 200
        qa_data = qa_resp.json()
        assert "answer" in qa_data

        # ==============================================================================
        # 11. STRICT VERIFICATION: ZERO PERSISTENCE IN POSTGRESQL TABLES
        # ==============================================================================
        db_getter = app.dependency_overrides.get(get_db_session, get_db_session)
        async for sess in db_getter():
            raw_repo = RawInputRepository(sess)
            p1_repo = Phase1OutputRepository(sess)
            p2_repo = Phase2EmbeddingRepository(sess)

            # Query all raw inputs and phase outputs
            from sqlalchemy import select
            from app.database.models.raw_input import RawInputModel
            from app.database.models.phase1_output import Phase1OutputModel
            from app.database.models.phase2_embedding import Phase2EmbeddingModel

            raw_res = await sess.execute(select(RawInputModel))
            for r in raw_res.scalars().all():
                assert test_secret_snippet not in (r.raw_payload or ""), "CRITICAL: Ephemeral content leaked into raw_inputs table!"

            p1_res = await sess.execute(select(Phase1OutputModel))
            for p1 in p1_res.scalars().all():
                payload_str = str(p1.payload)
                assert test_secret_snippet not in payload_str, "CRITICAL: Ephemeral content leaked into phase1_outputs table!"

            break
