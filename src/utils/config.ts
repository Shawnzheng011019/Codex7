import { config as dotenvConfig } from 'dotenv';
import { Config } from '../types/index.js';

// Load environment variables
dotenvConfig();

export function loadConfig(): Config {
  const milvusConfig: Config['milvus'] = {
    host: process.env.MILVUS_HOST || 'localhost',
    port: parseInt(process.env.MILVUS_PORT || '19530'),
    database: process.env.MILVUS_DATABASE || 'codex7',
  };
  
  if (process.env.MILVUS_USER) {
    milvusConfig.user = process.env.MILVUS_USER;
  }
  
  if (process.env.MILVUS_PASSWORD) {
    milvusConfig.password = process.env.MILVUS_PASSWORD;
  }

  const huggingfaceConfig: Config['huggingface'] = {};
  if (process.env.HUGGINGFACE_API_KEY) {
    huggingfaceConfig.apiKey = process.env.HUGGINGFACE_API_KEY;
  }

  return {
    milvus: milvusConfig,
    openai: {
      apiKey: process.env.OPENAI_API_KEY || '',
      baseUrl: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
    },
    huggingface: huggingfaceConfig,
    github: {
      token: process.env.GITHUB_TOKEN || '',
    },
    server: {
      port: parseInt(process.env.PORT || '3000'),
      logLevel: process.env.LOG_LEVEL || 'info',
    },
    data: {
      dataDir: process.env.DATA_DIR || './data',
      reposDir: process.env.REPOS_DIR || './data/repos',
      cacheDir: process.env.CACHE_DIR || './data/cache',
    },
    processing: {
      maxConcurrentDownloads: parseInt(process.env.MAX_CONCURRENT_DOWNLOADS || '5'),
      maxFileSizeMB: parseInt(process.env.MAX_FILE_SIZE_MB || '1'),
      chunkSize: parseInt(process.env.CHUNK_SIZE || '512'),
      chunkOverlap: parseInt(process.env.CHUNK_OVERLAP || '51'),
    },
    models: {
      bgeModelPath: process.env.BGE_MODEL_PATH || 'BAAI/bge-large-zh-v1.5',
      codeModelPath: process.env.CODE_MODEL_PATH || 'jinaai/jina-embeddings-v2-base-code',
      rerankModelPath: process.env.RERANK_MODEL_PATH || 'colbert-ir/colbertv2.0',
    },
    neo4j: {
      uri: process.env.NEO4J_URI || 'bolt://localhost:7687',
      user: process.env.NEO4J_USER || 'neo4j',
      password: process.env.NEO4J_PASSWORD || 'password',
      database: process.env.NEO4J_DATABASE || 'neo4j',
    },
  };
}

export const config = loadConfig(); 