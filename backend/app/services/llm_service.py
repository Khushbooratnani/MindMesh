import json
from pathlib import Path
import re
from typing import Any

import httpx2
from pydantic import ValidationError

from app.config import settings
from app.core.enums import Sentiment
from app.core.errors import InvalidLLMJSONError, LLMExtractionError
from app.schemas.canonical_input import CanonicalInput
from app.schemas.extraction_output import ExtractionOutput


FORBIDDEN_SYSTEM_FIELDS = {
    "memory_id",
    "owner_id",
    "group_id",
    "privacy",
    "allowed_users",
    "created_at",
}


class LLMService:
    def __init__(
        self,
        model_name: str = "mock-memory-extractor",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
    ):
        self.model_name = model_name
        self.base_url = base_url or settings.openai_compatible_base_url
        self.api_key = api_key or settings.openai_compatible_api_key
        self.timeout_seconds = timeout_seconds

    def extract_memory(self, canonical_input: CanonicalInput) -> ExtractionOutput:
        if self.model_name == "mock-memory-extractor":
            return self._mock_extract(canonical_input)

        return self._extract_with_chat_completions(canonical_input)

    def parse_extraction_json(self, raw_response: str) -> ExtractionOutput:
        try:
            payload = json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise InvalidLLMJSONError("LLM returned malformed JSON.") from exc

        self._reject_forbidden_fields(payload)

        try:
            return ExtractionOutput.model_validate(payload)
        except ValidationError as exc:
            raise InvalidLLMJSONError("LLM JSON did not match extraction schema.") from exc

    def _reject_forbidden_fields(self, payload: Any) -> None:
        if isinstance(payload, dict):
            forbidden = FORBIDDEN_SYSTEM_FIELDS.intersection(payload)
            if forbidden:
                fields = ", ".join(sorted(forbidden))
                raise InvalidLLMJSONError(f"LLM returned forbidden fields: {fields}.")
            for value in payload.values():
                self._reject_forbidden_fields(value)
        elif isinstance(payload, list):
            for item in payload:
                self._reject_forbidden_fields(item)

    def _extract_with_chat_completions(
        self,
        canonical_input: CanonicalInput,
    ) -> ExtractionOutput:
        if not self.base_url:
            raise LLMExtractionError("OPENAI_COMPATIBLE_BASE_URL is not configured.")

        system_prompt = _read_prompt("memory_extraction_system.md")
        user_template = _read_prompt("memory_extraction_user_template.md")
        user_prompt = (
            user_template
            .replace("{media_type}", canonical_input.media_type.value)
            .replace("{content}", canonical_input.source_text)
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
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
            raise LLMExtractionError("OpenAI-compatible extraction request failed.") from exc

        try:
            content = response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise InvalidLLMJSONError(
                "Provider response did not include choices[0].message.content."
            ) from exc

        return self.parse_extraction_json(content)

    def _mock_extract(self, canonical_input: CanonicalInput) -> ExtractionOutput:
        text = canonical_input.source_text
        people = _extract_capitalized_names(text)
        locations = _known_locations(text)
        places = _known_places(text)
        topics = _topics(text)
        activities = _activities(text)
        sentiment = _sentiment(text)

        return ExtractionOutput(
            description=f"The memory describes: {text}",
            summary=_summary(text),
            entities={
                "people": people,
                "places": places,
                "locations": locations,
                "events": [],
                "organizations": [],
            },
            semantics={
                "topics": topics,
                "activities": activities,
                "sentiment": sentiment,
                "mood": _mood(sentiment),
            },
            temporal={
                "mentioned_dates": [],
                "inferred_time": None,
                "time_of_day": "unknown",
            },
            additional_attributes=_additional_attributes(text),
        )


def _extract_capitalized_names(text: str) -> list[str]:
    excluded = {"Had", "The", "A", "An", "At", "In", "On", "Cafe", "Goa"}
    names = re.findall(r"\b[A-Z][a-z]+\b", text)
    return _dedupe([name for name in names if name not in excluded])


def _known_locations(text: str) -> list[str]:
    candidates = ["Goa", "Mumbai", "Delhi", "Bengaluru", "Pune"]
    return [location for location in candidates if location.lower() in text.lower()]


def _known_places(text: str) -> list[str]:
    match = re.search(r"\b(Cafe\s+[A-Z][A-Za-z0-9 '&-]+)", text)
    return [match.group(1).strip()] if match else []


def _topics(text: str) -> list[str]:
    lowered = text.lower()
    topics = []
    for keyword in ("coffee", "cafe", "travel", "food", "friends"):
        if keyword in lowered:
            topics.append(keyword)
    return topics or ["memory"]


def _activities(text: str) -> list[str]:
    lowered = text.lower()
    if "coffee" in lowered:
        return ["drinking coffee"]
    if "dinner" in lowered or "lunch" in lowered:
        return ["eating"]
    return []


def _sentiment(text: str) -> Sentiment:
    lowered = text.lower()
    if any(word in lowered for word in ("amazing", "happy", "great", "fun", "love")):
        return Sentiment.POSITIVE
    if any(word in lowered for word in ("sad", "bad", "angry", "upset")):
        return Sentiment.NEGATIVE
    return Sentiment.UNKNOWN


def _mood(sentiment: Sentiment) -> list[str]:
    if sentiment == Sentiment.POSITIVE:
        return ["happy"]
    if sentiment == Sentiment.NEGATIVE:
        return ["sad"]
    return []


def _additional_attributes(text: str) -> list[dict[str, Any]]:
    if "coffee" not in text.lower():
        return []
    return [
        {
            "key": "food_or_drink",
            "value": "coffee",
            "confidence": 0.8,
            "source": "llm",
        }
    ]


def _summary(text: str) -> str:
    if len(text) <= 80:
        return text
    return f"{text[:77].rstrip()}..."


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(value)
    return deduped


def _read_prompt(filename: str) -> str:
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / filename
    return prompt_path.read_text(encoding="utf-8")


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return f"{normalized}/chat/completions"
