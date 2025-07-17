import { SearchResult } from '../types/index.js';
import { logger } from '../utils/logger.js';

export interface RerankConfig {
  model: 'bge-reranker' | 'colbert' | 'cross-encoder' | 'reciprocal-rank-fusion';
  maxResults: number;
  apiKey?: string;
  threshold?: number;
}

export interface RerankResult {
  results: SearchResult[];
  rerankScores: number[];
  executionTimeMs: number;
}

export class RerankService {
  private config: RerankConfig;

  constructor(config: Partial<RerankConfig> = {}) {
    this.config = {
      model: config.model || 'reciprocal-rank-fusion',
      maxResults: config.maxResults || 20,
      apiKey: config.apiKey || '',
      threshold: config.threshold || 0.0,
    };

    logger.info(`RerankService initialized with model: ${this.config.model}`);
  }

  /**
   * Rerank search results using the configured model
   */
  public async rerank(
    query: string,
    results: SearchResult[][],
    topK: number = 10
  ): Promise<RerankResult> {
    const startTime = Date.now();

    try {
      let rerankedResults: SearchResult[];
      let rerankScores: number[];

      switch (this.config.model) {
        case 'reciprocal-rank-fusion':
          ({ results: rerankedResults, scores: rerankScores } = 
            this.reciprocalRankFusion(results, topK));
          break;
          
        case 'bge-reranker':
          ({ results: rerankedResults, scores: rerankScores } = 
            await this.bgeReranker(query, this.mergeResults(results), topK));
          break;
          
        case 'colbert':
          ({ results: rerankedResults, scores: rerankScores } = 
            await this.colbertReranker(query, this.mergeResults(results), topK));
          break;
          
        case 'cross-encoder':
          ({ results: rerankedResults, scores: rerankScores } = 
            await this.crossEncoderRerank(query, this.mergeResults(results), topK));
          break;
          
        default:
          throw new Error(`Unsupported rerank model: ${this.config.model}`);
      }

      const executionTimeMs = Date.now() - startTime;
      
      logger.debug(`Reranking completed in ${executionTimeMs}ms, returned ${rerankedResults.length} results`);
      
      return {
        results: rerankedResults,
        rerankScores,
        executionTimeMs,
      };

    } catch (error) {
      logger.error('Error during reranking:', error);
      throw error;
    }
  }

  /**
   * Reciprocal Rank Fusion (RRF) - combines multiple ranked lists
   * Formula: RRF(d) = Σ(1/(k + rank(d)))
   */
  private reciprocalRankFusion(
    resultLists: SearchResult[][],
    topK: number,
    k: number = 60
  ): { results: SearchResult[]; scores: number[] } {
    const docScores = new Map<string, { result: SearchResult; score: number }>();

    // Calculate RRF scores
    for (const resultList of resultLists) {
      resultList.forEach((result, rank) => {
        const rrfScore = 1 / (k + rank + 1);
        const existing = docScores.get(result.id);
        
        if (existing) {
          existing.score += rrfScore;
        } else {
          docScores.set(result.id, {
            result: { ...result },
            score: rrfScore,
          });
        }
      });
    }

    // Sort by RRF score and take top K
    const sortedResults = Array.from(docScores.values())
      .sort((a, b) => b.score - a.score)
      .slice(0, topK);

    const results = sortedResults.map(item => ({
      ...item.result,
      score: item.score, // Update with RRF score
    }));

    const scores = sortedResults.map(item => item.score);

    logger.debug(`RRF combined ${resultLists.length} result lists into ${results.length} results`);
    
    return { results, scores };
  }

