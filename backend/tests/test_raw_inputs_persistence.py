import uuid
import pytest
from app.database.repositories.raw_input_repo import RawInputRepository


@pytest.mark.asyncio
async def test_raw_input_exact_text_preservation(db_session):
    """Verify that user text is preserved verbatim without alteration."""
    async with db_session() as session:
        repo = RawInputRepository(session)
        exact_text = "  Yesterday I met Rohan & Akshat at Cafe Bodega! \n\t Cost was ₹1200.   "
        
        raw_record = await repo.create(
            media_type="text",
            raw_payload=exact_text,
            structured_payload={"text": exact_text, "privacy": "ONLY_ME"},
            client_id="U_DEVELOPMENT",
            group_id="G_TEAM_1",
            status="received",
        )
        await session.commit()
        record_id = raw_record.id

    async with db_session() as session:
        repo = RawInputRepository(session)
        fetched = await repo.get_by_id(record_id)
        
        assert fetched is not None
        assert fetched.raw_payload == exact_text
        assert fetched.media_type == "text"
        assert fetched.client_id == "U_DEVELOPMENT"
        assert fetched.group_id == "G_TEAM_1"
        assert fetched.status == "received"
        assert fetched.received_at is not None
        assert fetched.updated_at is not None
        assert fetched.structured_payload["privacy"] == "ONLY_ME"


@pytest.mark.asyncio
async def test_raw_input_status_lifecycle(db_session):
    """Verify status transitions from received to processing to completed or failed."""
    async with db_session() as session:
        repo = RawInputRepository(session)
        raw_record = await repo.create(
            media_type="text",
            raw_payload="Testing status transitions",
            status="received",
        )
        await session.commit()
        record_id = raw_record.id

    # Transition to processing
    async with db_session() as session:
        repo = RawInputRepository(session)
        updated = await repo.update_status(record_id, status="processing")
        await session.commit()
        assert updated.status == "processing"

    # Transition to completed
    async with db_session() as session:
        repo = RawInputRepository(session)
        completed = await repo.mark_completed(record_id)
        await session.commit()
        assert completed.status == "completed"
        assert completed.error_message is None

    # Transition to failed with error message
    async with db_session() as session:
        repo = RawInputRepository(session)
        failed = await repo.mark_failed(record_id, error_message="Simulated downstream error")
        await session.commit()
        assert failed.status == "failed"
        assert "Simulated downstream error" in failed.error_message
