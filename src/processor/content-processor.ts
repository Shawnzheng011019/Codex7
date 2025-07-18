/**
 * Content Processor
 * 
 * Processes extracted content by chunking text and generating embeddings
 * for storage in vector and graph databases.
 */

import { logger } from '../utils/logger.js';
import { ExtractedContent, TextChunk, EmbeddingVector } from '../types/index.js';

export interface ChunkingOptions {
  chunkSize?: number;
  chunkOverlap?: number;
  preserveStructure?: boolean;
}

export interface EmbeddingOptions {
  model?: string;
  batchSize?: number;
}

export class ContentProcessor {
  private readonly defaultChunkingOptions: Required<ChunkingOptions> = {
    chunkSize: 1000,
    chunkOverlap: 200,
    preserveStructure: true
  };

  private readonly defaultEmbeddingOptions: Required<EmbeddingOptions> = {
    model: 'text-embedding-3-small',
    batchSize: 100
  };

  async processContent(
    content: ExtractedContent[], 
    chunkingOptions?: ChunkingOptions,
    embeddingOptions?: EmbeddingOptions
  ): Promise<{ chunks: TextChunk[], vectors: EmbeddingVector[] }> {
    logger.info(`Processing ${content.length} content items`);

    // Step 1: Generate chunks
    const chunks = await this.generateChunks(content, chunkingOptions);
    logger.info(`Generated ${chunks.length} chunks`);

    // Step 2: Generate embeddings
    const vectors = await this.generateEmbeddings(chunks, embeddingOptions);
    logger.info(`Generated ${vectors.length} embeddings`);

    return { chunks, vectors };
  }

  async generateChunks(content: ExtractedContent[], options?: ChunkingOptions): Promise<TextChunk[]> {
    const opts = { ...this.defaultChunkingOptions, ...options };
    const chunks: TextChunk[] = [];

    for (const item of content) {
      try {
        const itemChunks = await this.chunkContent(item, opts);
        chunks.push(...itemChunks);
      } catch (error) {
        logger.error(`Error chunking content from ${item.path}: ${error}`);
      }
    }

    return chunks;
  }

  private async chunkContent(content: ExtractedContent, options: Required<ChunkingOptions>): Promise<TextChunk[]> {
    const chunks: TextChunk[] = [];
    const text = content.content;

    if (!text || text.trim().length === 0) {
      return chunks;
    }

    if (content.type === 'code') {
      return this.chunkCodeContent(content, options);
    } else {
      return this.chunkTextContent(content, options);
    }
  }

  private async chunkCodeContent(content: ExtractedContent, options: Required<ChunkingOptions>): Promise<TextChunk[]> {
    const chunks: TextChunk[] = [];
    const lines = content.content.split('\n');

    if (options.preserveStructure) {
      // Try to chunk by logical code structures
      chunks.push(...this.chunkByCodeStructure(content, lines, options));
    } else {
      // Simple line-based chunking
      chunks.push(...this.chunkByLines(content, lines, options));
    }

    return chunks;
  }

  private chunkByCodeStructure(content: ExtractedContent, lines: string[], options: Required<ChunkingOptions>): TextChunk[] {
    const chunks: TextChunk[] = [];
    let currentChunk: string[] = [];
    let currentSize = 0;
    let chunkStartLine = 1;

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const lineSize = line.length + 1; // +1 for newline

      // Check if this line starts a new logical block
              const isNewBlock = this.isCodeBlockStart(line);
      
      // If we hit size limit or found a new block and current chunk is substantial
      if ((currentSize + lineSize > options.chunkSize && currentChunk.length > 0) || 
          (isNewBlock && currentSize > options.chunkSize / 2)) {
        
        // Create chunk from current content
        if (currentChunk.length > 0) {
          chunks.push(this.createChunk(
            content,
            currentChunk.join('\n'),
            chunkStartLine,
            chunkStartLine + currentChunk.length - 1,
            chunks.length
          ));
        }

        // Start new chunk with overlap
        const overlapLines = Math.min(
          Math.floor(options.chunkOverlap / 50), // Approximate lines for overlap
          currentChunk.length
        );
        
        currentChunk = currentChunk.slice(-overlapLines);
        currentSize = currentChunk.reduce((sum, l) => sum + l.length + 1, 0);
        chunkStartLine = Math.max(1, i - overlapLines + 1);
      }

      currentChunk.push(line);
      currentSize += lineSize;
    }

