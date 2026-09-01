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
