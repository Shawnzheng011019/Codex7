"""
Embedding model wrappers and utilities.
"""

import os
import numpy as np
from typing import List, Optional, Dict, Any, Union
from abc import ABC, abstractmethod
from loguru import logger

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available")

try:
    from FlagEmbedding import FlagModel
    FLAG_EMBEDDING_AVAILABLE = True
except ImportError:
    FLAG_EMBEDDING_AVAILABLE = False
    logger.warning("FlagEmbedding not available")


class EmbeddingModel(ABC):
    """Abstract base class for embedding models."""
    
    @abstractmethod
    async def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts to embeddings."""
        pass
    
    @abstractmethod
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get model name."""
        pass


class BGEEmbeddingModel(EmbeddingModel):
    """BGE embedding model for general text and Chinese content."""
    
    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5", 
                 device: str = "cpu", max_length: int = 512):
        """
        Initialize BGE model.
        
        Args:
            model_name: BGE model name
            device: Device to run model on
            max_length: Maximum sequence length
        """
        self.model_name = model_name
        self.device = device
        self.max_length = max_length
        self.model = None
        
        if not FLAG_EMBEDDING_AVAILABLE:
            raise ImportError("FlagEmbedding package not installed")
    
    def _load_model(self):
        """Lazy load the model."""
        if self.model is None:
            logger.info(f"Loading BGE model: {self.model_name}")
            self.model = FlagModel(
                self.model_name,
                query_instruction_for_retrieval="Represent this sentence for searching relevant passages:",
                use_fp16=True if self.device == "cuda" else False
            )
            logger.success(f"BGE model loaded successfully")
    
    async def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts using BGE model."""
        self._load_model()
        
        try:
            # BGE models work best with instructional queries
            embeddings = self.model.encode(texts)
            
            # Ensure numpy array
            if not isinstance(embeddings, np.ndarray):
                embeddings = np.array(embeddings)
            
            logger.debug(f"Generated {len(embeddings)} embeddings with dimension {embeddings.shape[1]}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error encoding with BGE model: {e}")
            raise
    
    def get_dimension(self) -> int:
        """Get BGE embedding dimension."""
        if "large" in self.model_name.lower():
            return 1024
        elif "base" in self.model_name.lower():
            return 768
        else:
            return 768  # Default
    
    def get_model_name(self) -> str:
        """Get model name."""
        return self.model_name


class SentenceTransformerModel(EmbeddingModel):
    """Sentence transformer model for general embedding."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "cpu"):
        """
        Initialize Sentence Transformer model.
        
        Args:
            model_name: Model name
            device: Device to run model on
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers package not installed")
    
    def _load_model(self):
        """Lazy load the model."""
        if self.model is None:
            logger.info(f"Loading SentenceTransformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.success(f"SentenceTransformer model loaded successfully")
    
    async def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts using SentenceTransformer."""
        self._load_model()
        
        try:
            embeddings = self.model.encode(texts, show_progress_bar=False)
            
            # Ensure numpy array
            if not isinstance(embeddings, np.ndarray):
                embeddings = np.array(embeddings)
            
            logger.debug(f"Generated {len(embeddings)} embeddings with dimension {embeddings.shape[1]}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error encoding with SentenceTransformer: {e}")
            raise
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        self._load_model()
        return self.model.get_sentence_embedding_dimension()
    
    def get_model_name(self) -> str:
        """Get model name."""
        return self.model_name


