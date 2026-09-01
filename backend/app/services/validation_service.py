import re
from typing import Iterable

from pydantic import ValidationError

from app.core.enums import Privacy, Sentiment
from app.core.errors import SchemaValidationError
from app.schemas.memory_output import MemoryV1


class ValidationService:
    def validate(self, memory: MemoryV1 | dict) -> MemoryV1:
        try:
            memory_v1 = MemoryV1.model_validate(memory)
        except ValidationError as exc:
            raise SchemaValidationError("Final memory JSON failed schema validation.") from exc

        self._normalize(memory_v1)
        self._validate_business_rules(memory_v1)
        return memory_v1

    def _normalize(self, memory: MemoryV1) -> None:
        memory.content.clean_text = _trim(memory.content.clean_text)
        memory.content.description = _trim(memory.content.description)
        memory.content.summary = _trim(memory.content.summary)
        if memory.content.raw_text is not None:
            memory.content.raw_text = _trim(memory.content.raw_text)

        memory.entities.people = _clean_array(memory.entities.people)
        memory.entities.places = _clean_array(memory.entities.places)
        memory.entities.locations = _clean_array(memory.entities.locations)
        memory.entities.events = _clean_array(memory.entities.events)
        memory.entities.organizations = _clean_array(memory.entities.organizations)
        memory.semantics.topics = _clean_array(memory.semantics.topics)
        memory.semantics.activities = _clean_array(memory.semantics.activities)
        memory.semantics.mood = _clean_array(memory.semantics.mood)
        memory.temporal.mentioned_dates = _clean_array(memory.temporal.mentioned_dates)
        memory.system.allowed_users = _clean_array(memory.system.allowed_users)

        for attribute in memory.additional_attributes:
            attribute.key = re.sub(r"[^a-zA-Z0-9_]+", "_", attribute.key.strip()).strip("_").lower()

    def _validate_business_rules(self, memory: MemoryV1) -> None:
        if not memory.content.clean_text:
            raise SchemaValidationError("Final memory clean_text cannot be empty.")
        if not memory.content.description:
            raise SchemaValidationError("Final memory description cannot be empty.")
        if not memory.content.summary:
            raise SchemaValidationError("Final memory summary cannot be empty.")
        if memory.system.privacy != Privacy.SELECTED and memory.system.allowed_users:
            raise SchemaValidationError(
                "allowed_users can only be set when privacy is SELECTED."
            )
        if memory.semantics.sentiment not in set(Sentiment):
            raise SchemaValidationError("Invalid sentiment value.")


def _trim(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _clean_array(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        trimmed = _trim(value)
        key = trimmed.lower()
        if trimmed and key not in seen:
            seen.add(key)
            cleaned.append(trimmed)
    return cleaned
