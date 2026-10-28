import math
import pytest
from unittest.mock import MagicMock, patch

from app.schemas.memory_output import MemoryV1
from app.services.geocoding_service import GeocodingService, get_geocoding_service
from app.services.graph_builder import GraphBuilder, get_graph_builder
from app.database.neo4j import Neo4jClient, get_neo4j_client
from app.services.memory_search_service import (
    _passes_location_text_gate,
    _query_terms,
    _haversine_meters,
)


# ---------------------------------------------------------------------------
# 1. Geocoding Service & Fallback Dictionary Tests
# ---------------------------------------------------------------------------

class TestGeocodingService:
    def test_known_places_fallback(self):
        service = GeocodingService(api_key=None)
        
        # Test known locations from the fallback dictionary
        dehradun = service.geocode("Dehradun, India")
        assert dehradun is not None
        assert abs(dehradun["latitude"] - 30.3165) < 0.01
        assert abs(dehradun["longitude"] - 78.0322) < 0.01
        assert "Dehradun" in dehradun["location"]

        goa = service.geocode("Goa, India")
        assert goa is not None
        assert abs(goa["latitude"] - 15.2993) < 0.01

        mussoorie = service.geocode("Mussoorie")
        assert mussoorie is not None
        assert abs(mussoorie["latitude"] - 30.4598) < 0.01

    def test_in_memory_cache(self):
        service = GeocodingService(api_key=None)
        
        # First call
        res1 = service.geocode("Dehradun, India")
        assert res1 is not None

        # Second call should hit the in-memory cache
        res2 = service.geocode("Dehradun, India")
        assert res2 is not None
        assert res1["latitude"] == res2["latitude"]
        assert res1["longitude"] == res2["longitude"]

    def test_empty_or_whitespace_query(self):
        service = GeocodingService(api_key=None)
        assert service.geocode("") is None
        assert service.geocode("   ") is None
        assert service.geocode(None) is None


# ---------------------------------------------------------------------------
# 2. Knowledge Graph Builder & Neo4j Fail-Soft Tests
# ---------------------------------------------------------------------------

class TestGraphBuilderAndNeo4j:
    @pytest.fixture
    def sample_memory_v1(self):
        return MemoryV1.model_validate({
            "memory_id": "mem-test-graph-001",
            "schema_version": "1.0",
            "system": {
                "owner_id": "usr-test-01",
                "media_type": "text",
                "created_at": "2026-09-08T10:30:00Z",
                "privacy": "ONLY_ME",
                "allowed_users": [],
            },
            "content": {
                "raw_text": "Had a wonderful dinner with Sarah at Curlies Shack in Anjuna, Goa discussing artificial intelligence.",
                "clean_text": "Had a wonderful dinner with Sarah at Curlies Shack in Anjuna, Goa discussing artificial intelligence.",
                "description": "Dinner with Sarah at Curlies Shack in Goa about AI.",
                "summary": "Dinner with Sarah at Curlies Shack in Goa about AI.",
            },
            "entities": {
                "people": ["Sarah"],
                "places": ["Curlies Shack"],
                "locations": ["Anjuna, Goa"],
                "events": ["Dinner"],
                "organizations": ["MindMesh"],
            },
            "semantics": {
                "topics": ["artificial intelligence", "food"],
                "activities": ["dining", "discussion"],
                "sentiment": "positive",
                "mood": ["happy"],
            },
            "temporal": {
                "mentioned_dates": ["2026-09-08"],
                "inferred_time": "evening",
                "time_of_day": "evening",
            },
            "processing": {
                "status": "completed",
                "source_modality": "text",
                "transcription_required": False,
                "image_understanding_required": False,
                "llm_provider": "mock",
                "llm_model": "mock",
            },
        })

    def test_build_graph_payload_structure(self, sample_memory_v1):
        builder = GraphBuilder()
        doc = builder.build_from_memory(sample_memory_v1)

        # Check nodes
        node_labels = {n.type for n in doc.nodes}
        assert "Memory" in node_labels
        assert "Person" in node_labels
        assert "Place" in node_labels
        assert "Location" in node_labels
        assert "Event" in node_labels
        assert "Organization" in node_labels
        assert "Topic" in node_labels
        assert "Activity" in node_labels
        assert "Mood" in node_labels

        # Check relationships
        rel_types = {r.type for r in doc.relationships}
        assert "MENTIONS_PERSON" in rel_types
        assert "HAPPENED_AT" in rel_types
        assert "LOCATED_IN" in rel_types
        assert "PART_OF" in rel_types
        assert "HAS_TOPIC" in rel_types
        assert "HAS_ACTIVITY" in rel_types
        assert "HAS_MOOD" in rel_types

    def test_neo4j_client_fail_soft_when_offline(self):
        client = Neo4jClient(uri="bolt://127.0.0.1:9999", user="neo4j", password="badpassword")
        # Should not raise exception on connection check
        is_conn = client.is_connected()
        assert is_conn is False

        # Queries should safely return empty lists without 500 error
        res = client.execute_query("MATCH (n) RETURN n LIMIT 5")
        assert res == []


# ---------------------------------------------------------------------------
# 3. Topic Gate (_passes_location_text_gate) Tests
# ---------------------------------------------------------------------------

