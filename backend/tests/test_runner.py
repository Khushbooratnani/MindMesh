import pytest
from fastapi.testclient import TestClient

from app.api.routes.memories import get_ingestion_service
from app.main import app
from app.services.ingestion_service import IngestionService
from app.services.llm_service import LLMService


def test_runner_send_memory_ingestion_simulation(monkeypatch):
    """Verify that the runner logic converts raw text into valid JSON payload and receives complete MemoryV1."""
    app.dependency_overrides[get_ingestion_service] = lambda: IngestionService(
        llm_service=LLMService(model_name="mock-memory-extractor")
    )
    client = TestClient(app)

    raw_text = "Today I worked with my team on the MindMesh database architecture. We tested the Phase 1 ingestion pipeline and verified PostgreSQL persistence."
    
    response = client.post(
        "/api/v1/memories/ingest",
        json={
            "media_type": "text",
            "text": raw_text,
            "group_id": "G_CORE",
            "privacy": "ONLY_ME",
            "allowed_users": [],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "1.0"
    assert data["content"]["clean_text"] == raw_text
    assert data["processing"]["status"] == "completed"

    # Verify headers are present and non-empty
    raw_input_id_header = response.headers.get("X-Raw-Input-Id")
    phase1_output_id_header = response.headers.get("X-Phase1-Output-Id")
    assert raw_input_id_header is not None and raw_input_id_header != "N/A"
    assert phase1_output_id_header is not None and phase1_output_id_header != "N/A"

    import uuid
    raw_uuid = uuid.UUID(raw_input_id_header)
    phase1_uuid = uuid.UUID(phase1_output_id_header)
    assert raw_uuid is not None
    assert phase1_uuid is not None
    app.dependency_overrides.clear()


def test_runner_error_propagation_on_empty_text():
    """Verify that empty or whitespace text properly raises a 400 IngestionError."""
    client = TestClient(app)

    response = client.post(
        "/api/v1/memories/ingest",
        json={
            "media_type": "text",
            "text": "   ",
            "privacy": "ONLY_ME",
            "allowed_users": [],
        },
    )

    assert response.status_code == 400
    error_payload = response.json()
    assert "error" in error_payload
    assert error_payload["error"]["code"] == "EMPTY_TEXT"


def test_dataset_runner_image_sample_includes_context(monkeypatch, tmp_path):
    """Verify that dataset runner sends sample.ground_truth_caption as 'context' in multipart form data."""
    test_img = tmp_path / "test.jpg"
    test_img.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20)

    from app.tools.dataset_runner import DatasetSample, run_dataset_via_api

    sample = DatasetSample(
        sample_id=0,
        modality="image",
        timestamp="2026-01-01",
        text_content=None,
        media_relative_path="test.jpg",
        media_absolute_path=test_img,
        ground_truth_caption="A beautiful sunset at the beach with friends",
        extra_modalities=[],
    )

    captured_requests = []

    class MockResponse:
        status_code = 200
        headers = {"X-Raw-Input-Id": "raw-123", "X-Phase1-Output-Id": "phase1-123"}
        def json(self):
            return {
                "memory_id": "M_test",
                "schema_version": "1.0",
                "content": {"clean_text": "description"},
                "user_context": "A beautiful sunset at the beach with friends",
            }

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url):
            return MockResponse()
        def post(self, url, **kwargs):
            captured_requests.append({
                "url": url,
                "data": kwargs.get("data"),
                "files": kwargs.get("files"),
            })
            return MockResponse()

    monkeypatch.setattr("httpx.Client", MockClient)
    monkeypatch.setattr("app.tools.dataset_runner.parse_dataset_manifest", lambda *a, **k: [sample])

    results = run_dataset_via_api(api_base_url="http://testserver", csv_path="dummy.csv")

    assert len(results) == 1
    assert results[0].status == "success"
    assert len(captured_requests) == 1
    post_req = captured_requests[0]
    assert post_req["url"] == "http://testserver/api/v1/memories/ingest/image"
    assert post_req["data"]["context"] == "A beautiful sunset at the beach with friends"
    assert post_req["data"]["media_type"] == "image"


def test_dataset_runner_cli_modality_filter(monkeypatch, tmp_path):
    """Verify that CLI --modality filter filters samples correctly."""
    from app.tools.dataset_runner import DatasetSample, build_parser, main

    dummy_samples = [
        DatasetSample(0, "image", "2026-01-01", None, "img0.jpg", tmp_path / "img0.jpg", "caption0", []),
        DatasetSample(1, "text", "2026-01-01", "text1", None, None, "text1", []),
        DatasetSample(2, "audio", "2026-01-01", None, "aud2.ogg", tmp_path / "aud2.ogg", "caption2", []),
        DatasetSample(3, "image", "2026-01-01", None, "img3.jpg", tmp_path / "img3.jpg", "caption3", []),
    ]

    (tmp_path / "img0.jpg").write_bytes(b"dummy")
    (tmp_path / "aud2.ogg").write_bytes(b"dummy")
    (tmp_path / "img3.jpg").write_bytes(b"dummy")

    monkeypatch.setattr("app.tools.dataset_runner.parse_dataset_manifest", lambda *a, **k: dummy_samples)

    class MockResponse:
        status_code = 200
        headers = {"X-Raw-Input-Id": "raw", "X-Phase1-Output-Id": "p1"}
        def json(self):
            return {"memory_id": "M_1", "content": {"clean_text": "ok"}}

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url):
            return MockResponse()
        def post(self, url, **kwargs):
            return MockResponse()

    monkeypatch.setattr("httpx.Client", MockClient)

    # 1. Test --modality image selects only image samples
    parser = build_parser()
    args = parser.parse_args(["--modality", "image"])
    assert args.modality == "image"

    image_results = main(["--modality", "image", "--api-url", "http://testserver"])
    assert len(image_results) == 2
    assert all(r.modality == "image" for r in image_results)
    assert [r.sample_id for r in image_results] == [0, 3]

    # 2. Test --modality text selects only text samples
    text_results = main(["--modality", "text", "--api-url", "http://testserver"])
    assert len(text_results) == 1
    assert text_results[0].modality == "text"
    assert text_results[0].sample_id == 1

    # 3. Test --modality audio selects only audio samples
    audio_results = main(["--modality", "audio", "--api-url", "http://testserver"])
    assert len(audio_results) == 1
    assert audio_results[0].modality == "audio"
    assert audio_results[0].sample_id == 2

    # 4. Test omitting --modality selects all samples
    all_results = main(["--api-url", "http://testserver"])
    assert len(all_results) == 4
