import pytest
from typing import Dict, Any
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.types import CodeChunk, FileType
from src.graph.json_graph_client import JsonGraphClient


class TestJsonGraphClient:
    """Test JSON graph client functionality."""
    
    def setup_method(self):
        """Set up test environment."""
        self.test_graph_path = "test_graph_data.json"
        self.client = JsonGraphClient(self.test_graph_path)
    
    def teardown_method(self):
        """Clean up test environment."""
        # Clear the test database
        self.client.clear_database()
        # Remove test file if it exists
        if os.path.exists(self.test_graph_path):
            os.remove(self.test_graph_path)
    
    def test_create_file_node(self, sample_metadata: Dict[str, Any]):
        """Test creating file node with metadata."""
        file_path = "src/scanner/local_codebase_scanner.py"
        language = "python"
        file_type = "code"
        
        # This should not raise the previous TypeError about Map objects
        node = self.client.create_file_node(
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
    
    def test_create_chunk_node(self, sample_metadata: Dict[str, Any]):
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
        node = self.client.create_chunk_node(chunk)
        
        assert node is not None
        assert node.id == chunk.id
        assert node.type == "Chunk"
        assert node.file_path == chunk.file_path
        assert node.line_number == chunk.start_line
        assert "file_size" in node.properties
        assert "chunk_index" in node.properties
        assert "ast_node_type" in node.properties
    
    def test_create_function_node(self, sample_metadata: Dict[str, Any]):
        """Test creating function node."""
        name = "test_function"
        qualified_name = "module.test_function"
        file_path = "test_file.py"
        line_number = 10
        
        node = self.client.create_function_node(
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
    
    def test_create_class_node(self, sample_metadata: Dict[str, Any]):
        """Test creating class node."""
        name = "TestClass"
        qualified_name = "module.TestClass"
        file_path = "test_file.py"
        line_number = 5
        
        node = self.client.create_class_node(
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
    
    def test_create_relationships(self, sample_metadata: Dict[str, Any]):
        """Test creating relationships between nodes."""
        # Create file node
        file_path = "test_relationships.py"
        file_node = self.client.create_file_node(
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
        chunk_node = self.client.create_chunk_node(chunk)
        
        # Create file-chunk relationship
        edge = self.client.create_file_chunk_relationship(file_path, chunk.id)
        
        assert edge is not None
        assert edge.source_id == file_path
        assert edge.target_id == chunk.id
        assert edge.relationship_type == "CONTAINS"
    
    def test_search_by_text(self, sample_metadata: Dict[str, Any]):
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
            self.client.create_chunk_node(chunk)
        
        # Search for specific text
        results = self.client.search_by_text("Hello World", limit=5)
        
        assert len(results) >= 1
        assert any("Hello World" in node.properties.get("content", "") for node in results)
    
    def test_database_stats(self, sample_metadata: Dict[str, Any]):
        """Test database statistics."""
        # Create some test data
        self.client.create_file_node("stats_test.py", "python", "code", sample_metadata)
        
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
        self.client.create_chunk_node(chunk)
        
        # Get stats
        stats = self.client.get_database_stats()
        
        assert "nodes" in stats
        assert "relationships" in stats
        assert isinstance(stats["nodes"], dict)
        assert isinstance(stats["relationships"], dict)
    
    def test_metadata_handling_edge_cases(self):
        """Test metadata handling with edge cases."""
        # Test with None metadata
        node1 = self.client.create_file_node(
            file_path="test_none_metadata.py",
            language="python",
            file_type="code",
            metadata=None
        )
        assert node1 is not None
        
        # Test with empty metadata
        node2 = self.client.create_file_node(
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
        chunk_node = self.client.create_chunk_node(chunk)
        assert chunk_node is not None
    
    def test_clear_database(self, sample_metadata: Dict[str, Any]):
        """Test clearing database."""
        # Create some test data
        self.client.create_file_node("clear_test.py", "python", "code", sample_metadata)
        
        # Clear database
        self.client.clear_database()
        
        # Verify data is cleared
        stats = self.client.get_database_stats()
        total_nodes = sum(stats["nodes"].values()) if stats["nodes"] else 0
        total_relationships = sum(stats["relationships"].values()) if stats["relationships"] else 0
        
        assert total_nodes == 0
        assert total_relationships == 0
    
    def test_graph_data_retrieval(self, sample_metadata: Dict[str, Any]):
        """Test retrieving complete graph data."""
        # Create test data
        self.client.create_file_node("graph_test.py", "python", "code", sample_metadata)
        
        chunk = CodeChunk(
            id="graph_chunk",
            file_path="graph_test.py",
            content="def graph_test():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata=sample_metadata
        )
        self.client.create_chunk_node(chunk)
        
        # Create relationship
        self.client.create_file_chunk_relationship("graph_test.py", "graph_chunk")
        
        # Get graph data
        graph_data = self.client.get_graph_data()
        
        assert "nodes" in graph_data
        assert "edges" in graph_data
        assert "metadata" in graph_data
        assert len(graph_data["nodes"]) >= 2
        assert len(graph_data["edges"]) >= 1
    
    def test_node_details(self, sample_metadata: Dict[str, Any]):
        """Test getting node details."""
        # Create test function node
        func_name = "test_function"
        qualified_name = "test.py::test_function"
        
        self.client.create_function_node(
            name=func_name,
            qualified_name=qualified_name,
            file_path="test.py",
            line_number=1,
            metadata=sample_metadata
        )
        
        # Get node details
        details = self.client.get_node_details(qualified_name)
        
        assert details is not None
        assert "node" in details
        assert "related_edges" in details
        assert "related_nodes" in details
        assert details["node"]["id"] == qualified_name
        assert details["node"]["type"] == "Function"
    
    def test_file_structure(self, sample_metadata: Dict[str, Any]):
        """Test getting file structure."""
        file_path = "structure_test.py"
        
        # Create file node
        self.client.create_file_node(file_path, "python", "code", sample_metadata)
        
        # Create function node
        func_name = "test_func"
        qualified_name = f"{file_path}::test_func"
        self.client.create_function_node(
            name=func_name,
            qualified_name=qualified_name,
            file_path=file_path,
            line_number=1,
            metadata=sample_metadata
        )
        
        # Create chunk node
        chunk = CodeChunk(
            id="structure_chunk",
            file_path=file_path,
            content="def test_func():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata=sample_metadata
        )
        self.client.create_chunk_node(chunk)
        
        # Create relationships
        self.client.create_file_chunk_relationship(file_path, chunk.id)
        self.client.create_function_chunk_relationship(qualified_name, chunk.id)
        
        # Get file structure
        structure = self.client.get_file_structure(file_path)
        
        assert structure.nodes is not None
        assert structure.edges is not None
        assert len(structure.nodes) >= 3  # file + function + chunk
        assert len(structure.edges) >= 2  # file-chunk + function-chunk
    
    def test_function_dependencies(self, sample_metadata: Dict[str, Any]):
        """Test getting function dependencies."""
        # Create caller function
        caller_name = "caller_func"
        caller_qualified = "test.py::caller_func"
        self.client.create_function_node(
            name=caller_name,
            qualified_name=caller_qualified,
            file_path="test.py",
            line_number=1,
            metadata=sample_metadata
        )
        
        # Create callee function
        callee_name = "callee_func"
        callee_qualified = "test.py::callee_func"
        self.client.create_function_node(
            name=callee_name,
            qualified_name=callee_qualified,
            file_path="test.py",
            line_number=5,
            metadata=sample_metadata
        )
        
        # Create call relationship
        self.client.create_function_call_relationship(caller_qualified, callee_qualified)
        
        # Get dependencies
        dependencies = self.client.find_function_dependencies(caller_qualified)
        
        assert dependencies.nodes is not None
        assert dependencies.edges is not None
        assert len(dependencies.nodes) >= 2  # caller + callee
        assert len(dependencies.edges) >= 1  # call relationship
    
    def test_class_hierarchy(self, sample_metadata: Dict[str, Any]):
        """Test getting class hierarchy."""
        # Create parent class
        parent_name = "ParentClass"
        parent_qualified = "test.py::ParentClass"
        self.client.create_class_node(
            name=parent_name,
            qualified_name=parent_qualified,
            file_path="test.py",
            line_number=1,
            metadata=sample_metadata
        )
        
        # Create child class
        child_name = "ChildClass"
        child_qualified = "test.py::ChildClass"
        self.client.create_class_node(
            name=child_name,
            qualified_name=child_qualified,
            file_path="test.py",
            line_number=5,
            metadata=sample_metadata
        )
        
        # Create inheritance relationship
        self.client.create_class_inheritance_relationship(child_qualified, parent_qualified)
        
        # Get hierarchy
        hierarchy = self.client.find_class_hierarchy(child_qualified)
        
        assert hierarchy.nodes is not None
        assert hierarchy.edges is not None
        assert len(hierarchy.nodes) >= 2  # parent + child
        assert len(hierarchy.edges) >= 1  # inheritance relationship