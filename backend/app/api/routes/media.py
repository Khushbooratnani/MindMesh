import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.storage.file_storage import FileStorage

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.get("/{storage_key:path}")
async def get_media_file(storage_key: str):
    """Retrieve original binary image or audio asset using durable FileStorage."""
    storage = FileStorage()
    try:
        file_path = storage.get_file_path(storage_key)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Media asset not found: '{storage_key}'",
        ) from exc

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Media asset not found: '{storage_key}'",
        )

    guessed_mime, _ = mimetypes.guess_type(str(file_path))
    if not guessed_mime:
        ext = file_path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            guessed_mime = "image/jpeg"
        elif ext == ".png":
            guessed_mime = "image/png"
        elif ext in (".m4a", ".mp4"):
            guessed_mime = "audio/mp4"
        elif ext == ".mp3":
            guessed_mime = "audio/mpeg"
        elif ext == ".wav":
            guessed_mime = "audio/wav"
        elif ext in (".ogg", ".oga"):
            guessed_mime = "audio/ogg"
        else:
            guessed_mime = "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=guessed_mime,
        filename=file_path.name,
    )
