import base64
import mimetypes
from pathlib import Path

import httpx2

from app.config import settings
from app.core.enums import MediaType
from app.core.errors import ImageUnderstandingFailedError, UnsupportedFileFormatError
from app.schemas.canonical_input import ProcessedInput


SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
SUPPORTED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ImageProcessor:
    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ):
        self.model_name = model_name or settings.image_understanding_model
        self.base_url = base_url or settings.openai_compatible_base_url
        self.api_key = api_key or settings.openai_compatible_api_key
        self.timeout_seconds = timeout_seconds

    def process(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> ProcessedInput:
        suffix = Path(filename).suffix.lower()
        guessed_content_type = content_type or mimetypes.guess_type(filename)[0]

        if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            raise UnsupportedFileFormatError("Unsupported image format.")
        if guessed_content_type not in SUPPORTED_IMAGE_MIME_TYPES:
            raise UnsupportedFileFormatError("Unsupported image MIME type.")
        if not file_bytes:
            raise ImageUnderstandingFailedError("Image file is empty.")

        description = self._describe_image(
            file_bytes=file_bytes,
            content_type=guessed_content_type,
        )
        return ProcessedInput(
            media_type=MediaType.IMAGE,
            raw_text=None,
            clean_text=description,
        )

    def _describe_image(self, file_bytes: bytes, content_type: str) -> str:
        if not self.base_url:
            raise ImageUnderstandingFailedError("OPENAI_COMPATIBLE_BASE_URL is not configured.")
        if self.model_name == "to-be-decided":
            raise ImageUnderstandingFailedError("IMAGE_UNDERSTANDING_MODEL is not configured.")

        data_uri = _to_data_uri(file_bytes, content_type)
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You describe images for a memory application. "
                        "Describe only visible details. Do not invent names, dates, "
                        "locations, or relationships unless they are visibly present."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Give a detailed natural-language description of this image. "
                                "Mention visible people, places, objects, activities, mood, "
                                "food or drink, and setting when supported by the image."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_uri},
                        },
                    ],
                },
            ],
            "temperature": 0,
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key and self.api_key != "replace_with_your_api_key":
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx2.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    _chat_completions_url(self.base_url),
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                response_payload = response.json()
        except Exception as exc:
            raise ImageUnderstandingFailedError("Image understanding request failed.") from exc

        try:
            description = response_payload["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ImageUnderstandingFailedError(
                "Provider response did not include image description content."
            ) from exc

        if not description:
            raise ImageUnderstandingFailedError("Image description was empty.")
        return description


def _to_data_uri(file_bytes: bytes, content_type: str) -> str:
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"
