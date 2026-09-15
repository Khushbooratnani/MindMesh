"""Durable Local Filesystem Media Storage Layer.

Provides immutable UUID-based media file storage, SHA256 integrity checks,
path traversal protection, and retrieval for multimodal raw assets.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import mimetypes
import os
from pathlib import Path
import re
from typing import Any
import uuid

from app.config import settings
from app.core.enums import MediaType


@dataclass(frozen=True)
class StorageReference:
    """Immutable metadata returned when a file is durably persisted."""
    storage_key: str
    relative_path: str
    original_filename: str
    media_type: str
    content_type: str | None
    size_bytes: int
    sha256: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sanitize_filename(filename: str) -> str:
    """Sanitize user-provided filename to prevent path traversal and unsafe characters."""
    # Strip directory components
    clean_name = os.path.basename(filename).strip()
    # Remove null bytes, control characters, and replace path separators
    clean_name = re.sub(r"[\x00-\x1f\\/]", "", clean_name)
    # Remove leading dots to avoid hidden files or '..'
    clean_name = clean_name.lstrip(".")
    return clean_name or "unnamed_file"


class FileStorage:
    """Durable file storage provider for storing and retrieving raw media assets."""

    def __init__(self, base_dir: str | Path | None = None):
        target_dir = base_dir or settings.media_storage_dir
        self.base_dir = Path(target_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(
        self,
        file_bytes: bytes,
        filename: str,
        media_type: str | MediaType = "files",
        content_type: str | None = None,
    ) -> StorageReference:
        """Persists media bytes to a modality-specific directory using a unique UUID key."""
        if not isinstance(file_bytes, (bytes, bytearray)):
            raise TypeError("file_bytes must be bytes or bytearray.")

        media_type_str = media_type.value if isinstance(media_type, MediaType) else str(media_type).lower()
        if media_type_str in ("image", "images"):
            folder_name = "images"
        elif media_type_str in ("audio", "audios"):
            folder_name = "audio"
        else:
            folder_name = "files"

        safe_orig_name = _sanitize_filename(filename)
        ext = Path(safe_orig_name).suffix.lower()

        # Generate unique storage key and immutable file name
        storage_key = uuid.uuid4().hex
        stored_filename = f"{storage_key}{ext}"

        # Target directory structure: base_dir / images / {storage_key}.ext
        dest_dir = self.base_dir / folder_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = (dest_dir / stored_filename).resolve()

        # Strict path traversal check
        self._ensure_safe_path(dest_path)

        # Calculate SHA256 checksum and size
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        size_bytes = len(file_bytes)

        # Write to disk
        with open(dest_path, "wb") as f:
            bytes_written = f.write(file_bytes)

        # Integrity verification
        if bytes_written != size_bytes:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise IOError(f"Write verification failed: wrote {bytes_written} bytes, expected {size_bytes}")

        guessed_mime = content_type or mimetypes.guess_type(safe_orig_name)[0]
        relative_path = f"{folder_name}/{stored_filename}"

        return StorageReference(
            storage_key=storage_key,
            relative_path=relative_path,
            original_filename=safe_orig_name,
            media_type=media_type_str,
            content_type=guessed_mime,
            size_bytes=size_bytes,
            sha256=sha256_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_file_path(self, storage_key_or_path: str) -> Path:
        """Resolves storage_key or relative_path to an absolute Path with traversal validation."""
        clean_target = storage_key_or_path.replace("\\", "/").strip("/")

        # Check if direct relative path exists
        candidate_path = (self.base_dir / clean_target).resolve()
        self._ensure_safe_path(candidate_path)

        if candidate_path.is_file():
            return candidate_path

        # Check in subdirectories by storage_key prefix
        for subfolder in ("images", "audio", "files"):
            sub_dir = self.base_dir / subfolder
            if sub_dir.is_dir():
                for item in sub_dir.iterdir():
                    if item.is_file() and (item.stem == clean_target or item.name == clean_target):
                        resolved = item.resolve()
                        self._ensure_safe_path(resolved)
                        return resolved

        raise FileNotFoundError(f"Stored media asset not found: '{storage_key_or_path}'")

    def get_file(self, storage_key_or_path: str) -> bytes:
        """Reads and returns the raw file bytes for a stored asset."""
        path = self.get_file_path(storage_key_or_path)
        return path.read_bytes()

    def exists(self, storage_key_or_path: str) -> bool:
        """Check if stored asset exists."""
        try:
            path = self.get_file_path(storage_key_or_path)
            return path.is_file()
        except (FileNotFoundError, ValueError):
            return False

    def delete_file(self, storage_key_or_path: str) -> bool:
        """Deletes a stored asset from the local filesystem."""
        try:
            path = self.get_file_path(storage_key_or_path)
            path.unlink(missing_ok=True)
            return True
        except (FileNotFoundError, ValueError):
            return False

    def _ensure_safe_path(self, path: Path) -> None:
        """Enforces that resolved path cannot escape base_dir."""
        try:
            path.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError(f"Path traversal detected: '{path}' is outside storage root '{self.base_dir}'") from exc
