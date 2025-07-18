import dotenv from 'dotenv';
import { logger } from './logger.js';

// Load environment variables
dotenv.config();

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
}

const config: Config = {
  // Server configuration
  port: parseInt(process.env.PORT || '3000'),
  logLevel: process.env.LOG_LEVEL || 'info',
  
  // Database configuration
  milvusHost: process.env.MILVUS_HOST || 'localhost',
  milvusPort: parseInt(process.env.MILVUS_PORT || '19530'),
  milvusDatabase: 'default',
  neo4jUri: process.env.NEO4J_URI || 'bolt://localhost:7687',
  neo4jUser: process.env.NEO4J_USER || 'neo4j',
  neo4jPassword: process.env.NEO4J_PASSWORD || 'password',
  
  // Local processing configuration
  maxFileSize: parseInt(process.env.MAX_FILE_SIZE_MB || '5'), // 5MB default
  maxProjectSize: parseInt(process.env.MAX_PROJECT_SIZE_MB || '500'), // 500MB default
  supportedLanguages: (process.env.SUPPORTED_LANGUAGES || 
    'JavaScript,TypeScript,Python,Go,Rust,Java,C++,C,PHP,Ruby,Swift,Kotlin,Scala,R,Shell,SQL,HTML,CSS,Markdown')
    .split(',').map(lang => lang.trim()),
  
  // Embedding configuration
  defaultEmbeddingProvider: (process.env.DEFAULT_EMBEDDING_PROVIDER as any) || 'local',
  defaultEmbeddingModel: process.env.DEFAULT_EMBEDDING_MODEL || 'mock',
  openaiApiKey: process.env.OPENAI_API_KEY,
  huggingfaceApiKey: process.env.HUGGINGFACE_API_KEY,
  
  // Chunking configuration
  defaultChunkSize: parseInt(process.env.DEFAULT_CHUNK_SIZE || '1000'),
  defaultChunkOverlap: parseInt(process.env.DEFAULT_CHUNK_OVERLAP || '200'),
  
  // Search configuration
  maxSearchResults: parseInt(process.env.MAX_SEARCH_RESULTS || '50'),
  vectorWeight: parseFloat(process.env.VECTOR_WEIGHT || '0.6'),
  bm25Weight: parseFloat(process.env.BM25_WEIGHT || '0.4'),
  
  // Cache and storage
  cacheDir: process.env.CACHE_DIR || './cache',
  dataDir: process.env.DATA_DIR || './data'
};

// Add legacy properties manually
(config as any).milvus = {
  host: config.milvusHost,
  port: config.milvusPort,
  database: config.milvusDatabase,
  user: process.env.MILVUS_USER,
  password: process.env.MILVUS_PASSWORD
};

(config as any).neo4j = {
  uri: config.neo4jUri,
  user: config.neo4jUser,
  password: config.neo4jPassword,
  database: process.env.NEO4J_DATABASE || 'neo4j'
};

(config as any).server = {
  port: config.port,
  logLevel: config.logLevel
};

// Validation
function validateConfig(): void {
  const errors: string[] = [];
  
  if (config.port < 1 || config.port > 65535) {
    errors.push('PORT must be between 1 and 65535');
  }
  
  if (config.maxFileSize < 1 || config.maxFileSize > 100) {
    errors.push('MAX_FILE_SIZE_MB must be between 1 and 100');
  }
  
  if (config.maxProjectSize < 10 || config.maxProjectSize > 10000) {
    errors.push('MAX_PROJECT_SIZE_MB must be between 10 and 10000');
  }
  
  if (config.defaultChunkSize < 100 || config.defaultChunkSize > 5000) {
    errors.push('DEFAULT_CHUNK_SIZE must be between 100 and 5000');
  }
  
  if (config.defaultChunkOverlap < 0 || config.defaultChunkOverlap >= config.defaultChunkSize) {
    errors.push('DEFAULT_CHUNK_OVERLAP must be between 0 and DEFAULT_CHUNK_SIZE');
  }
  
  if (config.vectorWeight + config.bm25Weight !== 1) {
    logger.warn('VECTOR_WEIGHT + BM25_WEIGHT should equal 1.0 for optimal search results');
  }
  
  if (config.defaultEmbeddingProvider === 'openai' && !config.openaiApiKey) {
    errors.push('OPENAI_API_KEY is required when using OpenAI embedding provider');
  }
  
  if (config.defaultEmbeddingProvider === 'huggingface' && !config.huggingfaceApiKey) {
    errors.push('HUGGINGFACE_API_KEY is required when using Hugging Face embedding provider');
  }
  
  if (errors.length > 0) {
    logger.error('Configuration validation failed:');
    errors.forEach(error => logger.error(`  - ${error}`));
    process.exit(1);
  }
}

// Validate configuration on import
validateConfig();

logger.info('Configuration loaded successfully');
logger.debug('Configuration:', {
  port: config.port,
  logLevel: config.logLevel,
  milvusHost: config.milvusHost,
  milvusPort: config.milvusPort,
  milvusDatabase: config.milvusDatabase,
  maxFileSize: config.maxFileSize,
  maxProjectSize: config.maxProjectSize,
  defaultEmbeddingProvider: config.defaultEmbeddingProvider,
  defaultEmbeddingModel: config.defaultEmbeddingModel,
  supportedLanguages: config.supportedLanguages.slice(0, 5).join(', ') + '...'
});

export { config }; 