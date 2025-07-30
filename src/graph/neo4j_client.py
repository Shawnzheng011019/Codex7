from typing import List, Dict, Any, Optional, Tuple
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError

from ..config import settings
from ..types import GraphNode, GraphEdge, GraphResult, CodeChunk
from ..utils.logger import app_logger


class Neo4jClient:
    """Neo4j client for graph database operations."""
    
    def __init__(self):
        self.logger = app_logger.bind(component="neo4j_client")
        self.driver = None
        self._connect()
        self._ensure_constraints()
    
    def _connect(self):
        """Connect to Neo4j server."""
        try:
            self.driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            self.logger.info(f"Connected to Neo4j at {settings.neo4j_uri}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Neo4j: {e}")
            raise
    
    def _ensure_constraints(self):
        """Ensure necessary constraints exist."""
        constraints = [
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT function_name_unique IF NOT EXISTS FOR (f:Function) REQUIRE f.qualified_name IS UNIQUE",
            "CREATE CONSTRAINT class_name_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.qualified_name IS UNIQUE",
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    self.logger.debug(f"Created constraint: {constraint}")
                except Exception as e:
                    self.logger.warning(f"Failed to create constraint {constraint}: {e}")
    
    def close(self):
        """Close connection to Neo4j."""
        if self.driver:
            self.driver.close()
            self.logger.info("Disconnected from Neo4j")
    
    def create_file_node(self, file_path: str, language: str, file_type: str, metadata: Dict[str, Any]) -> GraphNode:
        """Create or update a file node."""
        query = """
        MERGE (f:File {path: $path})
        SET f.language = $language,
            f.file_type = $file_type,
            f.file_size = $file_size,
            f.updated_at = datetime()
        RETURN f
        """
        
        # Extract file_size from metadata if present, default to 0
        file_size = metadata.get('file_size', 0) if metadata else 0
        
        with self.driver.session() as session:
            result = session.run(
                query,
                path=file_path,
                language=language,
                file_type=file_type,
                file_size=file_size,
            )
            
            record = result.single()
            if record:
                node_data = record["f"]
                return GraphNode(
                    id=node_data.get("path"),
                    type="File",
                    properties=dict(node_data),
                    file_path=file_path,
                    line_number=0,
                )
        
        raise Exception(f"Failed to create file node: {file_path}")
    
    def create_chunk_node(self, chunk: CodeChunk) -> GraphNode:
        """Create or update a chunk node."""
        query = """
        MERGE (c:Chunk {id: $id})
        SET c.content = $content,
            c.start_line = $start_line,
            c.end_line = $end_line,
            c.language = $language,
            c.chunk_type = $chunk_type,
            c.file_size = $file_size,
            c.chunk_index = $chunk_index,
            c.ast_node_type = $ast_node_type,
            c.updated_at = datetime()
        RETURN c
        """
        
        # Extract metadata fields with defaults
        metadata = chunk.metadata or {}
        file_size = metadata.get('file_size', 0)
        chunk_index = metadata.get('chunk_index', 0)
        ast_node_type = metadata.get('ast_node_type', '')
        
        with self.driver.session() as session:
            result = session.run(
                query,
                id=chunk.id,
                content=chunk.content,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                language=chunk.language,
                chunk_type=chunk.chunk_type,
                file_size=file_size,
                chunk_index=chunk_index,
                ast_node_type=ast_node_type,
            )
            
            record = result.single()
            if record:
                node_data = record["c"]
                return GraphNode(
                    id=node_data.get("id"),
                    type="Chunk",
                    properties=dict(node_data),
                    file_path=chunk.file_path,
                    line_number=chunk.start_line,
                )
        
        raise Exception(f"Failed to create chunk node: {chunk.id}")
    
    def create_function_node(self, name: str, qualified_name: str, file_path: str, 
                           line_number: int, metadata: Dict[str, Any]) -> GraphNode:
        """Create or update a function node."""
        query = """
        MERGE (f:Function {qualified_name: $qualified_name})
        SET f.name = $name,
            f.file_path = $file_path,
            f.line_number = $line_number,
            f.updated_at = datetime()
        RETURN f
        """
        
        with self.driver.session() as session:
            result = session.run(
                query,
                name=name,
                qualified_name=qualified_name,
                file_path=file_path,
                line_number=line_number,
            )
            
            record = result.single()
            if record:
                node_data = record["f"]
                return GraphNode(
                    id=node_data.get("qualified_name"),
                    type="Function",
                    properties=dict(node_data),
                    file_path=file_path,
                    line_number=line_number,
                )
        
        raise Exception(f"Failed to create function node: {qualified_name}")
    
    def create_class_node(self, name: str, qualified_name: str, file_path: str, 
                         line_number: int, metadata: Dict[str, Any]) -> GraphNode:
        """Create or update a class node."""
        query = """
        MERGE (c:Class {qualified_name: $qualified_name})
        SET c.name = $name,
            c.file_path = $file_path,
            c.line_number = $line_number,
            c.updated_at = datetime()
        RETURN c
        """
        
        with self.driver.session() as session:
            result = session.run(
                query,
                name=name,
                qualified_name=qualified_name,
                file_path=file_path,
                line_number=line_number,
            )
            
            record = result.single()
            if record:
                node_data = record["c"]
                return GraphNode(
                    id=node_data.get("qualified_name"),
                    type="Class",
                    properties=dict(node_data),
                    file_path=file_path,
                    line_number=line_number,
                )
        
        raise Exception(f"Failed to create class node: {qualified_name}")
    
    def create_relationship(self, source_id: str, target_id: str, relationship_type: str, 
                          properties: Dict[str, Any] = None) -> GraphEdge:
        """Create a relationship between two nodes."""
        if properties is None:
            properties = {}
        
        query = """
        MATCH (source), (target)
        WHERE source.id = $source_id OR source.qualified_name = $source_id OR source.path = $source_id
        AND target.id = $target_id OR target.qualified_name = $target_id OR target.path = $target_id
        MERGE (source)-[r:%s]->(target)
        SET r += $properties, r.updated_at = datetime()
        RETURN r
        """ % relationship_type
        
        with self.driver.session() as session:
            result = session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                properties=properties,
            )
            
            record = result.single()
            if record:
                edge_data = record["r"]
                return GraphEdge(
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=relationship_type,
                    properties=dict(edge_data),
                )
        
        raise Exception(f"Failed to create relationship: {source_id} -[{relationship_type}]-> {target_id}")
    
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
        
        rel_types_pattern = "|".join(relationship_types)
        
        # For simplicity, we'll use direct relationships only
        # Variable length relationships with UNWIND are complex and may not be necessary for this use case
        query = """
        MATCH (c:Chunk {id: $chunk_id})-[r:%s]-(related)
        WHERE related:Chunk OR related:Function OR related:Class
        RETURN collect(DISTINCT c) + collect(DISTINCT related) as nodes,
               collect(DISTINCT [startNode(r), endNode(r), type(r), properties(r)]) as relationships
        """ % rel_types_pattern
        
        with self.driver.session() as session:
            result = session.run(query, chunk_id=chunk_id)
            record = result.single()
            
            if record:
                nodes = []
                edges = []
                
                # Process nodes
                for node_data in record["nodes"]:
                    if node_data.get("id"):
                        nodes.append(GraphNode(
                            id=node_data.get("id"),
                            type=list(node_data.labels)[0] if node_data.labels else "Unknown",
                            properties=dict(node_data),
                            file_path=node_data.get("file_path", ""),
                            line_number=node_data.get("line_number", 0),
                        ))
                
                # Process edges
                for edge_data in record["relationships"]:
                    if edge_data and len(edge_data) >= 3 and edge_data[0] and edge_data[1]:
                        source_id = (edge_data[0].get("id") or 
                                   edge_data[0].get("qualified_name") or 
                                   edge_data[0].get("path"))
                        target_id = (edge_data[1].get("id") or 
                                   edge_data[1].get("qualified_name") or 
                                   edge_data[1].get("path"))
                        
                        if source_id and target_id:
                            edges.append(GraphEdge(
                                source_id=source_id,
                                target_id=target_id,
                                relationship_type=edge_data[2],
                                properties=edge_data[3] if len(edge_data) > 3 else {},
                            ))
                
                return GraphResult(
                    nodes=nodes,
                    edges=edges,
                    metadata={"query_type": "related_chunks", "max_hops": max_hops},
                )
        
        return GraphResult(nodes=[], edges=[], metadata={"error": "No results found"})
    
    def find_function_dependencies(self, function_qualified_name: str) -> GraphResult:
        """Find function dependencies (what functions this function calls)."""
        query = """
        MATCH (func:Function {qualified_name: $qualified_name})-[:CALLS]->(dep:Function)
        RETURN collect(func) + collect(dep) as nodes,
               collect([func, dep, "CALLS", {}]) as relationships
        """
        
        with self.driver.session() as session:
            result = session.run(query, qualified_name=function_qualified_name)
            record = result.single()
            
            if record:
                nodes = []
                edges = []
                
                # Process nodes
                for node_data in record["nodes"]:
                    nodes.append(GraphNode(
                        id=node_data.get("qualified_name"),
                        type="Function",
                        properties=dict(node_data),
                        file_path=node_data.get("file_path", ""),
                        line_number=node_data.get("line_number", 0),
                    ))
                
                # Process edges
                for edge_data in record["relationships"]:
                    if edge_data and len(edge_data) >= 3 and edge_data[0] and edge_data[1]:
                        source_id = edge_data[0].get("qualified_name")
                        target_id = edge_data[1].get("qualified_name")
                        
                        if source_id and target_id:
                            edges.append(GraphEdge(
                                source_id=source_id,
                                target_id=target_id,
                                relationship_type=edge_data[2],
                                properties=edge_data[3] if len(edge_data) > 3 else {},
                            ))
                
                return GraphResult(
                    nodes=nodes,
                    edges=edges,
                    metadata={"query_type": "function_dependencies"},
                )
        
        return GraphResult(nodes=[], edges=[], metadata={"error": "No dependencies found"})
    
    def find_class_hierarchy(self, class_qualified_name: str) -> GraphResult:
        """Find class hierarchy (inheritance relationships)."""
        query = """
        MATCH (c:Class {qualified_name: $qualified_name})-[r:INHERITS_FROM]->(ancestor:Class)
        RETURN collect(DISTINCT c) + collect(DISTINCT ancestor) as nodes,
               collect(DISTINCT [startNode(r), endNode(r), type(r), properties(r)]) as relationships
        """
        
        with self.driver.session() as session:
            result = session.run(query, qualified_name=class_qualified_name)
            record = result.single()
            
            if record:
                nodes = []
                edges = []
                
                # Process nodes
                for node_data in record["nodes"]:
                    nodes.append(GraphNode(
                        id=node_data.get("qualified_name"),
                        type="Class",
                        properties=dict(node_data),
                        file_path=node_data.get("file_path", ""),
                        line_number=node_data.get("line_number", 0),
                    ))
                
                # Process edges
                for edge_data in record["relationships"]:
                    if edge_data and len(edge_data) >= 3 and edge_data[0] and edge_data[1]:
                        source_id = edge_data[0].get("qualified_name")
                        target_id = edge_data[1].get("qualified_name")
                        
                        if source_id and target_id:
                            edges.append(GraphEdge(
                                source_id=source_id,
                                target_id=target_id,
                                relationship_type=edge_data[2],
                                properties=edge_data[3] if len(edge_data) > 3 else {},
                            ))
                
                return GraphResult(
                    nodes=nodes,
                    edges=edges,
                    metadata={"query_type": "class_hierarchy"},
                )
        
        return GraphResult(nodes=[], edges=[], metadata={"error": "No hierarchy found"})
    
    def search_by_text(self, text: str, limit: int = 10) -> List[GraphNode]:
        """Search for chunks containing specific text."""
        query = """
        MATCH (c:Chunk)
        WHERE c.content CONTAINS $text
        RETURN c
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, text=text, limit=limit)
            nodes = []
            
            for record in result:
                node_data = record["c"]
                nodes.append(GraphNode(
                    id=node_data.get("id"),
                    type="Chunk",
                    properties=dict(node_data),
                    file_path=node_data.get("file_path", ""),
                    line_number=node_data.get("start_line", 0),
                ))
            
            return nodes
    
    def get_file_structure(self, file_path: str) -> GraphResult:
        """Get the complete structure of a file including functions and classes."""
        query = """
        MATCH (f:File {path: $file_path})-[:CONTAINS]->(c:Chunk)
        OPTIONAL MATCH (c)<-[:DEFINED_IN]-(func:Function)
        OPTIONAL MATCH (c)<-[:DEFINED_IN]-(cls:Class)
        OPTIONAL MATCH (cls)-[:HAS_METHOD]->(method:Function)
        WITH f, c, func, cls, method
        OPTIONAL MATCH (f)-[r1:CONTAINS]->(c)
        OPTIONAL MATCH (func)-[r2:DEFINED_IN]->(c)
        OPTIONAL MATCH (cls)-[r3:DEFINED_IN]->(c)
        OPTIONAL MATCH (cls)-[r4:HAS_METHOD]->(method)
        RETURN collect(DISTINCT f) + collect(DISTINCT c) + collect(DISTINCT func) + collect(DISTINCT cls) + collect(DISTINCT method) as nodes,
               collect(DISTINCT [startNode(r1), endNode(r1), type(r1), properties(r1)]) + 
               collect(DISTINCT [startNode(r2), endNode(r2), type(r2), properties(r2)]) + 
               collect(DISTINCT [startNode(r3), endNode(r3), type(r3), properties(r3)]) + 
               collect(DISTINCT [startNode(r4), endNode(r4), type(r4), properties(r4)]) as relationships
        """
        
        with self.driver.session() as session:
            result = session.run(query, file_path=file_path)
            record = result.single()
            
            if record:
                nodes = []
                edges = []
                
                # Process nodes
                for node_data in record["nodes"]:
                    if node_data:
                        node_type = list(node_data.labels)[0] if node_data.labels else "Unknown"
                        node_id = (node_data.get("id") or 
                                  node_data.get("qualified_name") or 
                                  node_data.get("path"))
                        
                        nodes.append(GraphNode(
                            id=node_id,
                            type=node_type,
                            properties=dict(node_data),
                            file_path=node_data.get("file_path", ""),
                            line_number=node_data.get("line_number", 0) or node_data.get("start_line", 0),
                        ))
                
                # Process edges - handle the new structure with multiple relationship lists
                all_edges = []
                for edge_list in record["relationships"]:
                    if edge_list:  # Check if edge_list is not None
                        for edge_data in edge_list:
                            if edge_data and len(edge_data) >= 3 and edge_data[0] and edge_data[1]:
                                source_id = (edge_data[0].get("id") or 
                                           edge_data[0].get("qualified_name") or 
                                           edge_data[0].get("path"))
                                target_id = (edge_data[1].get("id") or 
                                           edge_data[1].get("qualified_name") or 
                                           edge_data[1].get("path"))
                                
                                if source_id and target_id:  # Only add if both IDs exist
                                    all_edges.append(GraphEdge(
                                        source_id=source_id,
                                        target_id=target_id,
                                        relationship_type=edge_data[2],
                                        properties=edge_data[3] if len(edge_data) > 3 else {},
                                    ))
                
                return GraphResult(
                    nodes=nodes,
                    edges=all_edges,
                    metadata={"query_type": "file_structure", "file_path": file_path},
                )
        
        return GraphResult(nodes=[], edges=[], metadata={"error": "File not found"})
    
    def clear_database(self):
        """Clear all data from the database."""
        query = "MATCH (n) DETACH DELETE n"
        
        with self.driver.session() as session:
            session.run(query)
            self.logger.info("Cleared all data from Neo4j database")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        stats = {}
        
        # Count nodes by type
        node_counts = """
        MATCH (n)
        RETURN labels(n)[0] as label, count(n) as count
        """
        
        with self.driver.session() as session:
            result = session.run(node_counts)
            stats["nodes"] = {record["label"]: record["count"] for record in result}
        
        # Count relationships by type
        rel_counts = """
        MATCH ()-[r]->()
        RETURN type(r) as type, count(r) as count
        """
        
        with self.driver.session() as session:
            result = session.run(rel_counts)
            stats["relationships"] = {record["type"]: record["count"] for record in result}
        
        return stats