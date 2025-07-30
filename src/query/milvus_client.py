from typing import List, Dict, Any, Optional, Union
from pymilvus import (
    connections,
    utility,
    FieldSchema,
    CollectionSchema,
    DataType,
    Collection,
)
import numpy as np

from ..config import settings
from ..types import CodeChunk, SearchResult
from ..utils.logger import app_logger


class MilvusClient:
    """Milvus client for vector database operations."""
    
    def __init__(self):
        self.logger = app_logger.bind(component="milvus_client")
        self.collection = None
        self.dimension = settings.milvus_dimension
        self.collection_name = settings.milvus_collection_name
        
        self._connect()
        self._ensure_collection()
    
    def _connect(self):
        """Connect to Milvus server."""
        try:
            connections.connect(
                "default",
                host=settings.milvus_host,
                port=settings.milvus_port,
            )
            self.logger.info(f"Connected to Milvus at {settings.milvus_host}:{settings.milvus_port}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def _ensure_collection(self):
        """Ensure collection exists with proper schema."""
        try:
            if utility.has_collection(self.collection_name):
                self.collection = Collection(self.collection_name)
                self.logger.info(f"Using existing collection: {self.collection_name}")
            else:
                self._create_collection()
        except Exception as e:
            self.logger.error(f"Failed to ensure collection: {e}")
            raise
    
    def _create_collection(self):
        """Create collection with proper schema."""
        try:
            # Define schema
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
                FieldSchema(name="file_path", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="start_line", dtype=DataType.INT32),
                FieldSchema(name="end_line", dtype=DataType.INT32),
                FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=32),
                FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
            ]
            
            schema = CollectionSchema(fields=fields)
            self.collection = Collection(self.collection_name, schema)
            
            # Create index
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024},
            }
            
            self.collection.create_index("embedding", index_params)
            self.logger.info(f"Created collection: {self.collection_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to create collection: {e}")
            raise
    
    def insert_chunks(self, chunks: List[CodeChunk]) -> int:
        """Insert code chunks into Milvus."""
        if not chunks:
            return 0
        
        try:
            self.logger.info(f"Inserting {len(chunks)} chunks into Milvus")
            
            # Prepare data for insertion
            data = {
                "id": [chunk.id for chunk in chunks],
                "file_path": [chunk.file_path for chunk in chunks],
                "content": [chunk.content for chunk in chunks],
                "start_line": [chunk.start_line for chunk in chunks],
                "end_line": [chunk.end_line for chunk in chunks],
                "language": [chunk.language for chunk in chunks],
                "chunk_type": [chunk.chunk_type for chunk in chunks],
                "metadata": [chunk.metadata for chunk in chunks],
                "embedding": [chunk.embedding for chunk in chunks],
            }
            
            # Insert data
            insert_result = self.collection.insert([data[field] for field in data.keys()])
            
            # Flush to ensure data is persisted
            self.collection.flush()
            
            self.logger.info(f"Successfully inserted {len(chunks)} chunks")
            return len(chunks)
            
        except Exception as e:
            self.logger.error(f"Failed to insert chunks: {e}")
            raise
    
    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 10,
        filter_expression: Optional[str] = None,
        metric_type: str = "L2"
    ) -> List[SearchResult]:
        """Search for similar chunks using vector similarity."""
        try:
            self.logger.info(f"Searching for similar chunks with top_k={top_k}")
            
            # Load collection into memory
            self.collection.load()
            
            # Prepare search parameters
            search_params = {
                "metric_type": metric_type,
                "params": {"nprobe": 10},
            }
            
            # Perform search
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                expr=filter_expression,
                output_fields=["id", "file_path", "content", "start_line", "end_line", 
                             "language", "chunk_type", "metadata"],
            )
            
            # Convert results to SearchResult objects
            search_results = []
            for hits in results:
                for i, hit in enumerate(hits):
                    chunk = CodeChunk(
                        id=hit.id,
                        file_path=hit.entity.get("file_path"),
                        content=hit.entity.get("content"),
                        start_line=hit.entity.get("start_line"),
                        end_line=hit.entity.get("end_line"),
                        language=hit.entity.get("language"),
                        chunk_type=hit.entity.get("chunk_type"),
                        metadata=hit.entity.get("metadata", {}),
                    )
                    
                    search_result = SearchResult(
                        chunk=chunk,
                        score=hit.score,
                        rank=i + 1,
                        search_type="vector",
                        metadata={"distance": hit.distance},
                    )
                    search_results.append(search_result)
            
            self.logger.info(f"Found {len(search_results)} similar chunks")
            return search_results
            
        except Exception as e:
            self.logger.error(f"Failed to search similar chunks: {e}")
            raise
    
    def delete_by_file_path(self, file_path: str) -> int:
        """Delete all chunks for a specific file."""
        try:
            # Find chunks for the file
            expr = f'file_path == "{file_path}"'
            self.collection.delete(expr)
            
            self.logger.info(f"Deleted chunks for file: {file_path}")
            return 0  # Milvus doesn't return count
            
        except Exception as e:
            self.logger.error(f"Failed to delete chunks for file {file_path}: {e}")
            raise
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[CodeChunk]:
        """Get a specific chunk by ID."""
        try:
            expr = f'id == "{chunk_id}"'
            results = self.collection.query(
                expr=expr,
                output_fields=["id", "file_path", "content", "start_line", "end_line", 
                             "language", "chunk_type", "metadata", "embedding"],
            )
            
            if results:
                result = results[0]
                return CodeChunk(
                    id=result["id"],
                    file_path=result["file_path"],
                    content=result["content"],
                    start_line=result["start_line"],
                    end_line=result["end_line"],
                    language=result["language"],
                    chunk_type=result["chunk_type"],
                    metadata=result["metadata"],
                    embedding=result.get("embedding"),
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get chunk {chunk_id}: {e}")
            return None
    
    def get_chunks_by_file(self, file_path: str) -> List[CodeChunk]:
        """Get all chunks for a specific file."""
        try:
            expr = f'file_path == "{file_path}"'
            results = self.collection.query(
                expr=expr,
                output_fields=["id", "file_path", "content", "start_line", "end_line", 
                             "language", "chunk_type", "metadata", "embedding"],
            )
            
            chunks = []
            for result in results:
                chunk = CodeChunk(
                    id=result["id"],
                    file_path=result["file_path"],
                    content=result["content"],
                    start_line=result["start_line"],
                    end_line=result["end_line"],
                    language=result["language"],
                    chunk_type=result["chunk_type"],
                    metadata=result["metadata"],
                    embedding=result.get("embedding"),
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            self.logger.error(f"Failed to get chunks for file {file_path}: {e}")
            return []
    
    def drop_collection(self):
        """Drop the entire collection."""
        try:
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                self.logger.info(f"Dropped collection: {self.collection_name}")
        except Exception as e:
            self.logger.error(f"Failed to drop collection: {e}")
            raise
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            if not self.collection:
                return {"error": "Collection not initialized"}
            
            stats = {
                "collection_name": self.collection_name,
                "num_entities": self.collection.num_entities,
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e)}
    
    def close(self):
        """Close connection to Milvus."""
        try:
            connections.disconnect("default")
            self.logger.info("Disconnected from Milvus")
        except Exception as e:
            self.logger.error(f"Failed to disconnect from Milvus: {e}")