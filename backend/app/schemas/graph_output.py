from typing import Literal

from pydantic import BaseModel, Field


GraphNodeType = Literal[
    "Memory",
    "Person",
    "Place",
    "Location",
    "Event",
    "Organization",
    "Topic",
    "Activity",
    "Mood",
    "FoodDrink",
    "Attribute",
]


class GraphNode(BaseModel):
    type: GraphNodeType
    name: str
    normalized_name: str
    properties: dict = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    from_type: GraphNodeType
    from_normalized_name: str
    type: str
    to_type: GraphNodeType
    to_normalized_name: str
    properties: dict = Field(default_factory=dict)


class GraphDocument(BaseModel):
    memory_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    relationships: list[GraphRelationship] = Field(default_factory=list)
