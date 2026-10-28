import re
from typing import Any

from app.schemas.graph_output import GraphDocument, GraphNode, GraphRelationship


class GraphBuilder:
    """Constructs normalized Neo4j GraphDocuments from MemoryV1 or database output payloads."""

    def build_from_memory(self, memory_data: Any = None, memory: Any = None) -> GraphDocument:
        target = memory_data if memory_data is not None else memory
        if hasattr(target, "model_dump"):
            payload = target.model_dump()
        elif isinstance(target, dict):
            payload = target
        else:
            payload = getattr(target, "payload", {}) or {}

        memory_id = payload.get("memory_id") or payload.get("id") or "M_unknown"
        system = payload.get("system") or {}
        content = payload.get("content") or {}
        entities_data = payload.get("entities") or {}
        semantics_data = payload.get("semantics") or {}

        memory_node = GraphNode(
            type="Memory",
            name=memory_id,
            normalized_name=memory_id,
            properties={
                "memory_id": memory_id,
                "summary": content.get("summary", ""),
                "media_type": system.get("media_type", "text"),
                "created_at": str(system.get("created_at", "")),
            },
        )
        document = GraphDocument(memory_id=memory_id, nodes=[memory_node])

        by_type: dict[str, list[GraphNode]] = {
            "person": [],
            "place": [],
            "location": [],
            "event": [],
            "organization": [],
        }

        # Handle entities_data whether list of dicts (from DB) or dict with lists (MemoryV1)
        if isinstance(entities_data, dict):
            # MemoryV1 shape: {"people": [...], "places": [...], "locations": [...], "events": [...], "organizations": [...]}
            entity_mapping = [
                ("person", entities_data.get("people", [])),
                ("place", entities_data.get("places", [])),
                ("location", entities_data.get("locations", [])),
                ("event", entities_data.get("events", [])),
                ("organization", entities_data.get("organizations", [])),
            ]
            for ent_type, names in entity_mapping:
                for name in names:
                    if not name or not str(name).strip():
                        continue
                    clean_name = str(name).strip()
                    node_type = _entity_node_type(ent_type)
                    node = GraphNode(
                        type=node_type,
                        name=clean_name,
                        normalized_name=_normalize(clean_name),
                    )
                    document.nodes.append(node)
                    by_type[ent_type].append(node)
                    document.relationships.append(
                        _memory_relationship(memory_id, node, _memory_edge_type(ent_type))
                    )
        elif isinstance(entities_data, list):
            for entity in entities_data:
                if not isinstance(entity, dict):
                    continue
                ent_type = entity.get("type")
                value = entity.get("value")
                if not value or ent_type not in by_type:
                    continue
                clean_name = str(value).strip()
                node_type = _entity_node_type(ent_type)
                node = GraphNode(
                    type=node_type,
                    name=clean_name,
                    normalized_name=_normalize(clean_name),
                )
                document.nodes.append(node)
                by_type[ent_type].append(node)
                document.relationships.append(
                    _memory_relationship(memory_id, node, _memory_edge_type(ent_type))
                )

        # Semantics: topics, activities, mood, sentiment
        topics = semantics_data.get("topics", [])
        for topic in topics:
            self._add_named_node(document, memory_id, "Topic", str(topic), "HAS_TOPIC")

        activities = semantics_data.get("activities", [])
        for activity in activities:
            self._add_named_node(document, memory_id, "Activity", str(activity), "HAS_ACTIVITY")

        moods = semantics_data.get("mood", [])
        for mood in moods:
            self._add_named_node(document, memory_id, "Mood", str(mood), "HAS_MOOD")

        sentiment = semantics_data.get("sentiment")
        if sentiment and sentiment != "unknown":
            self._add_named_node(document, memory_id, "Mood", str(sentiment), "HAS_SENTIMENT")

        # Multi-hop relationships:
        # Person VISITED Place
        for person in by_type["person"]:
            for place in by_type["place"]:
                document.relationships.append(
                    _relationship(person, "VISITED", place, memory_id, 0.75, "deterministic")
                )

        # Place LOCATED_IN Location
        for place in by_type["place"]:
            for location in by_type["location"]:
                document.relationships.append(
                    _relationship(place, "LOCATED_IN", location, memory_id, 0.70, "deterministic")
                )

        # Memory PART_OF Event
        for event in by_type["event"]:
            document.relationships.append(
                GraphRelationship(
                    from_type="Memory",
                    from_normalized_name=memory_id,
                    type="PART_OF",
                    to_type=event.type,
                    to_normalized_name=event.normalized_name,
                    properties=_rel_props(memory_id, 0.70, "deterministic"),
                )
            )

        return _dedupe_document(document)

    build_graph_document = build_from_memory

    def _add_named_node(
        self,
        document: GraphDocument,
        memory_id: str,
        node_type: Any,
        name: str,
        relationship_type: str,
    ) -> None:
        clean = name.strip()
        if not clean:
            return
        node = GraphNode(type=node_type, name=clean, normalized_name=_normalize(clean))
        document.nodes.append(node)
        document.relationships.append(
            _memory_relationship(memory_id, node, relationship_type)
        )


def _entity_node_type(entity_type: str) -> str:
    return {
        "person": "Person",
        "place": "Place",
        "location": "Location",
        "event": "Event",
        "organization": "Organization",
    }.get(entity_type, "Place")


def _memory_edge_type(entity_type: str) -> str:
    return {
        "person": "MENTIONS_PERSON",
        "place": "HAPPENED_AT",
        "location": "RELATED_TO_LOCATION",
        "event": "PART_OF",
        "organization": "MENTIONS_ORGANIZATION",
    }.get(entity_type, "HAPPENED_AT")


def _memory_relationship(
    memory_id: str,
    node: GraphNode,
    relationship_type: str,
) -> GraphRelationship:
    return GraphRelationship(
        from_type="Memory",
        from_normalized_name=memory_id,
        type=relationship_type,
        to_type=node.type,
        to_normalized_name=node.normalized_name,
        properties=_rel_props(memory_id, 1.0, "phase1"),
    )


def _relationship(
    from_node: GraphNode,
    relationship_type: str,
    to_node: GraphNode,
    memory_id: str,
    confidence: float,
    source: str,
) -> GraphRelationship:
    return GraphRelationship(
        from_type=from_node.type,
        from_normalized_name=from_node.normalized_name,
        type=relationship_type,
        to_type=to_node.type,
        to_normalized_name=to_node.normalized_name,
        properties=_rel_props(memory_id, confidence, source),
    )


def _rel_props(memory_id: str, confidence: float, source: str) -> dict:
    return {
        "source_memory_id": memory_id,
        "confidence": confidence,
        "source": source,
    }


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _dedupe_document(document: GraphDocument) -> GraphDocument:
    nodes = {}
    for node in document.nodes:
        nodes[(node.type, node.normalized_name)] = node

    relationships = {}
    for rel in document.relationships:
        key = (
            rel.from_type,
            rel.from_normalized_name,
            rel.type,
            rel.to_type,
            rel.to_normalized_name,
        )
        relationships[key] = rel

    document.nodes = list(nodes.values())
    document.relationships = list(relationships.values())
    return document


_graph_builder = None


def get_graph_builder() -> GraphBuilder:
    global _graph_builder
    if _graph_builder is None:
        _graph_builder = GraphBuilder()
    return _graph_builder
