"""
MemorySearchService — Phase 2 + Phase 3 Tri-Modal Retrieval
============================================================
Pipeline:
  1. Embed the natural-language query (BAAI/bge-m3, 1024-dim).
  2. Vector search in PostgreSQL pgvector with privacy/ACL pre-filter.
  3. [Phase 3] If `mode` includes graph: query Neo4j and merge results (fail-soft).
  4. [Phase 3] If location parameters present: geocode, expanding-radius nearby search,
     geographic-semantic score fusion, and topic gate.
  5. LLM grounds a natural-language answer over the top-k results.
  6. Return structured MemorySearchResponse with optional location metadata.

Score fusion formula:
    Score_hybrid  = Score_vector + 0.25 * Score_graph
    Score_distance = max(0, 1 - distance_m / radius_m)
    Final          = 0.7 * Score_hybrid + 0.3 * Score_distance
"""
import math
import unicodedata
import uuid
from typing import Any, Optional

from sqlalchemy import text as _sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.errors import MemorySearchError
from app.database.repositories.phase2_embedding_repo import Phase2EmbeddingRepository
from app.schemas.search_schemas import MemorySearchResponse, MemorySearchResult
from app.services.embedding_service import EmbeddingService, EmbeddingGenerationError
from app.services.llm_service import LLMService
from app.services.crypto_service import locker_crypto

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GRAPH_ONLY_HYBRID_WEIGHT = 0.25
LOCATION_WEIGHT = 0.3
HYBRID_WEIGHT = 0.7
MIN_VECTOR_SCORE = 0.45
EXPANDING_RADIUS_STEPS_KM = [10.0, 20.0, 40.0, 50.0]
MAX_NEARBY_FALLBACK_RADIUS_KM = 50.0


# ---------------------------------------------------------------------------
# Text-gate helpers (adapted from Major/backend, now self-contained)
# ---------------------------------------------------------------------------

def _fold_text(value: str) -> str:
    """NFKD-normalise → lowercase → strip combining marks."""
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _query_terms(query: str) -> list[str]:
    """Return normalised, non-trivial tokens from a search query."""
    _STOP = {
        "a", "an", "the", "is", "in", "at", "on", "of", "for",
        "to", "my", "me", "i", "and", "or", "not", "with", "near",
        "around", "find", "show", "get", "where", "what",
    }
    return [
        t for t in _fold_text(query).split()
        if t not in _STOP and len(t) > 2
    ]


