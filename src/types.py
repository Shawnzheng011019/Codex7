from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path


class FileType(Enum):
    """File type enumeration."""
    CODE = "code"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    MARKUP = "markup"
    UNKNOWN = "unknown"


@dataclass
class CodeFile:
    """Represents a code file in the codebase."""
    path: str
    absolute_path: str
    file_type: FileType
    language: Optional[str] = None
    size: int = 0
    last_modified: float = 0.0
    content: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "absolute_path": self.absolute_path,
            "file_type": self.file_type.value,
            "language": self.language,
            "size": self.size,
            "last_modified": self.last_modified,
        }


@dataclass
class CodeChunk:
    """Represents a chunk of code with metadata."""
    id: str
    file_path: str
    content: str
    start_line: int
    end_line: int
    language: str
    chunk_type: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
        }


@dataclass
class SearchResult:
    """Represents a search result."""
    chunk: CodeChunk
    score: float
    rank: int
    search_type: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "rank": self.rank,
            "search_type": self.search_type,
            "metadata": self.metadata,
        }


@dataclass
class GraphNode:
    """Represents a node in the code graph."""
    id: str
    type: str
    properties: Dict[str, Any]
    file_path: str
    line_number: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "properties": self.properties,
            "file_path": self.file_path,
            "line_number": self.line_number,
        }


@dataclass
class GraphEdge:
    """Represents an edge in the code graph."""
    source_id: str
    target_id: str
    relationship_type: str
    properties: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type,
            "properties": self.properties,
        }


@dataclass
class GraphResult:
    """Represents a graph query result."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": self.metadata,
        }