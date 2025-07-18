/**
 * Embedding Service
 * 
 * Generates embeddings using various models for different types of content.
 * Supports OpenAI embeddings, Hugging Face models, and local models.
 */

import { logger } from '../utils/logger.js';
import { TextChunk, EmbeddingVector } from '../types/index.js';

export interface EmbeddingConfig {
  provider: 'openai' | 'huggingface' | 'local';
  model: string;
  apiKey?: string;
  baseUrl?: string;
  maxTokens?: number;
  batchSize?: number;
}

export interface EmbeddingResponse {
  embedding: number[];
  tokenCount?: number;
}

export class EmbeddingService {
  private config: EmbeddingConfig;

  constructor(config: EmbeddingConfig) {
    this.config = {
      maxTokens: 8192,
      batchSize: 100,
      ...config
    };
  }

  async generateEmbeddings(chunks: TextChunk[]): Promise<EmbeddingVector[]> {
    logger.info(`Generating embeddings for ${chunks.length} chunks using ${this.config.provider}/${this.config.model}`);

    const vectors: EmbeddingVector[] = [];
    const batchSize = this.config.batchSize!;

    // Process in batches to avoid rate limits
    for (let i = 0; i < chunks.length; i += batchSize) {
      const batch = chunks.slice(i, i + batchSize);
      
      try {
        const batchVectors = await this.processBatch(batch);
        vectors.push(...batchVectors);
        
        logger.info(`Processed batch ${Math.floor(i / batchSize) + 1}/${Math.ceil(chunks.length / batchSize)}`);
        
        // Add delay to respect rate limits
        if (this.config.provider === 'openai' && i + batchSize < chunks.length) {
          await this.delay(100); // 100ms delay between batches
        }
      } catch (error) {
        logger.error(`Error processing batch ${i}-${i + batch.length}: ${error}`);
        // Continue with next batch instead of failing completely
      }
    }

    logger.info(`Successfully generated ${vectors.length}/${chunks.length} embeddings`);
    return vectors;
  }

  private async processBatch(chunks: TextChunk[]): Promise<EmbeddingVector[]> {
    const vectors: EmbeddingVector[] = [];

    for (const chunk of chunks) {
      try {
        const embedding = await this.generateSingleEmbedding(chunk.content);
        
                 vectors.push({
           id: chunk.id,
           vector: embedding.embedding,
           metadata: {
             repo: chunk.repo,
             path: chunk.path,
             chunkType: chunk.chunkType as any,
             language: chunk.language,
             startLine: chunk.startLine,
             endLine: chunk.endLine,
             chunkIndex: chunk.chunkIndex,
             contentLength: chunk.content.length,
             tokenCount: embedding.tokenCount || 0
           }
         });
      } catch (error) {
        logger.error(`Error generating embedding for chunk ${chunk.id}: ${error}`);
      }
    }

    return vectors;
  }

  private async generateSingleEmbedding(text: string): Promise<EmbeddingResponse> {
    // Truncate text if it exceeds max tokens (rough estimate: 1 token ≈ 4 characters)
    const estimatedTokens = Math.ceil(text.length / 4);
    if (estimatedTokens > this.config.maxTokens!) {
      const maxChars = this.config.maxTokens! * 4;
      text = text.substring(0, maxChars);
      logger.debug(`Truncated text to ${maxChars} characters`);
    }

    switch (this.config.provider) {
      case 'openai':
        return this.generateOpenAIEmbedding(text);
      case 'huggingface':
        return this.generateHuggingFaceEmbedding(text);
      case 'local':
        return this.generateLocalEmbedding(text);
      default:
        throw new Error(`Unsupported embedding provider: ${this.config.provider}`);
    }
  }

  private async generateOpenAIEmbedding(text: string): Promise<EmbeddingResponse> {
    if (!this.config.apiKey) {
      throw new Error('OpenAI API key is required');
    }

    const response = await fetch('https://api.openai.com/v1/embeddings', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.config.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: this.config.model,
        input: text,
        encoding_format: 'float'
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`OpenAI API error: ${response.status} ${error}`);
    }

