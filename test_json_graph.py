#!/usr/bin/env python3
"""
Test script to verify the JSON-based graph system functionality
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.graph.json_graph_client import JsonGraphClient
from src.search.hybrid_search import HybridSearch
from src.query.milvus_client import MilvusClient
from src.embedding.embedding_service import EmbeddingService
from src.scanner.local_codebase_scanner import LocalCodebaseScanner
from src.processor.content_processor import ContentProcessor
from src.types import CodeChunk
from src.utils.logger import app_logger


async def test_json_graph_client():
    """Test JSON graph client functionality."""
    print("🧪 Testing JSON Graph Client...")
    
    # Initialize client
    client = JsonGraphClient("test_graph_data.json")
    
    # Test creating nodes
    file_node = client.create_file_node(
        file_path="/test/test.py",
        language="python",
        file_type="source",
        metadata={"file_size": 1024}
    )
    print(f"✅ Created file node: {file_node.id}")
    
    chunk = CodeChunk(
        id="test_chunk",
        file_path="/test/test.py",
        content="def test_function():\n    pass",
        start_line=1,
        end_line=2,
        language="python",
        chunk_type="function_definition",
        metadata={}
    )
    
    chunk_node = client.create_chunk_node(chunk)
    print(f"✅ Created chunk node: {chunk_node.id}")
    
    func_node = client.create_function_node(
        name="test_function",
        qualified_name="/test/test.py::test_function",
        file_path="/test/test.py",
        line_number=1,
        metadata={}
    )
    print(f"✅ Created function node: {func_node.id}")
    
    # Test creating relationships
    rel1 = client.create_file_chunk_relationship("/test/test.py", "test_chunk")
    print(f"✅ Created file-chunk relationship: {rel1.source_id} -> {rel1.target_id}")
    
    rel2 = client.create_function_chunk_relationship("/test/test.py::test_function", "test_chunk")
    print(f"✅ Created function-chunk relationship: {rel2.source_id} -> {rel2.target_id}")
    
    # Test file structure
    structure = client.get_file_structure("/test/test.py")
    print(f"✅ Got file structure: {len(structure.nodes)} nodes, {len(structure.edges)} edges")
    
    # Test stats
    stats = client.get_database_stats()
    print(f"✅ Got stats: {stats}")
    
    # Test graph data
    graph_data = client.get_graph_data()
    print(f"✅ Got graph data: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges")
    
    # Test node details
    details = client.get_node_details("/test/test.py::test_function")
    print(f"✅ Got node details: {details['node']['type']}")
    
    # Clean up
    client.clear_database()
    print("✅ Cleared database")
    
    # Remove test file
    if os.path.exists("test_graph_data.json"):
        os.remove("test_graph_data.json")
    
    return True


async def test_hybrid_search():
    """Test hybrid search with JSON graph."""
    print("\n🧪 Testing Hybrid Search...")
    
    try:
        # Initialize components
        graph_client = JsonGraphClient("test_search_graph.json")
        milvus_client = MilvusClient()
        embedding_service = EmbeddingService()
        hybrid_search = HybridSearch(milvus_client, graph_client, embedding_service)
        
        # Create test chunks
        test_chunks = [
            CodeChunk(
                id="chunk1",
                file_path="/test/test1.py",
                content="def hello_world():\n    print('Hello, World!')",
                start_line=1,
                end_line=2,
                language="python",
                chunk_type="function_definition",
                metadata={}
            ),
            CodeChunk(
                id="chunk2",
                file_path="/test/test2.py",
                content="def calculate_sum(a, b):\n    return a + b",
                start_line=1,
                end_line=2,
                language="python",
                chunk_type="function_definition",
                metadata={}
            )
        ]
        
        # Index chunks
        await hybrid_search.index_chunks(test_chunks)
        print("✅ Indexed test chunks")
        
        # Test search
        results = await hybrid_search.search("hello", top_k=5)
        print(f"✅ Search results: {len(results)} results")
        
        # Test graph enhancement
        results = await hybrid_search.search("function", top_k=5, use_graph=True)
        print(f"✅ Graph-enhanced search: {len(results)} results")
        
        # Clean up
        graph_client.clear_database()
        milvus_client.drop_collection()
        
        # Remove test file
        if os.path.exists("test_search_graph.json"):
            os.remove("test_search_graph.json")
        
        return True
        
    except Exception as e:
        print(f"❌ Hybrid search test failed: {e}")
        return False


async def test_ast_processor():
    """Test AST processor with JSON graph."""
    print("\n🧪 Testing AST Processor...")
    
    try:
        # Create test Python file
        test_file_content = '''
def hello_world():
    """Simple hello world function."""
    print("Hello, World!")

class Calculator:
    """Simple calculator class."""
    
    def add(self, a, b):
        return a + b
    
    def subtract(self, a, b):
        return a - b
'''
        
        # Write test file
        test_file = Path("test_sample.py")
        test_file.write_text(test_file_content)
        
        # Initialize components
        scanner = LocalCodebaseScanner()
        processor = ContentProcessor()
        
        # Scan file
        code_files = scanner.scan_directory(str(Path.cwd()))
        python_files = [f for f in code_files if f.path == "test_sample.py"]
        
        if python_files:
            python_files = scanner.load_files_content(python_files)
            
            # Process file
            chunks = processor.process_files(python_files)
            print(f"✅ Processed file into {len(chunks)} chunks")
            
            # Show chunk types
            for chunk in chunks:
                print(f"   - {chunk.chunk_type}: {chunk.start_line}-{chunk.end_line}")
        
        # Clean up
        if test_file.exists():
            test_file.unlink()
        
        return True
        
    except Exception as e:
        print(f"❌ AST processor test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting JSON Graph System Tests")
    print("=" * 50)
    
    tests = [
        ("JSON Graph Client", test_json_graph_client),
        ("Hybrid Search", test_hybrid_search),
        ("AST Processor", test_ast_processor),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print("-" * 30)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n📈 Summary: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! JSON Graph System is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
    
    return passed == len(results)


if __name__ == "__main__":
    asyncio.run(main())