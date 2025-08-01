import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from fastmcp import FastMCP
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from ..config import settings
from ..scanner.local_codebase_scanner import LocalCodebaseScanner
from ..processor.content_processor import ContentProcessor
from ..query.milvus_client import MilvusClient
from ..graph.json_graph_client import JsonGraphClient
from ..embedding.embedding_service import EmbeddingService
from ..search.hybrid_search import HybridSearch
from ..search.rerank_service import GraphReranker
from ..types import CodeChunk, SearchResult
from ..utils.logger import app_logger


class CodeRetrievalMCP:
    """MCP Server for Code Retrieval System."""
    
    def __init__(self):
        self.logger = app_logger.bind(component="mcp_server")
        self.mcp = FastMCP("Code Retrieval System")
        
        # Initialize components
        self.milvus_client = None
        self.graph_client = None
        self.embedding_service = None
        self.hybrid_search = None
        self.graph_reranker = None
        
        self._initialize_components()
        self._register_tools()
    
    def _initialize_components(self):
        """Initialize all system components."""
        try:
            self.milvus_client = MilvusClient()
            self.graph_client = JsonGraphClient()
            self.embedding_service = EmbeddingService()
            self.hybrid_search = HybridSearch(self.milvus_client, self.graph_client, self.embedding_service)
            self.graph_reranker = GraphReranker(self.graph_client)
            
            self.logger.info("All components initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing components: {e}")
            raise
    
    def _register_tools(self):
        """Register all MCP tools."""
        
        @self.mcp.tool()
        async def index_codebase(root_path: str = None, max_workers: int = 4) -> str:
            """Index a codebase for search.
            
            Args:
                root_path: Path to the codebase directory (optional, defaults to current directory)
                max_workers: Number of parallel workers for processing
                
            Returns:
                Status message with indexing statistics
            """
            try:
                # Initialize scanner and processor
                scanner = LocalCodebaseScanner(root_path)
                processor = ContentProcessor()
                
                # Scan files
                self.logger.info(f"Starting scan of {root_path}")
                code_files = scanner.scan_directory(max_workers)
                
                # Load file content
                code_files = scanner.load_files_content(code_files, max_workers)
                
                if not code_files:
                    return f"No files found to index in {root_path}"
                
                # Process files into chunks
                chunks = processor.process_files(code_files)
                
                if not chunks:
                    return f"No chunks generated from {len(code_files)} files"
                
                # Index chunks
                await self.hybrid_search.index_chunks(chunks)
                
                # Get statistics
                milvus_stats = self.milvus_client.get_collection_stats()
                neo4j_stats = self.graph_client.get_database_stats()
                
                result = f"""
✅ Successfully indexed codebase:
📁 Files processed: {len(code_files)}
🔧 Chunks generated: {len(chunks)}
🗄️  Milvus entities: {milvus_stats.get('num_entities', 0)}
🕸️  Graph nodes: {sum(neo4j_stats.get('nodes', {}).values())}
🔗 Graph relationships: {sum(neo4j_stats.get('relationships', {}).values())}
"""
                return result
                
            except Exception as e:
                self.logger.error(f"Error indexing codebase: {e}")
                return f"❌ Error indexing codebase: {str(e)}"
        
        @self.mcp.tool()
        async def search_code(query: str, top_k: int = 10, use_graph: bool = True, use_reranking: bool = True) -> str:
            """Search code using hybrid search.
            
            Args:
                query: Search query text
                top_k: Number of results to return
                use_graph: Whether to use graph information for enhancement
                use_reranking: Whether to apply reranking
                
            Returns:
                Search results formatted as text
            """
            try:
                # Perform search
                results = await self.hybrid_search.search(
                    query=query,
                    top_k=top_k,
                    vector_weight=0.6,
                    bm25_weight=0.4,
                    use_graph=use_graph
                )
                
                # Apply reranking if requested
                if use_reranking and results:
                    results = await self.graph_reranker.rerank_results(results, query, top_k)
                
                if not results:
                    return f"No results found for query: {query}"
                
                # Format results
                formatted_results = f"🔍 Search Results for: {query}\n"
                formatted_results += "=" * 50 + "\n\n"
                
                for i, result in enumerate(results, 1):
                    chunk = result.chunk
                    formatted_results += f"{i}. **{chunk.file_path}:{chunk.start_line}-{chunk.end_line}**\n"
                    formatted_results += f"   Score: {result.score:.4f}\n"
                    formatted_results += f"   Type: {chunk.chunk_type}\n"
                    formatted_results += f"   Language: {chunk.language}\n"
                    formatted_results += f"   Content: {chunk.content[:200]}{'...' if len(chunk.content) > 200 else ''}\n"
                    
                    # Add graph context if available
                    if "graph_context" in result.metadata:
                        graph_ctx = result.metadata["graph_context"]
                        if "related_functions" in graph_ctx:
                            formatted_results += f"   Related Functions: {', '.join([f['name'] for f in graph_ctx['related_functions'][:3]])}\n"
                    
                    formatted_results += "\n"
                
                return formatted_results
                
            except Exception as e:
                self.logger.error(f"Error searching code: {e}")
                return f"❌ Error searching code: {str(e)}"
        
        @self.mcp.tool()
        async def search_in_file(file_path: str, query: str = "", top_k: int = 10) -> str:
            """Search within a specific file.
            
            Args:
                file_path: Path to the file to search within (can be relative or absolute)
                query: Optional query to filter results
                top_k: Number of results to return
                
            Returns:
                Search results from the specified file
            """
            try:
                # Convert to absolute path
                abs_file_path = str(Path(file_path).resolve())
                results = self.hybrid_search.search_by_file(
                    file_path=abs_file_path,
                    query=query,
                    top_k=top_k
                )
                
                if not results:
                    return f"No results found in file: {file_path}"
                
                # Format results
                formatted_results = f"📁 Search Results in: {file_path}\n"
                if query:
                    formatted_results += f"🔍 Query: {query}\n"
                formatted_results += "=" * 50 + "\n\n"
                
                for i, result in enumerate(results, 1):
                    chunk = result.chunk
                    formatted_results += f"{i}. **Lines {chunk.start_line}-{chunk.end_line}**\n"
                    formatted_results += f"   Type: {chunk.chunk_type}\n"
                    formatted_results += f"   Content: {chunk.content[:150]}{'...' if len(chunk.content) > 150 else ''}\n\n"
                
                return formatted_results
                
            except Exception as e:
                self.logger.error(f"Error searching file: {e}")
                return f"❌ Error searching file: {str(e)}"
        
        @self.mcp.tool()
        async def get_function_dependencies(function_name: str) -> str:
            """Get function dependencies from the code graph.
            
            Args:
                function_name: Qualified name of the function
                
            Returns:
                Function dependency graph information
            """
            try:
                graph_result = self.graph_client.find_function_dependencies(function_name)
                
                if not graph_result.nodes:
                    return f"No dependencies found for function: {function_name}"
                
                # Format results
                formatted_results = f"🔗 Function Dependencies: {function_name}\n"
                formatted_results += "=" * 50 + "\n\n"
                
                # Find the main function
                main_function = next((node for node in graph_result.nodes if node.id == function_name), None)
                if main_function:
                    formatted_results += f"🎯 **Target Function:** {main_function.id}\n"
                    formatted_results += f"   File: {main_function.file_path}\n"
                    formatted_results += f"   Line: {main_function.line_number}\n\n"
                
                # Find dependencies
                dependencies = [node for node in graph_result.nodes if node.id != function_name]
                if dependencies:
                    formatted_results += "📋 **Dependencies:**\n"
                    for dep in dependencies:
                        formatted_results += f"   - {dep.id} ({dep.file_path}:{dep.line_number})\n"
                
                # Show relationships
                if graph_result.edges:
                    formatted_results += f"\n🔗 **Calls ({len(graph_result.edges)}):**\n"
                    for edge in graph_result.edges:
                        formatted_results += f"   {edge.source_id} → {edge.target_id}\n"
                
                return formatted_results
                
            except Exception as e:
                self.logger.error(f"Error getting function dependencies: {e}")
                return f"❌ Error getting function dependencies: {str(e)}"
        
        @self.mcp.tool()
        async def get_class_hierarchy(class_name: str) -> str:
            """Get class hierarchy from the code graph.
            
            Args:
                class_name: Qualified name of the class
                
            Returns:
                Class hierarchy information
            """
            try:
                graph_result = self.graph_client.find_class_hierarchy(class_name)
                
                if not graph_result.nodes:
                    return f"No hierarchy found for class: {class_name}"
                
                # Format results
                formatted_results = f"🏗️ Class Hierarchy: {class_name}\n"
                formatted_results += "=" * 50 + "\n\n"
                
                # Build hierarchy tree
                hierarchy = self._build_class_hierarchy(graph_result)
                formatted_results += self._format_hierarchy_tree(hierarchy, class_name)
                
                return formatted_results
                
            except Exception as e:
                self.logger.error(f"Error getting class hierarchy: {e}")
                return f"❌ Error getting class hierarchy: {str(e)}"
        
        @self.mcp.tool()
        async def get_file_structure(file_path: str) -> str:
            """Get the structure of a specific file.
            
            Args:
                file_path: Path to the file (can be relative or absolute)
                
            Returns:
                File structure information
            """
            try:
                # Convert to absolute path
                abs_file_path = str(Path(file_path).resolve())
                graph_result = self.graph_client.get_file_structure(abs_file_path)
                
                if not graph_result.nodes:
                    return f"No structure found for file: {file_path}"
                
                # Format results
                formatted_results = f"📁 File Structure: {file_path}\n"
                formatted_results += "=" * 50 + "\n\n"
                
                # Group by type
                classes = [node for node in graph_result.nodes if node.type == "Class"]
                functions = [node for node in graph_result.nodes if node.type == "Function"]
                chunks = [node for node in graph_result.nodes if node.type == "Chunk"]
                
                if classes:
                    formatted_results += "📦 **Classes:**\n"
                    for cls in classes:
                        formatted_results += f"   - {cls.id} (line {cls.line_number})\n"
                    formatted_results += "\n"
                
                if functions:
                    formatted_results += "🔧 **Functions:**\n"
                    for func in functions:
                        formatted_results += f"   - {func.id} (line {func.line_number})\n"
                    formatted_results += "\n"
                
                if chunks:
                    formatted_results += "📄 **Code Chunks:**\n"
                    for chunk in chunks:
                        chunk_type = chunk.properties.get("chunk_type", "unknown")
                        formatted_results += f"   - {chunk_type} (lines {chunk.start_line}-{chunk.end_line})\n"
                
                return formatted_results
                
            except Exception as e:
                self.logger.error(f"Error getting file structure: {e}")
                return f"❌ Error getting file structure: {str(e)}"
        
        @self.mcp.tool()
        async def get_system_stats() -> str:
            """Get system statistics and status.
            
            Returns:
                System statistics and health information
            """
            try:
                # Get statistics from all components
                milvus_stats = self.milvus_client.get_collection_stats()
                neo4j_stats = self.graph_client.get_database_stats()
                search_stats = self.hybrid_search.get_search_stats()
                
                formatted_stats = "📊 System Statistics\n"
                formatted_stats += "=" * 50 + "\n\n"
                
                # Milvus stats
                if "error" not in milvus_stats:
                    formatted_stats += "🗄️ **Milvus Vector Database:**\n"
                    formatted_stats += f"   Collection: {milvus_stats.get('collection_name', 'N/A')}\n"
                    formatted_stats += f"   Entities: {milvus_stats.get('num_entities', 0)}\n\n"
                
                # Graph stats
                formatted_stats += "🕸️ **Graph Graph Database:**\n"
                if "nodes" in neo4j_stats:
                    total_nodes = sum(neo4j_stats["nodes"].values())
                    formatted_stats += f"   Total Nodes: {total_nodes}\n"
                    for node_type, count in neo4j_stats["nodes"].items():
                        formatted_stats += f"   - {node_type}: {count}\n"
                
                if "relationships" in neo4j_stats:
                    total_rels = sum(neo4j_stats["relationships"].values())
                    formatted_stats += f"   Total Relationships: {total_rels}\n"
                    for rel_type, count in neo4j_stats["relationships"].items():
                        formatted_stats += f"   - {rel_type}: {count}\n"
                formatted_stats += "\n"
                
                # Search stats
                if "bm25_stats" in search_stats:
                    bm25_stats = search_stats["bm25_stats"]
                    formatted_stats += "🔍 **Search Engine:**\n"
                    formatted_stats += f"   BM25 Documents: {bm25_stats.get('indexed_documents', 0)}\n"
                    formatted_stats += f"   Vocabulary Size: {bm25_stats.get('vocabulary_size', 0)}\n"
                    formatted_stats += f"   Cached Chunks: {search_stats.get('cached_chunks', 0)}\n"
                
                return formatted_stats
                
            except Exception as e:
                self.logger.error(f"Error getting system stats: {e}")
                return f"❌ Error getting system stats: {str(e)}"
        
        @self.mcp.tool()
        async def clear_database() -> str:
            """Clear all data from the database.
            
            Returns:
                Status message
            """
            try:
                # Clear both databases
                self.milvus_client.drop_collection()
                self.graph_client.clear_database()
                
                return "✅ Database cleared successfully\nAll data has been removed from both vector and graph databases."
                
            except Exception as e:
                self.logger.error(f"Error clearing database: {e}")
                return f"❌ Error clearing database: {str(e)}"
        
        @self.mcp.tool()
        async def clear_index(root_path: str = None) -> str:
            """Clear index data for a specific directory or current directory.
            
            Args:
                root_path: Path to the directory to clear index for (optional, defaults to current directory)
                
            Returns:
                Status message with clearing statistics
            """
            try:
                from pathlib import Path
                
                # Determine the target directory
                if root_path is None:
                    target_path = Path.cwd().resolve()
                else:
                    target_path = Path(root_path).resolve()
                
                self.logger.info(f"Clearing index for directory: {target_path}")
                
                # Get statistics before clearing
                milvus_stats_before = self.milvus_client.get_collection_stats()
                graph_stats_before = self.graph_client.get_database_stats()
                
                # Clear data related to the specified directory
                # For Milvus: we need to filter by file_path and delete matching entries
                # For Graph: we need to delete nodes and relationships related to files in the directory
                
                # Clear Milvus entries for files in the directory
                milvus_cleared = await self._clear_milvus_index(target_path)
                
                # Clear Graph entries for files in the directory
                graph_cleared = await self._clear_graph_index(target_path)
                
                # Get statistics after clearing
                milvus_stats_after = self.milvus_client.get_collection_stats()
                graph_stats_after = self.graph_client.get_database_stats()
                
                result = f"""
✅ Successfully cleared index for directory: {target_path}

📊 Clearing Statistics:
🗄️  Milvus entries cleared: {milvus_cleared}
🕸️  Graph nodes cleared: {graph_cleared.get('nodes', 0)}
🕸️  Graph relationships cleared: {graph_cleared.get('relationships', 0)}

📊 Remaining Data:
🗄️  Milvus entities: {milvus_stats_after.get('num_entities', 0)}
🕸️  Graph nodes: {sum(graph_stats_after.get('nodes', {}).values())}
🕸️  Graph relationships: {sum(graph_stats_after.get('relationships', {}).values())}
"""
                return result
                
            except Exception as e:
                self.logger.error(f"Error clearing index: {e}")
                return f"❌ Error clearing index: {str(e)}"
    
    async def _clear_milvus_index(self, target_path: Path) -> int:
        """Clear Milvus entries for files in the target directory."""
        try:
            # Query for entries with file_path starting with the target path
            # This is a simplified approach - in practice, you might need more sophisticated filtering
            from pymilvus import connections
            
            # Connect to Milvus
            connections.connect("default", host=settings.milvus_host, port=settings.milvus_port)
            
            # Get collection
            from pymilvus import Collection
            collection = Collection(settings.milvus_collection_name)
            
            # Create a simple filter expression
            # Note: This assumes you have a 'file_path' field in your Milvus schema
            filter_expr = f'file_path like "{target_path}%"'
            
            # Query for matching IDs
            results = collection.query(
                expr=filter_expr,
                output_fields=["id"]
            )
            
            if results:
                # Delete matching entries
                ids_to_delete = [result["id"] for result in results]
                collection.delete(expr=f'id in [{",".join(map(str, ids_to_delete))}]')
                
                # Flush to ensure deletion is committed
                collection.flush()
                
                self.logger.info(f"Cleared {len(ids_to_delete)} entries from Milvus")
                return len(ids_to_delete)
            else:
                self.logger.info("No matching entries found in Milvus")
                return 0
                
        except Exception as e:
            self.logger.error(f"Error clearing Milvus index: {e}")
            return 0
    
    async def _clear_graph_index(self, target_path: Path) -> Dict[str, int]:
        """Clear Graph entries for files in the target directory."""
        try:
            nodes_cleared = 0
            relationships_cleared = 0
            
            # Get all graph data
            graph_data = self.graph_client.get_graph_data()
            
            # Find nodes and edges related to files in the target directory
            nodes_to_delete = []
            edges_to_delete = []
            
            for node in graph_data["nodes"]:
                if "file_path" in node and node["file_path"].startswith(str(target_path)):
                    nodes_to_delete.append(node["id"])
            
            for edge in graph_data["edges"]:
                if edge["source_id"] in nodes_to_delete or edge["target_id"] in nodes_to_delete:
                    edges_to_delete.append(edge)
            
            # Delete nodes and edges from JSON graph
            if nodes_to_delete:
                # Remove edges first
                for edge in edges_to_delete:
                    if edge in graph_data["edges"]:
                        graph_data["edges"].remove(edge)
                        relationships_cleared += 1
                
                # Remove nodes
                for node in graph_data["nodes"]:
                    if node["id"] in nodes_to_delete:
                        graph_data["nodes"].remove(node)
                        nodes_cleared += 1
                
                # Save the updated graph data
                self.graph_client._save_graph_data(graph_data)
                
                self.logger.info(f"Cleared {nodes_cleared} nodes and {relationships_cleared} relationships from Graph")
            else:
                self.logger.info("No matching nodes found in Graph")
            
            return {
                "nodes": nodes_cleared,
                "relationships": relationships_cleared
            }
            
        except Exception as e:
            self.logger.error(f"Error clearing Graph index: {e}")
            return {"nodes": 0, "relationships": 0}
    
    def _build_class_hierarchy(self, graph_result, parent_id=None, level=0):
        """Build class hierarchy tree structure."""
        hierarchy = {}
        
        for node in graph_result.nodes:
            if node.type == "Class":
                hierarchy[node.id] = {
                    "node": node,
                    "children": [],
                    "level": level
                }
        
        # Build parent-child relationships
        for edge in graph_result.edges:
            if edge.relationship_type == "INHERITS_FROM":
                parent_id = edge.target_id
                child_id = edge.source_id
                if parent_id in hierarchy and child_id in hierarchy:
                    hierarchy[parent_id]["children"].append(child_id)
        
        return hierarchy
    
    def _format_hierarchy_tree(self, hierarchy, root_id, level=0):
        """Format hierarchy tree as text."""
        if root_id not in hierarchy:
            return ""
        
        node_data = hierarchy[root_id]
        node = node_data["node"]
        indent = "  " * level
        
        result = f"{indent}🏗️ **{node.id}** ({node.file_path}:{node.line_number})\n"
        
        for child_id in node_data["children"]:
            result += self._format_hierarchy_tree(hierarchy, child_id, level + 1)
        
        return result
    
    def get_server(self):
        """Get the FastMCP server instance."""
        return self.mcp
    
