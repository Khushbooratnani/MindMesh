from pathlib import Path
from typing import Any

from app.core.errors import TranscriptionFailedError


class WhisperService:
    def transcribe(self, file_path: Path) -> dict[str, Any]:
        raise TranscriptionFailedError(
            f"Whisper transcription is not configured for {file_path.name}."
        )