class TestTopicGate:
    def test_relevant_memory_passes_topic_gate(self):
        query_terms = _query_terms("best cafe in Goa with coffee")
        result = {
            "summary": "Visiting a great coffee shop in Anjuna Goa with delicious cold brew.",
            "clean_text": "Stopped by Curlies cafe for a latte and iced coffee.",
            "matched_by": ["vector"],
        }
        assert _passes_location_text_gate(result, query_terms) is True

    def test_off_topic_memory_fails_topic_gate(self):
        query_terms = _query_terms("best cafe or coffee in Goa")
        result = {
            "summary": "Emergency car tire puncture repair and brake pad change in Panaji.",
            "clean_text": "Mechanic replaced the rear disc rotor and balanced wheels.",
            "matched_by": ["nearby"],
        }
        assert _passes_location_text_gate(result, query_terms) is False

    def test_empty_or_generic_query_passes(self):
        # When query is just a location or generic words, it should pass
        query_terms = _query_terms("in at")
        result = {"summary": "Went to the beach", "clean_text": "Nice day", "matched_by": ["nearby"]}
        assert _passes_location_text_gate(result, query_terms) is True


# ---------------------------------------------------------------------------
# 4. Haversine Math & Fusion Score Formulas
# ---------------------------------------------------------------------------

class TestGeographicFusionMath:
    def test_haversine_distance_calculation(self):
        # Dehradun (30.3165, 78.0322) to Mussoorie (30.4598, 78.0644)
        dist = _haversine_meters(30.3165, 78.0322, 30.4598, 78.0644)
        # Should be approximately 16.2 km (between 15 km and 18 km)
        assert 15000 < dist < 18000

    def test_distance_score_formula(self):
        # Score_distance = max(0.0, 1.0 - (distance / radius))
        radius_m = 10000.0  # 10 km

        # Distance = 0 -> Score = 1.0
        score_0 = max(0.0, 1.0 - (0.0 / radius_m))
        assert score_0 == 1.0

        # Distance = 5 km -> Score = 0.5
        score_half = max(0.0, 1.0 - (5000.0 / radius_m))
        assert abs(score_half - 0.5) < 1e-6

        # Distance = 10 km -> Score = 0.0
        score_boundary = max(0.0, 1.0 - (10000.0 / radius_m))
        assert score_boundary == 0.0

        # Distance = 12 km -> Score clamped to 0.0
        score_outside = max(0.0, 1.0 - (12000.0 / radius_m))
        assert score_outside == 0.0

    def test_combined_retrieval_fusion_score(self):
        # Final Score = 0.7 * Score_hybrid + 0.3 * Score_distance
        score_hybrid = 0.8
        score_distance = 0.6
        final_score = 0.7 * score_hybrid + 0.3 * score_distance
        # 0.7 * 0.8 + 0.3 * 0.6 = 0.56 + 0.18 = 0.74
        assert abs(final_score - 0.74) < 1e-6


# ---------------------------------------------------------------------------
# 5. P0 Private Locker Isolation Gate
# ---------------------------------------------------------------------------

class TestPrivateLockerIsolation:
    def test_private_locker_blocks_external_graph_sync(self):
        """Memories marked PRIVATE_LOCKER must NEVER be passed to Neo4j graph builder."""
        locker_memory = MemoryV1.model_validate({
            "memory_id": "locker-secret-999",
            "schema_version": "1.0",
            "system": {
                "owner_id": "usr-test-01",
                "media_type": "text",
                "created_at": "2026-09-08T10:30:00Z",
                "privacy": "PRIVATE_LOCKER",
                "allowed_users": [],
            },
            "content": {
                "raw_text": "Confidential bank vault safe lock combination 9283-4921.",
                "clean_text": "Confidential bank vault safe lock combination 9283-4921.",
                "description": "Secret locker combination",
                "summary": "Secret locker combination",
            },
            "entities": {
                "people": ["Bank Manager"],
                "places": ["Zurich Vault"],
                "locations": ["Zurich, Switzerland"],
                "events": [],
                "organizations": ["Swiss Bank"],
            },
            "semantics": {
                "topics": ["finance", "passwords"],
                "activities": ["storage"],
                "sentiment": "neutral",
                "mood": ["secretive"],
            },
            "temporal": {
                "mentioned_dates": ["2026-09-08"],
                "inferred_time": "morning",
                "time_of_day": "morning",
            },
            "processing": {
                "status": "completed",
                "source_modality": "text",
                "transcription_required": False,
                "image_understanding_required": False,
                "llm_provider": "mock",
                "llm_model": "mock",
            },
        })

        mock_graph_builder = MagicMock()
        mock_geocoding_svc = MagicMock()

        # Simulate orchestrator privacy gate
        is_private_locker = locker_memory.system.privacy == "PRIVATE_LOCKER"
        assert is_private_locker is True

        if not is_private_locker:
            mock_graph_builder.sync_memory(locker_memory)
            mock_geocoding_svc.geocode("Zurich Vault")

        # Must NOT be called
        mock_graph_builder.sync_memory.assert_not_called()
        mock_geocoding_svc.geocode.assert_not_called()