    const data = await response.json() as any;
    
    return {
      embedding: data.data[0].embedding,
      tokenCount: data.usage.total_tokens
    };
  }

  private async generateHuggingFaceEmbedding(text: string): Promise<EmbeddingResponse> {
    if (!this.config.apiKey) {
      throw new Error('Hugging Face API key is required');
    }

    const response = await fetch(
      `https://api-inference.huggingface.co/pipeline/feature-extraction/${this.config.model}`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.config.apiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          inputs: text,
          options: { wait_for_model: true }
        })
      }
    );

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Hugging Face API error: ${response.status} ${error}`);
    }

    const embedding = await response.json() as any;
    
    return {
      embedding: Array.isArray(embedding[0]) ? embedding[0] : embedding,
      tokenCount: Math.ceil(text.length / 4) // Estimate
    };
  }

  private async generateLocalEmbedding(text: string): Promise<EmbeddingResponse> {
    // Placeholder for local embedding generation
    // In a real implementation, this would call a local model service
    logger.debug('Generating local embedding (mock implementation)');
    
    // Generate a deterministic but pseudo-random embedding based on text content
    const embedding = this.generateMockEmbedding(text);
    
    return {
      embedding,
      tokenCount: Math.ceil(text.length / 4)
    };
  }

  private generateMockEmbedding(text: string): number[] {
    // Generate a consistent embedding based on text content
    // This is for development/testing purposes only
    const hash = this.simpleHash(text);
    const dimension = 1536; // OpenAI ada-002 dimension
    const embedding: number[] = [];
    
    for (let i = 0; i < dimension; i++) {
      // Use hash to seed pseudo-random generation
      const seed = (hash + i) * 2654435761;
      const value = ((seed % 1000000) / 1000000) * 2 - 1; // Range [-1, 1]
      embedding.push(value);
    }
    
    // Normalize the vector
    const magnitude = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
    return embedding.map(val => val / magnitude);
  }

  private simpleHash(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash);
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Method to estimate costs for different providers
  estimateCost(chunks: TextChunk[]): { totalTokens: number; estimatedCost: number } {
    const totalTokens = chunks.reduce((sum, chunk) => {
      return sum + Math.ceil(chunk.content.length / 4);
    }, 0);

    let costPerMToken = 0;
    
    switch (this.config.provider) {
      case 'openai':
        switch (this.config.model) {
          case 'text-embedding-3-small':
            costPerMToken = 0.02; // $0.02 per 1M tokens
            break;
          case 'text-embedding-3-large':
            costPerMToken = 0.13; // $0.13 per 1M tokens
            break;
          case 'text-embedding-ada-002':
            costPerMToken = 0.1; // $0.10 per 1M tokens
            break;
          default:
            costPerMToken = 0.1;
        }
        break;
      case 'huggingface':
        costPerMToken = 0.0; // Often free for inference API
        break;
      case 'local':
        costPerMToken = 0.0; // No cost for local models
        break;
    }

    const estimatedCost = (totalTokens / 1000000) * costPerMToken;

    return { totalTokens, estimatedCost };
  }

  // Method to validate embedding configuration
  async validateConfig(): Promise<boolean> {
    try {
      const testText = "This is a test for embedding configuration validation.";
      await this.generateSingleEmbedding(testText);
      logger.info(`Embedding service validation successful for ${this.config.provider}/${this.config.model}`);
      return true;
    } catch (error) {
      logger.error(`Embedding service validation failed: ${error}`);
      return false;
    }
  }

  // Get supported models for each provider
  static getSupportedModels(): Record<string, string[]> {
    return {
      openai: [
        'text-embedding-3-small',
        'text-embedding-3-large',
        'text-embedding-ada-002'
      ],
      huggingface: [
        'sentence-transformers/all-MiniLM-L6-v2',
        'sentence-transformers/all-mpnet-base-v2',
        'BAAI/bge-large-en-v1.5',
        'jinaai/jina-embeddings-v2-base-en'
      ],
      local: [
        'custom-local-model'
      ]
    };
  }
} 