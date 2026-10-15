from fastapi.testclient import TestClient

from app.main import app
from app.api.routes.memories import get_ingestion_service
from app.core.enums import MediaType
from app.schemas.canonical_input import ProcessedInput
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService


class FakeImageProcessor:
    def process(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> ProcessedInput:
        return ProcessedInput(
            media_type=MediaType.IMAGE,
            raw_text=None,
            clean_text="The image shows a cafe storefront and coffee shop setting.",
        )


def test_ingest_text_endpoint_returns_memory_v1():
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        llm_service=LLMService(model_name="mock-memory-extractor")
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/memories/ingest",
        json={
            "media_type": "text",
            "text": "Had amazing coffee with Akshat at Cafe Bodega in Goa.",
            "group_id": "G04",
            "privacy": "GROUP",
            "allowed_users": [],
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["schema_version"] == "1.0"
    assert payload["system"]["owner_id"] == "U_DEVELOPMENT"
    assert payload["system"]["media_type"] == "text"
    assert payload["processing"]["status"] == "completed"
    app.dependency_overrides.clear()


def test_ingest_image_endpoint_returns_memory_v1():
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        image_processor=FakeImageProcessor(),
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/memories/ingest/image",
        data={
            "media_type": "image",
            "group_id": "G04",
            "privacy": "GROUP",
            "allowed_users": "[]",
        },
        files={
            "file": (
                "cafe.jpg",
                b"fake-image-bytes",
                "image/jpeg",
            )
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["system"]["media_type"] == "image"
    assert payload["content"]["raw_text"] is None
    assert "cafe storefront" in payload["content"]["clean_text"]
    assert payload["processing"]["image_understanding_required"] is True
    app.dependency_overrides.clear()


def test_ingest_image_endpoint_respects_max_image_size_limit(monkeypatch):
    """Verify that image upload exceeding max_image_size_mb is rejected with FILE_TOO_LARGE."""
    from app.config import settings
    monkeypatch.setattr(settings, "max_image_size_mb", 1)

    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        image_processor=FakeImageProcessor(),
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )
    client = TestClient(app)

    large_bytes = b"X" * (1100 * 1024)
    response = client.post(
        "/api/v1/memories/ingest/image",
        data={"media_type": "image", "privacy": "ONLY_ME", "allowed_users": "[]"},
        files={"file": ("large.jpg", large_bytes, "image/jpeg")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    app.dependency_overrides.clear()


def test_search_memories_endpoint():
    from app.api.routes.memories import get_search_service
    from app.schemas.search_schemas import MemorySearchResponse, MemorySearchResult

    class FakeSearchService:
        async def search(self, session, query, top_k, user_id, content_weight, context_weight):
            return MemorySearchResponse(
                query=query,
                answer="Found 1 memory about Cafe Bodega.",
                results=[
                    MemorySearchResult(
                        memory_id="mem_123",
                        score=0.92,
                        similarity_score=0.92,
                        content_score=0.95,
                        context_score=0.89,
                        summary="Had coffee with Akshat.",
                        memory={"id": "mem_123", "title": "Coffee at Cafe Bodega"},
                    )
                ],
                total_results=1,
            )

    app.dependency_overrides[get_search_service] = lambda: FakeSearchService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/memories/search",
        json={"query": "Where did I have coffee?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Where did I have coffee?"
    assert len(data["results"]) == 1
    assert data["results"][0]["memory"]["title"] == "Coffee at Cafe Bodega"
    app.dependency_overrides.clear()


def test_get_feed_endpoint():
    from app.services.audio_processor import AudioProcessor
    from tests.test_audio_ingestion import get_mock_whisper_service

    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        image_processor=FakeImageProcessor(),
        audio_processor=AudioProcessor(whisper_service=get_mock_whisper_service("Discussing project architecture with team in Goa.")),
        llm_service=LLMService(model_name="mock-memory-extractor"),
    )
    client = TestClient(app)

    # Ingest text memory
    client.post(
        "/api/v1/memories/ingest",
        json={
            "media_type": "text",
            "text": "Brainstormed Q3 roadmap with Sarah in London.",
            "privacy": "ONLY_ME",
        },
    )

    # Ingest image memory
    client.post(
        "/api/v1/memories/ingest/image",
        data={"media_type": "image", "privacy": "ONLY_ME", "allowed_users": "[]", "context": "Cafe photo"},
        files={"file": ("storefront.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    # Ingest audio memory (with valid RIFF WAVE header)
    riff_audio = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00" + b"\x00" * 64
    client.post(
        "/api/v1/memories/ingest/audio",
        data={"media_type": "audio", "privacy": "ONLY_ME", "allowed_users": "[]", "context": "Team sync"},
        files={"file": ("sync.wav", riff_audio, "audio/wav")},
    )

    response = client.get("/api/v1/memories/feed?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "total_count" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) >= 3

    # Find audio memory in feed
    audio_items = [item for item in data["items"] if item["media_type"] == "audio"]
    assert len(audio_items) > 0
    audio_item = audio_items[0]

    # Verify audio memory requirements
    assert "memory_id" in audio_item
    assert audio_item["memory_id"].startswith("M_")
    assert audio_item["media"] is not None
    assert "storage_key" in audio_item["media"]
    assert len(audio_item["media"]["storage_key"]) > 0
    assert audio_item["media_url"] is not None
    assert audio_item["media"]["url"] == f"/api/v1/media/{audio_item['media']['storage_key']}"
    assert audio_item["content"]["raw_text"] == "Discussing project architecture with team in Goa."
    assert audio_item["content"]["summary"] is not None
    assert "topics" in audio_item["semantics"]
    assert audio_item["processing"]["source_modality"] == "audio"

    # Find image memory in feed
    image_items = [item for item in data["items"] if item["media_type"] == "image"]
    assert len(image_items) > 0
    image_item = image_items[0]

    # Verify image memory requirements
    assert "memory_id" in image_item
    assert image_item["media"] is not None
    assert "storage_key" in image_item["media"]
    assert image_item["media_url"] is not None
    assert image_item["media"]["url"] == f"/api/v1/media/{image_item['media']['storage_key']}"
    assert image_item["processing"]["source_modality"] == "image"

    app.dependency_overrides.clear()


def test_search_relevance_gate_rejects_irrelevant():
    from app.api.routes.memories import get_search_service
    from app.schemas.search_schemas import MemorySearchResponse

    class FakeSearchServiceGated:
        async def search(self, session, query, top_k, user_id, content_weight, context_weight):
            return MemorySearchResponse(
                query=query,
                answer=f'I couldn\'t find any stored memory related to "{query}".',
                grounded=False,
                results=[],
                total_results=0,
            )

    app.dependency_overrides[get_search_service] = lambda: FakeSearchServiceGated()
    client = TestClient(app)

    response = client.post(
        "/api/v1/memories/search",
        json={"query": "Best momos in Premnagar"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "Best momos in Premnagar"
    assert data["grounded"] is False
    assert len(data["results"]) == 0
    assert "couldn't find any stored memory" in data["answer"]
    app.dependency_overrides.clear()


