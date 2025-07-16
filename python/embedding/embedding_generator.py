"""
Embedding generator for text chunks.
"""

import asyncio
import numpy as np
from typing import List, Optional, Dict, Any
from pathlib import Path
from loguru import logger

from utils.models import TextChunk, EmbeddingVector, VectorMetadata
from utils.config import get_config
from .models import create_embedding_model, EmbeddingModel


class EmbeddingGenerator:
    """Main embedding generator for text chunks."""
    
    def __init__(self, 
                 model_type: str = "hybrid",
                 device: str = "cpu",
                 batch_size: int = 32,
                 max_retries: int = 3):
        """
        Initialize embedding generator.
        
        Args:
            model_type: Type of embedding model to use
            device: Device to run model on ('cpu', 'cuda')
            batch_size: Batch size for processing
            max_retries: Maximum retry attempts for failed embeddings
        """
        self.model_type = model_type
        self.device = device
        self.batch_size = batch_size
        self.max_retries = max_retries
        
        self.config = get_config()
        self.model: Optional[EmbeddingModel] = None
        
        logger.info(f"Initializing EmbeddingGenerator with {model_type} model on {device}")
    
    def _load_model(self):
        """Lazy load the embedding model."""
        if self.model is None:
            try:
                self.model = create_embedding_model(self.model_type, self.device)
                logger.success(f"Embedding model loaded: {self.model.get_model_name()}")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                # Fallback to simple sentence transformer
                logger.info("Falling back to sentence transformer model")
                self.model = create_embedding_model("sentence_transformer", self.device)
    
    async def generate_embeddings(self, chunks: List[TextChunk]) -> List[EmbeddingVector]:
        """
        Generate embeddings for text chunks.
        
        Args:
            chunks: List of text chunks
            
        Returns:
            List of embedding vectors
        """
        if not chunks:
            logger.warning("No chunks provided for embedding generation")
            return []
        
        self._load_model()
        
        logger.info(f"Generating embeddings for {len(chunks)} chunks using {self.model.get_model_name()}")
        
        all_vectors = []
        failed_count = 0
        
        # Process chunks in batches
        for i in range(0, len(chunks), self.batch_size):
            batch_chunks = chunks[i:i + self.batch_size]
            batch_end = min(i + self.batch_size, len(chunks))
            
            logger.info(f"Processing batch {i//self.batch_size + 1}/{(len(chunks) + self.batch_size - 1)//self.batch_size} "
                       f"(chunks {i+1}-{batch_end})")
            
            try:
                batch_vectors = await self._process_batch(batch_chunks)
                all_vectors.extend(batch_vectors)
                
            except Exception as e:
                logger.error(f"Error processing batch {i//self.batch_size + 1}: {e}")
                failed_count += len(batch_chunks)
                continue
        
        success_count = len(all_vectors)
        logger.info(f"Embedding generation complete: {success_count} successful, {failed_count} failed")
        
        return all_vectors
    
    async def _process_batch(self, chunks: List[TextChunk]) -> List[EmbeddingVector]:
        """Process a batch of chunks."""
        batch_vectors = []
        
        # Extract texts and content types
        texts = [chunk.content for chunk in chunks]
        content_types = [chunk.chunk_type for chunk in chunks]
        
        # Generate embeddings
        try:
            if hasattr(self.model, 'encode') and 'content_types' in self.model.encode.__code__.co_varnames:
                # Hybrid model that supports content types
                embeddings = await self.model.encode(texts, content_types)
            else:
                # Standard model
                embeddings = await self.model.encode(texts)
            
            # Create embedding vectors
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                try:
                    vector = self._create_embedding_vector(chunk, embedding)
                    batch_vectors.append(vector)
                    
                except Exception as e:
                    logger.warning(f"Failed to create vector for chunk {chunk.id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            # Try individual processing as fallback
            batch_vectors = await self._process_individual(chunks)
        
        return batch_vectors
    
    async def _process_individual(self, chunks: List[TextChunk]) -> List[EmbeddingVector]:
        """Process chunks individually as fallback."""
        vectors = []
        
        for chunk in chunks:
            for attempt in range(self.max_retries):
                try:
                    embedding = await self.model.encode([chunk.content])
                    vector = self._create_embedding_vector(chunk, embedding[0])
                    vectors.append(vector)
                    break
                    
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        logger.error(f"Failed to generate embedding for {chunk.id} after {self.max_retries} attempts: {e}")
                    else:
                        logger.warning(f"Attempt {attempt + 1} failed for {chunk.id}: {e}")
                        await asyncio.sleep(0.1)  # Brief delay before retry
        
        return vectors
    
    def _create_embedding_vector(self, chunk: TextChunk, embedding: np.ndarray) -> EmbeddingVector:
        """Create an embedding vector from chunk and embedding."""
        # Ensure embedding is a numpy array and flatten it
        if not isinstance(embedding, np.ndarray):
            embedding = np.array(embedding)
        
        if embedding.ndim > 1:
            embedding = embedding.flatten()
        
        # Create metadata
        metadata = VectorMetadata(
            repo=chunk.repo,
            path=chunk.path,
            chunk_type=chunk.chunk_type,
            language=chunk.language,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            star_count=chunk.metadata.star_count,
            last_commit_date=chunk.metadata.last_commit_date,
            text_hash=chunk.text_hash,
            token_count=chunk.token_count
        )
        
        return EmbeddingVector(
            id=chunk.id,
            vector=embedding.tolist(),  # Convert to list for JSON serialization
            metadata=metadata
        )
    
    async def generate_query_embedding(self, query_text: str, chunk_type: str = "doc") -> np.ndarray:
        """
        Generate embedding for a search query.
        
        Args:
            query_text: Query text
            chunk_type: Type of content being searched ('doc' or 'code')
            
        Returns:
            Query embedding
        """
        self._load_model()
        
        try:
            if hasattr(self.model, 'encode') and 'content_types' in self.model.encode.__code__.co_varnames:
                # Hybrid model
                embedding = await self.model.encode([query_text], [chunk_type])
            else:
                # Standard model
                embedding = await self.model.encode([query_text])
            
            return embedding[0]
            
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings."""
        self._load_model()
        return self.model.get_dimension()
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the embedding model."""
        self._load_model()
        
        return {
            "model_name": self.model.get_model_name(),
            "model_type": self.model_type,
            "device": self.device,
            "dimension": self.model.get_dimension(),
            "batch_size": self.batch_size
        } 