    // Add final chunk
    if (currentChunk.length > 0) {
      chunks.push(this.createChunk(
        content,
        currentChunk.join('\n'),
        chunkStartLine,
        lines.length,
        chunks.length
      ));
    }

    return chunks;
  }

  private chunkByLines(content: ExtractedContent, lines: string[], options: Required<ChunkingOptions>): TextChunk[] {
    const chunks: TextChunk[] = [];
    const approxLinesPerChunk = Math.ceil(options.chunkSize / 50); // Estimate 50 chars per line
    const overlapLines = Math.ceil(options.chunkOverlap / 50);

    for (let i = 0; i < lines.length; i += approxLinesPerChunk - overlapLines) {
      const chunkLines = lines.slice(i, i + approxLinesPerChunk);
      if (chunkLines.length > 0) {
        chunks.push(this.createChunk(
          content,
          chunkLines.join('\n'),
          i + 1,
          Math.min(i + chunkLines.length, lines.length),
          chunks.length
        ));
      }
    }

    return chunks;
  }

  private async chunkTextContent(content: ExtractedContent, options: Required<ChunkingOptions>): Promise<TextChunk[]> {
    const chunks: TextChunk[] = [];
    const text = content.content;

    if (options.preserveStructure && (content.type === 'doc' || content.type === 'readme')) {
      // Chunk by paragraphs/sections for documentation
      chunks.push(...this.chunkByParagraphs(content, text, options));
    } else {
      // Simple sentence-based chunking
      chunks.push(...this.chunkBySentences(content, text, options));
    }

    return chunks;
  }

  private chunkByParagraphs(content: ExtractedContent, text: string, options: Required<ChunkingOptions>): TextChunk[] {
    const chunks: TextChunk[] = [];
    const paragraphs = text.split(/\n\s*\n/);
    
    let currentChunk = '';
    let currentSize = 0;

    for (const paragraph of paragraphs) {
      const paragraphSize = paragraph.length;

      if (currentSize + paragraphSize > options.chunkSize && currentChunk.length > 0) {
        // Create chunk and start new one
        chunks.push(this.createTextChunk(content, currentChunk.trim(), chunks.length));
        
        // Start new chunk with overlap
        const sentences = currentChunk.split(/[.!?]+/);
        const overlapSentences = sentences.slice(-2).join('.').trim();
        currentChunk = overlapSentences ? overlapSentences + '. ' + paragraph : paragraph;
        currentSize = currentChunk.length;
      } else {
        currentChunk += (currentChunk ? '\n\n' : '') + paragraph;
        currentSize += paragraphSize + 2; // +2 for double newline
      }
    }

    // Add final chunk
    if (currentChunk.trim()) {
      chunks.push(this.createTextChunk(content, currentChunk.trim(), chunks.length));
    }

    return chunks;
  }

  private chunkBySentences(content: ExtractedContent, text: string, options: Required<ChunkingOptions>): TextChunk[] {
    const chunks: TextChunk[] = [];
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
    
    let currentChunk = '';
    let currentSize = 0;

    for (const sentence of sentences) {
      const sentenceSize = sentence.length + 1; // +1 for punctuation

      if (currentSize + sentenceSize > options.chunkSize && currentChunk.length > 0) {
        chunks.push(this.createTextChunk(content, currentChunk.trim(), chunks.length));
        
        // Start new chunk with overlap
        const words = currentChunk.split(' ');
        const overlapWords = words.slice(-Math.floor(options.chunkOverlap / 5)); // Approximate words for overlap
        currentChunk = overlapWords.join(' ') + ' ' + sentence.trim() + '.';
        currentSize = currentChunk.length;
      } else {
        currentChunk += (currentChunk ? ' ' : '') + sentence.trim() + '.';
        currentSize += sentenceSize;
      }
    }

    // Add final chunk
    if (currentChunk.trim()) {
      chunks.push(this.createTextChunk(content, currentChunk.trim(), chunks.length));
    }

    return chunks;
  }

  private createChunk(
    content: ExtractedContent,
    chunkText: string,
    startLine: number,
    endLine: number,
    index: number
  ): TextChunk {
    return {
      id: `${content.repo}_${content.path}_${index}`,
      repo: content.repo,
      path: content.path,
      content: chunkText,
      chunkType: content.type,
      language: content.language,
      startLine,
      endLine,
      chunkIndex: index,
      metadata: {
        ...content.metadata,
        chunkSize: chunkText.length,
        chunkIndex: index
      }
    };
  }

  private createTextChunk(content: ExtractedContent, chunkText: string, index: number): TextChunk {
    // For text content, estimate line numbers based on content position
    const totalLines = content.content.split('\n').length;
    const chunkPosition = chunkText.length / content.content.length;
    const estimatedStartLine = Math.floor(chunkPosition * totalLines) + 1;
    const estimatedEndLine = Math.min(estimatedStartLine + chunkText.split('\n').length - 1, totalLines);

    return this.createChunk(content, chunkText, estimatedStartLine, estimatedEndLine, index);
  }

  private isCodeBlockStart(line: string): boolean {
    const trimmedLine = line.trim();
    
    if (!trimmedLine || trimmedLine.startsWith('//') || trimmedLine.startsWith('#')) {
      return false;
    }

    // Common patterns for new logical blocks
    const blockStartPatterns = [
      /^(class|interface|enum|struct|namespace)\s+/,
      /^(function|async function|def|fn|func|method)\s+/,
      /^(public|private|protected|static)\s+(class|function|method)/,
      /^(if|for|while|switch|try|catch)\s*\(/,
      /^(const|let|var)\s+\w+\s*=\s*(function|class|\()/,
      /^\w+\s*:\s*function/,
      /^export\s+(default\s+)?(class|function|interface)/
    ];

    return blockStartPatterns.some(pattern => pattern.test(trimmedLine));
  }

  async generateEmbeddings(chunks: TextChunk[], options?: EmbeddingOptions): Promise<EmbeddingVector[]> {
    const opts = { ...this.defaultEmbeddingOptions, ...options };
    const vectors: EmbeddingVector[] = [];

    // Process chunks in batches
    for (let i = 0; i < chunks.length; i += opts.batchSize) {
      const batch = chunks.slice(i, i + opts.batchSize);
      try {
        const batchVectors = await this.generateEmbeddingsBatch(batch, opts.model);
        vectors.push(...batchVectors);
        
        if (i % 500 === 0) {
          logger.info(`Processed ${i + batch.length}/${chunks.length} embeddings`);
        }
      } catch (error) {
        logger.error(`Error generating embeddings for batch ${i}-${i + batch.length}: ${error}`);
      }
    }

    return vectors;
  }

  private async generateEmbeddingsBatch(chunks: TextChunk[], model: string): Promise<EmbeddingVector[]> {
    // This is a placeholder - in a real implementation, you would call an embedding service
    // For now, we'll return mock vectors
    logger.debug(`Generating embeddings for ${chunks.length} chunks using model ${model}`);

    const vectors: EmbeddingVector[] = [];

    for (const chunk of chunks) {
      // Mock embedding vector (in real implementation, call OpenAI/Hugging Face/etc.)
      const vector = Array.from({ length: 1536 }, () => Math.random() - 0.5);
      
      vectors.push({
        id: chunk.id,
        vector,
        metadata: {
          repo: chunk.repo,
          path: chunk.path,
          chunkType: chunk.chunkType,
          language: chunk.language,
          startLine: chunk.startLine,
          endLine: chunk.endLine,
          chunkIndex: chunk.chunkIndex,
          contentLength: chunk.content.length,
          tokenCount: chunk.tokenCount || 0
        }
      });
    }

    return vectors;
  }

  // Utility method to get processing statistics
  getProcessingStats(content: ExtractedContent[], chunks: TextChunk[], vectors: EmbeddingVector[]) {
    const stats = {
      totalContent: content.length,
      totalChunks: chunks.length,
      totalVectors: vectors.length,
      avgChunksPerFile: chunks.length / content.length,
      contentTypes: {} as Record<string, number>,
      languages: {} as Record<string, number>,
      avgChunkSize: chunks.reduce((sum, c) => sum + c.content.length, 0) / chunks.length
    };

    // Count content types and languages
    for (const item of content) {
      stats.contentTypes[item.type] = (stats.contentTypes[item.type] || 0) + 1;
      if (item.language) {
        stats.languages[item.language] = (stats.languages[item.language] || 0) + 1;
      }
    }

    return stats;
  }
} 