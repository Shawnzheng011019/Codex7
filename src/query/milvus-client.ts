import { MilvusClient, MetricType } from '@zilliz/milvus2-sdk-node';
import { SearchQuery, SearchResult, VectorMetadata } from '../types/index.js';
import { config } from '../utils/config.js';
import { logger } from '../utils/logger.js';

export class MilvusQueryClient {
  private client: MilvusClient;
  private isConnected = false;

  constructor() {
    const clientConfig: any = {
      address: `${config.milvus.host}:${config.milvus.port}`,
      database: config.milvus.database,
    };
    
    if (config.milvus.user) {
      clientConfig.username = config.milvus.user;
    }
    
    if (config.milvus.password) {
      clientConfig.password = config.milvus.password;
    }
    
    this.client = new MilvusClient(clientConfig);
  }

  async connect(): Promise<void> {
    try {
      // Test connection
      await this.client.checkHealth();
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
        starCount: result.star_count,
        lastCommitDate: result.last_commit_date,
        textHash: result.text_hash,
        tokenCount: result.token_count,
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
        starCount: result.star_count,
        lastCommitDate: result.last_commit_date,
        textHash: result.text_hash,
        tokenCount: result.token_count,
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
} 