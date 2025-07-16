import { SearchQuery, SearchResult } from '../types/index.js';
import { logger } from '../utils/logger.js';

export interface BM25Config {
  k1: number; // Controls term frequency normalization (typical: 1.2-2.0)
  b: number;  // Controls length normalization (typical: 0.75)
  epsilon: number; // Floor value for IDF (typical: 0.25)
}

export interface DocumentData {
  id: string;
  content: string;
  repo: string;
  path: string;
  chunkType: 'doc' | 'code';
  language?: string;
  startLine?: number;
  endLine?: number;
  metadata: any;
}

export class BM25Search {
  private documents: DocumentData[] = [];
  private termFreq: Map<string, Map<string, number>> = new Map(); // term -> docId -> freq
  private docFreq: Map<string, number> = new Map(); // term -> document frequency
  private docLengths: Map<string, number> = new Map(); // docId -> length
  private avgDocLength: number = 0;
  private config: BM25Config;
  private isIndexed: boolean = false;

  constructor(config: Partial<BM25Config> = {}) {
    this.config = {
      k1: config.k1 || 1.2,
      b: config.b || 0.75,
      epsilon: config.epsilon || 0.25,
    };
    
    logger.info('BM25Search initialized with config:', this.config);
  }

  /**
   * Add documents to the search index
   */
  public addDocuments(documents: DocumentData[]): void {
    this.documents = [...this.documents, ...documents];
    this.isIndexed = false;
    logger.info(`Added ${documents.length} documents to BM25 index`);
  }

  /**
   * Clear all documents and rebuild index
   */
  public setDocuments(documents: DocumentData[]): void {
    this.documents = documents;
    this.isIndexed = false;
    logger.info(`Set ${documents.length} documents in BM25 index`);
  }

  /**
   * Build the search index
   */
  public buildIndex(): void {
    if (this.isIndexed) {
      return;
    }

    logger.info(`Building BM25 index for ${this.documents.length} documents`);
    
    // Clear existing index
    this.termFreq.clear();
    this.docFreq.clear();
    this.docLengths.clear();

    // Process each document
    let totalLength = 0;
    for (const doc of this.documents) {
      const tokens = this.tokenize(doc.content);
      this.docLengths.set(doc.id, tokens.length);
      totalLength += tokens.length;

      // Count term frequencies in this document
      const termCounts = new Map<string, number>();
      for (const token of tokens) {
        termCounts.set(token, (termCounts.get(token) || 0) + 1);
      }

      // Update global term frequency and document frequency
      for (const [term, count] of termCounts) {
        // Update term frequency for this document
        if (!this.termFreq.has(term)) {
          this.termFreq.set(term, new Map());
        }
        this.termFreq.get(term)!.set(doc.id, count);

        // Update document frequency for this term
        this.docFreq.set(term, (this.docFreq.get(term) || 0) + 1);
      }
    }

    // Calculate average document length
    this.avgDocLength = this.documents.length > 0 ? totalLength / this.documents.length : 0;
    this.isIndexed = true;
    
    logger.info(`BM25 index built successfully. Terms: ${this.termFreq.size}, Avg doc length: ${this.avgDocLength.toFixed(2)}`);
  }

  /**
   * Search documents using BM25 algorithm
   */
  public search(query: SearchQuery, topK: number = 10): SearchResult[] {
    if (!this.isIndexed) {
      this.buildIndex();
    }

    const queryTerms = this.tokenize(query.query);
    if (queryTerms.length === 0) {
      return [];
    }

    const scores = new Map<string, number>();

    // Calculate BM25 score for each document
    for (const doc of this.documents) {
      // Apply filters
      if (!this.matchesFilters(doc, query)) {
        continue;
      }

      let score = 0;
      const docLength = this.docLengths.get(doc.id) || 0;

      for (const term of queryTerms) {
        const termFreqInDoc = this.termFreq.get(term)?.get(doc.id) || 0;
        if (termFreqInDoc === 0) {
          continue;
        }

        const docFreqForTerm = this.docFreq.get(term) || 0;
        const idf = this.calculateIDF(docFreqForTerm);
        const tf = this.calculateTF(termFreqInDoc, docLength);
        
        score += idf * tf;
      }

      if (score > 0) {
        scores.set(doc.id, score);
      }
    }

    // Sort by score and return top K results
    const sortedResults = Array.from(scores.entries())
      .sort(([, scoreA], [, scoreB]) => scoreB - scoreA)
      .slice(0, topK);

    const results: SearchResult[] = sortedResults.map(([docId, score]) => {
      const doc = this.documents.find(d => d.id === docId)!;
      const result: SearchResult = {
        id: doc.id,
        repo: doc.repo,
        path: doc.path,
        content: doc.content,
        score,
        chunkType: doc.chunkType,
        metadata: doc.metadata,
      };
      
      if (doc.language) {
        result.language = doc.language;
      }
      if (doc.startLine !== undefined) {
        result.startLine = doc.startLine;
      }
      if (doc.endLine !== undefined) {
        result.endLine = doc.endLine;
      }
      
      return result;
    });

    logger.debug(`BM25 search for "${query.query}" returned ${results.length} results`);
    return results;
  }

