import re

from neo4j import GraphDatabase

from app.config import settings
from app.schemas.graph_output import GraphDocument, GraphNode, GraphRelationship


class Neo4jRepository:
    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ):
        self.uri = uri or settings.neo4j_uri
        self.username = username or settings.neo4j_username
        self.password = password or settings.neo4j_password
        self.database = database or settings.neo4j_database

    def write_graph_document(self, document: GraphDocument) -> None:
        with GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
        ) as driver:
            with driver.session(database=self.database) as session:
                session.execute_write(_write_graph_document, document)

    def search_memory_ids(self, query: str, limit: int = 10) -> list[dict]:
        terms = _query_terms(query)
        with GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
        ) as driver:
            with driver.session(database=self.database) as session:
                return session.execute_read(_search_memory_ids, terms, limit)


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
    if not value.replace("_", "").isalnum():
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
        "at",
        "available",
        "care",
        "can",
        "could",
        "did",
        "does",
        "find",
        "for",
        "from",
        "give",
        "have",
        "how",
        "in",
        "is",
        "into",
        "near",
        "memories",
        "memory",
        "mention",
        "mentions",
        "our",
        "people",
        "please",
        "query",
        "search",
        "show",
        "take",
        "tell",
        "that",
        "the",
        "things",
        "this",
        "what",
        "when",
        "where",
        "which",
        "with",
        "would",
        "visit",
        "visited",
        "visiting",
        "places",
        "place",
    }
    normalized = query.lower()
    terms = []
    for source, target in aliases.items():
        if source in normalized:
            terms.append(target)
    for raw_term in re.sub(r"[^a-z0-9]+", " ", normalized).split():
        term = _normalize_query_term(raw_term.strip())
        if len(term) >= 3 and term not in stopwords:
            terms.append(term)
    return sorted(set(terms))


def _normalize_query_term(term: str) -> str:
    irregular = {
        "children": "child",
        "men": "man",
        "women": "woman",
    }
    if term in irregular:
        return irregular[term]
    if len(term) > 4 and term.endswith("ies"):
        return term[:-3] + "y"
    if len(term) > 5 and term.endswith(("ches", "shes")):
        return term[:-2]
    if len(term) > 4 and term.endswith(("ses", "xes", "zes")):
        return term[:-2]
    if len(term) > 3 and term.endswith("s"):
        return term[:-1]
    return term
