from app.services.query_orchestrator import QueryOrchestrator


class FakeRepository:
    def search_similar_memories(self, owner_id, query_embedding, embedding_model, limit):
        return [
            {
                "memory_id": "M_1",
                "summary": "Coffee with Akshat.",
                "score": 0.8,
            }
        ]

    def fetch_memories_by_ids(self, owner_id, memory_ids):
        return [
            {
                "memory_id": "M_1",
                "summary": "Coffee with Akshat.",
            }
        ]


class FakeEmbeddingService:
    def embed_text(self, text):
        return [0.1, 0.2, 0.3]


class FakeNeo4jRepository:
    def search_memory_ids(self, query, limit):
        return [
            {
                "memory_id": "M_1",
                "matched_nodes": 2,
                "relationships": ["VISITED"],
            }
        ]


class NoisyGraphRepository:
    def search_memory_ids(self, query, limit):
        return [
            {
                "memory_id": "M_noise",
                "matched_nodes": 5,
                "relationships": ["HAS_TOPIC"],
            }
        ]


class OrchidRepository:
    def search_similar_memories(self, owner_id, query_embedding, embedding_model, limit):
        return [
            {
                "memory_id": "M_orchid",
                "summary": "A single tall orchid stem with purple-magenta blossoms.",
                "score": 0.58,
            }
        ]

    def fetch_memories_by_ids(self, owner_id, memory_ids):
        return [
            {
                "memory_id": "M_noise",
                "summary": "A quiet mountain temple scene.",
            }
        ]


class LocationRepository:
    def __init__(self):
        self.radii = []

    def search_similar_memories(self, owner_id, query_embedding, embedding_model, limit):
        return [
            {
                "memory_id": "M_nearby",
                "summary": "Cafe memory in a nearby area.",
                "score": 0.7,
            }
        ]

    def search_nearby_memories(self, owner_id, latitude, longitude, radius_meters, limit):
        radius_km = radius_meters / 1000
        self.radii.append(radius_km)
        if radius_km < 40:
            return []
        return [
            {
                "memory_id": "M_nearby",
                "summary": "Cafe memory in a nearby area.",
                "location": "Nearby Area",
                "latitude": latitude + 0.1,
                "longitude": longitude + 0.1,
                "distance_meters": 25000,
                "location_confidence": 0.85,
            }
        ]

    def fetch_memories_by_ids(self, owner_id, memory_ids):
        return []


class EmptyLocationRepository(LocationRepository):
    def search_nearby_memories(self, owner_id, latitude, longitude, radius_meters, limit):
        self.radii.append(radius_meters / 1000)
        return []


def test_graph_search_returns_postgres_filtered_memory_summaries():
    results = QueryOrchestrator(
        repository=FakeRepository(),
        neo4j_repository=FakeNeo4jRepository(),
        embedding_service=FakeEmbeddingService(),
    ).graph_search("which cafes did Akshat visit in Goa", "U_DEVELOPMENT")

    assert results[0]["memory_id"] == "M_1"
    assert results[0]["matched_by"] == ["graph"]


def test_hybrid_search_merges_vector_and_graph_matches():
    results = QueryOrchestrator(
        repository=FakeRepository(),
        neo4j_repository=FakeNeo4jRepository(),
        embedding_service=FakeEmbeddingService(),
    ).hybrid_search("coffee memories in Goa", "U_DEVELOPMENT")

    assert results[0]["memory_id"] == "M_1"
    assert results[0]["matched_by"] == ["vector", "graph"]
    assert results[0]["score"] > 0.8


def test_hybrid_search_does_not_let_noisy_graph_only_result_beat_vector_match():
    results = QueryOrchestrator(
        repository=OrchidRepository(),
        neo4j_repository=NoisyGraphRepository(),
        embedding_service=FakeEmbeddingService(),
    ).hybrid_search("how to take care of orchids", "U_DEVELOPMENT")

    assert results[0]["memory_id"] == "M_orchid"
    assert results[0]["matched_by"] == ["vector"]
    assert len(results) == 1


def test_location_aware_search_labels_expanded_nearby_results():
    repository = LocationRepository()

    results = QueryOrchestrator(
        repository=repository,
        neo4j_repository=NoisyGraphRepository(),
        embedding_service=FakeEmbeddingService(),
    ).location_aware_search(
        query="cafes",
        owner_id="U_DEVELOPMENT",
        latitude=30.3,
        longitude=78.0,
        radius_km=10,
    )

    assert repository.radii == [10, 20, 40]
    assert results[0]["location_match_type"] == "expanded_nearby"
    assert results[0]["search_radius_km"] == 40
    assert results[0]["distance_meters"] == 25000


def test_location_aware_search_does_not_expand_beyond_fifty_km():
    repository = EmptyLocationRepository()

    results = QueryOrchestrator(
        repository=repository,
        neo4j_repository=NoisyGraphRepository(),
        embedding_service=FakeEmbeddingService(),
    ).location_aware_search(
        query="cafes",
        owner_id="U_DEVELOPMENT",
        latitude=30.3,
        longitude=78.0,
        radius_km=10,
    )

    assert results == []
    assert repository.radii == [10, 20, 40, 50.0]


def test_location_aware_search_filters_nearby_results_that_do_not_match_topic():
    class OffTopicLocationRepository(LocationRepository):
        def search_similar_memories(self, owner_id, query_embedding, embedding_model, limit):
            return [
                {
                    "memory_id": "M_perfume",
                    "summary": "A positive visit to a perfume store in Dehradun.",
                    "score": 0.7,
                }
            ]

        def search_nearby_memories(self, owner_id, latitude, longitude, radius_meters, limit):
            self.radii.append(radius_meters / 1000)
            return [
                {
                    "memory_id": "M_perfume",
                    "summary": "A positive visit to a perfume store in Dehradun.",
                    "location": "Dehradun",
                    "latitude": latitude,
                    "longitude": longitude,
                    "distance_meters": 0,
                    "location_confidence": 0.85,
                }
            ]

    results = QueryOrchestrator(
        repository=OffTopicLocationRepository(),
        neo4j_repository=NoisyGraphRepository(),
        embedding_service=FakeEmbeddingService(),
    ).location_aware_search(
        query="temples visited",
        owner_id="U_DEVELOPMENT",
        latitude=30.3,
        longitude=78.0,
        radius_km=10,
    )

    assert results == []
