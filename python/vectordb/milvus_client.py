"""
Milvus vector database client.
"""

import asyncio
import json
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from loguru import logger

from utils.models import EmbeddingVector, SearchQuery, SearchResult, VectorMetadata
from utils.config import get_config

try:
    from pymilvus import (
        connections, utility, Collection, CollectionSchema, FieldSchema, DataType,
        Index, SearchParams
    )
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False
    logger.error("pymilvus not available - install with: pip install pymilvus")


class MilvusClient:
    """Milvus vector database client."""
    
    def __init__(self, 
                 collection_name: str = "codex7_embeddings",
                 host: str = "localhost", 
                 port: int = 19530,
                 embedding_dim: int = 768):
        """
        Initialize Milvus client.
        
        Args:
            collection_name: Name of the collection
            host: Milvus server host
            port: Milvus server port
            embedding_dim: Dimension of embeddings
        """
        if not MILVUS_AVAILABLE:
            raise ImportError("pymilvus package not installed")
        
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.embedding_dim = embedding_dim
        
        self.config = get_config()
        self.collection: Optional[Collection] = None
        self._connected = False
        
        logger.info(f"Initializing Milvus client for {host}:{port}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self):
        """Connect to Milvus server."""
        if self._connected:
            return
        
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port
            )
            
            self._connected = True
            logger.success(f"Connected to Milvus at {self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from Milvus server."""
        if self._connected:
            try:
                connections.disconnect("default")
                self._connected = False
                logger.info("Disconnected from Milvus")
            except Exception as e:
                logger.warning(f"Error disconnecting from Milvus: {e}")
    
    async def create_collection(self) -> bool:
        """
        Create collection if it doesn't exist.
        
        Returns:
            True if collection was created or already exists
        """
        if not self._connected:
            await self.connect()
        
        try:
            # Check if collection exists
            if utility.has_collection(self.collection_name):
                logger.info(f"Collection {self.collection_name} already exists")
                self.collection = Collection(self.collection_name)
                return True
            
            # Define collection schema
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
                FieldSchema(name="repo", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="path", dtype=DataType.VARCHAR, max_length=1024),
                FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=10),
                FieldSchema(name="language", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="start_line", dtype=DataType.INT64),
                FieldSchema(name="end_line", dtype=DataType.INT64),
                FieldSchema(name="star_count", dtype=DataType.INT64),
                FieldSchema(name="last_commit_date", dtype=DataType.VARCHAR, max_length=50),
                FieldSchema(name="text_hash", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="token_count", dtype=DataType.INT64),
                FieldSchema(name="metadata_json", dtype=DataType.VARCHAR, max_length=2048)
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Codex7 RAG embeddings collection"
            )
            
            # Create collection
            self.collection = Collection(
                name=self.collection_name,
                schema=schema,
                using='default'
            )
            
            logger.success(f"Created collection: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise
    
    async def create_index(self) -> bool:
        """
        Create vector index for the collection.
        
        Returns:
            True if index was created successfully
        """
        if not self.collection:
            await self.create_collection()
        
        try:
            # Check if index already exists
            indexes = self.collection.indexes
            if indexes:
                logger.info("Vector index already exists")
                return True
            
            # Create IVF_FLAT index
            index_params = {
                "metric_type": "IP",  # Inner Product (cosine similarity)
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            
            self.collection.create_index(
                field_name="vector",
                index_params=index_params
            )
            
            logger.success("Created vector index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise
    
    async def insert_vectors(self, vectors: List[EmbeddingVector]) -> bool:
        """
        Insert embedding vectors into collection.
        
        Args:
            vectors: List of embedding vectors
            
        Returns:
            True if insertion was successful
        """
        if not vectors:
            logger.warning("No vectors to insert")
            return True
        
        if not self.collection:
            await self.create_collection()
        
        try:
            # Prepare data for insertion
            data = self._prepare_insertion_data(vectors)
            
            # Insert data
            mr = self.collection.insert(data)
            
            # Flush to ensure data is persisted
            self.collection.flush()
            
            logger.success(f"Inserted {len(vectors)} vectors into collection")
            return True
            
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            raise
    
    def _prepare_insertion_data(self, vectors: List[EmbeddingVector]) -> List[List]:
        """Prepare data for Milvus insertion."""
        ids = []
        embeddings = []
        repos = []
        paths = []
        chunk_types = []
        languages = []
        start_lines = []
        end_lines = []
        star_counts = []
        last_commit_dates = []
        text_hashes = []
        token_counts = []
        metadata_jsons = []
        
        for vector in vectors:
            ids.append(vector.id)
            embeddings.append(vector.vector)
            repos.append(vector.metadata.repo)
            paths.append(vector.metadata.path)
            chunk_types.append(vector.metadata.chunk_type)
            languages.append(vector.metadata.language or "")
            start_lines.append(vector.metadata.start_line or 0)
            end_lines.append(vector.metadata.end_line or 0)
            star_counts.append(vector.metadata.star_count)
            last_commit_dates.append(vector.metadata.last_commit_date)
            text_hashes.append(vector.metadata.text_hash)
            token_counts.append(vector.metadata.token_count)
            metadata_jsons.append(json.dumps(vector.metadata.dict(), ensure_ascii=False))
        
        return [
            ids, embeddings, repos, paths, chunk_types, languages,
            start_lines, end_lines, star_counts, last_commit_dates,
            text_hashes, token_counts, metadata_jsons
        ]
    
    async def search_vectors(self, 
                           query_vector: List[float],
                           top_k: int = 10,
                           filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Optional filters for metadata
            
        Returns:
            List of search results
        """
        if not self.collection:
            await self.create_collection()
        
        try:
            # Load collection into memory
            self.collection.load()
            
            # Prepare search parameters
            search_params = {
                "metric_type": "IP",
                "params": {"nprobe": 16}
            }
            
            # Build filter expression
            expr = self._build_filter_expression(filters) if filters else None
            
            # Perform search
            results = self.collection.search(
                data=[query_vector],
                anns_field="vector",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=["*"]
            )
            
            # Convert results to SearchResult objects
            search_results = []
            
            for hits in results:
                for hit in hits:
                    metadata = VectorMetadata(
                        repo=hit.entity.get("repo"),
                        path=hit.entity.get("path"),
                        chunk_type=hit.entity.get("chunk_type"),
                        language=hit.entity.get("language"),
                        start_line=hit.entity.get("start_line"),
                        end_line=hit.entity.get("end_line"),
                        star_count=hit.entity.get("star_count"),
                        last_commit_date=hit.entity.get("last_commit_date"),
                        text_hash=hit.entity.get("text_hash"),
                        token_count=hit.entity.get("token_count")
                    )
                    
                    search_result = SearchResult(
                        id=hit.entity.get("id"),
                        repo=hit.entity.get("repo"),
                        path=hit.entity.get("path"),
                        content="",  # Content not stored in vector DB
                        score=float(hit.score),
                        chunk_type=hit.entity.get("chunk_type"),
                        language=hit.entity.get("language"),
                        start_line=hit.entity.get("start_line"),
                        end_line=hit.entity.get("end_line"),
                        metadata=metadata
                    )
                    
                    search_results.append(search_result)
            
            logger.debug(f"Found {len(search_results)} similar vectors")
            return search_results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise
    
    def _build_filter_expression(self, filters: Dict[str, Any]) -> str:
        """Build Milvus filter expression from filters dict."""
        expressions = []
        
        for key, value in filters.items():
            if key == "repo" and value:
                expressions.append(f'repo == "{value}"')
            elif key == "language" and value:
                expressions.append(f'language == "{value}"')
            elif key == "chunk_type" and value:
                expressions.append(f'chunk_type == "{value}"')
            elif key == "min_star_count" and value:
                expressions.append(f'star_count >= {value}')
        
        return " and ".join(expressions) if expressions else None
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        if not self.collection:
            await self.create_collection()
        
        try:
            stats = self.collection.get_stats()
            num_entities = self.collection.num_entities
            
            return {
                "collection_name": self.collection_name,
                "num_entities": num_entities,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}
    
    async def delete_collection(self) -> bool:
        """Delete the collection."""
        try:
            if utility.has_collection(self.collection_name):
                utility.drop_collection(self.collection_name)
                logger.info(f"Deleted collection: {self.collection_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            return False 