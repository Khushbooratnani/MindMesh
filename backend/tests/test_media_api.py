import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.storage.file_storage import FileStorage

@pytest.mark.asyncio
async def test_get_media_endpoint(tmp_path, monkeypatch):
    storage = FileStorage(base_dir=tmp_path)
    ref = storage.save_file(b"\xFF\xD8\xFF\xE0\x00\x10JFIFtest", "sample.jpg", "image", "image/jpeg")

    # Patch FileStorage inside media route
    import app.api.routes.media as media_mod
    monkeypatch.setattr(media_mod, "FileStorage", lambda: storage)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Success test
        resp = await client.get(f"/api/v1/media/{ref.storage_key}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.content == b"\xFF\xD8\xFF\xE0\x00\x10JFIFtest"

        # 2. 404 test for non-existent key
        resp_404 = await client.get("/api/v1/media/nonexistent_key_12345")
        assert resp_404.status_code == 404

        # 3. Path traversal protection test
        resp_traversal = await client.get("/api/v1/media/../../etc/passwd")
        assert resp_traversal.status_code in (404, 400)
