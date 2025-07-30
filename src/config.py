import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""
    
    # Database Configuration
    milvus_host: str = Field(default="localhost", env="MILVUS_HOST")
    milvus_port: int = Field(default=19530, env="MILVUS_PORT")
    milvus_collection_name: str = Field(default="code_chunks", env="MILVUS_COLLECTION_NAME")
    milvus_dimension: int = Field(default=1536, env="MILVUS_DIMENSION")
    
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", env="NEO4J_USERNAME")
    neo4j_password: str = Field(default="neo4j", env="NEO4J_PASSWORD")
    
    # Embedding Service Configuration
    embedding_provider: str = Field(default="openai", env="EMBEDDING_PROVIDER")
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="text-embedding-ada-002", env="OPENAI_MODEL")
    
    huggingface_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", env="HUGGINGFACE_MODEL")
    huggingface_api_key: Optional[str] = Field(default=None, env="HUGGINGFACE_API_KEY")
    
    ollama_host: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")
    ollama_model: str = Field(default="nomic-embed-text", env="OLLAMA_MODEL")
    
    # Search Configuration
    bm25_k1: float = Field(default=1.2, env="BM25_K1")
    bm25_b: float = Field(default=0.75, env="BM25_B")
    top_k_results: int = Field(default=10, env="TOP_K_RESULTS")
    rerank_threshold: float = Field(default=0.5, env="RERANK_THRESHOLD")
    
    # File Processing Configuration
    max_chunk_size: int = Field(default=1000, env="MAX_CHUNK_SIZE")
    chunk_overlap: int = Field(default=200, env="CHUNK_OVERLAP")
    supported_extensions: str = Field(
        default=".py,.js,.ts,.java,.cpp,.c,.go,.rs,.md,.txt,.json,.yaml,.yml,.xml,.html,.css,.sql,.sh,.rb,.php,.swift,.kt,.scala,.dart,.vue,.jsx,.tsx",
        env="SUPPORTED_EXTENSIONS"
    )
    
    # MCP Configuration
    mcp_host: str = Field(default="localhost", env="MCP_HOST")
    mcp_port: int = Field(default=8000, env="MCP_PORT")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", env="LOG_FILE")
    
  
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def supported_extensions_list(self) -> List[str]:
        """Get supported extensions as a list."""
        return [ext.strip() for ext in self.supported_extensions.split(",")]
    
    @property
    def log_dir(self) -> Path:
        """Get log directory path."""
        return Path(self.log_file).parent
    
    def ensure_directories(self):
        """Ensure necessary directories exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()