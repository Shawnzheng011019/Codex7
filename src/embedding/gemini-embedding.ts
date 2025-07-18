import axios from 'axios';
import { logger } from '../utils/logger.js';

export interface GeminiEmbeddingConfig {
    model: string;
    apiKey: string;
    timeout?: number;
}

export interface GeminiEmbeddingVector {
    vector: number[];
    dimension: number;
}

export class GeminiEmbedding {
    private config: GeminiEmbeddingConfig;
    private dimension: number = 768; // Default dimension for text-embedding-004
    private baseUrl: string = 'https://generativelanguage.googleapis.com/v1beta';
    protected maxTokens: number = 2048; // Default max tokens

    constructor(config: GeminiEmbeddingConfig) {
        this.config = {
            timeout: 30000, // 30 seconds default timeout
            ...config
        };

        // Set dimension based on model
        this.updateModelSettings(config.model || 'text-embedding-004');
        
        logger.info(`Initialized Gemini embedding with model: ${this.config.model}`);
    }

    private updateModelSettings(model: string): void {
        const supportedModels = GeminiEmbedding.getSupportedModels();
        const modelInfo = supportedModels[model];

        if (modelInfo) {
            this.dimension = modelInfo.dimension;
            this.maxTokens = modelInfo.maxTokens;
        } else {
            // Use default dimension and context length for unknown models
            this.dimension = 768;
            this.maxTokens = 2048;
        }
    }

    private preprocessText(text: string): string {
        // Remove excessive whitespace and normalize
        let processed = text.replace(/\s+/g, ' ').trim();
        
        // Truncate if too long (rough estimate based on tokens)
        const maxLength = this.maxTokens * 4; // Rough estimate: 1 token ≈ 4 chars
        if (processed.length > maxLength) {
            processed = processed.substring(0, maxLength);
            logger.warn(`Text truncated to ${maxLength} characters for embedding`);
        }
        
        return processed;
    }

    async embed(text: string): Promise<GeminiEmbeddingVector> {
        const processedText = this.preprocessText(text);

        try {
            const response = await axios.post(
                `${this.baseUrl}/models/${this.config.model}:embedContent`,
                {
                    content: {
                        parts: [{ text: processedText }]
                    }
                },
                {
                    timeout: this.config.timeout,
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    params: {
                        key: this.config.apiKey
                    }
                }
            );

            if (!response.data || !response.data.embedding || !response.data.embedding.values) {
                throw new Error('Gemini API returned invalid response');
            }

            const embedding = response.data.embedding.values;
            
            return {
                vector: embedding,
                dimension: this.dimension
            };
        } catch (error) {
            if (axios.isAxiosError(error)) {
                if (error.response?.status === 401) {
                    throw new Error('Gemini API key is invalid or expired');
                }
                if (error.response?.status === 429) {
                    throw new Error('Gemini API rate limit exceeded. Please try again later.');
                }
                if (error.response?.status === 400) {
                    throw new Error(`Gemini API bad request: ${error.response.data?.error?.message || 'Invalid request'}`);
                }
                throw new Error(`Gemini API error: ${error.response?.data?.error?.message || error.message}`);
            }
            throw error;
        }
    }

    async embedBatch(texts: string[]): Promise<GeminiEmbeddingVector[]> {
        const results: GeminiEmbeddingVector[] = [];
        
        // Process texts in batches to avoid rate limits
        const batchSize = 5; // Gemini has stricter rate limits
        
        for (let i = 0; i < texts.length; i += batchSize) {
            const batch = texts.slice(i, i + batchSize);
            
            const batchPromises = batch.map(text => this.embed(text));
            
            try {
                const batchResults = await Promise.all(batchPromises);
                results.push(...batchResults);
                
                logger.debug(`Processed batch ${Math.floor(i / batchSize) + 1}/${Math.ceil(texts.length / batchSize)}`);
                
                // Add small delay between batches to respect rate limits
                if (i + batchSize < texts.length) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
            } catch (error) {
                logger.error(`Failed to embed batch starting at index ${i}:`, error);
                throw error;
            }
        }

        return results;
    }

    getDimension(): number {
        return this.dimension;
    }

    getProvider(): string {
        return 'Gemini';
    }

    getModel(): string {
        return this.config.model;
    }

    /**
     * Set model type
     * @param model Model name
     */
    setModel(model: string): void {
        this.config.model = model;
        this.updateModelSettings(model);
        logger.info(`Updated Gemini model to: ${model}`);
    }

    /**
     * Test API connection and key validity
     */
    async testConnection(): Promise<boolean> {
        try {
            const testResponse = await this.embed('test connection');
            return testResponse.vector.length > 0;
        } catch (error) {
            logger.error('Failed to connect to Gemini API:', error);
            return false;
        }
    }

    /**
     * Get list of supported models
     */
    static getSupportedModels(): Record<string, { dimension: number; maxTokens: number; description: string }> {
        return {
            'text-embedding-004': {
                dimension: 768,
                maxTokens: 2048,
                description: 'Latest text embedding model with improved performance'
            },
            'embedding-001': {
                dimension: 768,
                maxTokens: 2048,
                description: 'Original Gemini embedding model'
            }
        };
    }

    /**
     * Get recommended model for code embedding
     */
    static getRecommendedModelForCode(): string {
        return 'text-embedding-004';
    }

    /**
     * Get recommended model for general text
     */
    static getRecommendedModelForText(): string {
        return 'text-embedding-004';
    }
} 