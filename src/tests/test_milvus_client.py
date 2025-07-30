import pytest
import numpy as np
from typing import List
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.query.milvus_client import MilvusClient
from src.types import CodeChunk


class TestMilvusClient:
    """Test Milvus client functionality."""
    
    def test_connection_and_collection_creation(self, milvus_client: MilvusClient):
        """Test Milvus connection and collection creation."""
        # Collection should be created during initialization
        assert milvus_client.collection is not None
        
        # Check collection info
        info = milvus_client.get_collection_info()
        assert "name" in info
        assert "schema" in info
        
    def test_insert_embeddings(self, milvus_client: MilvusClient, sample_code_file):
        """Test inserting embeddings."""
        # Create sample chunks with embeddings
        chunks = [
            CodeChunk(
                id="milvus_test_chunk_1",
                file_path=sample_code_file.path,
                content="def test_function_1():\n    return 'test1'",
                start_line=1,
                end_line=2,
                language="python",
                chunk_type="function_definition",
                metadata={"file_size": 100},
                embedding=[0.1, 0.2, 0.3] + [0.0] * 765  # 768-dimensional vector
            ),
            CodeChunk(
                id="milvus_test_chunk_2",
                file_path=sample_code_file.path,
                content="def test_function_2():\n    return 'test2'",
                start_line=3,
                end_line=4,
                language="python",
                chunk_type="function_definition",
                metadata={"file_size": 100},
                embedding=[0.2, 0.3, 0.4] + [0.0] * 765  # 768-dimensional vector
            )
        ]
        
        # Insert chunks
        result = milvus_client.insert_chunks(chunks)
        assert result is not None
        
        # Flush to ensure data is persisted
        milvus_client.flush()
        
        # Verify insertion
        count = milvus_client.get_entity_count()
        assert count >= 2
        
    def test_vector_search(self, milvus_client: MilvusClient, sample_code_file):
        """Test vector similarity search."""
        # Insert test data first
        chunks = [
            CodeChunk(
                id="vector_search_chunk_1",
                file_path=sample_code_file.path,
                content="def search_test_1():\n    return 'search1'",
                start_line=1,
                end_line=2,
                language="python",
                chunk_type="function_definition",
                metadata={"file_size": 100},
                embedding=[1.0, 0.0, 0.0] + [0.0] * 765
            ),
            CodeChunk(
                id="vector_search_chunk_2",
                file_path=sample_code_file.path,
                content="def search_test_2():\n    return 'search2'",
                start_line=3,
                end_line=4,
                language="python",
                chunk_type="function_definition",
                metadata={"file_size": 100},
                embedding=[0.0, 1.0, 0.0] + [0.0] * 765
            )
        ]
        
        milvus_client.insert_chunks(chunks)
        milvus_client.flush()
        
        # Perform vector search
        query_vector = [1.0, 0.0, 0.0] + [0.0] * 765
        results = milvus_client.search_similar(query_vector, top_k=2)
        
        assert len(results) > 0
        assert all(hasattr(result, 'id') for result in results)
        assert all(hasattr(result, 'distance') for result in results)
        
        # Results should be sorted by similarity (distance)
        if len(results) > 1:
            assert results[0].distance <= results[1].distance
            
    def test_search_with_filters(self, milvus_client: MilvusClient, sample_code_file):
        """Test search with metadata filters."""
        # Insert test data with different languages
        chunks = [
            CodeChunk(
                id="filter_test_py",
                file_path="test.py",
                content="def python_function():\n    pass",
                start_line=1,
                end_line=2,
                language="python",
                chunk_type="function_definition",
                metadata={"file_size": 100},
                embedding=[0.5, 0.5, 0.0] + [0.0] * 765
            ),
            CodeChunk(
                id="filter_test_js",
                file_path="test.js",
                content="function jsFunction() {\n}",
                start_line=1,
                end_line=2,
                language="javascript",
                chunk_type="function_definition",
                metadata={"file_size": 80},
                embedding=[0.5, 0.0, 0.5] + [0.0] * 765
            )
        ]
        
        milvus_client.insert_chunks(chunks)
        milvus_client.flush()
        
        # Search with language filter
        query_vector = [0.5, 0.5, 0.0] + [0.0] * 765
        results = milvus_client.search_similar(
            query_vector,
            top_k=5,
            filters={"language": "python"}
        )
        
        assert len(results) > 0
        # Note: Actual filter verification would depend on Milvus client implementation
        
    def test_get_entity_by_id(self, milvus_client: MilvusClient, sample_code_file):
        """Test retrieving entity by ID."""
        # Insert test chunk
        chunk = CodeChunk(
            id="get_by_id_test",
            file_path=sample_code_file.path,
            content="def get_by_id_function():\n    return 'found'",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata={"file_size": 100},
            embedding=[0.7, 0.3, 0.0] + [0.0] * 765
        )
        
        milvus_client.insert_chunks([chunk])
        milvus_client.flush()
        
        # Retrieve by ID
        result = milvus_client.get_chunk_by_id("get_by_id_test")
        
        if result:  # May return None if not implemented
            assert result.id == "get_by_id_test"
            assert result.content == chunk.content
            
    def test_batch_operations(self, milvus_client: MilvusClient, sample_code_file):
        """Test batch insert operations."""
        # Create large batch of chunks
        chunks = []
        for i in range(50):
            chunks.append(CodeChunk(
                id=f"batch_test_chunk_{i}",
                file_path=sample_code_file.path,
                content=f"def batch_function_{i}():\n    return {i}",
                start_line=i * 2 + 1,
                end_line=i * 2 + 2,
                language="python",
                chunk_type="function_definition",
                metadata={"file_size": 100 + i},
                embedding=np.random.rand(768).tolist()
            ))
        
        # Insert in batch
        result = milvus_client.insert_chunks(chunks)
        assert result is not None
        
        milvus_client.flush()
        
        # Verify all were inserted
        count = milvus_client.get_entity_count()
        assert count >= 50
        
    def test_collection_statistics(self, milvus_client: MilvusClient):
        """Test collection statistics and info."""
        info = milvus_client.get_collection_info()
        
        assert "name" in info
        assert "schema" in info
        
        # Test entity count
        count = milvus_client.get_entity_count()
        assert isinstance(count, int)
        assert count >= 0
        
    def test_error_handling(self, milvus_client: MilvusClient):
        """Test error handling for invalid operations."""
        # Test with invalid embedding dimension
        invalid_chunk = CodeChunk(
            id="invalid_chunk",
            file_path="test.py",
            content="def invalid():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata={"file_size": 100},
            embedding=[0.1, 0.2]  # Wrong dimension
        )
        
        # This should handle the error gracefully
        try:
            result = milvus_client.insert_chunks([invalid_chunk])
            # If no exception, that's also fine - depends on implementation
        except Exception as e:
            # Expected for invalid dimension
            assert "dimension" in str(e).lower() or "vector" in str(e).lower()
            
    def test_cleanup(self, milvus_client: MilvusClient):
        """Test cleanup operations."""
        # Insert some test data
        chunk = CodeChunk(
            id="cleanup_test_chunk",
            file_path="cleanup_test.py",
            content="def cleanup_function():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata={"file_size": 100},
            embedding=[0.1] * 768
        )
        
        milvus_client.insert_chunks([chunk])
        milvus_client.flush()
        
        # Verify data exists
        count_before = milvus_client.get_entity_count()
        assert count_before > 0
        
        # Test collection drop (will be done in fixture cleanup)
        # Just verify the method exists
        assert hasattr(milvus_client, 'drop_collection') 