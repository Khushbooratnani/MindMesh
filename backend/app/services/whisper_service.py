from pathlib import Path
from typing import Any

from app.core.errors import TranscriptionFailedError
from app.config import settings


class WhisperService:
    _model = None

    def transcribe(self, file_path: Path) -> dict[str, Any]:
        try:
            from faster_whisper import WhisperModel

            if self._model is None:
                self._model = WhisperModel(settings.whisper_model, device="auto", compute_type="int8")
            segments, info = self._model.transcribe(str(file_path))
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            if not transcript:
                raise TranscriptionFailedError(f"Whisper produced no transcript for {file_path.name}.")
            return {"transcript": transcript, "language": info.language}
        except TranscriptionFailedError:
            raise
        except Exception as exc:
            raise TranscriptionFailedError(f"Whisper transcription failed for {file_path.name}: {exc}") from exc
