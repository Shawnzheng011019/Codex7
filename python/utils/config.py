import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator
from pathlib import Path


class Config(BaseSettings):
    # GitHub Configuration
    github_token: str
    
    # OpenAI Configuration (for embeddings)
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = "https://api.openai.com/v1"
    
    # Vector Database Configuration
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_user: Optional[str] = None
    milvus_password: Optional[str] = None
    milvus_database: str = "codex7"
    
    # Hugging Face Configuration
    huggingface_token: Optional[str] = None
    huggingface_api_key: Optional[str] = None  # Alternative name
    
    # Server Configuration
    port: int = 3000
    
    # Data Configuration
    data_dir: str = "../data"
    repos_dir: str = "../data/repos"
    cache_dir: str = "../data/cache"
    
    # Processing Configuration
    max_concurrent_downloads: int = 5
    max_file_size_mb: int = 1
    chunk_size: int = 512
    chunk_overlap: int = 51
    max_repos: int = 100
    
    # Model Configuration
    bge_model_name: str = "BAAI/bge-large-zh-v1.5"
    bge_model_path: Optional[str] = None  # Alternative name
    code_model_name: str = "jinaai/jina-embeddings-v2-base-code"
    code_model_path: Optional[str] = None  # Alternative name
    rerank_model_name: str = "BAAI/bge-reranker-large"
    rerank_model_path: Optional[str] = None  # Alternative name
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/processing.log"
    
    @field_validator('data_dir', 'repos_dir', 'cache_dir')
    @classmethod
    def ensure_directory_exists(cls, v):
        Path(v).mkdir(parents=True, exist_ok=True)
        return v
    
    def get_bge_model_name(self) -> str:
        """Get BGE model name, prioritizing bge_model_path if set."""
        return self.bge_model_path or self.bge_model_name
    
    def get_code_model_name(self) -> str:
        """Get code model name, prioritizing code_model_path if set."""
        return self.code_model_path or self.code_model_name
    
    def get_rerank_model_name(self) -> str:
        """Get rerank model name, prioritizing rerank_model_path if set."""
        return self.rerank_model_path or self.rerank_model_name
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields in .env file


# Global config instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config 