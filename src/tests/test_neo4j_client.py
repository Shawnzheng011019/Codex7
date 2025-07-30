import pytest
from typing import Dict, Any
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.types import CodeChunk, FileType
from src.graph.neo4j_client import Neo4jClient


class TestNeo4jClient:
    """Test Neo4j client functionality."""
    
    def test_create_file_node(self, neo4j_client: Neo4jClient, sample_metadata: Dict[str, Any]):
        """Test creating file node with metadata."""
        file_path = "src/scanner/local_codebase_scanner.py"
        language = "python"
        file_type = "code"
        
        # This should not raise the previous TypeError about Map objects
        node = neo4j_client.create_file_node(
            file_path=file_path,
            language=language,
            file_type=file_type,
            metadata=sample_metadata
        )
        
        assert node is not None
        assert node.id == file_path
        assert node.type == "File"
        assert node.file_path == file_path
        assert "file_size" in node.properties
        assert node.properties["language"] == language
        assert node.properties["file_type"] == file_type
        
    def test_create_chunk_node(self, neo4j_client: Neo4jClient, sample_metadata: Dict[str, Any]):
        """Test creating chunk node with metadata."""
        chunk = CodeChunk(
            id="test_chunk_001",
            file_path="test_file.py",
            content="def test():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata=sample_metadata
        )
        
        # This should not raise TypeError about Map objects
        node = neo4j_client.create_chunk_node(chunk)
        
        assert node is not None
        assert node.id == chunk.id
        assert node.type == "Chunk"
        assert node.file_path == chunk.file_path
        assert node.line_number == chunk.start_line
        assert "file_size" in node.properties
        assert "chunk_index" in node.properties
        assert "ast_node_type" in node.properties
        
    def test_create_function_node(self, neo4j_client: Neo4jClient, sample_metadata: Dict[str, Any]):
        """Test creating function node."""
        name = "test_function"
        qualified_name = "module.test_function"
        file_path = "test_file.py"
        line_number = 10
        
        node = neo4j_client.create_function_node(
            name=name,
            qualified_name=qualified_name,
            file_path=file_path,
            line_number=line_number,
            metadata=sample_metadata
        )
        
        assert node is not None
        assert node.id == qualified_name
        assert node.type == "Function"
        assert node.file_path == file_path
        assert node.line_number == line_number
        assert node.properties["name"] == name
        
    def test_create_class_node(self, neo4j_client: Neo4jClient, sample_metadata: Dict[str, Any]):
        """Test creating class node."""
        name = "TestClass"
        qualified_name = "module.TestClass"
        file_path = "test_file.py"
        line_number = 5
        
        node = neo4j_client.create_class_node(
            name=name,
            qualified_name=qualified_name,
            file_path=file_path,
            line_number=line_number,
            metadata=sample_metadata
        )
        
        assert node is not None
        assert node.id == qualified_name
        assert node.type == "Class"
        assert node.file_path == file_path
        assert node.line_number == line_number
        assert node.properties["name"] == name
        
    def test_create_relationships(self, neo4j_client: Neo4jClient, sample_metadata: Dict[str, Any]):
        """Test creating relationships between nodes."""
        # Create file node
        file_path = "test_relationships.py"
        file_node = neo4j_client.create_file_node(
            file_path=file_path,
            language="python",
            file_type="code",
            metadata=sample_metadata
        )
        
        # Create chunk node
        chunk = CodeChunk(
            id="test_chunk_rel",
            file_path=file_path,
            content="def test():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata=sample_metadata
        )
        chunk_node = neo4j_client.create_chunk_node(chunk)
        
        # Create file-chunk relationship
        edge = neo4j_client.create_file_chunk_relationship(file_path, chunk.id)
        
        assert edge is not None
        assert edge.source_id == file_path
        assert edge.target_id == chunk.id
        assert edge.relationship_type == "CONTAINS"
        
    def test_search_by_text(self, neo4j_client: Neo4jClient, sample_metadata: Dict[str, Any]):
        """Test text search functionality."""
        # Create some chunks with different content
        chunks = [
            CodeChunk(
                id="search_chunk_1",
                file_path="search_test.py",
                content="def hello_world():\n    print('Hello World')",
                start_line=1,
                end_line=2,
                language="python",
                chunk_type="function_definition",
                metadata=sample_metadata
            ),
            CodeChunk(
                id="search_chunk_2",
                file_path="search_test.py",
                content="def goodbye():\n    print('Goodbye')",
                start_line=3,
                end_line=4,
                language="python",
                chunk_type="function_definition",
                metadata=sample_metadata
            )
        ]
        
        # Insert chunks
        for chunk in chunks:
            neo4j_client.create_chunk_node(chunk)
        
        # Search for specific text
        results = neo4j_client.search_by_text("Hello World", limit=5)
        
        assert len(results) >= 1
        assert any("Hello World" in node.properties.get("content", "") for node in results)
        
    def test_database_stats(self, neo4j_client: Neo4jClient, sample_metadata: Dict[str, Any]):
        """Test database statistics."""
        # Create some test data
        neo4j_client.create_file_node("stats_test.py", "python", "code", sample_metadata)
        
        chunk = CodeChunk(
            id="stats_chunk",
            file_path="stats_test.py",
            content="def stats_test():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata=sample_metadata
        )
        neo4j_client.create_chunk_node(chunk)
        
        # Get stats
        stats = neo4j_client.get_database_stats()
        
        assert "nodes" in stats
        assert "relationships" in stats
        assert isinstance(stats["nodes"], dict)
        assert isinstance(stats["relationships"], dict)
        
    def test_metadata_handling_edge_cases(self, neo4j_client: Neo4jClient):
        """Test metadata handling with edge cases."""
        # Test with None metadata
        node1 = neo4j_client.create_file_node(
            file_path="test_none_metadata.py",
            language="python",
            file_type="code",
            metadata=None
        )
        assert node1 is not None
        
        # Test with empty metadata
        node2 = neo4j_client.create_file_node(
            file_path="test_empty_metadata.py",
            language="python",
            file_type="code",
            metadata={}
        )
        assert node2 is not None
        
        # Test chunk with None metadata
        chunk = CodeChunk(
            id="test_chunk_none_meta",
            file_path="test_none_metadata.py",
            content="def test():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata=None
        )
        chunk_node = neo4j_client.create_chunk_node(chunk)
        assert chunk_node is not None
        
    def test_clear_database(self, neo4j_client: Neo4jClient, sample_metadata: Dict[str, Any]):
        """Test clearing database."""
        # Create some test data
        neo4j_client.create_file_node("clear_test.py", "python", "code", sample_metadata)
        
        # Clear database
        neo4j_client.clear_database()
        
        # Verify data is cleared
        stats = neo4j_client.get_database_stats()
        total_nodes = sum(stats["nodes"].values()) if stats["nodes"] else 0
        total_relationships = sum(stats["relationships"].values()) if stats["relationships"] else 0
        
        assert total_nodes == 0
        assert total_relationships == 0 