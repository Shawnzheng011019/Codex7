from typing import List, Dict, Any, Optional
import json
import os
from pathlib import Path
from ..types import GraphNode, GraphEdge, GraphResult, CodeChunk
from ..utils.logger import app_logger


class JsonGraphClient:
    """JSON-based graph storage client."""
    
    def __init__(self, storage_path: str = "graph_data.json"):
        self.logger = app_logger.bind(component="json_graph_client")
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize data structure
        self.data = {
            "nodes": {},
            "edges": [],
            "metadata": {
                "version": "1.0",
                "created_at": None,
                "updated_at": None
            }
        }
        
        # Load existing data if file exists
        self._load_data()
    
    def _load_data(self):
        """Load data from JSON file."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                self.logger.info(f"Loaded graph data from {self.storage_path}")
            except Exception as e:
                self.logger.error(f"Error loading graph data: {e}")
                self.data = self._initialize_data()
        else:
            self.data = self._initialize_data()
    
    def _initialize_data(self) -> Dict[str, Any]:
        """Initialize empty data structure."""
        return {
            "nodes": {},
            "edges": [],
            "metadata": {
                "version": "1.0",
                "created_at": None,
                "updated_at": None
            }
        }
    
    def _save_data(self):
        """Save data to JSON file."""
        try:
            import datetime
            self.data["metadata"]["updated_at"] = datetime.datetime.now().isoformat()
            if not self.data["metadata"]["created_at"]:
                self.data["metadata"]["created_at"] = self.data["metadata"]["updated_at"]
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved graph data to {self.storage_path}")
        except Exception as e:
            self.logger.error(f"Error saving graph data: {e}")
    
    def create_file_node(self, file_path: str, language: str, file_type: str, metadata: Dict[str, Any]) -> GraphNode:
        """Create or update a file node."""
        node_id = file_path
        
        # Handle None metadata
        if metadata is None:
            metadata = {}
        
        node_data = {
            "id": node_id,
            "type": "File",
            "properties": {
                "path": file_path,
                "language": language,
                "file_type": file_type,
                "file_size": metadata.get('file_size', 0),
                "created_at": metadata.get('created_at', ''),
                "updated_at": metadata.get('updated_at', '')
            },
            "file_path": file_path,
            "line_number": 0
        }
        
        self.data["nodes"][node_id] = node_data
        self._save_data()
        
        return GraphNode(**node_data)
    
    def create_chunk_node(self, chunk: CodeChunk) -> GraphNode:
        """Create or update a chunk node."""
        metadata = chunk.metadata or {}
        
        node_data = {
            "id": chunk.id,
            "type": "Chunk",
            "properties": {
                "content": chunk.content,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": chunk.language,
                "chunk_type": chunk.chunk_type,
                "file_size": metadata.get('file_size', 0),
                "chunk_index": metadata.get('chunk_index', 0),
                "ast_node_type": metadata.get('ast_node_type', '')
            },
            "file_path": chunk.file_path,
            "line_number": chunk.start_line
        }
        
        self.data["nodes"][chunk.id] = node_data
        self._save_data()
        
        return GraphNode(**node_data)
    
    def create_function_node(self, name: str, qualified_name: str, file_path: str, 
                           line_number: int, metadata: Dict[str, Any]) -> GraphNode:
        """Create or update a function node."""
        node_data = {
            "id": qualified_name,
            "type": "Function",
            "properties": {
                "name": name,
                "qualified_name": qualified_name,
                "file_path": file_path,
                "line_number": line_number,
                "created_at": metadata.get('created_at', ''),
                "updated_at": metadata.get('updated_at', '')
            },
            "file_path": file_path,
            "line_number": line_number
        }
        
        self.data["nodes"][qualified_name] = node_data
        self._save_data()
        
        return GraphNode(**node_data)
    
    def create_class_node(self, name: str, qualified_name: str, file_path: str, 
                         line_number: int, metadata: Dict[str, Any]) -> GraphNode:
        """Create or update a class node."""
        node_data = {
            "id": qualified_name,
            "type": "Class",
            "properties": {
                "name": name,
                "qualified_name": qualified_name,
                "file_path": file_path,
                "line_number": line_number,
                "created_at": metadata.get('created_at', ''),
                "updated_at": metadata.get('updated_at', '')
            },
            "file_path": file_path,
            "line_number": line_number
        }
        
        self.data["nodes"][qualified_name] = node_data
        self._save_data()
        
        return GraphNode(**node_data)
    
    def create_relationship(self, source_id: str, target_id: str, relationship_type: str, 
                          properties: Dict[str, Any] = None) -> GraphEdge:
        """Create a relationship between two nodes."""
        if properties is None:
            properties = {}
        
        # Check if relationship already exists
        for edge in self.data["edges"]:
            if (edge["source_id"] == source_id and 
                edge["target_id"] == target_id and 
                edge["relationship_type"] == relationship_type):
                # Update existing relationship
                edge["properties"].update(properties)
                self._save_data()
                return GraphEdge(**edge)
        
        # Create new relationship
        edge_data = {
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            "properties": properties
        }
        
        self.data["edges"].append(edge_data)
        self._save_data()
        
        return GraphEdge(**edge_data)
    
    def create_file_chunk_relationship(self, file_path: str, chunk_id: str) -> GraphEdge:
        """Create relationship between file and chunk."""
        return self.create_relationship(file_path, chunk_id, "CONTAINS")
    
    def create_function_chunk_relationship(self, function_qualified_name: str, chunk_id: str) -> GraphEdge:
        """Create relationship between function and chunk."""
        return self.create_relationship(function_qualified_name, chunk_id, "DEFINED_IN")
    
    def create_class_chunk_relationship(self, class_qualified_name: str, chunk_id: str) -> GraphEdge:
        """Create relationship between class and chunk."""
        return self.create_relationship(class_qualified_name, chunk_id, "DEFINED_IN")
    
    def create_function_call_relationship(self, caller_qualified_name: str, callee_qualified_name: str) -> GraphEdge:
        """Create relationship between caller and callee functions."""
        return self.create_relationship(caller_qualified_name, callee_qualified_name, "CALLS")
    
    def create_class_inheritance_relationship(self, child_qualified_name: str, parent_qualified_name: str) -> GraphEdge:
        """Create inheritance relationship between classes."""
        return self.create_relationship(child_qualified_name, parent_qualified_name, "INHERITS_FROM")
    
    def create_class_method_relationship(self, class_qualified_name: str, method_qualified_name: str) -> GraphEdge:
        """Create relationship between class and method."""
        return self.create_relationship(class_qualified_name, method_qualified_name, "HAS_METHOD")
    
    def find_related_chunks(self, chunk_id: str, relationship_types: List[str] = None, 
                          max_hops: int = 2) -> GraphResult:
        """Find chunks related to a given chunk."""
        if relationship_types is None:
            relationship_types = ["CALLS", "DEFINED_IN", "CONTAINS", "HAS_METHOD", "INHERITS_FROM"]
        
        nodes = []
        edges = []
        
        # Find direct relationships
        for edge in self.data["edges"]:
            if edge["relationship_type"] in relationship_types:
                if edge["source_id"] == chunk_id or edge["target_id"] == chunk_id:
                    # Add edge
                    edges.append(GraphEdge(**edge))
                    
                    # Add related nodes
                    for node_id in [edge["source_id"], edge["target_id"]]:
                        if node_id in self.data["nodes"]:
                            node_data = self.data["nodes"][node_id]
                            nodes.append(GraphNode(**node_data))
        
        # Remove duplicates by ID
        unique_nodes = []
        node_ids = set()
        for node in nodes:
            if node.id not in node_ids:
                unique_nodes.append(node)
                node_ids.add(node.id)
        
        # Remove duplicate edges by source-target-type combination
        unique_edges = []
        edge_keys = set()
        for edge in edges:
            edge_key = (edge.source_id, edge.target_id, edge.relationship_type)
            if edge_key not in edge_keys:
                unique_edges.append(edge)
                edge_keys.add(edge_key)
        
        return GraphResult(
            nodes=unique_nodes,
            edges=unique_edges,
            metadata={"query_type": "related_chunks", "max_hops": max_hops},
        )
    
    def find_function_dependencies(self, function_qualified_name: str) -> GraphResult:
        """Find function dependencies (what functions this function calls)."""
        nodes = []
        edges = []
        
        # Find function node
        if function_qualified_name not in self.data["nodes"]:
            return GraphResult(nodes=[], edges=[], metadata={"error": "Function not found"})
        
        func_node = GraphNode(**self.data["nodes"][function_qualified_name])
        nodes.append(func_node)
        
        # Find CALLS relationships
        for edge in self.data["edges"]:
            if (edge["source_id"] == function_qualified_name and 
                edge["relationship_type"] == "CALLS"):
                
                edges.append(GraphEdge(**edge))
                
                # Add called function node
                if edge["target_id"] in self.data["nodes"]:
                    target_node = GraphNode(**self.data["nodes"][edge["target_id"]])
                    nodes.append(target_node)
        
        # Remove duplicates by ID
        unique_nodes = []
        node_ids = set()
        for node in nodes:
            if node.id not in node_ids:
                unique_nodes.append(node)
                node_ids.add(node.id)
        
        # Remove duplicate edges by source-target-type combination
        unique_edges = []
        edge_keys = set()
        for edge in edges:
            edge_key = (edge.source_id, edge.target_id, edge.relationship_type)
            if edge_key not in edge_keys:
                unique_edges.append(edge)
                edge_keys.add(edge_key)
        
        return GraphResult(
            nodes=unique_nodes,
            edges=unique_edges,
            metadata={"query_type": "function_dependencies"},
        )
    
    def find_class_hierarchy(self, class_qualified_name: str) -> GraphResult:
        """Find class hierarchy (inheritance relationships)."""
        nodes = []
        edges = []
        
        # Find class node
        if class_qualified_name not in self.data["nodes"]:
            return GraphResult(nodes=[], edges=[], metadata={"error": "Class not found"})
        
        class_node = GraphNode(**self.data["nodes"][class_qualified_name])
        nodes.append(class_node)
        
        # Find INHERITS_FROM relationships
        for edge in self.data["edges"]:
            if (edge["source_id"] == class_qualified_name and 
                edge["relationship_type"] == "INHERITS_FROM"):
                
                edges.append(GraphEdge(**edge))
                
                # Add parent class node
                if edge["target_id"] in self.data["nodes"]:
                    target_node = GraphNode(**self.data["nodes"][edge["target_id"]])
                    nodes.append(target_node)
        
        # Remove duplicates by ID
        unique_nodes = []
        node_ids = set()
        for node in nodes:
            if node.id not in node_ids:
                unique_nodes.append(node)
                node_ids.add(node.id)
        
        # Remove duplicate edges by source-target-type combination
        unique_edges = []
        edge_keys = set()
        for edge in edges:
            edge_key = (edge.source_id, edge.target_id, edge.relationship_type)
            if edge_key not in edge_keys:
                unique_edges.append(edge)
                edge_keys.add(edge_key)
        
        return GraphResult(
            nodes=unique_nodes,
            edges=unique_edges,
            metadata={"query_type": "class_hierarchy"},
        )
    
    def search_by_text(self, text: str, limit: int = 10) -> List[GraphNode]:
        """Search for chunks containing specific text."""
        matching_nodes = []
        
        for node_id, node_data in self.data["nodes"].items():
            if node_data["type"] == "Chunk":
                content = node_data["properties"].get("content", "")
                if text.lower() in content.lower():
                    matching_nodes.append(GraphNode(**node_data))
                    
                    if len(matching_nodes) >= limit:
                        break
        
        return matching_nodes
    
    def get_file_structure(self, file_path: str) -> GraphResult:
        """Get the complete structure of a file including functions and classes."""
        nodes = []
        edges = []
        
        # Find file node
        if file_path not in self.data["nodes"]:
            return GraphResult(nodes=[], edges=[], metadata={"error": "File not found"})
        
        file_node = GraphNode(**self.data["nodes"][file_path])
        nodes.append(file_node)
        
        # Find all relationships related to this file
        for edge in self.data["edges"]:
            if edge["source_id"] == file_path or edge["target_id"] == file_path:
                edges.append(GraphEdge(**edge))
                
                # Add related nodes
                for node_id in [edge["source_id"], edge["target_id"]]:
                    if node_id in self.data["nodes"] and node_id != file_path:
                        node_data = self.data["nodes"][node_id]
                        nodes.append(GraphNode(**node_data))
        
        # Also find all nodes connected to the chunks (functions, classes, etc.)
        chunk_ids = [node.id for node in nodes if node.type == "Chunk"]
        for edge in self.data["edges"]:
            if edge["source_id"] in chunk_ids or edge["target_id"] in chunk_ids:
                edges.append(GraphEdge(**edge))
                
                # Add related nodes
                for node_id in [edge["source_id"], edge["target_id"]]:
                    if node_id in self.data["nodes"] and node_id != file_path:
                        node_data = self.data["nodes"][node_id]
                        nodes.append(GraphNode(**node_data))
        
        # Remove duplicates by ID
        unique_nodes = []
        node_ids = set()
        for node in nodes:
            if node.id not in node_ids:
                unique_nodes.append(node)
                node_ids.add(node.id)
        
        # Remove duplicate edges by source-target-type combination
        unique_edges = []
        edge_keys = set()
        for edge in edges:
            edge_key = (edge.source_id, edge.target_id, edge.relationship_type)
            if edge_key not in edge_keys:
                unique_edges.append(edge)
                edge_keys.add(edge_key)
        
        return GraphResult(
            nodes=unique_nodes,
            edges=unique_edges,
            metadata={"query_type": "file_structure", "file_path": file_path},
        )
    
    def clear_database(self):
        """Clear all data from the database."""
        self.data = self._initialize_data()
        self._save_data()
        self.logger.info("Cleared all data from JSON graph database")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        
        # Count nodes by type
        node_counts = {}
        for node_data in self.data["nodes"].values():
            node_type = node_data["type"]
            node_counts[node_type] = node_counts.get(node_type, 0) + 1
        stats["nodes"] = node_counts
        
        # Count relationships by type
        rel_counts = {}
        for edge in self.data["edges"]:
            rel_type = edge["relationship_type"]
            rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
        stats["relationships"] = rel_counts
        
        return stats
    
    def get_all_nodes(self) -> List[GraphNode]:
        """Get all nodes in the graph."""
        return [GraphNode(**node_data) for node_data in self.data["nodes"].values()]
    
    def get_all_edges(self) -> List[GraphEdge]:
        """Get all edges in the graph."""
        return [GraphEdge(**edge_data) for edge_data in self.data["edges"]]
    
    def get_graph_data(self) -> Dict[str, Any]:
        """Get the complete graph data for visualization."""
        return {
            "nodes": [GraphNode(**node_data).to_dict() for node_data in self.data["nodes"].values()],
            "edges": [GraphEdge(**edge_data).to_dict() for edge_data in self.data["edges"]],
            "metadata": self.data["metadata"]
        }
    
    def get_node_details(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific node."""
        if node_id not in self.data["nodes"]:
            return None
        
        node_data = self.data["nodes"][node_id]
        
        # Find related edges
        related_edges = []
        for edge in self.data["edges"]:
            if edge["source_id"] == node_id or edge["target_id"] == node_id:
                related_edges.append(edge)
        
        # Find related nodes
        related_node_ids = set()
        for edge in related_edges:
            related_node_ids.add(edge["source_id"])
            related_node_ids.add(edge["target_id"])
        
        # Remove the current node from related nodes
        if node_id in related_node_ids:
            related_node_ids.remove(node_id)
        
        related_nodes = []
        for related_id in related_node_ids:
            if related_id in self.data["nodes"]:
                related_nodes.append(self.data["nodes"][related_id])
        
        return {
            "node": node_data,
            "related_edges": related_edges,
            "related_nodes": related_nodes
        }