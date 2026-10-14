from typing import Any

import httpx2

from app.config import settings
from app.core.errors import IngestionError


class EmbeddingError(IngestionError):
    code = "EMBEDDING_FAILED"
    status_code = 502


class EmbeddingService:
    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        dimensions: int | None = None,
        timeout_seconds: float = 60.0,
    ):
        self.base_url = base_url or settings.ollama_base_url
        self.model_name = model_name or settings.embedding_model
        self.dimensions = dimensions or settings.embedding_dimensions
        self.timeout_seconds = timeout_seconds

    def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            raise EmbeddingError("Cannot embed empty text.")

        payload = {"model": self.model_name, "prompt": text}
        try:
            with httpx2.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/api/embeddings",
                    json=payload,
                )
                response.raise_for_status()
                response_payload = response.json()
        except Exception as exc:
            raise EmbeddingError("Ollama embedding request failed.") from exc

        return self._parse_embedding(response_payload)

    def _parse_embedding(self, payload: dict[str, Any]) -> list[float]:
        embedding = payload.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            raise EmbeddingError("Ollama response did not include an embedding list.")

        try:
            vector = [float(value) for value in embedding]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("Embedding contains non-numeric values.") from exc

        if len(vector) != self.dimensions:
            raise EmbeddingError(
                f"Embedding dimension mismatch: expected {self.dimensions}, got {len(vector)}."
            )
        return vector
