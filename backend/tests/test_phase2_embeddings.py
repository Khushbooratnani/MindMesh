import uuid
import pytest
from app.database.repositories.phase1_output_repo import Phase1OutputRepository
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.database.repositories.raw_input_repo import RawInputRepository
from app.services.embedding_service import EmbeddingService
from app.services.memory_search_service import MemorySearchService
from app.services.phase2_service import Phase2Service


SAMPLE_MEMORY_V1 = {
    "memory_id": "M_test_1024",
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
        "raw_text": "Had coffee with Akshat at Cafe Bodega in Panjim.",
        "clean_text": "Had coffee with Akshat at Cafe Bodega in Panjim.",
        "description": "A coffee meeting with Akshat at Cafe Bodega.",
        "summary": "Coffee with Akshat at Cafe Bodega in Panjim.",
    },
    "entities": {
        "people": ["Akshat"],
        "places": ["Cafe Bodega"],
        "locations": ["Panjim", "Goa"],
        "events": ["Coffee meetup"],
        "organizations": [],
    },
    "semantics": {
        "topics": ["coffee", "catchup"],
        "activities": ["drinking coffee", "talking"],
        "sentiment": "positive",
        "mood": ["relaxed", "happy"],
    },
    "temporal": {
        "mentioned_dates": ["2026-09-08"],
        "inferred_time": "morning",
        "time_of_day": "morning",
    },
    "additional_attributes": [
        {
            "key": "beverage",
            "value": "cappuccino",
            "confidence": 0.9,
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


def test_dual_text_representations():
    """Verify that Content and Context text builders extract the correct fields."""
    embedding_service = EmbeddingService(force_mock=True)

    content_text = embedding_service.build_content_text(SAMPLE_MEMORY_V1)
    context_text = embedding_service.build_context_text(SAMPLE_MEMORY_V1)

    assert "Coffee with Akshat at Cafe Bodega in Panjim." in content_text
    assert "Had coffee with Akshat at Cafe Bodega in Panjim." in content_text

    assert "People: Akshat" in context_text
    assert "Places: Cafe Bodega" in context_text
    assert "Events: Coffee meetup" in context_text
    assert "Topics: coffee, catchup" in context_text
    assert "Activities: drinking coffee, talking" in context_text
    assert "Sentiment: positive" in context_text
    assert "Mood: relaxed, happy" in context_text
    assert "Time of Day: morning" in context_text


def test_embedding_vector_dimensions():
    """Verify that generated embeddings are exactly 1024-dimensional vectors."""
    embedding_service = EmbeddingService(force_mock=True)
    vector = embedding_service.generate_embedding("Coffee with Akshat")

    assert len(vector) == 1024
    assert all(isinstance(val, float) for val in vector)


@pytest.mark.asyncio
async def test_milestone1_phase2_embedding_generation_and_storage(db_session):
    """
    Test Milestone 1 Flow:
    1. Create raw_input record
    2. Create phase1_outputs record with canonical MemoryV1
    3. Run Phase2Service on the phase1_output record
    4. Verify phase2_embeddings record created with 1024-dim vectors
    5. Verify FK links and no data duplication of MemoryV1
    """
    mem_payload = dict(SAMPLE_MEMORY_V1)
    mem_id = f"M_{uuid.uuid4().hex}"
    mem_payload["memory_id"] = mem_id

    # 1. Insert Phase 1 records
    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        raw_record = await raw_repo.create(
            media_type="text",
            raw_payload=mem_payload["content"]["raw_text"],
            status="processing",
        )
        await session.commit()
        raw_id = raw_record.id

        phase1_repo = Phase1OutputRepository(session)
        p1_record = await phase1_repo.create(
            raw_input_id=raw_id,
            memory_id=mem_id,
            schema_version="1.0",
            payload=mem_payload,
            processing_status="completed",
            extractor_model="mock-memory-extractor",
        )
        await session.commit()
        phase1_output_id = p1_record.id

    # 2. Process with Phase2Service
    embedding_service = EmbeddingService(force_mock=True)
    phase2_service = Phase2Service(embedding_service=embedding_service)

    async with db_session() as session:
        result = await phase2_service.process_phase1_output_id(
            phase1_output_id=phase1_output_id,
            session=session,
        )
        await session.commit()

        assert result.phase1_output_id == phase1_output_id
        assert result.memory_id == mem_id
        assert result.embeddings.content.dimension == 1024
        assert result.embeddings.context.dimension == 1024
        assert result.embeddings.model == embedding_service.model_name

    # 3. Verify PostgreSQL / Database persistence via Phase2EmbeddingRepository
    async with db_session() as session:
        p2_repo = Phase2EmbeddingRepository(session)
        stored_emb = await p2_repo.get_by_phase1_output_id(phase1_output_id)

        assert stored_emb is not None
        assert stored_emb.phase1_output_id == phase1_output_id
        assert stored_emb.memory_id == mem_id
        assert len(stored_emb.content_vector) == 1024
        assert len(stored_emb.context_vector) == 1024
        assert stored_emb.embedding_model == embedding_service.model_name

        # Ensure Phase 1 record payload remains intact and unmodified
        phase1_repo = Phase1OutputRepository(session)
        p1_check = await phase1_repo.get_by_id(phase1_output_id)
        assert p1_check is not None
        assert p1_check.payload == mem_payload


@pytest.mark.asyncio
async def test_semantic_search_service_retrieval(db_session):
    """Verify semantic memory search retrieval over embedded records."""
    mem_payload = dict(SAMPLE_MEMORY_V1)
    mem_id = f"M_{uuid.uuid4().hex}"
    mem_payload["memory_id"] = mem_id

    async with db_session() as session:
        raw_repo = RawInputRepository(session)
        raw_record = await raw_repo.create(
            media_type="text",
            raw_payload="Had cappuccino with Akshat at Cafe Bodega.",
            status="processing",
        )
        await session.commit()

        phase1_repo = Phase1OutputRepository(session)
        p1_record = await phase1_repo.create(
            raw_input_id=raw_record.id,
            memory_id=mem_id,
            schema_version="1.0",
            payload=mem_payload,
            processing_status="completed",
            extractor_model="mock-memory-extractor",
        )
        await session.commit()
        phase1_output_id = p1_record.id

    embedding_service = EmbeddingService(force_mock=True)
    phase2_service = Phase2Service(embedding_service=embedding_service)

    async with db_session() as session:
        await phase2_service.process_phase1_output_id(
            phase1_output_id=phase1_output_id,
            session=session,
        )
        await session.commit()

    search_service = MemorySearchService(embedding_service=embedding_service)

    async with db_session() as session:
        response = await search_service.search(
            session=session,
            query="Where did I have coffee with Akshat?",
            top_k=3,
            user_id="U17",
        )

        assert response is not None
        assert response.total_results >= 1
        assert any(r.memory_id == mem_id for r in response.results)
        assert -1.0 <= response.results[0].similarity_score <= 1.0



