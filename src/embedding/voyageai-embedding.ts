import axios from 'axios';
import { logger } from '../utils/logger.js';

export interface VoyageAIEmbeddingConfig {
    model: string;
    apiKey: string;
    timeout?: number;
}

export interface VoyageAIEmbeddingVector {
    vector: number[];
    dimension: number;
}

export class VoyageAIEmbedding {
    private config: VoyageAIEmbeddingConfig;
    private dimension: number = 1024; // Default dimension for voyage-code-3
    private inputType: 'document' | 'query' = 'document';
    private baseUrl: string = 'https://api.voyageai.com/v1';
    protected maxTokens: number = 32000; // Default max tokens

    constructor(config: VoyageAIEmbeddingConfig) {
        this.config = {
            timeout: 30000, // 30 seconds default timeout
            ...config
        };

        // Set dimension and context length based on different models
        this.updateModelSettings(config.model || 'voyage-code-3');
        
        logger.info(`Initialized VoyageAI embedding with model: ${this.config.model}`);
    }

    private updateModelSettings(model: string): void {
        const supportedModels = VoyageAIEmbedding.getSupportedModels();
        const modelInfo = supportedModels[model];

        if (modelInfo) {
            // If dimension is a string (indicating variable dimension), use default value 1024
            if (typeof modelInfo.dimension === 'string') {
                this.dimension = 1024; // Default dimension
            } else {
                this.dimension = modelInfo.dimension;
            }
            // Set max tokens based on model's context length
            this.maxTokens = modelInfo.contextLength;
        } else {
            // Use default dimension and context length for unknown models
            this.dimension = 1024;
            this.maxTokens = 32000;
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

    private preprocessTexts(texts: string[]): string[] {
        return texts.map(text => this.preprocessText(text));
    }

    async embed(text: string): Promise<VoyageAIEmbeddingVector> {
        const processedText = this.preprocessText(text);
        const model = this.config.model || 'voyage-code-3';

        try {
            const response = await axios.post(
                `${this.baseUrl}/embeddings`,
                {
                    input: processedText,
                    model: model,
                    input_type: this.inputType,
                },
                {
                    timeout: this.config.timeout,
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.config.apiKey}`
                    }
                }
            );

            if (!response.data || !response.data.data || !response.data.data[0] || !response.data.data[0].embedding) {
                throw new Error('VoyageAI API returned invalid response');
            }

            return {
                vector: response.data.data[0].embedding,
                dimension: this.dimension
            };
        } catch (error) {
            if (axios.isAxiosError(error)) {
                if (error.response?.status === 401) {
                    throw new Error('VoyageAI API key is invalid or expired');
                }
                if (error.response?.status === 429) {
                    throw new Error('VoyageAI API rate limit exceeded. Please try again later.');
                }
                if (error.response?.status === 400) {
                    throw new Error(`VoyageAI API bad request: ${error.response.data?.detail || 'Invalid request'}`);
                }
                throw new Error(`VoyageAI API error: ${error.response?.data?.detail || error.message}`);
            }
            throw error;
        }
    }

    async embedBatch(texts: string[]): Promise<VoyageAIEmbeddingVector[]> {
        const processedTexts = this.preprocessTexts(texts);
        const model = this.config.model || 'voyage-code-3';

        try {
            const response = await axios.post(
                `${this.baseUrl}/embeddings`,
                {
                    input: processedTexts,
                    model: model,
                    input_type: this.inputType,
                },
                {
                    timeout: this.config.timeout,
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this.config.apiKey}`
                    }
                }
            );

            if (!response.data || !response.data.data) {
                throw new Error('VoyageAI API returned invalid response');
            }

            return response.data.data.map((item: any) => {
                if (!item.embedding) {
                    throw new Error('VoyageAI API returned invalid embedding data');
                }
                return {
                    vector: item.embedding,
                    dimension: this.dimension
                };
            });
        } catch (error) {
            if (axios.isAxiosError(error)) {
                if (error.response?.status === 401) {
                    throw new Error('VoyageAI API key is invalid or expired');
                }
                if (error.response?.status === 429) {
                    throw new Error('VoyageAI API rate limit exceeded. Please try again later.');
                }
                if (error.response?.status === 400) {
                    throw new Error(`VoyageAI API bad request: ${error.response.data?.detail || 'Invalid request'}`);
                }
                throw new Error(`VoyageAI API error: ${error.response?.data?.detail || error.message}`);
            }
            throw error;
        }
    }

