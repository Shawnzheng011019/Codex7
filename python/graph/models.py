"""
Data models for the knowledge graph.
"""
from typing import List, Dict, Any
from pydantic import BaseModel, Field
import uuid

class Node(BaseModel):
    """Represents a node in the knowledge graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str  # e.g., 'File', 'Function', 'Class'
    properties: Dict[str, Any]

class Relationship(BaseModel):
    """Represents a relationship between two nodes."""
    source_id: str
    target_id: str
    type: str  # e.g., 'IMPORTS', 'CONTAINS', 'CALLS'
    properties: Dict[str, Any] = Field(default_factory=dict)
