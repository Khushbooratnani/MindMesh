import unicodedata

from app.config import settings
from app.db.neo4j import _query_terms
from app.db.neo4j import Neo4jRepository
from app.db.postgres import PostgresRepository
from app.services.embedding_service import EmbeddingService


MIN_VECTOR_SCORE = 0.45
MIN_HYBRID_SCORE = 0.45
GRAPH_ONLY_HYBRID_WEIGHT = 0.25
MAX_NEARBY_FALLBACK_RADIUS_KM = 50.0


class QueryOrchestrator:
    def __init__(
        self,
        repository: PostgresRepository | None = None,
        neo4j_repository: Neo4jRepository | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.repository = repository or PostgresRepository()
        self.neo4j_repository = neo4j_repository or Neo4jRepository()
        self.embedding_service = embedding_service or EmbeddingService()

    def vector_search(self, query: str, owner_id: str, limit: int = 5) -> list[dict]:
        query_embedding = self.embedding_service.embed_text(query)
        rows = self.repository.search_similar_memories(
            owner_id=owner_id,
            query_embedding=query_embedding,
            embedding_model=settings.embedding_model,
            limit=limit,
        )
        return [
            {
                "memory_id": row["memory_id"],
                "summary": row["summary"],
                "score": float(row["score"]),
                "matched_by": ["vector"],
            }
            for row in rows
            if float(row["score"]) >= MIN_VECTOR_SCORE
        ]

    def graph_search(self, query: str, owner_id: str, limit: int = 5) -> list[dict]:
        graph_rows = self.neo4j_repository.search_memory_ids(query=query, limit=limit)
        memory_ids = [row["memory_id"] for row in graph_rows]
        summaries = self.repository.fetch_memories_by_ids(owner_id=owner_id, memory_ids=memory_ids)
        summary_by_id = {row["memory_id"]: row["summary"] for row in summaries}

        results = []
        for index, row in enumerate(graph_rows):
            memory_id = row["memory_id"]
            if memory_id not in summary_by_id:
                continue
            matched_nodes = int(row.get("matched_nodes") or 0)
            score = max(0.0, 1.0 - (index * 0.1)) + min(matched_nodes, 5) * 0.05
            results.append(
                {
                    "memory_id": memory_id,
                    "summary": summary_by_id[memory_id],
                    "score": round(score, 4),
                    "matched_by": ["graph"],
                }
            )
        return results

    def hybrid_search(self, query: str, owner_id: str, limit: int = 5) -> list[dict]:
        vector_results = self.vector_search(query=query, owner_id=owner_id, limit=limit)
        graph_results = self.graph_search(query=query, owner_id=owner_id, limit=limit)

        merged: dict[str, dict] = {}
        for result in vector_results:
            merged[result["memory_id"]] = {
                **result,
                "score": result["score"],
                "matched_by": ["vector"],
            }

        for result in graph_results:
            if result["memory_id"] in merged:
                merged[result["memory_id"]]["score"] += result["score"] * GRAPH_ONLY_HYBRID_WEIGHT
                merged[result["memory_id"]]["matched_by"] = ["vector", "graph"]
            else:
                merged[result["memory_id"]] = {
                    **result,
                    "score": result["score"] * GRAPH_ONLY_HYBRID_WEIGHT,
                    "matched_by": ["graph"],
                }

        return sorted(
            (
                {**result, "score": round(float(result["score"]), 4)}
                for result in merged.values()
                if float(result["score"]) >= MIN_HYBRID_SCORE
            ),
            key=lambda item: item["score"],
            reverse=True,
        )[:limit]

    def location_aware_search(
        self, query: str, owner_id: str, latitude: float, longitude: float,
        radius_km: float, limit: int = 5,
    ) -> list[dict]:
        text_results = self.hybrid_search(query=query, owner_id=owner_id, limit=100)
        query_terms = _query_terms(query)
        nearby_results = []
        candidate_radius = radius_km
        while candidate_radius <= MAX_NEARBY_FALLBACK_RADIUS_KM:
            nearby_results = self.nearby_search(
                owner_id=owner_id, latitude=latitude, longitude=longitude,
                radius_km=candidate_radius, limit=100,
            )
            if nearby_results:
                break
            candidate_radius *= 2
        if not nearby_results and radius_km < MAX_NEARBY_FALLBACK_RADIUS_KM < candidate_radius:
            candidate_radius = MAX_NEARBY_FALLBACK_RADIUS_KM
            nearby_results = self.nearby_search(
                owner_id=owner_id, latitude=latitude, longitude=longitude,
                radius_km=candidate_radius, limit=100,
            )
        if not nearby_results:
            return []
        location_match_type = (
            "within_requested_radius"
            if candidate_radius <= radius_km
            else "expanded_nearby"
        )
        nearby_by_id = {row["memory_id"]: row for row in nearby_results}
        results = []
        for result in text_results:
            nearby = nearby_by_id.get(result["memory_id"])
            if nearby is None:
                continue
            if not _passes_location_text_gate(result, query_terms):
                continue
            results.append({
                **result,
                "score": round(float(result["score"]) * 0.7 + nearby["score"] * 0.3, 4),
                "matched_by": sorted(set(result["matched_by"] + ["postgis"])),
                "location": nearby["location"],
                "latitude": nearby["latitude"],
                "longitude": nearby["longitude"],
                "distance_meters": nearby["distance_meters"],
                "location_confidence": nearby["location_confidence"],
                "location_match_type": location_match_type,
                "search_radius_km": candidate_radius,
            })
        return sorted(results, key=lambda row: row["score"], reverse=True)[:limit]

    def nearby_search(self, owner_id: str, latitude: float, longitude: float, radius_km: float, limit: int = 5) -> list[dict]:
        rows = self.repository.search_nearby_memories(
            owner_id=owner_id, latitude=latitude, longitude=longitude,
            radius_meters=radius_km * 1000, limit=limit,
        )
        return [
            {
                "memory_id": row["memory_id"],
                "summary": row["summary"],
                "score": round(max(0.0, 1.0 - float(row["distance_meters"]) / (radius_km * 1000)), 4),
                "matched_by": ["postgis"],
                "location": row["location"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "distance_meters": round(float(row["distance_meters"]), 2),
                "location_confidence": float(row["location_confidence"]),
            }
            for row in rows
        ]


def _passes_location_text_gate(result: dict, query_terms: list[str]) -> bool:
    if not query_terms:
        return True
    if "graph" in result.get("matched_by", []):
        return True
    summary = _fold_text(result.get("summary", ""))
    return any(term in summary for term in query_terms)


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(character for character in normalized if not unicodedata.combining(character))