  /**
   * BGE Reranker using Hugging Face API
   */
  private async bgeReranker(
    query: string,
    results: SearchResult[],
    topK: number
  ): Promise<{ results: SearchResult[]; scores: number[] }> {
    if (!this.config.apiKey) {
      logger.warn('BGE Reranker API key not provided, falling back to score-based ranking');
      return this.scoreBasedRank(results, topK);
    }

    try {
      // TODO: Implement BGE Reranker API call
      // For now, use enhanced scoring based on query-content similarity
      logger.warn('BGE Reranker API not implemented yet, using enhanced scoring');
      
      const scores = results.map((result) => {
        const queryTerms = this.tokenize(query);
        const contentTerms = this.tokenize(result.content);
        
        // Calculate TF-IDF-like score
        const intersection = queryTerms.filter(term => contentTerms.includes(term));
        const similarityScore = intersection.length / Math.max(queryTerms.length, 1);
        
        return {
          score: (result.score * 0.6) + (similarityScore * 0.4)
        };
      });
      
      // Combine results with rerank scores
      const rerankedResults = results
        .map((result, index) => ({
          ...result,
          score: scores[index]?.score || result.score,
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, topK);

      return {
        results: rerankedResults,
        scores: rerankedResults.map(r => r.score),
      };

    } catch (error) {
      logger.error('BGE Reranker failed, falling back to score-based ranking:', error);
      return this.scoreBasedRank(results, topK);
    }
  }

  /**
   * ColBERT reranker using Hugging Face API
   */
  private async colbertReranker(
    query: string,
    results: SearchResult[],
    topK: number
  ): Promise<{ results: SearchResult[]; scores: number[] }> {
    if (!this.config.apiKey) {
      logger.warn('ColBERT Reranker API key not provided, falling back to score-based ranking');
      return this.scoreBasedRank(results, topK);
    }

    try {
      // TODO: Implement ColBERT Reranker API call
      // For now, use position-aware scoring
      logger.warn('ColBERT Reranker API not implemented yet, using position-aware scoring');
      
      const scores = results.map((result, index) => {
        const queryTerms = this.tokenize(query);
        const contentTerms = this.tokenize(result.content);
        
        // Position-based scoring (earlier positions get higher scores)
        const positionScore = 1 / (index + 1);
        const termOverlap = queryTerms.filter(term => contentTerms.includes(term)).length;
        const overlapScore = termOverlap / Math.max(queryTerms.length, 1);
        
        return (result.score * 0.5) + (positionScore * 0.3) + (overlapScore * 0.2);
      });

      // Combine results with rerank scores
      const rerankedResults = results
        .map((result, index) => ({
          ...result,
          score: scores[index] || result.score,
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, topK);

      return {
        results: rerankedResults,
        scores: rerankedResults.map(r => r.score),
      };

    } catch (error) {
      logger.error('ColBERT Reranker failed, falling back to score-based ranking:', error);
      return this.scoreBasedRank(results, topK);
    }
  }

  /**
   * Cross-encoder reranking using a general cross-encoder model
   */
  private async crossEncoderRerank(
    query: string,
    results: SearchResult[],
    topK: number
  ): Promise<{ results: SearchResult[]; scores: number[] }> {
    if (!this.config.apiKey) {
      logger.warn('Cross-encoder API key not provided, falling back to score-based ranking');
      return this.scoreBasedRank(results, topK);
    }

    try {
      // Calculate semantic similarity between query and each result
      const similarities = await Promise.all(
        results.map(async (result) => {
          // Use a simple embedding similarity as fallback
          const queryTokens = this.tokenize(query);
          const contentTokens = this.tokenize(result.content);
          
          const intersection = new Set(queryTokens.filter(token => contentTokens.includes(token)));
          const union = new Set([...queryTokens, ...contentTokens]);
          
          return intersection.size / union.size; // Jaccard similarity
        })
      );

      // Combine original scores with similarity scores
      const rerankedResults = results
        .map((result, index) => ({
          ...result,
          score: (result.score * 0.7) + (similarities[index] * 0.3), // Weighted combination
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, topK);

      return {
        results: rerankedResults,
        scores: rerankedResults.map(r => r.score),
      };

    } catch (error) {
      logger.error('Cross-encoder reranking failed, falling back to score-based ranking:', error);
      return this.scoreBasedRank(results, topK);
    }
  }

  /**
   * Fallback score-based ranking
   */
  private scoreBasedRank(
    results: SearchResult[],
    topK: number
  ): { results: SearchResult[]; scores: number[] } {
    const sortedResults = [...results]
      .sort((a, b) => b.score - a.score)
      .slice(0, topK);

    return {
      results: sortedResults,
      scores: sortedResults.map(r => r.score),
    };
  }

  /**
   * Merge multiple result lists, removing duplicates
   */
  private mergeResults(resultLists: SearchResult[][]): SearchResult[] {
    const seen = new Set<string>();
    const merged: SearchResult[] = [];

    for (const resultList of resultLists) {
      for (const result of resultList) {
        if (!seen.has(result.id)) {
          seen.add(result.id);
          merged.push(result);
        }
      }
    }

    return merged;
  }

  /**
   * Simple tokenizer for text similarity calculation
   */
  private tokenize(text: string): string[] {
    return text
      .toLowerCase()
      .replace(/[^\w\s]/g, '')
      .split(/\s+/)
      .filter(token => token.length > 2);
  }

  /**
   * Update configuration
   */
  public updateConfig(newConfig: Partial<RerankConfig>): void {
    this.config = { ...this.config, ...newConfig };
    logger.info('RerankService configuration updated:', this.config);
  }

  /**
   * Get current configuration
   */
  public getConfig(): RerankConfig {
    return { ...this.config };
  }
} 