#!/usr/bin/env python3
"""
Example usage script for the Code Retrieval System

This script demonstrates a complete index-search flow using local components
without requiring a server. It indexes the current directory, performs searches,
and cleans up resources afterward.
"""

import asyncio
import time
import os
from pathlib import Path

# Set up mock environment variables for demo
os.environ.setdefault('MCP_HOST', 'localhost')
os.environ.setdefault('MCP_PORT', '8000')

# Import local components
from src.scanner.local_codebase_scanner import LocalCodebaseScanner
from src.processor.content_processor import ContentProcessor
from src.query.milvus_client import MilvusClient
from src.graph.json_graph_client import JsonGraphClient
from src.embedding.embedding_service import EmbeddingService
from src.search.hybrid_search import HybridSearch
from src.search.rerank_service import GraphReranker
from src.types import CodeChunk, SearchResult
from src.utils.logger import app_logger


class CodeRetrievalDemo:
    """Demonstration of complete code retrieval workflow."""
    
    def __init__(self):
        self.logger = app_logger.bind(component="demo")
        
        # Initialize components
        self.scanner = None
        self.processor = None
        self.milvus_client = None
        self.graph_client = None
        self.embedding_service = None
        self.hybrid_search = None
        self.graph_reranker = None
        
        # Demo data - focus on Python files only
        self.codebase_path = str(Path.cwd().resolve())
        self.indexed_chunks = []
        self.search_results = []
    
    async def initialize_components(self):
        """Initialize all system components."""
        try:
            self.logger.info("Initializing system components...")
            
            # Initialize core components
            self.milvus_client = MilvusClient()
            self.graph_client = JsonGraphClient()
            self.embedding_service = EmbeddingService()
            self.hybrid_search = HybridSearch(self.milvus_client, self.graph_client, self.embedding_service)
            self.graph_reranker = GraphReranker(self.graph_client)
            
            self.logger.info("✅ All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing components: {e}")
            raise
    
    async def get_initial_stats(self):
        """Get initial system statistics."""
        try:
            print("\n📊 Initial System Statistics:")
            print("-" * 30)
            
            milvus_stats = self.milvus_client.get_collection_stats()
            graph_stats = self.graph_client.get_database_stats()
            
            if "error" not in milvus_stats:
                print(f"🗄️  Milvus entities: {milvus_stats.get('num_entities', 0)}")
            
            if "nodes" in graph_stats:
                total_nodes = sum(graph_stats["nodes"].values())
                total_rels = sum(graph_stats["relationships"].values())
                print(f"🕸️  Graph nodes: {total_nodes}")
                print(f"🕸️  Graph relationships: {total_rels}")
            
        except Exception as e:
            self.logger.error(f"Error getting initial stats: {e}")
    
    async def scan_and_process_files(self):
        """Scan and process files from the codebase."""
        try:
            print(f"\n📁 Scanning codebase: {self.codebase_path}")
            print("-" * 30)
            
            # Initialize scanner and processor
            self.scanner = LocalCodebaseScanner()
            self.processor = ContentProcessor()
            
            # Force AST splitter usage
            self.processor.ast_parser._initialize_parsers()
            
            # Scan files
            print("🔍 Scanning for Python files...")
            code_files = self.scanner.scan_directory(max_workers=4)
            
            # Filter to only Python files
            python_files = [f for f in code_files if f.language == 'python']
            
            if not python_files:
                print("ℹ️  No Python files found in current directory")
                return
            
            print(f"📋 Found {len(python_files)} Python files to process")
            
            # Load file content
            print("📖 Loading Python file content...")
            python_files = self.scanner.load_files_content(python_files, max_workers=4)
            
            if not python_files:
                print("ℹ️  No Python files could be loaded")
                return
            
            print(f"✅ Successfully loaded {len(python_files)} Python files")
            
            # Process files into chunks using AST splitter
            print("🔧 Processing Python files into chunks using AST splitter...")
            self.indexed_chunks = self.processor.process_files(python_files)
            
            if not self.indexed_chunks:
                print("ℹ️  No chunks generated from files")
                return
            
            print(f"✅ Generated {len(self.indexed_chunks)} chunks")
            
            # Show some sample chunks
            print("\n📝 Sample Python chunks:")
            for i, chunk in enumerate(self.indexed_chunks[:3]):
                print(f"  {i+1}. {chunk.file_path}:{chunk.start_line}-{chunk.end_line} ({chunk.chunk_type})")
                print(f"     Content preview: {chunk.content[:100]}...")
            
        except Exception as e:
            self.logger.error(f"Error scanning and processing files: {e}")
            raise
    
    async def index_chunks(self):
        """Index the processed chunks."""
        try:
            print(f"\n📚 Indexing {len(self.indexed_chunks)} chunks...")
            print("-" * 30)
            
            await self.hybrid_search.index_chunks(self.indexed_chunks)
            
            print("✅ Chunks indexed successfully")
            
            # Get updated statistics
            milvus_stats = self.milvus_client.get_collection_stats()
            graph_stats = self.graph_client.get_database_stats()
            
            print(f"\n📊 Updated Statistics:")
            if "error" not in milvus_stats:
                print(f"🗄️  Milvus entities: {milvus_stats.get('num_entities', 0)}")
            
            if "nodes" in graph_stats:
                total_nodes = sum(graph_stats["nodes"].values())
                total_rels = sum(graph_stats["relationships"].values())
                print(f"🕸️  Graph nodes: {total_nodes}")
                print(f"🕸️  Graph relationships: {total_rels}")
            
        except Exception as e:
            self.logger.error(f"Error indexing chunks: {e}")
            raise
    
    async def perform_searches(self):
        """Perform various search queries."""
        try:
            print(f"\n🔍 Performing Search Demonstrations")
            print("-" * 30)
            
            # Define search queries relevant to Python code
            search_queries = [
                "function definition",
                "class implementation",
                "import statements",
                "error handling",
                "main function",
                "async function",
                "class method",
                "logger usage"
            ]
            
            # Filter queries to those relevant to the codebase
            relevant_queries = []
            for query in search_queries:
                # Perform a quick search to see if results exist
                results = await self.hybrid_search.search(
                    query=query,
                    top_k=3,
                    vector_weight=0.6,
                    bm25_weight=0.4,
                    use_graph=True
                )
                if results:
                    relevant_queries.append(query)
                    self.search_results.extend(results)
            
            if not relevant_queries:
                print("ℹ️  No relevant search results found")
                # Try some generic queries
                generic_queries = ["main", "class", "def", "import"]
                for query in generic_queries:
                    results = await self.hybrid_search.search(
                        query=query,
                        top_k=3,
                        vector_weight=0.6,
                        bm25_weight=0.4,
                        use_graph=True
                    )
                    if results:
                        relevant_queries.append(query)
                        self.search_results.extend(results)
                        break
            
            # Perform and display searches
            for query in relevant_queries[:3]:  # Limit to 3 queries
                print(f"\n🔎 Query: '{query}'")
                
                results = await self.hybrid_search.search(
                    query=query,
                    top_k=5,
                    vector_weight=0.6,
                    bm25_weight=0.4,
                    use_graph=True
                )
                
                if results:
                    print(f"✅ Found {len(results)} results:")
                    for i, result in enumerate(results[:3], 1):
                        chunk = result.chunk
                        print(f"  {i}. {chunk.file_path}:{chunk.start_line}-{chunk.end_line}")
                        print(f"     Score: {result.score:.4f}")
                        print(f"     Type: {chunk.chunk_type}")
                        print(f"     Content: {chunk.content[:100]}...")
                else:
                    print("ℹ️  No results found")
                
                time.sleep(0.5)  # Small delay between searches
            
        except Exception as e:
            self.logger.error(f"Error performing searches: {e}")
            raise
    
    async def demonstrate_graph_features(self):
        """Demonstrate graph-based features."""
        try:
            print(f"\n🕸️  Graph Feature Demonstrations")
            print("-" * 30)
            
            # Get file structure for a sample Python file
            if self.indexed_chunks:
                sample_file = self.indexed_chunks[0].file_path
                print(f"📁 Getting structure for Python file: {sample_file}")
                
                graph_result = self.graph_client.get_file_structure(sample_file)
                
                if graph_result.nodes:
                    print(f"✅ Found {len(graph_result.nodes)} nodes:")
                    
                    classes = [node for node in graph_result.nodes if node.type == "Class"]
                    functions = [node for node in graph_result.nodes if node.type == "Function"]
                    
                    if classes:
                        print(f"   📦 Python Classes: {len(classes)}")
                        for cls in classes[:2]:
                            print(f"      - {cls.id}")
                    
                    if functions:
                        print(f"   🔧 Python Functions: {len(functions)}")
                        for func in functions[:2]:
                            print(f"      - {func.id}")
                else:
                    print("ℹ️  No graph structure found for sample file")
            
        except Exception as e:
            self.logger.error(f"Error demonstrating graph features: {e}")
            # Don't raise - this is a demo feature
    
    async def cleanup_resources(self):
        """Clean up all indexed resources."""
        try:
            print(f"\n🧹 Cleaning Up Resources")
            print("-" * 30)
            
            # Clear all data from databases
            print("🗑️  Clearing database entries...")
            
            # Get final stats before cleanup
            milvus_stats_before = self.milvus_client.get_collection_stats()
            graph_stats_before = self.graph_client.get_database_stats()
            
            # Clear databases
            self.milvus_client.drop_collection()
            self.graph_client.clear_database()
            
            print("✅ Database entries cleared")
            
            # Show cleanup summary
            print(f"\n📊 Cleanup Summary:")
            if "error" not in milvus_stats_before:
                print(f"🗄️  Milvus entries removed: {milvus_stats_before.get('num_entities', 0)}")
            
            if "nodes" in graph_stats_before:
                total_nodes = sum(graph_stats_before["nodes"].values())
                total_rels = sum(graph_stats_before["relationships"].values())
                print(f"🕸️  Graph nodes removed: {total_nodes}")
                print(f"🕸️  Graph relationships removed: {total_rels}")
            
            print(f"📝 Chunks processed: {len(self.indexed_chunks)}")
            print(f"🔍 Searches performed: {len(self.search_results)}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up resources: {e}")
            raise
    
    async def run_demo(self):
        """Run the complete demonstration."""
        print("🚀 Python Code Retrieval System - Complete Demo")
        print("=" * 50)
        print(f"📁 Python Codebase: {self.codebase_path}")
        print("=" * 50)
        
        try:
            # Step 1: Initialize components
            await self.initialize_components()
            
            # Step 2: Get initial statistics
            await self.get_initial_stats()
            
            # Step 3: Scan and process files
            await self.scan_and_process_files()
            
            if not self.indexed_chunks:
                print("ℹ️  No files to process. Demo completed.")
                return
            
            # Step 4: Index chunks
            await self.index_chunks()
            
            # Step 5: Perform searches
            await self.perform_searches()
            
            # Step 6: Demonstrate graph features
            await self.demonstrate_graph_features()
            
            # Step 7: Cleanup resources
            await self.cleanup_resources()
            
            print(f"\n✅ Python Code Demo completed successfully!")
            print(f"📊 Summary: Processed {len(self.indexed_chunks)} Python chunks, performed {len(self.search_results)} searches")
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            self.logger.error(f"Demo error: {e}")
            raise
        finally:
            # Ensure cleanup even if demo fails
            try:
                if self.milvus_client and self.graph_client:
                    print(f"\n🧹 Final cleanup...")
                    self.milvus_client.drop_collection()
                    self.graph_client.clear_database()
                    print("✅ Resources cleaned up")
            except Exception as cleanup_error:
                print(f"⚠️  Cleanup error: {cleanup_error}")


async def main():
    """Main demo function."""
    demo = CodeRetrievalDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main())