  /**
   * Calculate Inverse Document Frequency (IDF)
   */
  private calculateIDF(docFreq: number): number {
    const N = this.documents.length;
    return Math.log((N - docFreq + 0.5) / (docFreq + 0.5) + this.config.epsilon);
  }

  /**
   * Calculate Term Frequency (TF) with normalization
   */
  private calculateTF(termFreq: number, docLength: number): number {
    const { k1, b } = this.config;
    const norm = 1 - b + b * (docLength / this.avgDocLength);
    return (termFreq * (k1 + 1)) / (termFreq + k1 * norm);
  }

  /**
   * Tokenize text into searchable terms
   */
  private tokenize(text: string): string[] {
    // Enhanced tokenization for code and documentation
    return text
      .toLowerCase()
      // Split on whitespace and common punctuation
      .split(/[\s\n\r\t.,;:!?()[\]{}"'`~@#$%^&*+=|\\/<>]+/)
      // Split camelCase and snake_case
      .flatMap(token => {
        if (token.length <= 1) return [];
        
        // Split camelCase: getUser -> ['get', 'user']
        const camelSplit = token.split(/(?=[A-Z])/).filter(Boolean);
        
        // Split snake_case and kebab-case
        const snakeSplit = token.split(/[_-]/).filter(Boolean);
        
        // Return all variants
        const variants = [token, ...camelSplit, ...snakeSplit];
        return [...new Set(variants)].filter(t => t.length > 1);
      })
      // Remove common stop words and very short tokens
      .filter(token => 
        token.length > 1 && 
        !this.isStopWord(token) &&
        /[a-zA-Z0-9]/.test(token) // Contains at least one alphanumeric character
      );
  }

  /**
   * Check if a token is a stop word
   */
  private isStopWord(token: string): boolean {
    const stopWords = new Set([
      'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
      'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
      'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
      'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
      'my', 'your', 'his', 'her', 'its', 'our', 'their',
      'if', 'then', 'else', 'when', 'where', 'why', 'how', 'what', 'which', 'who', 'whom',
      'from', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then', 'once'
    ]);
    return stopWords.has(token);
  }

  /**
   * Check if document matches query filters
   */
  private matchesFilters(doc: DocumentData, query: SearchQuery): boolean {
    if (query.language && doc.language !== query.language) {
      return false;
    }

    if (query.repo && doc.repo !== query.repo) {
      return false;
    }

    if (query.chunkType && query.chunkType !== 'both' && doc.chunkType !== query.chunkType) {
      return false;
    }

    return true;
  }

  /**
   * Get index statistics
   */
  public getStats(): {
    documentsCount: number;
    termsCount: number;
    avgDocLength: number;
    isIndexed: boolean;
  } {
    return {
      documentsCount: this.documents.length,
      termsCount: this.termFreq.size,
      avgDocLength: this.avgDocLength,
      isIndexed: this.isIndexed,
    };
  }

  /**
   * Clear the index
   */
  public clear(): void {
    this.documents = [];
    this.termFreq.clear();
    this.docFreq.clear();
    this.docLengths.clear();
    this.avgDocLength = 0;
    this.isIndexed = false;
    logger.info('BM25 index cleared');
  }
} 