def _passes_location_text_gate(result: dict, query_terms: list[str]) -> bool:
    """
    Return True if the result is topically related to the query.
    Nearby-only matches that are clearly off-topic (e.g., searching "café"
    but getting a nearby temple) are filtered out unless the Knowledge Graph
    already linked them explicitly or vector similarity is sufficiently high.
    """
    if not query_terms:
        return True
    if "graph" in result.get("matched_by", []):
        return True
    if float(result.get("similarity_score", 0.0)) >= 0.35:
        return True
    summary = _fold_text(result.get("summary", "") or result.get("clean_text", "") or "")
    return any(term in summary for term in query_terms)


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Pure-Python Haversine fallback when PostGIS is unavailable."""
    R = 6_371_000.0  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class MemorySearchService:
    """
    Orchestrator for Semantic Retrieval across Phase 2 Dual-Vector Embeddings.

    Extended in Phase 3 to support:
    - Knowledge Graph (Neo4j) hybrid retrieval.
    - Location-Aware Nearby Search with expanding radius fallback.
    - Geographic × Semantic score fusion.
    - Topic Gate to discard off-topic nearby matches.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None,
        embedding_repo: Optional[Phase2EmbeddingRepository] = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        self.llm_service = llm_service or LLMService()
        self.embedding_repo = embedding_repo or Phase2EmbeddingRepository()

    # ------------------------------------------------------------------
    # Privacy enforcement (unchanged from Phase 2)
    # ------------------------------------------------------------------

    def _can_read(self, memory_json: dict[str, Any], user_id: str, locker_session_valid: bool = False) -> bool:
        """Enforces privacy rules for memories (default-deny)."""
        if not memory_json:
            return False
        system = memory_json.get("system", {})
        owner_id = system.get("owner_id")
        privacy = (system.get("privacy") or "ONLY_ME").upper()
        allowed_users = system.get("allowed_users", [])

        # 1. Private Locker isolation firewall
        if privacy == "PRIVATE_LOCKER":
            return owner_id == user_id and locker_session_valid

        # 2. Personal ownership
        if owner_id == user_id or owner_id in ("U_DEVELOPMENT", "U_DATASET_RUNNER"):
            return True

        # 3. Explicitly public memories
        if privacy == "PUBLIC":
            return True

        # 4. Explicitly allowed users in payload
        if privacy in ("SELECTED", "CUSTOM", "SHARED") and user_id in allowed_users:
            return True

        # 5. Development mode fallback (non-private memories only)
        if not user_id or user_id in ("U_DEVELOPMENT", "U_DATASET_RUNNER"):
            return True

        return False

    # ------------------------------------------------------------------
    # Phase 3: Neo4j graph query (fail-soft)
    # ------------------------------------------------------------------

    def _graph_search(self, query: str, user_id: str, limit: int = 50) -> list[dict]:
        """Query Neo4j Knowledge Graph; returns [] gracefully if unavailable."""
        try:
            from app.database.neo4j import Neo4jRepository
            repo = Neo4jRepository()
            if not repo.is_available():
                return []
            return repo.search(query=query, owner_id=user_id, limit=limit)
        except Exception as exc:
            logger.debug("[Phase 3] Graph search skipped: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Phase 3: Nearby spatial search (PostGIS → Haversine fallback)
    # ------------------------------------------------------------------

    async def _nearby_search(
        self,
        session: AsyncSession,
        user_id: str,
        latitude: float,
        longitude: float,
        radius_km: float,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch memories near (lat, lon) within radius_km using spatial distance calculation."""
        radius_m = radius_km * 1000.0

        try:
            plain_sql = _sql_text(
                """
                WITH candidate AS (
                    SELECT
                        p.memory_id,
                        p.payload->'content'->>'summary' AS summary,
                        p.payload             AS memory_json,
                        l.display_name        AS location,
                        l.latitude,
                        l.longitude,
                        ml.confidence         AS location_confidence,
                        ROW_NUMBER() OVER (PARTITION BY p.memory_id ORDER BY ml.confidence DESC) AS rn
                    FROM memory_locations ml
                    JOIN phase1_outputs p ON p.memory_id = ml.memory_id
                    JOIN locations l ON l.location_id = ml.location_id
                    WHERE (
                        p.owner_id = :uid
                        OR p.owner_id = 'U_DEVELOPMENT'
                        OR p.owner_id = 'U_DATASET_RUNNER'
                        OR p.payload->'system'->>'privacy' = 'PUBLIC'
                    )
                    AND (p.payload->'system'->>'privacy' IS NULL OR p.payload->'system'->>'privacy' != 'PRIVATE_LOCKER')
                    AND l.latitude IS NOT NULL AND l.longitude IS NOT NULL
                )
                SELECT * FROM candidate WHERE rn = 1
                """
            )
            rows = (await session.execute(plain_sql, {"uid": user_id})).mappings().all()

            results = []
            for row in rows:
                dist = _haversine_meters(
                    latitude, longitude,
                    float(row["latitude"]), float(row["longitude"]),
                )
                if dist <= radius_m:
                    results.append({
                        "memory_id": str(row["memory_id"]),
                        "summary": row.get("summary", ""),
                        "score": round(max(0.0, 1.0 - dist / radius_m), 4),
                        "matched_by": ["haversine"],
                        "location": row.get("location"),
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "distance_meters": round(dist, 2),
                        "location_confidence": float(row.get("location_confidence") or 1.0),
                        "memory_json": row.get("memory_json") or {},
                    })
            results.sort(key=lambda r: r["distance_meters"])
            logger.info("[Nearby] Found %d memories within %s km of (%s, %s)", len(results), radius_km, latitude, longitude)
            for res in results[:5]:
                logger.info("[Nearby]   - %s: %s m away (id=%s)", res["location"], res["distance_meters"], res["memory_id"])
            return results[:limit]
        except Exception as exc:
            logger.warning("[Phase 3] Spatial query failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Phase 3: Location-aware search strictly within radius_km
    # ------------------------------------------------------------------

    async def _location_aware_search(
        self,
        session: AsyncSession,
        vector_results: list[dict],
        user_id: str,
        latitude: float,
        longitude: float,
        radius_km: float,
        query_terms: list[str],
        limit: int,
        mode: str = "hybrid",
    ) -> list[dict]:
        """
        Nearby search strictly within radius_km fused with vector/graph hybrid scores.
        """
        nearby_results = await self._nearby_search(
            session=session, user_id=user_id,
            latitude=latitude, longitude=longitude,
            radius_km=radius_km, limit=100,
        )

        logger.info("[Nearby] _location_aware_search: nearby_results=%d, vector_results=%d", len(nearby_results), len(vector_results))

        if not nearby_results:
            return []  # No memories within requested radius

        location_match_type = "within_requested_radius"
        nearby_by_id = {r["memory_id"]: r for r in nearby_results}
        radius_m = radius_km * 1000.0

        fused: list[dict] = []
        fused_ids = set()
        for result in vector_results:
            nearby = nearby_by_id.get(result["memory_id"])
            if nearby is None:
                continue
            if not _passes_location_text_gate(result, query_terms):
                logger.info("[Nearby] Memory %s failed text gate with terms %s", result["memory_id"], query_terms)
                continue

            score_hybrid = float(result.get("similarity_score") or result.get("score", 0.0))
            score_distance = max(0.0, 1.0 - float(nearby["distance_meters"]) / radius_m)
            final_score = round(HYBRID_WEIGHT * score_hybrid + LOCATION_WEIGHT * score_distance, 4)

            fused.append({
                **result,
                "score": final_score,
                "matched_by": sorted(set(result.get("matched_by", ["vector"]) + nearby["matched_by"])),
                "location": nearby["location"],
                "latitude": nearby["latitude"],
                "longitude": nearby["longitude"],
                "distance_meters": nearby["distance_meters"],
                "location_confidence": nearby["location_confidence"],
                "location_match_type": location_match_type,
                "search_radius_km": radius_km,
            })
            fused_ids.add(result["memory_id"])

        # When in 'nearby' mode or if vector search missed nearby candidate spots, include them
        for nearby in nearby_results:
            mid = nearby["memory_id"]
            if mid not in fused_ids:
                dist_score = max(0.0, 1.0 - float(nearby["distance_meters"]) / radius_m)
                mem_json = nearby.get("memory_json") or {}
                content = mem_json.get("content", {})
                summary = nearby.get("summary") or content.get("summary") or content.get("clean_text") or ""
                fused.append({
                    "memory_id": mid,
                    "similarity_score": round(dist_score, 4),
                    "score": round(dist_score * (0.85 if mode == "nearby" else 0.5), 4),
                    "matched_by": ["haversine"],
                    "summary": summary,
                    "location": nearby["location"],
                    "latitude": nearby["latitude"],
                    "longitude": nearby["longitude"],
                    "distance_meters": nearby["distance_meters"],
                    "location_confidence": nearby["location_confidence"],
                    "location_match_type": location_match_type,
                    "search_radius_km": radius_km,
                    "memory_json": mem_json,
                })

        logger.info("[Nearby] Fused results count: %d", len(fused))
        if mode == "nearby":
            fused.sort(key=lambda r: (r.get("distance_meters", 999999), -r["score"]))
        else:
            fused.sort(key=lambda r: r["score"], reverse=True)
        return fused[:limit]

    # ------------------------------------------------------------------
    # Main search entrypoint (backward-compatible)
    # ------------------------------------------------------------------

    async def search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int = 5,
        user_id: Optional[str] = "U_DEVELOPMENT",
        content_weight: Optional[float] = None,
        context_weight: Optional[float] = None,
        locker_session_valid: bool = False,
        group_id: Optional[Any] = None,
        # Phase 3 location parameters
        location_query: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_km: Optional[float] = None,
        mode: str = "hybrid",  # "hybrid" | "nearby" | "graph" | "vector"
    ) -> MemorySearchResponse:
        cw = content_weight if content_weight is not None else settings.default_content_weight
        ctx_w = context_weight if context_weight is not None else settings.default_context_weight
        effective_user_id = user_id or "U_DEVELOPMENT"

        # Resolve location parameters ONLY if radius_km is specified, location_query is set, or mode == 'nearby'
        is_spatial_search = (radius_km is not None and radius_km > 0) or bool(location_query) or (mode == "nearby")

        if is_spatial_search:
            from app.services.geocoding_service import LocationIQGeocoder
            geocoder = LocationIQGeocoder()

            if location_query and (latitude is None or longitude is None):
                try:
                    geo = geocoder.geocode(location_query)
                    if geo:
                        latitude = geo.get("latitude")
                        longitude = geo.get("longitude")
                        logger.info("[Phase 3] Geocoded '%s' → (%s, %s)", location_query, latitude, longitude)
                except Exception as exc:
                    logger.warning("[Phase 3] Geocoding failed for '%s': %s", location_query, exc)

            # If radius_km is specified but no coordinates yet, check if query contains any known location name
            if (latitude is None or longitude is None):
                q_lower = query.lower()
                for place_name in ["goa", "panjim", "dehradun", "pune", "delhi", "mumbai", "mussoorie", "rishikesh", "bengaluru", "indiranagar", "jaipur"]:
                    if place_name in q_lower:
                        try:
                            geo = geocoder.geocode(place_name)
                            if geo:
                                latitude = geo.get("latitude")
                                longitude = geo.get("longitude")
                                if not location_query:
                                    location_query = place_name.title()
                                logger.info("[Phase 3] Inferred location from query: '%s' → (%s, %s)", place_name, latitude, longitude)
                                break
                        except Exception:
                            pass

            # If radius_km is specified and still no coordinates, default to user's home location (Dehradun)
            if (latitude is None or longitude is None) and (radius_km is not None or mode == "nearby"):
                latitude = 30.3164945
                longitude = 78.0321918
                if not location_query:
                    location_query = "Dehradun"

        # Group membership check (unchanged from Phase 2)
        target_group_uuid: Optional[uuid.UUID] = None
        if group_id:
            try:
                target_group_uuid = group_id if isinstance(group_id, uuid.UUID) else uuid.UUID(str(group_id))
            except Exception:
                target_group_uuid = None

            if target_group_uuid:
                from app.services.group_service import GroupService
                try:
                    await GroupService.verify_membership(
                        session=session,
                        group_id=target_group_uuid,
                        user_id=effective_user_id,
                    )
                except Exception:
                    return MemorySearchResponse(
                        query=query,
                        answer=f'I couldn\'t find any stored memory in this group related to "{query}".',
                        grounded=False,
                        results=[],
                        total_results=0,
                    )

        # 1. Generate query vector (1024-dim)
        try:
            query_vector = self.embedding_service.generate_embedding(query)
        except EmbeddingGenerationError as exc:
            raise MemorySearchError(f"Query embedding generation failed: {str(exc)}") from exc

        # 2. Vector search in PostgreSQL pgvector
        try:
            candidates = await self.embedding_repo.search_by_vectors(
                session=session,
                query_vector=query_vector,
                user_id=effective_user_id,
                content_weight=cw,
                context_weight=ctx_w,
                top_k=max(top_k * 4, 30),
                locker_session_valid=locker_session_valid,
                group_id=target_group_uuid,
            )
        except Exception as exc:
            raise MemorySearchError(f"Vector search failed: {str(exc)}") from exc

        # 3. Defense-in-depth post-filter & Relevance Gate
        accessible = []
        for cand in candidates:
            m_json = cand.get("memory_json", {})
            sys_meta = m_json.get("system", {})
            priv = (sys_meta.get("privacy") or "ONLY_ME").upper()
            if priv == "PRIVATE_LOCKER" and not (sys_meta.get("owner_id") == effective_user_id and locker_session_valid):
                continue
            accessible.append(cand)

        min_threshold = (
            -1.0
            if (self.embedding_service.force_mock or settings.embedding_force_mock)
            else settings.search_min_relevance_score
        )
        relevant = [c for c in accessible if c.get("similarity_score", 0.0) >= min_threshold]

        # 4. Phase 3: Graph search merge (fail-soft)
        graph_results: list[dict] = []
        if mode in ("hybrid", "graph") and settings.neo4j_enabled:
            graph_results = self._graph_search(query=query, user_id=effective_user_id, limit=50)

        # Build unified result map (memory_id → score dict)
        vector_map: dict[str, dict] = {}
        for cand in relevant:
            mem_json = cand.get("memory_json", {})
            content_meta = mem_json.get("content", {})
            vector_map[str(cand["memory_id"])] = {
                "memory_id": str(cand["memory_id"]),
                "similarity_score": cand["similarity_score"],
                "score": cand["similarity_score"],
                "matched_by": ["vector"],
                "summary": content_meta.get("summary") or content_meta.get("clean_text") or "",
                **{k: v for k, v in cand.items() if k not in ("memory_json",)},
                "memory_json": mem_json,
            }

        # Merge graph hits
        for graph_hit in graph_results:
            mid = str(graph_hit.get("memory_id", ""))
            if not mid:
                continue
            if mid in vector_map:
                existing = vector_map[mid]
                g_score = float(graph_hit.get("score", 0.0))
                existing["score"] = round(existing["score"] + GRAPH_ONLY_HYBRID_WEIGHT * g_score, 4)
                existing["matched_by"] = sorted(set(existing["matched_by"] + ["graph"]))
            else:
                vector_map[mid] = {
                    "memory_id": mid,
                    "similarity_score": float(graph_hit.get("score", 0.0)),
                    "score": float(graph_hit.get("score", 0.0)),
                    "matched_by": ["graph"],
                    "summary": graph_hit.get("summary", ""),
                    "memory_json": {},
                }

        merged_results = sorted(vector_map.values(), key=lambda r: r["score"], reverse=True)

        # 5. Phase 3: Location-aware fusion (if explicit radius or spatial search is requested)
        has_location = (
            latitude is not None and longitude is not None and (radius_km is not None or mode == "nearby")
        )
        if has_location and mode in ("hybrid", "nearby"):
            query_terms = _query_terms(query)
            merged_results = await self._location_aware_search(
                session=session,
                vector_results=merged_results,
                user_id=effective_user_id,
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km or 10.0,
                query_terms=query_terms,
                limit=top_k * 2,
                mode=mode,
            )

        if not merged_results:
            loc_detail = f" within {radius_km:g} km of {location_query or 'your search location'}" if has_location and radius_km else ""
            return MemorySearchResponse(
                query=query,
                answer=f'I couldn\'t find any stored memory{loc_detail} related to "{query}". Try expanding the search radius.',
                grounded=False,
                results=[],
                total_results=0,
            )

        selected = merged_results[:top_k]

        # 6. Decrypt and prepare memories for LLM
        memories_for_llm = []
        for r in selected:
            mem_json = r.get("memory_json")
            if not mem_json:
                continue
            m_copy = dict(mem_json)
            c_copy = dict(m_copy.get("content", {}))
            for field in ("clean_text", "raw_text", "summary"):
                if c_copy.get(field):
                    c_copy[field] = locker_crypto.decrypt(c_copy[field])
            # Inject location context into LLM memories
            if r.get("location"):
                c_copy["_location_context"] = (
                    f"{r['location']} ({r.get('distance_meters', 0):.0f}m away)"
                )
            m_copy["content"] = c_copy
            memories_for_llm.append(m_copy)

        # 7. Generate grounded answer
        answer = self.llm_service.answer_from_memories(
            query=query,
            memories=memories_for_llm,
        )

        # 8. Format structured results
        results = []
        for r in selected:
            mem = dict(r.get("memory_json") or {})
            system_meta = mem.get("system", {})
            content_meta = mem.get("content", {})
            media_meta = dict(mem.get("media", {})) if mem.get("media") else {}

            storage_key = (
                media_meta.get("storage_key")
                or system_meta.get("media_reference")
                or (media_meta.get("relative_path") if media_meta.get("relative_path") else None)
            )
            if storage_key:
                if not media_meta.get("storage_key"):
                    media_meta["storage_key"] = storage_key
                if not media_meta.get("url"):
                    media_meta["url"] = f"/api/v1/media/{storage_key}"
                mem["media"] = media_meta

            raw_clean_text = content_meta.get("clean_text") or content_meta.get("raw_text")
            decrypted_clean_text = locker_crypto.decrypt(raw_clean_text) if raw_clean_text else None
            raw_summary = content_meta.get("summary") or content_meta.get("clean_text")
            decrypted_summary = locker_crypto.decrypt(raw_summary) if raw_summary else None

            results.append(
                MemorySearchResult(
                    memory_id=r["memory_id"],
                    similarity_score=round(r.get("similarity_score", r.get("score", 0.0)), 4),
                    score=round(r.get("score", 0.0), 4),
                    source_modality=system_meta.get("media_type", "text").upper(),
                    user_context=mem.get("user_context"),
                    clean_text=decrypted_clean_text,
                    media=media_meta if media_meta else None,
                    content_score=round(r.get("content_score", 0.0), 4) if r.get("content_score") is not None else None,
                    context_score=round(r.get("context_score", 0.0), 4) if r.get("context_score") is not None else None,
                    summary=decrypted_summary,
                    entities=mem.get("entities"),
                    semantics=mem.get("semantics"),
                    memory=mem,
                    # Phase 3 location enrichment (optional fields, backward-compat)
                    matched_by=r.get("matched_by"),
                    location=r.get("location"),
                    latitude=r.get("latitude"),
                    longitude=r.get("longitude"),
                    distance_meters=r.get("distance_meters"),
                    location_match_type=r.get("location_match_type"),
                    search_radius_km=r.get("search_radius_km"),
                )
            )

        return MemorySearchResponse(
            query=query,
            answer=answer,
            grounded=True,
            results=results,
            total_results=len(results),
        )

    # ------------------------------------------------------------------
    # Convenience: pure nearby search (coordinates only, no text query)
    # ------------------------------------------------------------------

    async def search_nearby(
        self,
        session: AsyncSession,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        user_id: str = "U_DEVELOPMENT",
        limit: int = 20,
    ) -> MemorySearchResponse:
        """Pure proximity search — no vector embedding, no LLM answer."""
        nearby = await self._nearby_search(
            session=session, user_id=user_id,
            latitude=latitude, longitude=longitude,
            radius_km=radius_km, limit=limit,
        )

        # Expanding radius fallback
        if not nearby:
            for r in EXPANDING_RADIUS_STEPS_KM:
                if r <= radius_km:
                    continue
                nearby = await self._nearby_search(
                    session=session, user_id=user_id,
                    latitude=latitude, longitude=longitude,
                    radius_km=r, limit=limit,
                )
                if nearby:
                    radius_km = r
                    break

        results = []
        for r in nearby:
            results.append(
                MemorySearchResult(
                    memory_id=r["memory_id"],
                    similarity_score=r["score"],
                    score=r["score"],
                    source_modality="TEXT",
                    summary=r.get("summary"),
                    memory={},
                    matched_by=r.get("matched_by"),
                    location=r.get("location"),
                    latitude=r.get("latitude"),
                    longitude=r.get("longitude"),
                    distance_meters=r.get("distance_meters"),
                    search_radius_km=radius_km,
                )
            )

        return MemorySearchResponse(
            query=f"Nearby ({latitude}, {longitude}) within {radius_km} km",
            answer=None,
            grounded=False,
            results=results,
            total_results=len(results),
        )
