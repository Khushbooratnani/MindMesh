import pytest

from app.core.errors import InvalidLLMJSONError
from app.services.llm_service import LLMService


def test_parse_extraction_json_rejects_malformed_json():
    with pytest.raises(InvalidLLMJSONError):
        LLMService().parse_extraction_json("{bad json")


def test_parse_extraction_json_rejects_forbidden_system_fields():
    raw_response = """
    {
      "owner_id": "U_EVIL",
      "description": "A memory.",
      "summary": "A memory.",
      "entities": {},
      "semantics": {},
      "temporal": {},
      "additional_attributes": []
    }
    """

    with pytest.raises(InvalidLLMJSONError):
        LLMService().parse_extraction_json(raw_response)
