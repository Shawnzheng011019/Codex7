"""
Unified vector store interface.
"""

import asyncio
from typing import List, Optional, Dict, Any, Protocol
from abc import ABC, abstractmethod
from loguru import logger

from utils.models import EmbeddingVector, SearchResult, SearchQuery
from .milvus_client import MilvusClient


class VectorStoreInterface(Protocol):
    """Interface for vector stores."""
    
    async def insert_vectors(self, vectors: List[EmbeddingVector]) -> bool:
        """Insert vectors into the store."""
        ...
    
    async def search_vectors(self, 
                           query_vector: List[float],
                           top_k: int = 10,
                           filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """Search for similar vectors."""
        ...
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get store statistics."""
        ...


class VectorStore:
    """Unified vector store that can work with different backends."""
    
    def __init__(self, 
                 backend: str = "milvus",
                 **kwargs):
        """
        Initialize vector store.
        
        Args:
            backend: Backend type ('milvus', 'faiss', 'chroma')
            **kwargs: Backend-specific arguments
        """
        self.backend = backend.lower()
        self.client = None
        
        if self.backend == "milvus":
            self.client = MilvusClient(**kwargs)
        else:
            raise ValueError(f"Unsupported backend: {backend}")
        
        logger.info(f"Initialized VectorStore with {backend} backend")
    
    async def __aenter__(self):
        """Async context manager entry."""
        if hasattr(self.client, '__aenter__'):
            await self.client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if hasattr(self.client, '__aexit__'):
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def initialize(self) -> bool:
        """Initialize the vector store."""
        try:
            if hasattr(self.client, 'create_collection'):
                await self.client.create_collection()
            
            if hasattr(self.client, 'create_index'):
                await self.client.create_index()
            
            logger.success("Vector store initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise
    
    async def insert_vectors(self, vectors: List[EmbeddingVector]) -> bool:
        """
        Insert embedding vectors.
        
        Args:
            vectors: List of embedding vectors
            
        Returns:
            True if successful
        """
        if not vectors:
            logger.warning("No vectors to insert")
            return True
        
        try:
            result = await self.client.insert_vectors(vectors)
            logger.info(f"Inserted {len(vectors)} vectors successfully")
            return result
            
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            raise
    
    async def search_vectors(self, 
                           query_vector: List[float],
                           top_k: int = 10,
                           filters: Optional[Dict[str, Any]] = None) -> List[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of search results
        """
        try:
            results = await self.client.search_vectors(
                query_vector=query_vector,
                top_k=top_k,
                filters=filters
            )
            
            logger.debug(f"Vector search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            raise
    
    async def search_by_query(self, query: SearchQuery, query_vector: List[float]) -> List[SearchResult]:
        """
        Search using a structured query.
        
        Args:
            query: Search query object
            query_vector: Pre-computed query embedding
            
        Returns:
            List of search results
        """
        # Build filters from query
        filters = {}
        
        if query.language:
            filters["language"] = query.language
        
        if query.repo:
            filters["repo"] = query.repo
        
        if query.chunk_type != "both":
            filters["chunk_type"] = query.chunk_type
        
        return await self.search_vectors(
            query_vector=query_vector,
            top_k=query.top_k,
            filters=filters
        )
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        try:
            if hasattr(self.client, 'get_collection_stats'):
                stats = await self.client.get_collection_stats()
            else:
                stats = {"backend": self.backend}
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the vector store."""
        try:
            stats = await self.get_stats()
            
            health = {
                "status": "healthy",
                "backend": self.backend,
                "stats": stats
            }
            
            # Check if we can perform a simple operation
            if hasattr(self.client, '_connected') and not self.client._connected:
                health["status"] = "disconnected"
            
            return health
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": self.backend,
                "error": str(e)
            }
    
    async def clear_all(self) -> bool:
        """Clear all data from the vector store."""
        try:
            if hasattr(self.client, 'delete_collection'):
                result = await self.client.delete_collection()
                logger.warning("Cleared all data from vector store")
                return result
            else:
                logger.warning("Clear operation not supported by backend")
                return False
                
        except Exception as e:
            logger.error(f"Failed to clear vector store: {e}")
            raise 