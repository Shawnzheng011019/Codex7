import { SearchQuery, SearchResult, HybridSearchResult } from '../types/index.js';
import { MilvusQueryClient } from '../query/milvus-client.js';
import { BM25Search, DocumentData } from './bm25-search.js';
import { RerankService, RerankConfig } from './rerank-service.js';
import { logger } from '../utils/logger.js';

export interface HybridSearchConfig {
  // Search weights
  vectorWeight: number;     // Weight for vector search results
  bm25Weight: number;       // Weight for BM25 search results
  
  // Search parameters
  vectorTopK: number;       // Number of results from vector search
  bm25TopK: number;         // Number of results from BM25 search
  finalTopK: number;        // Final number of results to return
  
  // Reranking configuration
  useReranking: boolean;
  rerankConfig: Partial<RerankConfig>;
  
  // Performance settings
  enableCaching: boolean;
  cacheSize: number;
  searchTimeoutMs: number;
}

export interface SearchMetrics {
  totalTime: number;
  vectorSearchTime: number;
  bm25SearchTime: number;
  rerankTime: number;
  resultsCombined: number;
  finalResults: number;
}

export class HybridSearchService {
  private milvusClient: MilvusQueryClient;
  private bm25Search: BM25Search;
  private rerankService: RerankService;
  private config: HybridSearchConfig;
  private isInitialized: boolean = false;
  
  // Result cache for performance
  private resultCache = new Map<string, { result: HybridSearchResult; timestamp: number }>();

  constructor(config: Partial<HybridSearchConfig> = {}) {
    this.config = {
      vectorWeight: config.vectorWeight || 0.6,
      bm25Weight: config.bm25Weight || 0.4,
      vectorTopK: config.vectorTopK || 50,
      bm25TopK: config.bm25TopK || 50,
      finalTopK: config.finalTopK || 20,
      useReranking: config.useReranking !== false,
      rerankConfig: config.rerankConfig || { model: 'reciprocal-rank-fusion' },
      enableCaching: config.enableCaching !== false,
      cacheSize: config.cacheSize || 100,
      searchTimeoutMs: config.searchTimeoutMs || 10000,
    };

    this.milvusClient = new MilvusQueryClient();
    this.bm25Search = new BM25Search();
    this.rerankService = new RerankService(this.config.rerankConfig);

    logger.info('HybridSearchService initialized with config:', this.config);
  }