class CodeEmbeddingModel(EmbeddingModel):
    """Specialized embedding model for code."""
    
    def __init__(self, model_name: str = "microsoft/codebert-base", device: str = "cpu"):
        """
        Initialize code embedding model.
        
        Args:
            model_name: Code model name
            device: Device to run model on
        """
        self.model_name = model_name
        self.device = device
        self.model = None
        
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers package not installed")
    
    def _load_model(self):
        """Lazy load the model."""
        if self.model is None:
            logger.info(f"Loading code embedding model: {self.model_name}")
            try:
                self.model = SentenceTransformer(self.model_name, device=self.device)
            except Exception as e:
                logger.warning(f"Failed to load {self.model_name}, falling back to generic model")
                # Fallback to a generic model that works well with code
                self.model = SentenceTransformer("all-MiniLM-L6-v2", device=self.device)
            logger.success(f"Code embedding model loaded successfully")
    
    async def encode(self, texts: List[str]) -> np.ndarray:
        """Encode code texts."""
        self._load_model()
        
        try:
            # Preprocess code for better embedding
            processed_texts = [self._preprocess_code(text) for text in texts]
            
            embeddings = self.model.encode(processed_texts, show_progress_bar=False)
            
            # Ensure numpy array
            if not isinstance(embeddings, np.ndarray):
                embeddings = np.array(embeddings)
            
            logger.debug(f"Generated {len(embeddings)} code embeddings with dimension {embeddings.shape[1]}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error encoding code: {e}")
            raise
    
    def _preprocess_code(self, code_text: str) -> str:
        """Preprocess code for better embedding."""
        # Remove excessive whitespace
        lines = code_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):  # Remove comments and empty lines
                cleaned_lines.append(line)
        
        return ' '.join(cleaned_lines)
    
    def get_dimension(self) -> int:
        """Get embedding dimension."""
        self._load_model()
        return self.model.get_sentence_embedding_dimension()
    
    def get_model_name(self) -> str:
        """Get model name."""
        return self.model_name


class HybridEmbeddingModel(EmbeddingModel):
    """Hybrid model that uses different models for different content types."""
    
    def __init__(self, 
                 doc_model: Optional[EmbeddingModel] = None,
                 code_model: Optional[EmbeddingModel] = None,
                 device: str = "cpu"):
        """
        Initialize hybrid model.
        
        Args:
            doc_model: Model for documentation
            code_model: Model for code
            device: Device to run models on
        """
        self.device = device
        
        # Initialize default models if not provided
        if doc_model is None:
            try:
                self.doc_model = BGEEmbeddingModel(device=device)
            except ImportError:
                self.doc_model = SentenceTransformerModel(device=device)
        else:
            self.doc_model = doc_model
        
        if code_model is None:
            self.code_model = CodeEmbeddingModel(device=device)
        else:
            self.code_model = code_model
        
        logger.info("Hybrid embedding model initialized")
    
    async def encode(self, texts: List[str], content_types: Optional[List[str]] = None) -> np.ndarray:
        """
        Encode texts using appropriate models.
        
        Args:
            texts: List of texts to encode
            content_types: List of content types ('doc' or 'code')
            
        Returns:
            Embeddings array
        """
        if content_types is None:
            # Use doc model by default
            return await self.doc_model.encode(texts)
        
        if len(texts) != len(content_types):
            raise ValueError("texts and content_types must have same length")
        
        # Group texts by type
        doc_texts = []
        code_texts = []
        doc_indices = []
        code_indices = []
        
        for i, (text, content_type) in enumerate(zip(texts, content_types)):
            if content_type == 'code':
                code_texts.append(text)
                code_indices.append(i)
            else:
                doc_texts.append(text)
                doc_indices.append(i)
        
        # Generate embeddings
        all_embeddings = np.zeros((len(texts), self.get_dimension()))
        
        if doc_texts:
            doc_embeddings = await self.doc_model.encode(doc_texts)
            for i, idx in enumerate(doc_indices):
                all_embeddings[idx] = doc_embeddings[i]
        
        if code_texts:
            code_embeddings = await self.code_model.encode(code_texts)
            for i, idx in enumerate(code_indices):
                all_embeddings[idx] = code_embeddings[i]
        
        return all_embeddings
    
    def get_dimension(self) -> int:
        """Get embedding dimension (assumes both models have same dimension)."""
        return self.doc_model.get_dimension()
    
    def get_model_name(self) -> str:
        """Get model description."""
        return f"Hybrid({self.doc_model.get_model_name()}, {self.code_model.get_model_name()})"


def create_embedding_model(model_type: str = "hybrid", device: str = "cpu") -> EmbeddingModel:
    """
    Factory function to create embedding models.
    
    Args:
        model_type: Type of model ('bge', 'sentence_transformer', 'code', 'hybrid')
        device: Device to run model on
        
    Returns:
        Embedding model instance
    """
    model_type = model_type.lower()
    
    if model_type == "bge":
        return BGEEmbeddingModel(device=device)
    elif model_type == "sentence_transformer":
        return SentenceTransformerModel(device=device)
    elif model_type == "code":
        return CodeEmbeddingModel(device=device)
    elif model_type == "hybrid":
        return HybridEmbeddingModel(device=device)
    else:
        raise ValueError(f"Unknown model type: {model_type}") 