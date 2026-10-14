import re
from typing import Any

from app.schemas.graph_output import GraphDocument, GraphNode, GraphRelationship


class GraphBuilder:
    def build_from_memory_row(self, row: dict[str, Any]) -> GraphDocument:
        memory_id = row["memory_id"]
        memory_node = GraphNode(
            type="Memory",
            name=memory_id,
            normalized_name=memory_id,
            properties={
                "memory_id": memory_id,
                "summary": row.get("summary"),
                "media_type": row.get("media_type"),
                "created_at": str(row.get("created_at")),
            },
        )
        document = GraphDocument(memory_id=memory_id, nodes=[memory_node])

        entities = row.get("entities") or []
        by_type: dict[str, list[GraphNode]] = {
            "person": [],
            "place": [],
            "location": [],
            "event": [],
            "organization": [],
        }
        for entity in entities:
            entity_type = entity.get("type")
            value = entity.get("value")
            if not value or entity_type not in by_type:
                continue
            node_type = _entity_node_type(entity_type)
            node = GraphNode(
                type=node_type,
                name=value,
                normalized_name=_normalize(value),
            )
            document.nodes.append(node)
            by_type[entity_type].append(node)
            document.relationships.append(
                _memory_relationship(memory_id, node, _memory_edge_type(entity_type))
            )

        for topic in row.get("topics") or []:
            self._add_named_node(document, memory_id, "Topic", topic, "HAS_TOPIC")
        for activity in row.get("activities") or []:
            self._add_named_node(document, memory_id, "Activity", activity, "HAS_ACTIVITY")
        for mood in row.get("moods") or []:
            self._add_named_node(document, memory_id, "Mood", mood, "HAS_MOOD")

        sentiment = row.get("sentiment")
        if sentiment:
            self._add_named_node(document, memory_id, "Mood", sentiment, "HAS_SENTIMENT")

        for person in by_type["person"]:
            for place in by_type["place"]:
                document.relationships.append(
                    _relationship(person, "VISITED", place, memory_id, 0.75, "deterministic")
                )

        for place in by_type["place"]:
            for location in by_type["location"]:
                document.relationships.append(
                    _relationship(place, "LOCATED_IN", location, memory_id, 0.7, "deterministic")
                )

        for event in by_type["event"]:
            document.relationships.append(
                GraphRelationship(
                    from_type="Memory",
                    from_normalized_name=memory_id,
                    type="PART_OF",
                    to_type=event.type,
                    to_normalized_name=event.normalized_name,
                    properties=_rel_props(memory_id, 0.7, "deterministic"),
                )
            )

        return _dedupe_document(document)

    def _add_named_node(
        self,
        document: GraphDocument,
        memory_id: str,
        node_type,
        name: str,
        relationship_type: str,
    ) -> None:
        if not name:
            return
        node = GraphNode(type=node_type, name=name, normalized_name=_normalize(name))
        document.nodes.append(node)
        document.relationships.append(
            _memory_relationship(memory_id, node, relationship_type)
        )


def _entity_node_type(entity_type: str):
    return {
        "person": "Person",
        "place": "Place",
        "location": "Location",
        "event": "Event",
        "organization": "Organization",
    }[entity_type]


def _memory_edge_type(entity_type: str) -> str:
    return {
        "person": "MENTIONS_PERSON",
        "place": "HAPPENED_AT",
        "location": "RELATED_TO_LOCATION",
        "event": "PART_OF",
        "organization": "MENTIONS_ORGANIZATION",
    }[entity_type]


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
    for relationship in document.relationships:
        key = (
            relationship.from_type,
            relationship.from_normalized_name,
            relationship.type,
            relationship.to_type,
            relationship.to_normalized_name,
        )
        relationships[key] = relationship

    document.nodes = list(nodes.values())
    document.relationships = list(relationships.values())
    return document