  /**
   * Initialize the hybrid search service
   */
  public async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }

    try {
      logger.info('Initializing HybridSearchService...');
      
      // Initialize Milvus connection
      await this.milvusClient.connect();
      
      // Load documents for BM25 indexing
      await this.loadDocumentsForBM25();
      
      this.isInitialized = true;
      logger.info('HybridSearchService initialized successfully');
      
    } catch (error) {
      logger.error('Failed to initialize HybridSearchService:', error);
      throw error;
    }
  }

  /**
   * Perform hybrid search combining vector search, BM25, and reranking
   */
  public async search(query: SearchQuery): Promise<HybridSearchResult> {
    if (!this.isInitialized) {
      await this.initialize();
    }

    const startTime = Date.now();
    const cacheKey = this.getCacheKey(query);

    // Check cache first
    if (this.config.enableCaching) {
      const cached = this.getCachedResult(cacheKey);
      if (cached) {
        logger.debug('Returning cached hybrid search result');
        return cached;
      }
    }

    try {
      const metrics: SearchMetrics = {
        totalTime: 0,
        vectorSearchTime: 0,
        bm25SearchTime: 0,
        rerankTime: 0,
        resultsCombined: 0,
        finalResults: 0,
      };

      // Step 1: Vector Search
      const vectorStartTime = Date.now();
      const embeddingResults = await this.performVectorSearch(query);
      metrics.vectorSearchTime = Date.now() - vectorStartTime;
      
      // Step 2: BM25 Search
      const bm25StartTime = Date.now();
      const bm25Results = await this.performBM25Search(query);
      metrics.bm25SearchTime = Date.now() - bm25StartTime;

      // Step 3: Combine Results
      const combinedResults = this.combineResults(embeddingResults, bm25Results);
      metrics.resultsCombined = combinedResults.length;

      // Step 4: Reranking (if enabled)
      let finalResults: SearchResult[] = combinedResults;
      let rerankedResults: SearchResult[] = [];
      
      if (this.config.useReranking) {
        const rerankStartTime = Date.now();
        const rerankResult = await this.rerankService.rerank(
          query.query,
          [embeddingResults, bm25Results],
          this.config.finalTopK
        );
        rerankedResults = rerankResult.results;
        finalResults = rerankedResults;
        metrics.rerankTime = Date.now() - rerankStartTime;
      } else {
        // Simple score-based ranking without reranking
        finalResults = combinedResults
          .sort((a, b) => b.score - a.score)
          .slice(0, this.config.finalTopK);
      }

      metrics.finalResults = finalResults.length;
      metrics.totalTime = Date.now() - startTime;

      const result: HybridSearchResult = {
        embeddingResults,
        bm25Results,
        rerankedResults,
        finalResults,
      };

      // Cache the result
      if (this.config.enableCaching) {
        this.setCachedResult(cacheKey, result);
      }

      logger.debug('Hybrid search completed:', {
        query: query.query,
        metrics,
        vectorResults: embeddingResults.length,
        bm25Results: bm25Results.length,
        finalResults: finalResults.length,
      });

      return result;

    } catch (error) {
      logger.error('Hybrid search failed:', error);
      throw error;
    }
  }

  /**
   * Perform vector search using Milvus
   */
  private async performVectorSearch(query: SearchQuery): Promise<SearchResult[]> {
    try {
      // Use text-based search as fallback since we don't have embedding generation here
      const results = await this.milvusClient.searchByText(query, this.config.vectorTopK);
      
      logger.debug(`Vector search returned ${results.length} results`);
      return results;
      
    } catch (error) {
      logger.warn('Vector search failed, returning empty results:', error);
      return [];
    }
  }

  /**
   * Perform BM25 search
   */
  private async performBM25Search(query: SearchQuery): Promise<SearchResult[]> {
    try {
      const results = this.bm25Search.search(query, this.config.bm25TopK);
      
      logger.debug(`BM25 search returned ${results.length} results`);
      return results;
      
    } catch (error) {
      logger.warn('BM25 search failed, returning empty results:', error);
      return [];
    }
  }

  /**
   * Combine vector and BM25 results with weighted scoring
   */
  private combineResults(
    vectorResults: SearchResult[],
    bm25Results: SearchResult[]
  ): SearchResult[] {
    const combinedScores = new Map<string, { result: SearchResult; score: number }>();

    // Add vector results with weight
    vectorResults.forEach((result) => {
      const weightedScore = result.score * this.config.vectorWeight;
      combinedScores.set(result.id, {
        result: { ...result },
        score: weightedScore,
      });
    });

    // Add BM25 results with weight (merge if already exists)
    bm25Results.forEach((result) => {
      const weightedScore = result.score * this.config.bm25Weight;
      const existing = combinedScores.get(result.id);
      
      if (existing) {
        // Combine scores if result exists in both
        existing.score += weightedScore;
      } else {
        combinedScores.set(result.id, {
          result: { ...result },
          score: weightedScore,
        });
      }
    });

    // Convert back to SearchResult array with combined scores
    const combined = Array.from(combinedScores.values())
      .map(item => ({
        ...item.result,
        score: item.score,
      }))
      .sort((a, b) => b.score - a.score);

    logger.debug(`Combined ${vectorResults.length} vector + ${bm25Results.length} BM25 results into ${combined.length} unique results`);
    
    return combined;
  }

  /**
   * Load documents from Milvus for BM25 indexing
   */
  private async loadDocumentsForBM25(): Promise<void> {
    try {
      logger.info('Loading documents for BM25 indexing...');
      
      // Get all documents from Milvus (this is a simplified approach)
      // In a real implementation, you'd want to load from a dedicated document store
      const allDocs = await this.milvusClient.getRepositoryFiles('all_repos'); // Get all
      
      // Convert to BM25 document format
      const bm25Documents: DocumentData[] = allDocs.map(doc => {
        const document: DocumentData = {
          id: doc.id,
          content: doc.content,
          repo: doc.repo,
          path: doc.path,
          chunkType: doc.chunkType,
          metadata: doc.metadata,
        };
        
        if (doc.language) {
          document.language = doc.language;
        }
        if (doc.startLine !== undefined) {
          document.startLine = doc.startLine;
        }
        if (doc.endLine !== undefined) {
          document.endLine = doc.endLine;
        }
        
        return document;
      });

      // Set documents in BM25 index
      this.bm25Search.setDocuments(bm25Documents);
      
      logger.info(`Loaded ${bm25Documents.length} documents for BM25 indexing`);
      
    } catch (error) {
      logger.warn('Failed to load documents for BM25, continuing without BM25 search:', error);
    }
  }

  /**
   * Generate cache key for query
   */
  private getCacheKey(query: SearchQuery): string {
    return JSON.stringify({
      query: query.query,
      language: query.language,
      repo: query.repo,
      chunkType: query.chunkType,
      topK: query.topK,
    });
  }

  /**
   * Get cached result if valid
   */
  private getCachedResult(cacheKey: string): HybridSearchResult | null {
    const cached = this.resultCache.get(cacheKey);
    if (!cached) {
      return null;
    }

    // Check if cache is still valid (5 minutes)
    const cacheAge = Date.now() - cached.timestamp;
    if (cacheAge > 5 * 60 * 1000) {
      this.resultCache.delete(cacheKey);
      return null;
    }

    return cached.result;
  }

  /**
   * Cache search result
   */
  private setCachedResult(cacheKey: string, result: HybridSearchResult): void {
    // Clean old cache entries if at capacity
    if (this.resultCache.size >= this.config.cacheSize) {
      const firstKey = this.resultCache.keys().next();
      if (firstKey.value) {
        this.resultCache.delete(firstKey.value);
      }
    }

    this.resultCache.set(cacheKey, {
      result: { ...result },
      timestamp: Date.now(),
    });
  }

  /**
   * Update search configuration
   */
  public updateConfig(newConfig: Partial<HybridSearchConfig>): void {
    this.config = { ...this.config, ...newConfig };
    
    // Update sub-service configurations
    if (newConfig.rerankConfig) {
      this.rerankService.updateConfig(newConfig.rerankConfig);
    }
    
    logger.info('HybridSearchService configuration updated');
  }

  /**
   * Get search statistics
   */
  public getStats(): {
    isInitialized: boolean;
    cacheSize: number;
    bm25Stats: any;
    config: HybridSearchConfig;
  } {
    return {
      isInitialized: this.isInitialized,
      cacheSize: this.resultCache.size,
      bm25Stats: this.bm25Search.getStats(),
      config: { ...this.config },
    };
  }

  /**
   * Clear all caches
   */
  public clearCache(): void {
    this.resultCache.clear();
    logger.info('HybridSearchService cache cleared');
  }

  /**
   * Shutdown the service
   */
  public async shutdown(): Promise<void> {
    try {
      await this.milvusClient.disconnect();
      this.clearCache();
      this.isInitialized = false;
      logger.info('HybridSearchService shutdown completed');
    } catch (error) {
      logger.error('Error during HybridSearchService shutdown:', error);
    }
  }
} 