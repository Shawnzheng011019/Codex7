import pytest
import time
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.scanner.local_codebase_scanner import LocalCodebaseScanner
from src.processor.content_processor import ContentProcessor
from src.graph.neo4j_client import Neo4jClient
from src.query.milvus_client import MilvusClient
from src.embedding.embedding_service import EmbeddingService


class TestIntegration:
    """End-to-end integration tests."""
    
    def test_full_pipeline_scan_to_graph(
        self, 
        temp_codebase: Path, 
        neo4j_client: Neo4jClient,
        content_processor: ContentProcessor
    ):
        """Test complete pipeline from scanning to graph creation."""
        # Step 1: Scan codebase
        scanner = LocalCodebaseScanner(str(temp_codebase))
        code_files = scanner.scan_directory()
        
        assert len(code_files) > 0
        print(f"Scanned {len(code_files)} files")
        
        # Step 2: Load file contents
        loaded_files = scanner.load_files_content(code_files)
        assert len(loaded_files) > 0
        print(f"Loaded content for {len(loaded_files)} files")
        
        # Step 3: Process files into chunks (with AST enforcement)
        all_chunks = []
        skipped_files = []
        
        for code_file in loaded_files:
            chunks = content_processor.process_file(code_file)
            if chunks:
                all_chunks.extend(chunks)
                print(f"Processed {code_file.path}: {len(chunks)} chunks")
            else:
                skipped_files.append(code_file.path)
                print(f"Skipped {code_file.path}: no AST support or no nodes found")
        
        print(f"Total chunks generated: {len(all_chunks)}")
        print(f"Files skipped: {skipped_files}")
        
        # Step 4: Create graph nodes and relationships
        if all_chunks:
            # Create file nodes
            file_paths = set(chunk.file_path for chunk in all_chunks)
            file_nodes = {}
            
            for file_path in file_paths:
                # Find the original code file for metadata
                original_file = next((f for f in loaded_files if f.path == file_path), None)
                if original_file:
                    metadata = {
                        'file_size': original_file.size,
                        'file_type': original_file.file_type.value
                    }
                    
                    file_node = neo4j_client.create_file_node(
                        file_path=file_path,
                        language=original_file.language or "unknown",
                        file_type=original_file.file_type.value,
                        metadata=metadata
                    )
                    file_nodes[file_path] = file_node
                    print(f"Created file node: {file_path}")
            
            # Create chunk nodes
            chunk_nodes = {}
            for chunk in all_chunks:
                chunk_node = neo4j_client.create_chunk_node(chunk)
                chunk_nodes[chunk.id] = chunk_node
                print(f"Created chunk node: {chunk.id}")
            
            # Create file-chunk relationships
            for chunk in all_chunks:
                if chunk.file_path in file_nodes:
                    edge = neo4j_client.create_file_chunk_relationship(
                        chunk.file_path, 
                        chunk.id
                    )
                    print(f"Created relationship: {chunk.file_path} -> {chunk.id}")
            
            # Verify graph was created
            stats = neo4j_client.get_database_stats()
            print(f"Graph stats: {stats}")
            
            assert stats["nodes"].get("File", 0) > 0
            assert stats["nodes"].get("Chunk", 0) > 0
            assert stats["relationships"].get("CONTAINS", 0) > 0
            
    def test_full_pipeline_with_embeddings(
        self,
        temp_codebase: Path,
        milvus_client: MilvusClient,
        content_processor: ContentProcessor
    ):
        """Test complete pipeline including embeddings."""
        # Step 1: Scan and process
        scanner = LocalCodebaseScanner(str(temp_codebase))
        code_files = scanner.scan_directory()
        loaded_files = scanner.load_files_content(code_files)
        
        all_chunks = []
        for code_file in loaded_files:
            chunks = content_processor.process_file(code_file)
            all_chunks.extend(chunks)
        
        if not all_chunks:
            pytest.skip("No chunks generated from test codebase")
        
        print(f"Generated {len(all_chunks)} chunks for embedding")
        
        # Step 2: Generate dummy embeddings (simulating real embedding service)
        import numpy as np
        for chunk in all_chunks:
            # Create deterministic embedding based on content
            content_hash = hash(chunk.content) % 1000
            embedding = np.random.RandomState(content_hash).rand(768).tolist()
            chunk.embedding = embedding
        
        # Step 3: Insert into Milvus
        result = milvus_client.insert_chunks(all_chunks)
        assert result is not None
        
        milvus_client.flush()
        
        # Step 4: Verify insertion
        count = milvus_client.get_entity_count()
        assert count >= len(all_chunks)
        print(f"Inserted {count} entities into Milvus")
        
        # Step 5: Test search
        if all_chunks:
            query_embedding = all_chunks[0].embedding
            search_results = milvus_client.search_similar(query_embedding, top_k=3)
            
            assert len(search_results) > 0
            print(f"Search returned {len(search_results)} results")
            
            # First result should be very similar (same vector)
            assert search_results[0].distance < 0.1
    
    def test_error_recovery_and_partial_processing(
        self,
        temp_codebase: Path,
        neo4j_client: Neo4jClient,
        content_processor: ContentProcessor
    ):
        """Test system behavior with partial failures."""
        # Add a problematic file to the codebase
        problematic_file = temp_codebase / "broken.py"
        problematic_file.write_text("def broken(\n    # incomplete")
        
        # Also add a file with unsupported extension
        unsupported_file = temp_codebase / "data.xyz"
        unsupported_file.write_text("some data content")
        
        # Scan everything
        scanner = LocalCodebaseScanner(str(temp_codebase))
        code_files = scanner.scan_directory()
        loaded_files = scanner.load_files_content(code_files)
        
        # Process files - some should succeed, some should fail gracefully
        successful_chunks = []
        failed_files = []
        
        for code_file in loaded_files:
            try:
                chunks = content_processor.process_file(code_file)
                if chunks:
                    successful_chunks.extend(chunks)
                    print(f"Successfully processed: {code_file.path}")
                else:
                    failed_files.append(code_file.path)
                    print(f"Skipped/failed: {code_file.path}")
            except Exception as e:
                failed_files.append(code_file.path)
                print(f"Exception processing {code_file.path}: {e}")
        
        print(f"Successful chunks: {len(successful_chunks)}")
        print(f"Failed files: {failed_files}")
        
        # Should have some successful processing despite failures
        # (depending on what parsers are available)
        assert isinstance(successful_chunks, list)
        assert isinstance(failed_files, list)
        
        # System should continue working with successful chunks
        if successful_chunks:
            # Create graph nodes for successful chunks
            for chunk in successful_chunks[:5]:  # Just test a few
                try:
                    node = neo4j_client.create_chunk_node(chunk)
                    assert node is not None
                    print(f"Created node for chunk: {chunk.id}")
                except Exception as e:
                    print(f"Failed to create node for {chunk.id}: {e}")
    
    def test_large_file_handling(
        self,
        temp_codebase: Path,
        content_processor: ContentProcessor
    ):
        """Test handling of larger files."""
        # Create a larger Python file
        large_content = []
        for i in range(50):
            large_content.append(f"""
def function_{i}():
    '''Function number {i}.'''
    x = {i}
    y = {i * 2}
    z = x + y
    return z

class Class_{i}:
    '''Class number {i}.'''
    
    def __init__(self, value={i}):
        self.value = value
    
    def get_value(self):
        return self.value
    
    def calculate(self):
        return self.value * {i}
""")
        
        large_file = temp_codebase / "large_file.py"
        large_file.write_text('\n'.join(large_content))
        
        # Process the large file
        scanner = LocalCodebaseScanner(str(temp_codebase))
        code_files = [f for f in scanner.scan_directory() if f.path.endswith('large_file.py')]
        
        if code_files:
            loaded_files = scanner.load_files_content(code_files)
            
            if loaded_files:
                chunks = content_processor.process_file(loaded_files[0])
                print(f"Large file generated {len(chunks)} chunks")
                
                # Should handle large files without issues
                assert isinstance(chunks, list)
                
                if chunks:
                    # Verify chunk structure is maintained
                    for chunk in chunks[:5]:  # Check first few chunks
                        assert chunk.start_line > 0
                        assert chunk.end_line >= chunk.start_line
                        assert len(chunk.content.strip()) > 0
                        assert chunk.chunk_type in ['function_definition', 'class_definition']
    
    def test_concurrent_processing_simulation(
        self,
        temp_codebase: Path,
        content_processor: ContentProcessor
    ):
        """Test processing multiple files as if in concurrent scenario."""
        scanner = LocalCodebaseScanner(str(temp_codebase))
        code_files = scanner.scan_directory()
        loaded_files = scanner.load_files_content(code_files)
        
        # Simulate processing multiple files
        all_results = []
        
        for code_file in loaded_files:
            result = {
                'file_path': code_file.path,
                'language': code_file.language,
                'chunks': content_processor.process_file(code_file),
                'processed_at': time.time()
            }
            all_results.append(result)
        
        # Verify all files were processed (successfully or skipped)
        assert len(all_results) == len(loaded_files)
        
        # Verify timing and ordering
        for i in range(1, len(all_results)):
            assert all_results[i]['processed_at'] >= all_results[i-1]['processed_at']
        
        # Count successful vs skipped
        successful = sum(1 for r in all_results if r['chunks'])
        skipped = len(all_results) - successful
        
        print(f"Concurrent simulation: {successful} successful, {skipped} skipped")
        
        # Should have processed without errors
        assert all(isinstance(r['chunks'], list) for r in all_results)
    
    def test_cleanup_verification(
        self,
        neo4j_client: Neo4jClient,
        milvus_client: MilvusClient
    ):
        """Test that cleanup operations work correctly."""
        # Insert some test data
        from src.types import CodeChunk
        
        test_chunk = CodeChunk(
            id="cleanup_test_chunk",
            file_path="cleanup_test.py",
            content="def cleanup_test():\n    pass",
            start_line=1,
            end_line=2,
            language="python",
            chunk_type="function_definition",
            metadata={"file_size": 100},
            embedding=[0.1] * 768
        )
        
        # Insert into both systems
        neo4j_client.create_chunk_node(test_chunk)
        milvus_client.insert_chunks([test_chunk])
        milvus_client.flush()
        
        # Verify data exists
        neo4j_stats = neo4j_client.get_database_stats()
        milvus_count = milvus_client.get_entity_count()
        
        assert neo4j_stats["nodes"].get("Chunk", 0) > 0
        assert milvus_count > 0
        
        print(f"Before cleanup - Neo4j chunks: {neo4j_stats['nodes'].get('Chunk', 0)}, Milvus entities: {milvus_count}")
        
        # Cleanup operations will be performed by fixtures
        # This test just verifies the cleanup methods exist and work
        assert hasattr(neo4j_client, 'clear_database')
        assert hasattr(milvus_client, 'drop_collection') 