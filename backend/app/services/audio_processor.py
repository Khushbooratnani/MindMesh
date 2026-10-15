import logging
import os
from pathlib import Path
import tempfile
from typing import BinaryIO

from app.core.enums import MediaType
from app.core.errors import UnsupportedFileFormatError, TranscriptionFailedError
from app.schemas.canonical_input import ProcessedInput
from app.services.text_processor import normalize_whitespace
from app.services.transcript_normalizer import TranscriptNormalizer
from app.services.whisper_service import WhisperService

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".webm",
    ".ogg",
    ".flac",
    ".aac",
    ".bin",  # Often used for raw audio container dumps from web/forms (e.g. Ogg Opus)
}

SUPPORTED_AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4",
    "audio/webm",
    "audio/ogg",
    "audio/opus",
    "audio/flac",
    "audio/aac",
    "application/octet-stream",
}

# Known audio file magic headers
OGG_MAGIC = b"OggS"
RIFF_MAGIC = b"RIFF"
ID3_MAGIC = b"ID3"
FTYP_MAGIC = b"ftyp"  # Offset 4 in MP4/M4A containers


def is_valid_audio_header(header_bytes: bytes) -> bool:
    """Check magic bytes to determine if the payload is a recognized audio format."""
    if len(header_bytes) < 4:
        return False
    if header_bytes.startswith(OGG_MAGIC):
        return True
    if header_bytes.startswith(RIFF_MAGIC):
        return True
    if header_bytes.startswith(ID3_MAGIC):
        return True
    if len(header_bytes) >= 8 and header_bytes[4:8] == FTYP_MAGIC:
        return True
    # MPEG sync word check (first 11 bits are 1s -> 0xFF 0xE0..0xFF)
    if header_bytes[0] == 0xFF and (header_bytes[1] & 0xE0) == 0xE0:
        return True
    return False


class AudioProcessor:
    """Processes audio inputs, validates audio formats/containers, and transcribes via WhisperService."""

    def __init__(
        self,
        whisper_service: WhisperService | None = None,
        transcript_normalizer: TranscriptNormalizer | None = None,
    ):
        self.whisper_service = whisper_service or WhisperService()
        self.transcript_normalizer = transcript_normalizer or TranscriptNormalizer()

    def process(
        self,
        file_path: Path | None = None,
        file_bytes: bytes | None = None,
        filename: str | None = None,
        content_type: str | None = None,
        user_context: str | None = None,
    ) -> ProcessedInput:
        """Process an audio input from file_path or raw file_bytes."""
        if file_path is not None:
            return self._process_path(file_path, user_context=user_context)
        if file_bytes is not None:
            return self._process_bytes(
                file_bytes,
                filename=filename or "audio_upload",
                content_type=content_type,
                user_context=user_context,
            )
        raise TranscriptionFailedError("Neither file_path nor file_bytes was provided for audio processing.")

    def _process_path(
        self,
        file_path: Path,
        user_context: str | None = None,
    ) -> ProcessedInput:
        if not file_path.exists():
            raise TranscriptionFailedError(f"Audio file not found: {file_path}")

        suffix = file_path.suffix.lower()
        if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
            raise UnsupportedFileFormatError(f"Unsupported audio format: {suffix}")

        with open(file_path, "rb") as f:
            header = f.read(32)

        # If .bin or unknown suffix, ensure header is a valid audio container (e.g. OggS)
        if suffix == ".bin" and not is_valid_audio_header(header):
            raise UnsupportedFileFormatError("Binary file does not contain a recognized audio signature.")

        # If it's a .bin file containing OggS, create a temp .ogg symlink/file for decoder compatibility
        if suffix == ".bin" and header.startswith(OGG_MAGIC):
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
            try:
                with open(file_path, "rb") as src, open(tmp_path, "wb") as dst:
                    dst.write(src.read())
                transcript_data = self.whisper_service.transcribe(tmp_path)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink(missing_ok=True)
        else:
            transcript_data = self.whisper_service.transcribe(file_path)

        raw_text = transcript_data.get("transcript", "")
        detected_lang = transcript_data.get("language")
        lang_prob = transcript_data.get("language_probability")

        try:
            norm_res = self.transcript_normalizer.normalize(
                raw_transcript=raw_text,
                detected_language=detected_lang,
                language_probability=lang_prob,
                user_context=user_context,
            )
            clean_text = normalize_whitespace(norm_res.normalized_text)
            norm_lang = norm_res.normalized_language
            disp_script = norm_res.display_script
        except Exception as exc:
            logger.warning("[AudioProcessor] Normalization failed (%s), using raw transcript.", exc)
            clean_text = normalize_whitespace(raw_text)
            norm_lang = detected_lang
            disp_script = "latin"

        return ProcessedInput(
            media_type=MediaType.AUDIO,
            raw_text=raw_text,
            clean_text=clean_text,
            detected_language=detected_lang,
            language_probability=lang_prob,
            normalized_language=norm_lang,
            display_script=disp_script,
        )

    def _process_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None = None,
        user_context: str | None = None,
    ) -> ProcessedInput:
        if not file_bytes:
            raise TranscriptionFailedError("Audio file is empty.")

        suffix = Path(filename).suffix.lower()
        header = file_bytes[:32]

        is_supported_ext = suffix in SUPPORTED_AUDIO_EXTENSIONS
        has_valid_header = is_valid_audio_header(header)

        if not is_supported_ext and not has_valid_header:
            raise UnsupportedFileFormatError(f"Unsupported audio format: {suffix or 'unknown'}")

        # Determine best suffix for temporary file so audio decoders (ffmpeg/PyAV) recognize the container
        temp_suffix = suffix
        if header.startswith(OGG_MAGIC) or suffix == ".bin":
            temp_suffix = ".ogg"
        elif not temp_suffix:
            temp_suffix = ".m4a"

        with tempfile.NamedTemporaryFile(suffix=temp_suffix, delete=False) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = Path(tmp_file.name)

        try:
            transcript_data = self.whisper_service.transcribe(tmp_path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

        raw_text = transcript_data.get("transcript", "")
        detected_lang = transcript_data.get("language")
        lang_prob = transcript_data.get("language_probability")

        try:
            norm_res = self.transcript_normalizer.normalize(
                raw_transcript=raw_text,
                detected_language=detected_lang,
                language_probability=lang_prob,
                user_context=user_context,
            )
            clean_text = normalize_whitespace(norm_res.normalized_text)
            norm_lang = norm_res.normalized_language
            disp_script = norm_res.display_script
        except Exception as exc:
            logger.warning("[AudioProcessor] Normalization failed (%s), using raw transcript.", exc)
            clean_text = normalize_whitespace(raw_text)
            norm_lang = detected_lang
            disp_script = "latin"

        return ProcessedInput(
            media_type=MediaType.AUDIO,
            raw_text=raw_text,
            clean_text=clean_text,
            detected_language=detected_lang,
            language_probability=lang_prob,
            normalized_language=norm_lang,
            display_script=disp_script,
        )
