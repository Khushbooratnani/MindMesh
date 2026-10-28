import json
from unittest.mock import MagicMock, patch

from app.services.llm_service import LLMService


def test_answer_from_memories_prompt_instructions():
    """Verify that the system prompt constructed in answer_from_memories strictly mandates second-person."""
    service = LLMService(base_url="http://mock-llm:8128/v1")
    memories = [
        {
            "content": {"summary": "The user went to Panjim and had filter coffee with Rohan."},
            "entities": {"people": ["Rohan"], "places": ["Panjim"]},
            "semantics": {"topics": ["coffee"]},
            "temporal": {},
        }
    ]

    captured_payload = {}

    def mock_post(url, headers=None, json=None):
        nonlocal captured_payload
        captured_payload = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "You went to Panjim and had filter coffee with Rohan."}}]
        }
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        answer = service.answer_from_memories("What did I do in Panjim?", memories)

    assert "second person" in captured_payload["messages"][0]["content"].lower()
    assert "never refer to the current user in the third person" in captured_payload["messages"][0]["content"].lower()
    assert "you went to panjim" in answer.lower()
    assert "the user" not in answer.lower()


def test_answer_from_memories_third_person_to_second_person():
    """Verify conversion of third-person memory summary to second-person answer."""
    service = LLMService(base_url="http://mock-llm:8128/v1")
    memories = [
        {
            "content": {"summary": "The user had dinner at Fisherman's Wharf in Goa."},
            "entities": {"places": ["Fisherman's Wharf", "Goa"]},
            "semantics": {},
            "temporal": {},
        }
    ]

    def mock_post(url, headers=None, json=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "You had dinner at Fisherman's Wharf in Goa."}}]
        }
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        answer = service.answer_from_memories("Where did I have dinner in Goa?", memories)

    assert "you had dinner" in answer.lower()
    assert "the user" not in answer.lower()


def test_answer_from_memories_does_not_inject_user_name():
    """Verify that a name like Mehul in a memory is not injected as third-person speaker name."""
    service = LLMService(base_url="http://mock-llm:8128/v1")
    memories = [
        {
            "content": {"summary": "Mehul visited Cafe Bodega in Goa for coffee."},
            "entities": {"places": ["Cafe Bodega", "Goa"], "people": []},
            "semantics": {},
            "temporal": {},
        }
    ]

    def mock_post(url, headers=None, json=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "You visited Cafe Bodega in Goa for coffee."}}]
        }
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        answer = service.answer_from_memories("Did I go to Cafe Bodega?", memories)

    assert "you visited" in answer.lower()
    assert not answer.lower().startswith("mehul visited")


def test_answer_from_memories_recommendation_query():
    """Verify recommendation query style answer."""
    service = LLMService(base_url="http://mock-llm:8128/v1")
    memories = [
        {
            "content": {"summary": "The user had good momos at Nanda Ki Chowki in Dehradun."},
            "entities": {"places": ["Nanda Ki Chowki", "Dehradun"]},
            "semantics": {"topics": ["food", "momos"]},
            "temporal": {},
        }
    ]

    def mock_post(url, headers=None, json=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "You can try the momos at Nanda Ki Chowki in Dehradun, which you enjoyed previously."}}]
        }
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        answer = service.answer_from_memories("Where can I get good momos?", memories)

    assert "you" in answer.lower()
    assert "nanda ki chowki" in answer.lower()
    assert "the user" not in answer.lower()


def test_answer_from_memories_confirmation_query():
    """Verify confirmation query style answer."""
    service = LLMService(base_url="http://mock-llm:8128/v1")
    memories = [
        {
            "content": {"summary": "The user had filter coffee with Rohan at Cafe Bodega."},
            "entities": {"people": ["Rohan"], "places": ["Cafe Bodega"]},
            "semantics": {},
            "temporal": {},
        }
    ]

    def mock_post(url, headers=None, json=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Yes, you had filter coffee with Rohan at Cafe Bodega."}}]
        }
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        answer = service.answer_from_memories("Did I have coffee with Rohan?", memories)

    assert "yes" in answer.lower()
    assert "you had" in answer.lower()
    assert "rohan" in answer.lower()
    assert "the user" not in answer.lower()


def test_answer_from_memories_fallback_converts_third_person():
    """Verify offline fallback converts 'The user ...' prefix to 'You ...'."""
    service = LLMService(base_url=None)  # Forces fallback
    memories = [
        {
            "content": {"summary": "The user went to Mussoorie with Akshat."},
            "entities": {"people": ["Akshat"], "places": ["Mussoorie"]},
            "semantics": {},
            "temporal": {},
        }
    ]

    answer = service.answer_from_memories("Where did I go?", memories)
    assert answer.startswith("You went to Mussoorie with Akshat.")
    assert "the user" not in answer.lower()


def test_answer_from_memories_insufficient_information():
    """Verify clear statement when information is missing."""
    service = LLMService(base_url="http://mock-llm:8128/v1")
    memories = [
        {
            "content": {"summary": "Discussion about Q3 roadmap."},
            "entities": {},
            "semantics": {},
            "temporal": {},
        }
    ]

    def mock_post(url, headers=None, json=None):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "I couldn't find any information about your flight tickets in stored memories."}}]
        }
        return mock_resp

    with patch("httpx.Client.post", side_effect=mock_post):
        answer = service.answer_from_memories("What time is my flight?", memories)

    assert "couldn't find" in answer.lower() or "insufficient" in answer.lower()
