import logging
import re
from typing import Any, List, Optional

from app.config import settings
from app.schemas.graph_output import GraphDocument, GraphNode, GraphRelationship

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
except ImportError:
    GraphDatabase = None


class Neo4jRepository:
    """Manages Neo4j connections and Cypher graph queries with graceful offline fallback."""

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
    ):
        self.uri = uri or getattr(settings, "neo4j_uri", "bolt://localhost:7687")
        self.username = username or user or getattr(settings, "neo4j_username", "neo4j")
        self.password = password or getattr(settings, "neo4j_password", "change_me")
        self.database = database or getattr(settings, "neo4j_database", "neo4j")
        self._enabled = bool(GraphDatabase is not None and self.uri and self.password != "change_me")

    def execute_query(self, query: str, parameters: Optional[dict] = None) -> list[dict[str, Any]]:
        if not self._enabled or GraphDatabase is None:
            return []
        try:
            with GraphDatabase.driver(self.uri, auth=(self.username, self.password)) as driver:
                with driver.session(database=self.database) as session:
                    result = session.run(query, parameters or {})
                    return [record.data() for record in result]
        except Exception as exc:
            logger.warning("Neo4j query execution failed: %s", exc)
            return []

    def is_available(self) -> bool:
        if not self._enabled or GraphDatabase is None:
            return False
        try:
            with GraphDatabase.driver(self.uri, auth=(self.username, self.password)) as driver:
                driver.verify_connectivity()
                return True
        except Exception:
            return False

    def write_graph_document(self, document: GraphDocument) -> bool:
        if not self._enabled or GraphDatabase is None:
            logger.debug("Neo4j is not configured or neo4j driver not installed; skipping graph write.")
            return False

        try:
            with GraphDatabase.driver(self.uri, auth=(self.username, self.password)) as driver:
                with driver.session(database=self.database) as session:
                    session.execute_write(_write_graph_document, document)
            return True
        except Exception as exc:
            logger.warning("Failed to write to Neo4j knowledge graph: %s", exc)
            return False

    def search_memory_ids(self, query: str, limit: int = 10) -> List[dict[str, Any]]:
        terms = _query_terms(query)
        if not terms or not self._enabled or GraphDatabase is None:
            return []

        try:
            with GraphDatabase.driver(self.uri, auth=(self.username, self.password)) as driver:
                with driver.session(database=self.database) as session:
                    return session.execute_read(_search_memory_ids, terms, limit)
        except Exception as exc:
            logger.warning("Neo4j graph search failed: %s; falling back gracefully.", exc)
            return []


def _write_graph_document(tx, document: GraphDocument) -> None:
    for node in document.nodes:
        _merge_node(tx, node)
    for relationship in document.relationships:
        _merge_relationship(tx, relationship)


def _merge_node(tx, node: GraphNode) -> None:
    label = _safe_label(node.type)
    tx.run(
        f"""
        MERGE (n:{label} {{normalized_name: $normalized_name}})
        ON CREATE SET n.name = $name
        SET n += $properties
        """,
        normalized_name=node.normalized_name,
        name=node.name,
        properties=node.properties,
    )


def _merge_relationship(tx, relationship: GraphRelationship) -> None:
    from_label = _safe_label(relationship.from_type)
    to_label = _safe_label(relationship.to_type)
    rel_type = _safe_label(relationship.type)
    tx.run(
        f"""
        MATCH (from_node:{from_label} {{normalized_name: $from_normalized_name}})
        MATCH (to_node:{to_label} {{normalized_name: $to_normalized_name}})
        MERGE (from_node)-[r:{rel_type}]->(to_node)
        SET r += $properties
        """,
        from_normalized_name=relationship.from_normalized_name,
        to_normalized_name=relationship.to_normalized_name,
        properties=relationship.properties,
    )


def _search_memory_ids(tx, terms: list[str], limit: int) -> list[dict]:
    result = tx.run(
        """
        MATCH (m:Memory)-[r]-(n)
        WHERE any(term IN $terms WHERE
            toLower(coalesce(n.name, '')) CONTAINS term OR
            toLower(coalesce(n.normalized_name, '')) CONTAINS term OR
            toLower(coalesce(m.summary, '')) CONTAINS term
        )
        WITH m, collect(DISTINCT type(r)) AS relationships, count(DISTINCT n) AS matched_nodes
        RETURN
            m.memory_id AS memory_id,
            matched_nodes,
            relationships
        ORDER BY matched_nodes DESC, memory_id
        LIMIT $limit
        """,
        terms=terms,
        limit=limit,
    )
    return [dict(record) for record in result]


def _safe_label(value: str) -> str:
    cleaned = value.replace("_", "")
    if not cleaned.isalnum():
        raise ValueError(f"Unsafe Neo4j label or relationship type: {value}")
    return value


def _query_terms(query: str) -> list[str]:
    aliases = {
        "cafes": "cafe",
        "cafés": "café",
        "liked": "positive",
        "like": "positive",
        "goa trip": "goa",
    }
    stopwords = {
        "about",
        "and",
        "anything",
        "are",
        "around",
        "did",
        "for",
        "from",
        "how",
        "in",
        "is",
        "me",
        "my",
        "of",
        "on",
        "our",
        "show",
        "tell",
        "the",
        "there",
        "to",
        "was",
        "we",
        "what",
        "where",
        "which",
        "who",
        "with",
    }

    normalized = query.lower().strip()
    for source, target in aliases.items():
        normalized = normalized.replace(source, target)

    raw_tokens = re.findall(r"[A-Za-z0-9_]+", normalized)
    tokens: list[str] = []
    for token in raw_tokens:
        clean = token.strip()
        if not clean or clean in stopwords:
            continue
        if len(clean) > 3 and clean.endswith("s") and not clean.endswith("ss"):
            singular = clean[:-1]
            if singular not in stopwords:
                clean = singular
        if clean not in tokens:
            tokens.append(clean)
    return tokens


# Aliases for compatibility
Neo4jClient = Neo4jRepository
Neo4jRepository.is_connected = Neo4jRepository.is_available

_neo4j_repository: Optional[Neo4jRepository] = None


def get_neo4j_repository() -> Neo4jRepository:
    global _neo4j_repository
    if _neo4j_repository is None:
        _neo4j_repository = Neo4jRepository()
    return _neo4j_repository


get_neo4j_client = get_neo4j_repository

