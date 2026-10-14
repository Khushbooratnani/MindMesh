from fastapi.testclient import TestClient

from app.api.routes.phase2 import (
    get_embedding_worker,
    get_graph_sync_worker,
    get_query_orchestrator,
)
from app.main import app


class FakeEmbeddingWorker:
    def run(self, limit, memory_ids):
        return {
            "processed": 2,
            "failed": 0,
            "embedding_model": "bge-m3:latest",
            "errors": [],
        }


class FakeGraphSyncWorker:
    def run(self, limit, memory_ids):
        return {
            "processed": 2,
            "failed": 0,
            "neo4j_database": "neo4j",
            "errors": [],
        }


class FakeQueryOrchestrator:
    last_limit = None

    def vector_search(self, query, owner_id, limit):
        self.last_limit = limit
        return [
            {
                "memory_id": "M_1",
                "summary": "Coffee with Akshat.",
                "score": 0.91,
                "matched_by": ["vector"],
            }
        ]

    def graph_search(self, query, owner_id, limit):
        self.last_limit = limit
        return [
            {
                "memory_id": "M_2",
                "summary": "Akshat visited Cafe Bodega in Goa.",
                "score": 1.05,
                "matched_by": ["graph"],
            }
        ]

    def hybrid_search(self, query, owner_id, limit):
        self.last_limit = limit
        return [
            {
                "memory_id": "M_1",
                "summary": "Coffee with Akshat.",
                "score": 0.94,
                "matched_by": ["vector", "graph"],
            }
        ]


def test_run_embeddings_endpoint():
    app.dependency_overrides[get_embedding_worker] = lambda: FakeEmbeddingWorker()
    client = TestClient(app)

    response = client.post("/api/v1/phase2/embeddings/run", json={"limit": 2})

    assert response.status_code == 200
    assert response.json()["processed"] == 2
    assert response.json()["embedding_model"] == "bge-m3:latest"
    app.dependency_overrides.clear()


def test_sync_graph_endpoint():
    app.dependency_overrides[get_graph_sync_worker] = lambda: FakeGraphSyncWorker()
    client = TestClient(app)

    response = client.post("/api/v1/phase2/graph/sync", json={"limit": 2})

    assert response.status_code == 200
    assert response.json()["processed"] == 2
    assert response.json()["neo4j_database"] == "neo4j"
    app.dependency_overrides.clear()


def test_vector_search_endpoint():
    app.dependency_overrides[get_query_orchestrator] = lambda: FakeQueryOrchestrator()
    client = TestClient(app)

    response = client.post(
        "/api/v1/search",
        json={"query": "coffee memories", "mode": "vector", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["memory_id"] == "M_1"
    app.dependency_overrides.clear()


def test_graph_search_endpoint():
    app.dependency_overrides[get_query_orchestrator] = lambda: FakeQueryOrchestrator()
    client = TestClient(app)

    response = client.post(
        "/api/v1/search",
        json={"query": "Which cafes did Akshat visit in Goa?", "mode": "graph", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["memory_id"] == "M_2"
    assert response.json()["results"][0]["matched_by"] == ["graph"]
    app.dependency_overrides.clear()


def test_hybrid_search_endpoint():
    app.dependency_overrides[get_query_orchestrator] = lambda: FakeQueryOrchestrator()
    client = TestClient(app)

    response = client.post(
        "/api/v1/search",
        json={"query": "coffee memories in Goa", "mode": "hybrid", "limit": 5},
    )

    assert response.status_code == 200
    assert response.json()["results"][0]["matched_by"] == ["vector", "graph"]
    app.dependency_overrides.clear()


def test_search_endpoint_defaults_to_top_five_results():
    orchestrator = FakeQueryOrchestrator()
    app.dependency_overrides[get_query_orchestrator] = lambda: orchestrator
    client = TestClient(app)

    response = client.post(
        "/api/v1/search",
        json={"query": "architecture memories"},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid"
    assert orchestrator.last_limit == 5
    assert "score" in response.json()["results"][0]
    app.dependency_overrides.clear()
