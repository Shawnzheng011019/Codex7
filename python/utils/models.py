from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class GitHubRepo(BaseModel):
    """GitHub repository model."""
    id: int
    name: str
    full_name: str
    description: str
    url: str
    clone_url: str
    star_count: int
    fork_count: int
    language: str
    topics: List[str] = Field(default_factory=list)
    last_commit_date: str
    created_at: str
    updated_at: str
    size: int
    default_branch: str
    license: Optional[str] = None
    readme: Optional[str] = None


class ContentMetadata(BaseModel):
    """Metadata for extracted content."""
    repo: str
    path: str
    language: Optional[str] = None
    file_size: int
    last_modified: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    star_count: int
    last_commit_date: str
    content_type: Literal['readme', 'doc', 'wiki', 'issue', 'code', 'function', 'class']


class ExtractedContent(BaseModel):
    """Extracted content from repositories."""
    repo: str
    path: str
    type: Literal['doc', 'code']
    language: Optional[str] = None
    content: str
    metadata: ContentMetadata


class CodeSymbol(BaseModel):
    """Code symbol information."""
    repo: str
    path: str
    symbol_type: Literal['function', 'class', 'interface', 'type', 'variable', 'method']
    name: str
    signature: str
    start_line: int
    end_line: int
    language: str
    context: str  # 5 lines above and below


class TextChunk(BaseModel):
    """Text chunk for embedding."""
    id: str
    repo: str
    path: str
    chunk_type: Literal['doc', 'code']
    content: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    token_count: int
    language: Optional[str] = None
    metadata: ContentMetadata
    text_hash: str


class VectorMetadata(BaseModel):
    """Metadata for vector embeddings."""
    repo: str
    path: str
    chunk_type: Literal['doc', 'code']
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    star_count: int
    last_commit_date: str
    text_hash: str
    token_count: int


class EmbeddingVector(BaseModel):
    """Embedding vector with metadata."""
    id: str
    vector: List[float]
    metadata: VectorMetadata


class SearchQuery(BaseModel):
    """Search query parameters."""
    query: str
    language: Optional[str] = None
    repo: Optional[str] = None
    top_k: int = 10
    chunk_type: Literal['doc', 'code', 'both'] = 'both'


class SearchResult(BaseModel):
    """Search result item."""
    id: str
    repo: str
    path: str
    content: str
    score: float
    chunk_type: Literal['doc', 'code']
    language: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    metadata: VectorMetadata


class HybridSearchResult(BaseModel):
    """Hybrid search results."""
    embedding_results: List[SearchResult]
    bm25_results: List[SearchResult]
    reranked_results: List[SearchResult]
    final_results: List[SearchResult]


class ProcessingStep(BaseModel):
    """Processing pipeline step."""
    name: str
    status: Literal['pending', 'running', 'completed', 'failed']
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    error: Optional[str] = None
    progress: Optional[float] = None


class ProcessingPipeline(BaseModel):
    """Processing pipeline for a repository."""
    repo_url: str
    steps: List[ProcessingStep]
    overall_status: Literal['pending', 'running', 'completed', 'failed']
    start_time: datetime
    end_time: Optional[datetime] = None


class CrawlResult(BaseModel):
    """Result of crawling operation."""
    repos: List[GitHubRepo]
    total_found: int
    processed_count: int
    errors: List[str] = Field(default_factory=list)


class EmbeddingResult(BaseModel):
    """Result of embedding operation."""
    vectors: List[EmbeddingVector]
    total_chunks: int
    successful_embeddings: int
    failed_embeddings: int
    errors: List[str] = Field(default_factory=list)


class IndexingResult(BaseModel):
    """Result of vector indexing operation."""
    collection_name: str
    total_vectors: int
    indexed_vectors: int
    failed_vectors: int
    index_status: str
    errors: List[str] = Field(default_factory=list) 