import re

from app.core.enums import MediaType
from app.core.errors import EmptyTextError
from app.schemas.canonical_input import ProcessedInput


class TextProcessor:
    def process(self, text: str) -> ProcessedInput:
        raw_text = text
        clean_text = normalize_whitespace(text)
        if not clean_text:
            raise EmptyTextError("Text memory cannot be empty.")

        return ProcessedInput(
            media_type=MediaType.TEXT,
            raw_text=raw_text,
            clean_text=clean_text,
        )


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
