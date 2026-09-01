from fastapi.testclient import TestClient

from app.main import app


def test_ingest_text_endpoint_returns_memory_v1():
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
