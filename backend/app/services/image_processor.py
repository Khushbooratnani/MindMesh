from pathlib import Path

from app.core.enums import MediaType
from app.core.errors import ImageUnderstandingFailedError, UnsupportedFileFormatError
from app.schemas.canonical_input import ProcessedInput


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class ImageProcessor:
    def process(self, file_path: Path) -> ProcessedInput:
        if file_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise UnsupportedFileFormatError("Unsupported image format.")

        raise ImageUnderstandingFailedError(
            f"Image understanding is not configured for {file_path.name}."
        )
