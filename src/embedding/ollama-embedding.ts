import axios from 'axios';
import { logger } from '../utils/logger.js';

export interface OllamaEmbeddingConfig {
    model: string;
    host: string;
    timeout?: number;
}

export interface OllamaEmbeddingVector {
    vector: number[];
    dimension: number;
}

export class OllamaEmbedding {
    private config: OllamaEmbeddingConfig;
    private dimension: number = 1024; // Default dimension
    protected maxTokens: number = 8192; // Default max tokens

    constructor(config: OllamaEmbeddingConfig) {
        this.config = {
            timeout: 30000, // 30 seconds default timeout
            ...config
        };
        
        // Ensure host has proper protocol
        if (!this.config.host.startsWith('http://') && !this.config.host.startsWith('https://')) {
            this.config.host = `http://${this.config.host}`;
        }
        
        // Remove trailing slash
        this.config.host = this.config.host.replace(/\/$/, '');
        
        logger.info(`Initialized Ollama embedding with model: ${this.config.model} at ${this.config.host}`);
    }

    async embed(text: string): Promise<OllamaEmbeddingVector> {
        const processedText = this.preprocessText(text);

        try {
            const response = await axios.post(
                `${this.config.host}/api/embeddings`,
                {
                    model: this.config.model,
                    prompt: processedText
                },
                {
                    timeout: this.config.timeout,
                    headers: {
                        'Content-Type': 'application/json'
                    }
                }
            );

            if (!response.data || !response.data.embedding) {
                throw new Error('Ollama API returned invalid response');
            }

            const embedding = response.data.embedding;
            this.dimension = embedding.length;

            return {
                vector: embedding,
                dimension: this.dimension
            };
        } catch (error) {
            if (axios.isAxiosError(error)) {
                if (error.code === 'ECONNREFUSED') {
                    throw new Error(`Cannot connect to Ollama server at ${this.config.host}. Please ensure Ollama is running.`);
                }
                if (error.response?.status === 404) {
                    throw new Error(`Model '${this.config.model}' not found. Please pull the model first: ollama pull ${this.config.model}`);
                }
                throw new Error(`Ollama API error: ${error.response?.data?.error || error.message}`);
            }
            throw error;
        }
    }

    async embedBatch(texts: string[]): Promise<OllamaEmbeddingVector[]> {
        const results: OllamaEmbeddingVector[] = [];
        
        // Ollama typically processes one at a time, so we'll do sequential requests
        for (let i = 0; i < texts.length; i++) {
            try {
                const result = await this.embed(texts[i]);
                results.push(result);
                logger.debug(`Processed embedding ${i + 1}/${texts.length}`);
            } catch (error) {
                logger.error(`Failed to embed text ${i + 1}:`, error);
                throw error;
            }
        }

        return results;
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

    getDimension(): number {
        return this.dimension;
    }

    getProvider(): string {
        return 'Ollama';
    }

    getModel(): string {
        return this.config.model;
    }

    getHost(): string {
        return this.config.host;
    }

    /**
     * Set model name
     * @param model Model name
     */
    setModel(model: string): void {
        this.config.model = model;
        logger.info(`Updated Ollama model to: ${model}`);
    }

    /**
     * Set host URL
     * @param host Host URL
     */
    setHost(host: string): void {
        // Ensure host has proper protocol
        if (!host.startsWith('http://') && !host.startsWith('https://')) {
            host = `http://${host}`;
        }
        
        // Remove trailing slash
        host = host.replace(/\/$/, '');
        
        this.config.host = host;
        logger.info(`Updated Ollama host to: ${host}`);
    }

    /**
     * Test connection to Ollama server
     */
    async testConnection(): Promise<boolean> {
        try {
            const response = await axios.get(`${this.config.host}/api/tags`, {
                timeout: 5000
            });
            return response.status === 200;
        } catch (error) {
            logger.error('Failed to connect to Ollama server:', error);
            return false;
        }
    }

    /**
     * List available models
     */
    async listModels(): Promise<string[]> {
        try {
            const response = await axios.get(`${this.config.host}/api/tags`, {
                timeout: 10000
            });
            
            if (response.data && response.data.models) {
                return response.data.models.map((model: any) => model.name);
            }
            
            return [];
        } catch (error) {
            logger.error('Failed to list Ollama models:', error);
            throw new Error(`Cannot list models from Ollama server: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    /**
     * Get list of recommended embedding models
     */
    static getRecommendedModels(): Record<string, { dimension: number; description: string }> {
        return {
            'nomic-embed-text': {
                dimension: 768,
                description: 'High-performance text embedding model with strong retrieval capabilities'
            },
            'mxbai-embed-large': {
                dimension: 1024,
                description: 'Large multilingual embedding model with excellent performance'
            },
            'all-minilm': {
                dimension: 384,
                description: 'Fast and efficient embedding model, good for general use'
            },
            'snowflake-arctic-embed': {
                dimension: 1024,
                description: 'Snowflake Arctic embedding model optimized for retrieval'
            },
            'bge-large': {
                dimension: 1024,
                description: 'BGE large embedding model with strong multilingual support'
            },
            'bge-base': {
                dimension: 768,
                description: 'BGE base embedding model, balanced performance and speed'
            },
            'bge-small': {
                dimension: 512,
                description: 'BGE small embedding model, optimized for speed'
            }
        };
    }
} 