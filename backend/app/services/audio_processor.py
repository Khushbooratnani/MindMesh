from pathlib import Path

from app.core.enums import MediaType
from app.core.errors import UnsupportedFileFormatError
from app.schemas.canonical_input import ProcessedInput
from app.services.whisper_service import WhisperService
from app.services.text_processor import normalize_whitespace


SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".webm", ".ogg"}


class AudioProcessor:
    def __init__(self, whisper_service: WhisperService | None = None):
        self.whisper_service = whisper_service or WhisperService()

    def process(self, file_path: Path) -> ProcessedInput:
        if file_path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            raise UnsupportedFileFormatError("Unsupported audio format.")

        transcript = self.whisper_service.transcribe(file_path)
        return ProcessedInput(
            media_type=MediaType.AUDIO,
            raw_text=transcript["transcript"],
            clean_text=normalize_whitespace(transcript["transcript"]),
        )