    getDimension(): number {
        return this.dimension;
    }

    getProvider(): string {
        return 'VoyageAI';
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
        logger.info(`Updated VoyageAI model to: ${model}`);
    }

    /**
     * Set input type (VoyageAI specific feature)
     * @param inputType Input type: 'document' | 'query'
     */
    setInputType(inputType: 'document' | 'query'): void {
        this.inputType = inputType;
        logger.info(`Updated VoyageAI input type to: ${inputType}`);
    }

    /**
     * Test API connection and key validity
     */
    async testConnection(): Promise<boolean> {
        try {
            const testResponse = await this.embed('test connection');
            return testResponse.vector.length > 0;
        } catch (error) {
            logger.error('Failed to connect to VoyageAI API:', error);
            return false;
        }
    }

    /**
     * Get list of supported models
     */
    static getSupportedModels(): Record<string, { dimension: number | string; contextLength: number; description: string }> {
        return {
            // Latest recommended models
            'voyage-3-large': {
                dimension: '1024 (default), 256, 512, 2048',
                contextLength: 32000,
                description: 'The best general-purpose and multilingual retrieval quality'
            },
            'voyage-3.5': {
                dimension: '1024 (default), 256, 512, 2048',
                contextLength: 32000,
                description: 'Optimized for general-purpose and multilingual retrieval quality'
            },
            'voyage-3.5-lite': {
                dimension: '1024 (default), 256, 512, 2048',
                contextLength: 32000,
                description: 'Optimized for latency and cost'
            },
            'voyage-code-3': {
                dimension: '1024 (default), 256, 512, 2048',
                contextLength: 32000,
                description: 'Optimized for code retrieval (recommended for code)'
            },
            // Professional domain models
            'voyage-finance-2': {
                dimension: 1024,
                contextLength: 32000,
                description: 'Optimized for finance retrieval and RAG'
            },
            'voyage-law-2': {
                dimension: 1024,
                contextLength: 16000,
                description: 'Optimized for legal retrieval and RAG'
            },
            'voyage-multilingual-2': {
                dimension: 1024,
                contextLength: 32000,
                description: 'Legacy: Use voyage-3.5 for multilingual tasks'
            },
            'voyage-large-2-instruct': {
                dimension: 1024,
                contextLength: 16000,
                description: 'Legacy: Use voyage-3.5 instead'
            },
            // Legacy models
            'voyage-large-2': {
                dimension: 1536,
                contextLength: 16000,
                description: 'Legacy: Use voyage-3.5 instead'
            },
            'voyage-code-2': {
                dimension: 1536,
                contextLength: 16000,
                description: 'Previous generation of code embeddings'
            },
            'voyage-3': {
                dimension: 1024,
                contextLength: 32000,
                description: 'Legacy: Use voyage-3.5 instead'
            },
            'voyage-3-lite': {
                dimension: 512,
                contextLength: 32000,
                description: 'Legacy: Use voyage-3.5-lite instead'
            },
            'voyage-2': {
                dimension: 1024,
                contextLength: 4000,
                description: 'Legacy: Use voyage-3.5-lite instead'
            },
            // Other legacy models
            'voyage-02': {
                dimension: 1024,
                contextLength: 4000,
                description: 'Legacy model'
            },
            'voyage-01': {
                dimension: 1024,
                contextLength: 4000,
                description: 'Legacy model'
            },
            'voyage-lite-01': {
                dimension: 1024,
                contextLength: 4000,
                description: 'Legacy model'
            },
            'voyage-lite-01-instruct': {
                dimension: 1024,
                contextLength: 4000,
                description: 'Legacy model'
            },
            'voyage-lite-02-instruct': {
                dimension: 1024,
                contextLength: 4000,
                description: 'Legacy model'
            }
        };
    }
} 