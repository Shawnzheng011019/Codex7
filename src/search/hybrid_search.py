from typing import List, Dict, Any, Optional, Tuple
import re
import math
from rank_bm25 import BM25Okapi
import numpy as np
from collections import Counter

from ..config import settings
from ..types import SearchResult, CodeChunk
from ..utils.logger import app_logger


class BM25Search:
    """BM25 search implementation for keyword-based retrieval."""
    
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.logger = app_logger.bind(component="bm25_search")
        self.k1 = k1 or settings.bm25_k1
        self.b = b or settings.bm25_b
        self.corpus = []
        self.bm25 = None
        self.chunk_metadata = []
    
    def index_chunks(self, chunks: List[CodeChunk]):
        """Index chunks for BM25 search."""
        if not chunks:
            return
        
        self.logger.info(f"Indexing {len(chunks)} chunks for BM25 search")
        
        # Preprocess text
        self.corpus = []
        self.chunk_metadata = []
        
        for chunk in chunks:
            # Preprocess text: lowercase, tokenize
            tokens = self._preprocess_text(chunk.content)
            self.corpus.append(tokens)
            self.chunk_metadata.append({
                "chunk_id": chunk.id,
                "file_path": chunk.file_path,
                "language": chunk.language,
                "chunk_type": chunk.chunk_type,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            })
        
        # Create BM25 index
        self.bm25 = BM25Okapi(self.corpus, k1=self.k1, b=self.b)
        self.logger.info("BM25 index created successfully")
    
    def _preprocess_text(self, text: str) -> List[str]:
        """Preprocess text for BM25."""
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep underscores and dots (for identifiers)
        text = re.sub(r'[^\w\s\.]', ' ', text)
        
        # Split into tokens
        tokens = text.split()
        
        # Remove very short tokens
        tokens = [token for token in tokens if len(token) > 1]
        
        return tokens
    
    def search(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Search using BM25."""
        if not self.bm25:
            return []
        
        # Preprocess query
        query_tokens = self._preprocess_text(query)
        
        # Get BM25 scores
        bm25_scores = self.bm25.get_scores(query_tokens)
        
        # Get top-k results
        top_indices = np.argsort(bm25_scores)[::-1][:top_k]
        
        results = []
        for rank, idx in enumerate(top_indices):
            if bm25_scores[idx] > 0:  # Only include results with positive scores
                result = SearchResult(
                    chunk=CodeChunk(
                        id=self.chunk_metadata[idx]["chunk_id"],
                        file_path=self.chunk_metadata[idx]["file_path"],
                        content="",  # Will be filled by the caller
                        start_line=self.chunk_metadata[idx]["start_line"],
                        end_line=self.chunk_metadata[idx]["end_line"],
                        language=self.chunk_metadata[idx]["language"],
                        chunk_type=self.chunk_metadata[idx]["chunk_type"],
                        metadata={},
                    ),
                    score=float(bm25_scores[idx]),
                    rank=rank + 1,
                    search_type="bm25",
                    metadata={"bm25_score": float(bm25_scores[idx])},
                )
                results.append(result)
        
        return results
    
    def get_document_frequency(self, token: str) -> int:
        """Get document frequency for a token."""
        if not self.bm25:
            return 0
        
        token_count = 0
        for doc in self.corpus:
            if token in doc:
                token_count += 1
        
        return token_count
    
    def get_vocabulary_size(self) -> int:
        """Get vocabulary size."""
        if not self.corpus:
            return 0
        
        vocabulary = set()
        for doc in self.corpus:
            vocabulary.update(doc)
        
        return len(vocabulary)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get BM25 statistics."""
        return {
            "indexed_documents": len(self.corpus),
            "vocabulary_size": self.get_vocabulary_size(),
            "k1": self.k1,
            "b": self.b,
        }


class HybridSearch:
    """Hybrid search combining vector similarity and BM25."""
    
    def __init__(self, milvus_client, graph_client, embedding_service):
        self.logger = app_logger.bind(component="hybrid_search")
        self.milvus_client = milvus_client
        self.graph_client = graph_client
        self.embedding_service = embedding_service
        self.bm25_search = BM25Search()
        self.chunk_cache = {}  # Cache for chunk data
    
    async def index_chunks(self, chunks: List[CodeChunk]):
        """Index chunks for hybrid search."""
        if not chunks:
            return
        
        self.logger.info(f"Indexing {len(chunks)} chunks for hybrid search")
        
        # Generate embeddings
        chunks_with_embeddings = await self.embedding_service.embed_chunks(chunks)
        
        # Insert into Milvus
        self.milvus_client.insert_chunks(chunks_with_embeddings)
        
        # Index for BM25
        self.bm25_search.index_chunks(chunks)
        
        # Create graph nodes and relationships in JSON graph
        await self._create_graph_data(chunks)
        
        # Cache chunks for quick retrieval
        for chunk in chunks:
            self.chunk_cache[chunk.id] = chunk
        
        self.logger.info("Hybrid search indexing completed")
    
    async def search(self, query: str, top_k: int = 10, 
                    vector_weight: float = 0.6, 
                    bm25_weight: float = 0.4,
                    use_graph: bool = True) -> List[SearchResult]:
        """Perform hybrid search."""
        self.logger.info(f"Performing hybrid search for query: {query}")
        
        # Get vector search results
        vector_results = await self._vector_search(query, top_k)
        
        # Get BM25 search results
        bm25_results = self._bm25_search(query, top_k)
        
        # Combine results
        combined_results = self._combine_results(
            vector_results, bm25_results, 
            vector_weight, bm25_weight, top_k
        )
        
        # Enhance with graph information if requested
        if use_graph and combined_results:
            combined_results = await self._enhance_with_graph(combined_results)
        
        return combined_results
    
    async def _vector_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Perform vector search."""
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.embed_query(query)
            
            # Search in Milvus
            vector_results = self.milvus_client.search_similar(
                query_embedding, top_k
            )
            
            return vector_results
            
        except Exception as e:
            self.logger.error(f"Error in vector search: {e}")
            return []
    
    def _bm25_search(self, query: str, top_k: int) -> List[SearchResult]:
        """Perform BM25 search."""
        try:
            bm25_results = self.bm25_search.search(query, top_k)
            
            # Fill in chunk content from cache
            for result in bm25_results:
                if result.chunk.id in self.chunk_cache:
                    cached_chunk = self.chunk_cache[result.chunk.id]
                    result.chunk.content = cached_chunk.content
                    result.chunk.metadata = cached_chunk.metadata
            
            return bm25_results
            
        except Exception as e:
            self.logger.error(f"Error in BM25 search: {e}")
            return []
    
    def _combine_results(self, vector_results: List[SearchResult], 
                         bm25_results: List[SearchResult],
                         vector_weight: float, bm25_weight: float,
                         top_k: int) -> List[SearchResult]:
        """Combine vector and BM25 results."""
        # Normalize scores
        vector_scores = [r.score for r in vector_results]
        bm25_scores = [r.score for r in bm25_results]
        
        # Min-max normalization
        def normalize_scores(scores):
            if not scores:
                return []
            min_score = min(scores)
            max_score = max(scores)
            if max_score == min_score:
                return [0.5] * len(scores)
            return [(s - min_score) / (max_score - min_score) for s in scores]
        
        vector_norm = normalize_scores(vector_scores)
        bm25_norm = normalize_scores(bm25_scores)
        
        # Create combined results dictionary
        combined_dict = {}
        
        # Add vector results
        for i, result in enumerate(vector_results):
            chunk_id = result.chunk.id
            if chunk_id not in combined_dict:
                combined_dict[chunk_id] = {
                    "chunk": result.chunk,
                    "vector_score": vector_norm[i] if i < len(vector_norm) else 0,
                    "bm25_score": 0,
                    "search_types": ["vector"],
                }
        
        # Add BM25 results
        for i, result in enumerate(bm25_results):
            chunk_id = result.chunk.id
            if chunk_id not in combined_dict:
                combined_dict[chunk_id] = {
                    "chunk": result.chunk,
                    "vector_score": 0,
                    "bm25_score": bm25_norm[i] if i < len(bm25_norm) else 0,
                    "search_types": ["bm25"],
                }
            else:
                combined_dict[chunk_id]["bm25_score"] = bm25_norm[i] if i < len(bm25_norm) else 0
                combined_dict[chunk_id]["search_types"].append("bm25")
        
        # Calculate combined scores
        for chunk_id, data in combined_dict.items():
            combined_score = (
                data["vector_score"] * vector_weight + 
                data["bm25_score"] * bm25_weight
            )
            data["combined_score"] = combined_score
        
        # Sort by combined score and return top-k
        sorted_results = sorted(
            combined_dict.items(),
            key=lambda x: x[1]["combined_score"],
            reverse=True
        )
        
        final_results = []
        for rank, (chunk_id, data) in enumerate(sorted_results[:top_k]):
            result = SearchResult(
                chunk=data["chunk"],
                score=data["combined_score"],
                rank=rank + 1,
                search_type="hybrid",
                metadata={
                    "vector_score": data["vector_score"],
                    "bm25_score": data["bm25_score"],
                    "search_types": data["search_types"],
                },
            )
            final_results.append(result)
        
        return final_results
    
    async def _enhance_with_graph(self, results: List[SearchResult]) -> List[SearchResult]:
        """Enhance search results with graph information."""
        try:
            for result in results:
                # Find related chunks in graph
                graph_result = self.graph_client.find_related_chunks(
                    result.chunk.id, 
                    relationship_types=["CALLS", "DEFINED_IN", "CONTAINS"],
                    max_hops=2
                )
                
                # Add graph context to metadata
                result.metadata["graph_context"] = {
                    "related_nodes": len(graph_result.nodes),
                    "related_edges": len(graph_result.edges),
                }
                
                # If there are related functions, add them to context
                related_functions = [
                    node for node in graph_result.nodes 
                    if node.type == "Function"
                ]
                if related_functions:
                    result.metadata["graph_context"]["related_functions"] = [
                        {"name": node.id, "file_path": node.file_path}
                        for node in related_functions
                    ]
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error enhancing with graph: {e}")
            return results
    
    def search_by_file(self, file_path: str, query: str = "", top_k: int = 10) -> List[SearchResult]:
        """Search within a specific file."""
        try:
            # Get chunks for the file
            chunks = self.milvus_client.get_chunks_by_file(file_path)
            
            if not chunks:
                return []
            
            # If no query, return all chunks
            if not query:
                return [
                    SearchResult(
                        chunk=chunk,
                        score=1.0,
                        rank=i + 1,
                        search_type="file",
                        metadata={},
                    )
                    for i, chunk in enumerate(chunks[:top_k])
                ]
            
            # Otherwise, filter chunks by query content
            filtered_chunks = []
            for chunk in chunks:
                if query.lower() in chunk.content.lower():
                    filtered_chunks.append(chunk)
            
            return [
                SearchResult(
                    chunk=chunk,
                    score=1.0,
                    rank=i + 1,
                    search_type="file_query",
                    metadata={},
                )
                for i, chunk in enumerate(filtered_chunks[:top_k])
            ]
            
        except Exception as e:
            self.logger.error(f"Error searching by file: {e}")
            return []
    
    async def _create_graph_data(self, chunks: List[CodeChunk]):
        """Create graph nodes and relationships in JSON graph."""
        try:
            self.logger.info(f"Creating graph data for {len(chunks)} chunks")
            
            # Group chunks by file
            files_dict = {}
            for chunk in chunks:
                if chunk.file_path not in files_dict:
                    files_dict[chunk.file_path] = {
                        'chunks': [],
                        'language': chunk.language,
                        'metadata': chunk.metadata
                    }
                files_dict[chunk.file_path]['chunks'].append(chunk)
            
            created_nodes = 0
            created_relationships = 0  # Add missing variable initialization
            
            # Process each file
            for file_path, file_data in files_dict.items():
                try:
                    # Extract file size from metadata
                    metadata = file_data['metadata'] or {}
                    file_size = metadata.get('file_size', 0)
                    
                    # Create file node with flattened metadata
                    file_node = self.graph_client.create_file_node(
                        file_path=file_path,
                        language=file_data['language'] or 'unknown',
                        file_type=self._determine_file_type(file_path),
                        metadata={'file_size': file_size}  # Only pass primitive types
                    )
                    created_nodes += 1
                    self.logger.debug(f"Created file node: {file_path}")
                    
                    # Create chunk nodes and relationships
                    for chunk in file_data['chunks']:
                        try:
                            # Create chunk node
                            chunk_node = self.graph_client.create_chunk_node(chunk)
                            created_nodes += 1
                            
                            # Create file-chunk relationship
                            file_chunk_rel = self.graph_client.create_file_chunk_relationship(
                                file_path, chunk.id
                            )
                            created_relationships += 1
                            
                            # Extract and create function/class nodes if available
                            await self._extract_and_create_code_entities(chunk)
                            
                        except Exception as e:
                            self.logger.warning(f"Failed to create chunk node {chunk.id}: {e}")
                            continue
                            
                except Exception as e:
                    self.logger.warning(f"Failed to create file node {file_path}: {e}")
                    continue
            
            self.logger.info(f"Graph data creation completed: {created_nodes} nodes, {created_relationships} relationships")
            
        except Exception as e:
            self.logger.error(f"Error creating graph data: {e}")
    
    def _determine_file_type(self, file_path: str) -> str:
        """Determine file type from file path."""
        from pathlib import Path
        suffix = Path(file_path).suffix.lower()
        
        type_mapping = {
            '.py': 'source',
            '.js': 'source', '.ts': 'source', '.jsx': 'source', '.tsx': 'source',
            '.java': 'source', '.cpp': 'source', '.c': 'source', '.h': 'source',
            '.go': 'source', '.rs': 'source', '.rb': 'source', '.php': 'source',
            '.swift': 'source', '.kt': 'source', '.scala': 'source', '.dart': 'source',
            '.md': 'documentation', '.txt': 'documentation', '.rst': 'documentation',
            '.json': 'config', '.yaml': 'config', '.yml': 'config', '.xml': 'config',
            '.html': 'web', '.css': 'web', '.scss': 'web', '.sass': 'web',
            '.sql': 'database', '.sh': 'script', '.bat': 'script', '.ps1': 'script'
        }
        
        return type_mapping.get(suffix, 'other')
    
    async def _extract_and_create_code_entities(self, chunk: CodeChunk):
        """Extract and create function/class nodes from code chunks."""
        try:
            # Simple regex-based extraction for common patterns
            # This is a basic implementation - could be enhanced with proper AST parsing
            
            functions = self._extract_functions(chunk.content, chunk.language)
            classes = self._extract_classes(chunk.content, chunk.language)
            
            created_entities = 0
            
            # Create function nodes
            for func_info in functions:
                try:
                    func_node = self.graph_client.create_function_node(
                        name=func_info['name'],
                        qualified_name=f"{chunk.file_path}::{func_info['name']}",
                        file_path=chunk.file_path,
                        line_number=chunk.start_line + func_info.get('line_offset', 0),
                        metadata={}  # Empty metadata dict
                    )
                    
                    # Create function-chunk relationship
                    self.graph_client.create_function_chunk_relationship(
                        f"{chunk.file_path}::{func_info['name']}", chunk.id
                    )
                    created_entities += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to create function node {func_info['name']}: {e}")
            
            # Create class nodes
            for class_info in classes:
                try:
                    class_node = self.graph_client.create_class_node(
                        name=class_info['name'],
                        qualified_name=f"{chunk.file_path}::{class_info['name']}",
                        file_path=chunk.file_path,
                        line_number=chunk.start_line + class_info.get('line_offset', 0),
                        metadata={}  # Empty metadata dict
                    )
                    
                    # Create class-chunk relationship
                    self.graph_client.create_class_chunk_relationship(
                        f"{chunk.file_path}::{class_info['name']}", chunk.id
                    )
                    created_entities += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to create class node {class_info['name']}: {e}")
            
            if created_entities > 0:
                self.logger.debug(f"Created {created_entities} code entities for chunk {chunk.id}")
                
        except Exception as e:
            self.logger.warning(f"Error extracting code entities from chunk {chunk.id}: {e}")
    
    def _extract_functions(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract function definitions from content."""
        functions = []
        lines = content.split('\n')
        
        patterns = {
            'python': [
                r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                r'^\s*async\s+def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
            ],
            'javascript': [
                r'^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*function\s*\(',
                r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=>\s*'
            ],
            'typescript': [
                r'^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*function\s*\(',
                r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=>\s*'
            ],
            'java': [
                r'^\s*(?:public|private|protected)?\s*(?:static)?\s*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
            ],
            'cpp': [
                r'^\s*\w+\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
            ],
            'go': [
                r'^\s*func\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
            ]
        }
        
        if language not in patterns:
            return functions
        
        import re
        for line_num, line in enumerate(lines):
            for pattern in patterns[language]:
                match = re.match(pattern, line)
                if match:
                    functions.append({
                        'name': match.group(1),
                        'line_offset': line_num,
                        'signature': line.strip()
                    })
        
        return functions
    
    def _extract_classes(self, content: str, language: str) -> List[Dict[str, Any]]:
        """Extract class definitions from content."""
        classes = []
        lines = content.split('\n')
        
        patterns = {
            'python': [r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]'],
            'javascript': [r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[{(]'],
            'typescript': [r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[{(]'],
            'java': [r'^\s*(?:public|private|protected)?\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[{(]'],
            'cpp': [r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[{:]'],
            'go': [r'^\s*type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+struct\s*{']
        }
        
        if language not in patterns:
            return classes
        
        import re
        for line_num, line in enumerate(lines):
            for pattern in patterns[language]:
                match = re.match(pattern, line)
                if match:
                    classes.append({
                        'name': match.group(1),
                        'line_offset': line_num,
                        'signature': line.strip()
                    })
        
        return classes

    def get_search_stats(self) -> Dict[str, Any]:
        """Get search statistics."""
        return {
            "bm25_stats": self.bm25_search.get_stats(),
            "cached_chunks": len(self.chunk_cache),
            "milvus_stats": self.milvus_client.get_collection_stats(),
        }