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

// Project types for local codebase
export interface ProjectInfo {
  name: string;
  path: string;
  type: string;
  mainLanguage: string;
  languages: string[];
  fileCount: number;
  totalSize: number;
}

export interface LocalProject {
  name: string;
  path: string;
  project_type: string;
  main_language: string;
  languages: string[];
  file_count: number;
  total_size: number;
}

// Content extraction types
export interface ExtractedContent {
  repo: string;
  path: string;
  type: 'readme' | 'doc' | 'wiki' | 'issue' | 'code' | 'function' | 'class' | 'config' | 'other';
  language: string;
  content: string;
  metadata: ContentMetadata;
  isBinary: boolean;
}

export interface ContentMetadata {
  repo: string;
  path: string;
  language: string;
  fileSize: number;
  lastModified: string | number;
  startLine?: number;
  endLine?: number;
  starCount?: number;
  lastCommitDate?: string;
  contentType: 'readme' | 'doc' | 'wiki' | 'issue' | 'code' | 'function' | 'class' | 'config' | 'other';
  projectType?: string;
  mainLanguage?: string;
  chunkSize?: number;
  chunkIndex?: number;
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
  chunkType: 'readme' | 'doc' | 'wiki' | 'issue' | 'code' | 'function' | 'class' | 'config' | 'other';
  content: string;
  startLine: number;
  endLine: number;
  chunkIndex: number;
  tokenCount?: number;
  language: string;
  metadata: ContentMetadata;
  textHash?: string;
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
  chunkType: 'readme' | 'doc' | 'wiki' | 'issue' | 'code' | 'function' | 'class' | 'config' | 'other';
  language: string;
  startLine: number;
  endLine: number;
  chunkIndex: number;
  starCount?: number;
  lastCommitDate?: string;
  textHash?: string;
  tokenCount: number;
  contentLength: number;
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
  // For backward compatibility we allow both `inputSchema` and the MCP spec preferred `parameters` field.
  inputSchema?: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
  parameters?: {
    type: 'object';
    properties: Record<string, any>;
    required?: string[];
  };
}

export interface MCPRequest {
  method: string;
  params?: any;
}

export interface MCPToolCallRequest {
  method: string;
  params: {
    name: string;
    arguments: Record<string, any>;
  };
}

export interface MCPResponse {
  // Standard content response
  content?: Array<{
    type: 'text';
    text: string;
  }>;
  isError?: boolean;
  
  // MCP initialization response
  protocolVersion?: string;
  capabilities?: {
    tools?: Record<string, any>;
    [key: string]: any;
  };
  serverInfo?: {
    name: string;
    version: string;
  };
  
  // Tools list response
  tools?: MCPTool[];
  
  // Empty response for notifications
  [key: string]: any;
}

// Configuration types
export interface Config {
  // Server configuration
  port: number;
  logLevel: string;
  
  // Database configuration
  milvusHost: string;
  milvusPort: number;
  milvusDatabase: string;
  neo4jUri: string;
  neo4jUser: string;
  neo4jPassword: string;
  
  // Local processing configuration
  maxFileSize: number; // in MB
  maxProjectSize: number; // in MB
  supportedLanguages: string[];
  
  // Embedding configuration
  defaultEmbeddingProvider: 'openai' | 'huggingface' | 'local';
  defaultEmbeddingModel: string;
  openaiApiKey?: string;
  huggingfaceApiKey?: string;
  
  // Chunking configuration
  defaultChunkSize: number;
  defaultChunkOverlap: number;
  
  // Search configuration
  maxSearchResults: number;
  vectorWeight: number;
  bm25Weight: number;
  
  // Cache and storage
  cacheDir: string;
  dataDir: string;

  // Legacy interface structure for compatibility
  readonly milvus: {
    host: string;
    port: number;
    user?: string;
    password?: string;
    database: string;
  };
  readonly neo4j: {
    uri: string;
    user: string;
    password?: string;
    database?: string;
  };
  readonly server: {
    port: number;
    logLevel: string;
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