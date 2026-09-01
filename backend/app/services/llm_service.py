import json
import re
from typing import Any

from pydantic import ValidationError

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
    def __init__(self, model_name: str = "mock-memory-extractor"):
        self.model_name = model_name

    def extract_memory(self, canonical_input: CanonicalInput) -> ExtractionOutput:
        if self.model_name == "mock-memory-extractor":
            return self._mock_extract(canonical_input)

        raise LLMExtractionError(
            "Real OpenAI-compatible extraction is not configured yet."
        )

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
