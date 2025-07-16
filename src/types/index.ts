// Repository and project types
export interface GitHubRepo {
  id: number;
  name: string;
  fullName: string;
  description: string;
  url: string;
  cloneUrl: string;
  starCount: number;
  forkCount: number;
  language: string;
  topics: string[];
  lastCommitDate: string;
  createdAt: string;
  updatedAt: string;
  size: number;
  defaultBranch: string;
  license?: string;
  readme?: string;
}

// Content extraction types
export interface ExtractedContent {
  repo: string;
  path: string;
  type: 'doc' | 'code';
  language?: string;
  content: string;
  metadata: ContentMetadata;
}

export interface ContentMetadata {
  repo: string;
  path: string;
  language?: string;
  fileSize: number;
  lastModified: string;
  startLine?: number;
  endLine?: number;
  starCount: number;
  lastCommitDate: string;
  contentType: 'readme' | 'doc' | 'wiki' | 'issue' | 'code' | 'function' | 'class';
}

// Code parsing types
export interface CodeSymbol {
  repo: string;
  path: string;
  symbolType: 'function' | 'class' | 'interface' | 'type' | 'variable' | 'method';
  name: string;
  signature: string;
  startLine: number;
  endLine: number;
  language: string;
  context: string; // 5 lines above and below
}

// Chunking types
export interface TextChunk {
  id: string;
  repo: string;
  path: string;
  chunkType: 'doc' | 'code';
  content: string;
  startLine?: number;
  endLine?: number;
  tokenCount: number;
  language?: string;
  metadata: ContentMetadata;
  textHash: string;
}

// Embedding types
export interface EmbeddingVector {
  id: string;
  vector: number[];
  metadata: VectorMetadata;
}

export interface VectorMetadata {
  repo: string;
  path: string;
  chunkType: 'doc' | 'code';
  language?: string;
  startLine?: number;
  endLine?: number;
  starCount: number;
  lastCommitDate: string;
  textHash: string;
  tokenCount: number;
}

// Search types
export interface SearchQuery {
  query: string;
  language?: string;
  repo?: string;
  topK?: number;
  chunkType?: 'doc' | 'code' | 'both';
}

export interface SearchResult {
  id: string;
  repo: string;
  path: string;
  content: string;
  score: number;
  chunkType: 'doc' | 'code';
  language?: string;
  startLine?: number;
  endLine?: number;
  metadata: VectorMetadata;
}

export interface HybridSearchResult {
  embeddingResults: SearchResult[];
  bm25Results: SearchResult[];
  rerankedResults: SearchResult[];
  finalResults: SearchResult[];
}

// MCP Server types
export interface MCPTool {
  name: string;
  description: string;
  inputSchema: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
}

export interface MCPRequest {
  method: string;
  params: {
    name: string;
    arguments: Record<string, any>;
  };
}

export interface MCPResponse {
  content: Array<{
    type: 'text';
    text: string;
  }>;
  isError?: boolean;
}

// Configuration types
export interface Config {
  milvus: {
    host: string;
    port: number;
    user?: string;
    password?: string;
    database: string;
  };
  openai: {
    apiKey: string;
    baseUrl: string;
  };
  huggingface: {
    apiKey?: string;
  };
  github: {
    token: string;
  };
  server: {
    port: number;
    logLevel: string;
  };
  data: {
    dataDir: string;
    reposDir: string;
    cacheDir: string;
  };
  processing: {
    maxConcurrentDownloads: number;
    maxFileSizeMB: number;
    chunkSize: number;
    chunkOverlap: number;
  };
  models: {
    bgeModelPath: string;
    codeModelPath: string;
    rerankModelPath: string;
  };
}

// Crawler types
export interface CrawlerOptions {
  maxRepos: number;
  sortBy: 'stars' | 'forks' | 'updated';
  language?: string;
  minStars?: number;
}

export interface CrawlResult {
  repos: GitHubRepo[];
  totalFound: number;
  processedCount: number;
  errors: string[];
}

// Processing pipeline types
export interface ProcessingStep {
  name: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startTime?: Date;
  endTime?: Date;
  error?: string;
  progress?: number;
}

export interface ProcessingPipeline {
  repoUrl: string;
  steps: ProcessingStep[];
  overallStatus: 'pending' | 'running' | 'completed' | 'failed';
  startTime: Date;
  endTime?: Date;
}

// Database schema types
export interface MilvusCollectionSchema {
  name: string;
  fields: Array<{
    name: string;
    dataType: string;
    isPrimary?: boolean;
    autoId?: boolean;
    dimension?: number;
  }>;
}

// Error types
export class CodexError extends Error {
  public readonly code: string;
  public readonly details?: any;

  constructor(message: string, code: string, details?: any) {
    super(message);
    this.name = 'CodexError';
    this.code = code;
    this.details = details;
  }
}

// Utility types
export type LogLevel = 'error' | 'warn' | 'info' | 'debug';

export interface Logger {
  error(message: string, error?: any): void;
  warn(message: string, data?: any): void;
  info(message: string, data?: any): void;
  debug(message: string, data?: any): void;
} 