import { MilvusClient, MetricType, DataType } from '@zilliz/milvus2-sdk-node';
import { SearchQuery, SearchResult, VectorMetadata } from '../types/index.js';
import { config } from '../utils/config.js';
import { logger } from '../utils/logger.js';

export class MilvusQueryClient {
  private client: MilvusClient;
  private isConnected = false;

  constructor() {
    const clientConfig: any = {
      address: `${config.milvusHost}:${config.milvusPort}`,
    };
    
    if (process.env.MILVUS_USER) {
      clientConfig.username = process.env.MILVUS_USER;
    }
    
    if (process.env.MILVUS_PASSWORD) {
      clientConfig.password = process.env.MILVUS_PASSWORD;
    }
    
    this.client = new MilvusClient(clientConfig);
  }

  async connect(): Promise<void> {
    try {
      // Test connection
      await this.client.checkHealth();
      
      // Use default database only
      await this.client.useDatabase({ db_name: 'default' });
      logger.info('Using default database');
      
      // Check if collection exists, create if not
      await this.ensureCollectionExists();
      
      this.isConnected = true;
      logger.info('Connected to Milvus successfully');
    } catch (error) {
      logger.error('Failed to connect to Milvus:', error);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    if (this.isConnected) {
      // Note: SDK doesn't have explicit disconnect, connection is managed automatically
      this.isConnected = false;
      logger.info('Disconnected from Milvus');
    }
  }

  async searchEmbedding(
    query: SearchQuery,
    queryVector: number[],
    topK: number = 10
  ): Promise<SearchResult[]> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      const collectionName = this.getCollectionName(query.chunkType);
      
      // Build search params
      const searchParams = {
        collection_name: collectionName,
        vectors: [queryVector],
        search_params: {
          anns_field: 'vector',
          topk: topK,
          metric_type: MetricType.COSINE,
          params: JSON.stringify({ nprobe: 16 }),
        },
        output_fields: [
          'id', 'repo', 'path', 'content', 'chunk_type', 
          'language', 'start_line', 'end_line', 'star_count',
          'last_commit_date', 'text_hash', 'token_count'
        ],
        expr: this.buildFilterExpression(query),
      };

      const results = await this.client.search(searchParams);
      
      return this.formatSearchResults(results.results);
    } catch (error) {
      logger.error('Error searching embeddings:', error);
      throw error;
    }
  }

  async searchByText(
    query: SearchQuery,
    topK: number = 10
  ): Promise<SearchResult[]> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      const collectionName = this.getCollectionName(query.chunkType);
      
      // Use text-based search (if available) or hybrid search
      const searchParams = {
        collection_name: collectionName,
        expr: this.buildTextSearchExpression(query),
        output_fields: [
          'id', 'repo', 'path', 'content', 'chunk_type', 
          'language', 'start_line', 'end_line', 'star_count',
          'last_commit_date', 'text_hash', 'token_count'
        ],
        limit: topK,
      };

      const results = await this.client.query(searchParams);
      
      return this.formatQueryResults(results.data);
    } catch (error) {
      logger.error('Error searching by text:', error);
      throw error;
    }
  }

  async getRepositoryFiles(repoName: string): Promise<SearchResult[]> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      const searchParams = {
        collection_name: 'codex7_chunks',
        expr: `repo == "${repoName}"`,
        output_fields: [
          'id', 'repo', 'path', 'content', 'chunk_type', 
          'language', 'start_line', 'end_line', 'star_count',
          'last_commit_date', 'text_hash', 'token_count'
        ],
        limit: 1000, // Large limit to get all files
      };

      const results = await this.client.query(searchParams);
      
      return this.formatQueryResults(results.data);
    } catch (error) {
      logger.error('Error getting repository files:', error);
      throw error;
    }
  }

  async searchSymbols(symbolName: string, repo?: string): Promise<SearchResult[]> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      let expr = `content like "%${symbolName}%"`;
      if (repo) {
        expr += ` and repo == "${repo}"`;
      }
      expr += ` and chunk_type == "code"`;

      const searchParams = {
        collection_name: 'codex7_chunks',
        expr,
        output_fields: [
          'id', 'repo', 'path', 'content', 'chunk_type', 
          'language', 'start_line', 'end_line', 'star_count',
          'last_commit_date', 'text_hash', 'token_count'
        ],
        limit: 50,
      };

      const results = await this.client.query(searchParams);
      
      return this.formatQueryResults(results.data);
    } catch (error) {
      logger.error('Error searching symbols:', error);
      throw error;
    }
  }

  async insertVectors(vectors: any[]): Promise<void> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      if (vectors.length === 0) {
        logger.warn('No vectors to insert');
        return;
      }

      const collectionName = 'codex7_chunks';
      
      // Prepare data for insertion
      const data = vectors.map(vector => ({
        id: vector.id,
        vector: vector.vector,
        repo: vector.metadata.repo,
        path: vector.metadata.path,
        content: vector.content || '',
        chunk_type: vector.metadata.chunkType,
        language: vector.metadata.language,
        start_line: vector.metadata.startLine,
        end_line: vector.metadata.endLine,
        chunk_index: vector.metadata.chunkIndex,
        star_count: vector.metadata.starCount || 0,
        last_commit_date: vector.metadata.lastCommitDate || '',
        text_hash: vector.metadata.textHash || '',
        token_count: vector.metadata.tokenCount,
        content_length: vector.metadata.contentLength
      }));

      const insertParams = {
        collection_name: collectionName,
        data: data
      };

      await this.client.insert(insertParams);
      logger.info(`Inserted ${vectors.length} vectors into ${collectionName}`);
    } catch (error) {
      logger.error('Error inserting vectors:', error);
      throw error;
    }
  }

  async getCollectionStats(): Promise<any> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      const stats = await this.client.getCollectionStatistics({
        collection_name: 'codex7_chunks',
      });
      
      return stats;
    } catch (error) {
      logger.error('Error getting collection stats:', error);
      throw error;
    }
  }

  private getCollectionName(chunkType: string | undefined): string {
    if (chunkType === 'doc') {
      return 'codex7_docs';
    } else if (chunkType === 'code') {
      return 'codex7_code';
    } else {
      return 'codex7_chunks'; // Default collection with both types
    }
  }

  private buildFilterExpression(query: SearchQuery): string {
    const filters: string[] = [];

    if (query.language) {
      filters.push(`language == "${query.language}"`);
    }

    if (query.repo) {
      filters.push(`repo == "${query.repo}"`);
    }

    if (query.chunkType && query.chunkType !== 'both') {
      filters.push(`chunk_type == "${query.chunkType}"`);
    }

    return filters.length > 0 ? filters.join(' and ') : '';
  }

  private buildTextSearchExpression(query: SearchQuery): string {
    const filters: string[] = [];

    // Add text search condition
    filters.push(`content like "%${query.query}%"`);

    if (query.language) {
      filters.push(`language == "${query.language}"`);
    }

    if (query.repo) {
      filters.push(`repo == "${query.repo}"`);
    }

    if (query.chunkType && query.chunkType !== 'both') {
      filters.push(`chunk_type == "${query.chunkType}"`);
    }

    return filters.join(' and ');
  }

  private formatSearchResults(results: any[]): SearchResult[] {
    return results.map(result => {
      const metadata: VectorMetadata = {
        repo: result.repo,
        path: result.path,
        chunkType: result.chunk_type,
        language: result.language,
        startLine: result.start_line,
        endLine: result.end_line,
        chunkIndex: result.chunk_index || 0,
        starCount: result.star_count,
        lastCommitDate: result.last_commit_date,
        textHash: result.text_hash,
        tokenCount: result.token_count || 0,
        contentLength: result.content_length || result.content?.length || 0,
      };

      return {
        id: result.id,
        repo: result.repo,
        path: result.path,
        content: result.content,
        score: result.score || 0,
        chunkType: result.chunk_type,
        language: result.language,
        startLine: result.start_line,
        endLine: result.end_line,
        metadata,
      };
    });
  }

  private formatQueryResults(results: any[]): SearchResult[] {
    return results.map(result => {
      const metadata: VectorMetadata = {
        repo: result.repo,
        path: result.path,
        chunkType: result.chunk_type,
        language: result.language,
        startLine: result.start_line,
        endLine: result.end_line,
        chunkIndex: result.chunk_index || 0,
        starCount: result.star_count,
        lastCommitDate: result.last_commit_date,
        textHash: result.text_hash,
        tokenCount: result.token_count || 0,
        contentLength: result.content_length || result.content?.length || 0,
      };

      return {
        id: result.id,
        repo: result.repo,
        path: result.path,
        content: result.content,
        score: 1.0, // Default score for query results
        chunkType: result.chunk_type,
        language: result.language,
        startLine: result.start_line,
        endLine: result.end_line,
        metadata,
      };
    });
  }

  // Database creation logic removed - using default database only

  private async ensureCollectionExists(): Promise<void> {
    try {
      const collectionName = 'codex7_chunks';
      const exists = await this.client.hasCollection({
        collection_name: collectionName,
      });
      
      if (!exists.value) {
        await this.createCollection(collectionName);
        logger.info(`Created collection: ${collectionName}`);
      }
    } catch (error) {
      logger.error('Error ensuring collection exists:', error);
      throw error;
    }
  }

  private async createCollection(collectionName: string): Promise<void> {
    const schema = {
      collection_name: collectionName,
      fields: [
        {
          name: 'id',
          data_type: DataType.VarChar,
          is_primary_key: true,
          max_length: 256,
        },
        {
          name: 'vector',
          data_type: DataType.FloatVector,
          dim: 1536, // OpenAI text-embedding-3-small dimension
        },
        {
          name: 'repo',
          data_type: DataType.VarChar,
          max_length: 256,
        },
        {
          name: 'path',
          data_type: DataType.VarChar,
          max_length: 512,
        },
        {
          name: 'content',
          data_type: DataType.VarChar,
          max_length: 32768,
        },
        {
          name: 'chunk_type',
          data_type: DataType.VarChar,
          max_length: 32,
        },
        {
          name: 'language',
          data_type: DataType.VarChar,
          max_length: 32,
        },
        {
          name: 'start_line',
          data_type: DataType.Int32,
        },
        {
          name: 'end_line',
          data_type: DataType.Int32,
        },
        {
          name: 'chunk_index',
          data_type: DataType.Int32,
        },
        {
          name: 'star_count',
          data_type: DataType.Int32,
        },
        {
          name: 'last_commit_date',
          data_type: DataType.VarChar,
          max_length: 32,
        },
        {
          name: 'text_hash',
          data_type: DataType.VarChar,
          max_length: 64,
        },
        {
          name: 'token_count',
          data_type: DataType.Int32,
        },
        {
          name: 'content_length',
          data_type: DataType.Int32,
        },
      ],
    };

    await this.client.createCollection(schema);
    
    // Create index for vector field
    await this.client.createIndex({
      collection_name: collectionName,
      field_name: 'vector',
      index_type: 'IVF_FLAT',
      metric_type: MetricType.COSINE,
      params: { nlist: 128 },
    });

    // Load collection
    await this.client.loadCollection({
      collection_name: collectionName,
    });
  }

  /**
   * Check if a codebase already exists in Milvus
   */
  async codebaseExists(repo: string): Promise<boolean> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      const searchParams = {
        collection_name: 'codex7_chunks',
        filter: `repo == "${repo}"`,
        output_fields: ['id'],
        limit: 1,
      };

      const results = await this.client.query(searchParams);
      return results.data.length > 0;
    } catch (error) {
      logger.error(`Error checking if codebase ${repo} exists in Milvus:`, error);
      return false;
    }
  }

  /**
   * Clean up specific codebase data from Milvus
   */
  async cleanupCodebase(repo: string): Promise<void> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      logger.info(`Cleaning up Milvus data for codebase: ${repo}`);
      
      const deleteParams = {
        collection_name: 'codex7_chunks',
        filter: `repo == "${repo}"`,
      };

      const result = await this.client.delete(deleteParams);
      logger.info(`Successfully cleaned up Milvus data for codebase: ${repo}, deleted ${result.delete_cnt} records`);
    } catch (error) {
      logger.error(`Error cleaning up Milvus data for codebase ${repo}:`, error);
    }
  }

  /**
   * Get repository statistics from Milvus
   */
  async getRepositoryStats(repo: string): Promise<number> {
    if (!this.isConnected) {
      await this.connect();
    }

    try {
      const searchParams = {
        collection_name: 'codex7_chunks',
        filter: `repo == "${repo}"`,
        output_fields: ['id'],
        limit: 0, // Just get count
      };

      const results = await this.client.query(searchParams);
      return results.data.length;
    } catch (error) {
      logger.error(`Error getting repository stats for ${repo}:`, error);
      return 0;
    }
  }
} 