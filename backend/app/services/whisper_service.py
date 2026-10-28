import logging
from pathlib import Path
from typing import Any, Callable

from app.config import settings
from app.core.errors import TranscriptionFailedError

logger = logging.getLogger(__name__)


class WhisperService:
    """Audio transcription service wrapping Whisper models with lazy loading and model reuse."""

    # Class-level cache to ensure Whisper models are loaded once and reused across requests
    _MODEL_CACHE: dict[tuple[str, str, str], Any] = {}

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        initial_prompt: str | None = None,
        mock_transcriber: Callable[[Path], dict[str, Any]] | None = None,
    ):
        self.model_name = model_name or settings.whisper_model
        self.device = device or settings.whisper_device
        self.compute_type = compute_type or settings.whisper_compute_type
        self.initial_prompt = (
            initial_prompt
            if initial_prompt is not None
            else getattr(settings, "whisper_initial_prompt", None)
        )
        self.mock_transcriber = mock_transcriber

    def _get_model(self) -> Any:
        """Lazily load and cache the faster-whisper model instance."""
        cache_key = (self.model_name, self.device, self.compute_type)
        if cache_key not in self._MODEL_CACHE:
            try:
                from faster_whisper import WhisperModel
                logger.info(
                    "Loading Whisper model '%s' on %s (%s)...",
                    self.model_name,
                    self.device,
                    self.compute_type,
                )
                self._MODEL_CACHE[cache_key] = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                logger.info("Whisper model '%s' loaded successfully.", self.model_name)
            except ImportError as exc:
                raise TranscriptionFailedError(
                    "faster-whisper is not installed. Please install faster-whisper to transcribe audio."
                ) from exc
            except Exception as exc:
                raise TranscriptionFailedError(
                    f"Failed to load Whisper model '{self.model_name}': {str(exc)}"
                ) from exc
        return self._MODEL_CACHE[cache_key]

    def transcribe(
        self,
        file_path: Path,
        initial_prompt: str | None = None,
    ) -> dict[str, Any]:
        """Transcribe an audio file and return a structured dictionary."""
        if not file_path.exists():
            raise TranscriptionFailedError(f"Audio file not found: {file_path}")

        if file_path.stat().st_size == 0:
            raise TranscriptionFailedError("Audio file is empty.")

        # Support mock transcriber for fast dependency injection in unit tests
        if self.mock_transcriber is not None:
            return self.mock_transcriber(file_path)

        try:
            model = self._get_model()
            effective_prompt = initial_prompt if initial_prompt is not None else self.initial_prompt
            transcribe_kwargs: dict[str, Any] = {
                "beam_size": 5,
                "vad_filter": True,
            }
            if effective_prompt:
                transcribe_kwargs["initial_prompt"] = effective_prompt

            segments, info = model.transcribe(
                str(file_path),
                **transcribe_kwargs,
            )

            segment_list = []
            transcript_parts = []
            for segment in segments:
                segment_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                })
                transcript_parts.append(segment.text.strip())

            full_transcript = " ".join(part for part in transcript_parts if part)

            return {
                "transcript": full_transcript,
                "language": getattr(info, "language", None),
                "language_probability": getattr(info, "language_probability", None),
                "duration": getattr(info, "duration", None),
                "segments": segment_list,
            }
        except TranscriptionFailedError:
            raise
        except Exception as exc:
            raise TranscriptionFailedError(
                f"Whisper transcription failed for {file_path.name}: {str(exc)}"
            ) from exc
