from typing import List, Dict, Any, Optional
import asyncio
import numpy as np
from openai import OpenAI
import requests

from ..config import settings
from ..utils.logger import app_logger


class OllamaEmbeddingProvider:
    """Ollama embedding provider."""
    
    def __init__(self, host: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.host = host
        self.model = model
        self.logger = app_logger.bind(component="ollama_embedding")
        self.dimension = 768  # nomic-embed-text dimension
        self.session = requests.Session()
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text using Ollama."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.session.post(
                    f"{self.host}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text
                    }
                )
            )
            response.raise_for_status()
            result = response.json()
            return result["embedding"]
        except Exception as e:
            self.logger.error(f"Error generating Ollama embedding: {e}")
            raise
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts using Ollama."""
        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text)
            embeddings.append(embedding)
        return embeddings
    
    def get_dimension(self) -> int:
        """Get the dimension of embeddings."""
        return self.dimension


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider."""
    
    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.logger = app_logger.bind(component="openai_embedding")
        self.dimension = 1536  # OpenAI ada-002 dimension
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    model=self.model,
                    input=text
                )
            )
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"Error generating OpenAI embedding: {e}")
            raise
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.embeddings.create(
                    model=self.model,
                    input=texts
                )
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            self.logger.error(f"Error generating OpenAI embeddings: {e}")
            raise
    
    def get_dimension(self) -> int:
        """Get the dimension of embeddings."""
        return self.dimension


class EmbeddingService:
    """Service for embedding generation optimized for Milvus."""
    
    def __init__(self):
        self.logger = app_logger.bind(component="embedding_service")
        self.provider = self._initialize_provider()
        self.dimension = self.provider.get_dimension()
    
    def _initialize_provider(self):
        """Initialize the embedding provider based on configuration."""
        if settings.embedding_provider == "ollama":
            return OllamaEmbeddingProvider(
                host=settings.ollama_host,
                model=settings.ollama_model
            )
        elif settings.embedding_provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key is required for OpenAI embeddings")
            return OpenAIEmbeddingProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model
            )
        else:
            raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
    
    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return await self.provider.embed_text(text)
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return await self.provider.embed_texts(texts)
    
    async def embed_chunks(self, chunks) -> List:
        """Generate embeddings for chunks and update them."""
        if not chunks:
            return []
        
        # Extract text from chunks
        texts = [chunk.content for chunk in chunks]
        
        # Generate embeddings
        embeddings = await self.embed_texts(texts)
        
        # Update chunks with embeddings
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        
        return chunks
    
    def get_dimension(self) -> int:
        """Get the dimension of embeddings."""
        return self.dimension
    
    async def embed_query(self, query: str) -> List[float]:
        """Generate embedding for a search query."""
        return await self.embed_text(query)
    
    async def similarity_search(self, query_embedding: List[float], 
                              document_embeddings: List[List[float]], 
                              top_k: int = 10) -> List[Dict[str, Any]]:
        """Perform similarity search using embeddings."""
        if not document_embeddings:
            return []
        
        # Convert to numpy arrays for efficient computation
        query_np = np.array(query_embedding)
        doc_np = np.array(document_embeddings)
        
        # Calculate cosine similarity
        similarities = np.dot(doc_np, query_np) / (
            np.linalg.norm(doc_np, axis=1) * np.linalg.norm(query_np)
        )
        
        # Get top-k results
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                "index": idx,
                "similarity": float(similarities[idx]),
            })
        
        return results