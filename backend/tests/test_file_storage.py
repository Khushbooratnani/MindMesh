import hashlib
from pathlib import Path
import pytest

from app.core.enums import MediaType
from app.storage.file_storage import FileStorage, StorageReference, _sanitize_filename


@pytest.fixture
def storage(tmp_path):
    """Provides an isolated FileStorage instance using pytest tmp_path."""
    return FileStorage(base_dir=tmp_path / "media_store")


def test_image_save_and_metadata(storage):
    """Verify saving an image produces valid StorageReference, correct folder, and correct bytes."""
    image_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 128  # Sample JPEG bytes
    ref = storage.save_file(
        file_bytes=image_bytes,
        filename="vacation_photo.jpg",
        media_type=MediaType.IMAGE,
        content_type="image/jpeg",
    )

    assert isinstance(ref, StorageReference)
    assert len(ref.storage_key) == 32  # UUID hex
    assert ref.original_filename == "vacation_photo.jpg"
    assert ref.media_type == "image"
    assert ref.content_type == "image/jpeg"
    assert ref.size_bytes == len(image_bytes)
    assert ref.sha256 == hashlib.sha256(image_bytes).hexdigest()
    assert ref.relative_path.startswith("images/")
    assert ref.relative_path.endswith(".jpg")

    # Verify physical file existence and content
    saved_path = storage.get_file_path(ref.relative_path)
    assert saved_path.exists()
    assert saved_path.read_bytes() == image_bytes


def test_audio_save_and_metadata(storage):
    """Verify saving audio produces valid StorageReference in audio folder."""
    audio_bytes = b"OggS\x00\x02" + b"\x00" * 200  # Sample Ogg bytes
    ref = storage.save_file(
        file_bytes=audio_bytes,
        filename="voice_note.ogg",
        media_type=MediaType.AUDIO,
    )

    assert ref.media_type == "audio"
    assert ref.relative_path.startswith("audio/")
    assert ref.relative_path.endswith(".ogg")
    assert ref.size_bytes == len(audio_bytes)
    assert storage.get_file(ref.relative_path) == audio_bytes


def test_sha256_and_size_correctness(storage):
    """Verify SHA256 checksum and size calculations match exactly."""
    payload = b"Exact test bytes for SHA256 verification 12345"
    expected_sha = hashlib.sha256(payload).hexdigest()

    ref = storage.save_file(
        file_bytes=payload,
        filename="data.bin",
        media_type="files",
    )

    assert ref.sha256 == expected_sha
    assert ref.size_bytes == len(payload)
    assert storage.get_file(ref.storage_key) == payload


def test_unique_storage_keys_for_identical_files(storage):
    """Verify two uploads with identical content and names receive distinct unique storage keys."""
    content = b"Duplicate file content test"

    ref1 = storage.save_file(file_bytes=content, filename="note.txt")
    ref2 = storage.save_file(file_bytes=content, filename="note.txt")

    assert ref1.storage_key != ref2.storage_key
    assert ref1.relative_path != ref2.relative_path
    assert storage.exists(ref1.storage_key)
    assert storage.exists(ref2.storage_key)


def test_retrieval_by_key_and_path(storage):
    """Verify assets can be retrieved both by storage_key and relative_path."""
    content = b"Sample content for retrieval test"
    ref = storage.save_file(file_bytes=content, filename="test.png", media_type=MediaType.IMAGE)

    # Retrieval by relative path
    assert storage.get_file(ref.relative_path) == content
    assert storage.get_file_path(ref.relative_path).is_file()

    # Retrieval by storage_key (stem)
    assert storage.get_file(ref.storage_key) == content
    assert storage.get_file_path(ref.storage_key).is_file()


def test_path_traversal_protection(storage):
    """Verify malicious filenames with path traversal cannot escape storage root."""
    malicious_filename = "../../../../etc/passwd.jpg"
    ref = storage.save_file(
        file_bytes=b"SAFE_CONTENT",
        filename=malicious_filename,
        media_type=MediaType.IMAGE,
    )

    # Filename must be sanitized
    assert ".." not in ref.original_filename
    assert "/" not in ref.original_filename
    assert "\\" not in ref.original_filename

    # Stored file must be within base_dir
    saved_path = storage.get_file_path(ref.storage_key)
    assert saved_path.is_relative_to(storage.base_dir)

    # Explicit traversal query on retrieval must raise ValueError
    with pytest.raises(ValueError):
        storage.get_file_path("../../outside_file.txt")


def test_filename_sanitization_helper():
    """Verify _sanitize_filename handles edge cases."""
    assert _sanitize_filename("../../test.jpg") == "test.jpg"
    assert _sanitize_filename("C:\\Users\\test\\image.png") == "image.png"
    assert _sanitize_filename("/var/log/audio.m4a") == "audio.m4a"
    assert _sanitize_filename("...hidden.jpg") == "hidden.jpg"
    assert _sanitize_filename("") == "unnamed_file"
