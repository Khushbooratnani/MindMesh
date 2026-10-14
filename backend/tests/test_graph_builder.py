from app.services.graph_builder import GraphBuilder


def test_graph_builder_creates_memory_entities_and_inferred_edges():
    document = GraphBuilder().build_from_memory_row(
        {
            "memory_id": "M_1",
            "summary": "Coffee with Akshat at Cafe Bodega.",
            "media_type": "text",
            "created_at": "2026-09-01T10:00:00+00:00",
            "sentiment": "positive",
            "entities": [
                {"type": "person", "value": "Akshat"},
                {"type": "place", "value": "Cafe Bodega"},
                {"type": "location", "value": "Goa"},
            ],
            "topics": ["coffee"],
            "activities": ["having coffee"],
            "moods": ["happy"],
        }
    )

    node_keys = {(node.type, node.normalized_name) for node in document.nodes}
    relationship_types = {relationship.type for relationship in document.relationships}

    assert ("Memory", "M_1") in node_keys
    assert ("Person", "akshat") in node_keys
    assert ("Place", "cafe bodega") in node_keys
    assert ("Location", "goa") in node_keys
    assert "MENTIONS_PERSON" in relationship_types
    assert "HAPPENED_AT" in relationship_types
    assert "VISITED" in relationship_types
    assert "LOCATED_IN" in relationship_types
