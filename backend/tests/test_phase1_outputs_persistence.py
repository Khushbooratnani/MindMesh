import uuid
import pytest
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.raw_input_repo import RawInputRepository


@pytest.mark.asyncio
async def test_phase1_output_full_json_preservation_and_fk(db_session):
    """Verify that complete MemoryV1 JSON is stored unflattened and correctly linked to raw_input."""
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        phase1_repo = Phase1OutputRepository(session)

        # 1. Create parent raw input
        raw_record = await raw_repo.create(
            media_type="text",
            raw_payload="Had coffee with Akshat at Cafe Bodega.",
            status="processing",
        )
        await session.commit()
        raw_id = raw_record.id

    full_memory_payload = {
        "memory_id": f"M_{uuid.uuid4().hex}",
        "schema_version": "1.0",
        "system": {
            "owner_id": "U17",
            "group_id": "G04",
            "media_type": "text",
            "created_at": "2026-09-08T10:30:00Z",
            "privacy": "ONLY_ME",
            "allowed_users": [],
        },
        "content": {
            "raw_text": "Had coffee with Akshat at Cafe Bodega.",
            "clean_text": "Had coffee with Akshat at Cafe Bodega.",
            "description": "A coffee meeting with Akshat.",
            "summary": "Coffee with Akshat at Cafe Bodega.",
        },
        "entities": {
            "people": ["Akshat"],
            "places": ["Cafe Bodega"],
            "locations": [],
            "events": [],
            "organizations": [],
        },
        "semantics": {
            "topics": ["coffee"],
            "activities": ["drinking coffee"],
            "sentiment": "positive",
            "mood": ["happy"],
        },
        "temporal": {
            "mentioned_dates": [],
            "inferred_time": None,
            "time_of_day": "morning",
        },
        "additional_attributes": [
            {
                "key": "food_or_drink",
                "value": "coffee",
                "confidence": 0.8,
                "source": "llm",
            }
        ],
        "processing": {
            "status": "completed",
            "source_modality": "text",
            "transcription_required": False,
            "image_understanding_required": False,
            "llm_provider": "openai-compatible",
            "llm_model": "mock-memory-extractor",
            "errors": [],
        },
    }

    # 2. Persist Phase 1 output linked to raw_id
    async with db_session() as session:
        phase1_repo = Phase1OutputRepository(session)
        out_record = await phase1_repo.create(
            raw_input_id=raw_id,
            memory_id=full_memory_payload["memory_id"],
            schema_version="1.0",
            payload=full_memory_payload,
            processing_status="completed",
            extractor_model="mock-memory-extractor",
        )
        await session.commit()
        output_id = out_record.id
        memory_id = out_record.memory_id

    # 3. Verify querying and unflattened data integrity
    async with db_session() as session:
        phase1_repo = Phase1OutputRepository(session)
        
        # Query by primary key
        fetched_by_id = await phase1_repo.get_by_id(output_id)
        assert fetched_by_id is not None
        assert fetched_by_id.raw_input_id == raw_id
        assert fetched_by_id.memory_id == memory_id
        assert fetched_by_id.payload == full_memory_payload
        assert fetched_by_id.payload["entities"]["people"] == ["Akshat"]
        assert fetched_by_id.payload["additional_attributes"][0]["key"] == "food_or_drink"

        # Query by memory_id
        fetched_by_memory = await phase1_repo.get_by_memory_id(memory_id)
        assert fetched_by_memory is not None
        assert fetched_by_memory.id == output_id

        # Query by raw_input_id
        outputs_for_raw = await phase1_repo.get_by_raw_input_id(raw_id)
        assert len(outputs_for_raw) == 1
        assert outputs_for_raw[0].id == output_id
