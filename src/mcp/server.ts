/**
 * Codex7 MCP Server
 * 
 * MCP server for local codebase analysis and search.
 * Provides essential tools for scanning, indexing, and querying local projects.
 */

import { MCPTool, SearchQuery } from '../types/index.js';
import { LocalCodebaseScanner } from '../scanner/local-codebase-scanner.js';
import { ContentProcessor } from '../processor/content-processor.js';
import { EmbeddingService } from '../embedding/embedding-service.js';
import { MilvusQueryClient } from '../query/milvus-client.js';
import { HybridSearchService } from '../search/hybrid-search.js';
import { graphQueryService } from '../graph/graph-query-service.js';
import { ASTParser } from '../parser/ast-parser.js';
import { CodeGraphService } from '../graph/code-graph-service.js';
import { logger } from '../utils/logger.js';
import { config } from '../utils/config.js';

export class MCPServer {
  private scanner: LocalCodebaseScanner;
  private processor: ContentProcessor;
  private embeddingService: EmbeddingService;
  private milvusClient: MilvusQueryClient;
  private hybridSearchService: HybridSearchService;
  private astParser: ASTParser;
  private codeGraphService: CodeGraphService;
  private tools: MCPTool[];
  private indexedProjects: Map<string, string> = new Map(); // projectName -> projectPath
  private isInitialized = false;
  private clientConnected = false;

  constructor() {
    this.scanner = new LocalCodebaseScanner();
    this.processor = new ContentProcessor();
    this.milvusClient = new MilvusQueryClient();
    this.hybridSearchService = new HybridSearchService({
      vectorWeight: 0.6,
      bm25Weight: 0.4,
      useReranking: true,
      rerankConfig: { model: 'reciprocal-rank-fusion' },
    });
    this.astParser = new ASTParser();
    this.codeGraphService = new CodeGraphService();
    
    // Initialize embedding service with OpenAI from environment variables
    this.embeddingService = new EmbeddingService({
      provider: 'openai',
      model: process.env.OPENAI_EMBEDDING_MODEL || 'text-embedding-3-small',
      apiKey: process.env.OPENAI_API_KEY,
      batchSize: 50
    });
    
    this.tools = this.defineTools();
  }

  public getTools(): MCPTool[] {
    return this.tools;
  }

  public async handleRequest(request: any): Promise<any> {
    try {
      // Ensure request has required fields
      if (!request || typeof request !== 'object') {
        return {
          jsonrpc: '2.0',
          id: 0,
          error: {
            code: -32600,
            message: 'Invalid Request: request must be a JSON object'
          }
        };
      }

      // Validate required fields according to JSON-RPC 2.0
      if (typeof request.jsonrpc !== 'string' || request.jsonrpc !== '2.0') {
        const responseId = request.id !== undefined && request.id !== null ? request.id : 0;
        return {
          jsonrpc: '2.0',
          id: responseId,
          error: {
            code: -32600,
            message: 'Invalid Request: jsonrpc version must be "2.0"'
          }
        };
      }

      if (typeof request.method !== 'string') {
        const responseId = request.id !== undefined && request.id !== null ? request.id : 0;
        return {
          jsonrpc: '2.0',
          id: responseId,
          error: {
            code: -32600,
            message: 'Invalid Request: method is required and must be a string'
          }
        };
      }

      // Ensure id is properly handled - it must be included in responses
      // MCP requires id to be string or number, not null
      const responseId = request.id !== undefined && request.id !== null ? request.id : 0;

      // Handle MCP initialization
      if (request.method === 'initialize') {
        this.isInitialized = true;
        this.clientConnected = true;
        logger.info('MCP client initialization started');
        const response: any = {
          jsonrpc: '2.0',
          id: responseId,
          result: {
            protocolVersion: '2024-11-05',
            capabilities: {
              tools: {}
            },
            serverInfo: {
              name: 'codex7-local-rag',
              version: '1.0.0'
            }
          }
        };
        return this.cleanResponse(response);
      }

      // Handle IDE notification that initialization is finished. Per JSON-RPC 2.0
      // spec, notifications (requests without an "id") must NOT generate a
      // response. Simply perform the side-effects and return undefined so the
      // caller knows not to write anything back to stdout.
      if (request.method === 'notifications/initialized') {
        this.clientConnected = true;
        logger.info('MCP client fully initialized and connected');
        return undefined; // no response for notifications
      }

      // Check if client is properly initialized for other requests
      if (!this.isInitialized && request.method !== 'initialize') {
        logger.warn('Received request before initialization:', request.method);
        const response: any = {
          jsonrpc: '2.0',
          id: responseId,
          error: {
            code: -32002,
            message: 'Server not initialized. Please call initialize first.'
          }
        };
        return this.cleanResponse(response);
      }

      if (request.method === 'tools/list') {
        const response: any = {
          jsonrpc: '2.0',
          id: responseId,
          result: {
            tools: this.tools
          }
        };
        return this.cleanResponse(response);
      }

      if (request.method === 'tools/call' && request.params) {
        const toolName = request.params.name;
        const args = request.params.arguments || {};
        try {
          const toolResult = await this.callTool(toolName, args);
          const response: any = {
            jsonrpc: '2.0',
            id: responseId,
            result: {
              content: [
                {
                  type: 'text',
                  text: typeof toolResult === 'string' ? toolResult : JSON.stringify(toolResult, null, 2)
                }
              ]
            }
          };
          return this.cleanResponse(response);
        } catch (toolError) {
          logger.error('Error in tool call:', toolError);
          const response: any = {
            jsonrpc: '2.0',
            id: responseId,
            error: {
              code: -32003,
              message: toolError instanceof Error ? toolError.message : String(toolError)
            }
          };
          return this.cleanResponse(response);
        }
      }

      const response: any = {
        jsonrpc: '2.0',
        id: responseId,
        error: {
          code: -32601,
          message: `Unknown method: ${request.method}`
        }
      };
      return this.cleanResponse(response);

    } catch (error) {
      logger.error('Error handling MCP request:', error);
      const responseId = request?.id !== undefined && request?.id !== null ? request.id : 0;
      const response: any = {
        jsonrpc: '2.0',
        id: responseId,
        error: {
          code: -32603,
          message: error instanceof Error ? error.message : String(error)
        }
      };
      return this.cleanResponse(response);
    }
  }

  public async cleanup(): Promise<void> {
    try {
      logger.info('Cleaning up MCP server resources...');
      this.clientConnected = false;
      this.isInitialized = false;
      
      // Cleanup resources
      await this.milvusClient.disconnect();
      await this.hybridSearchService.shutdown();
      
      logger.info('MCP server cleanup completed');
    } catch (error) {
      logger.error('Error during MCP server cleanup:', error);
    }
  }

  public isClientConnected(): boolean {
    return this.clientConnected;
  }

  private cleanResponse(response: any): any {
    // Remove any undefined values to prevent JSON serialization issues
    const cleaned: any = {};
    
    // Ensure proper structure for MCP responses
    cleaned.jsonrpc = '2.0';
    
    // Handle id - must be present for responses (except notifications)
    // MCP requires id to be string or number, never undefined
    if (response.id !== undefined && response.id !== null) {
      cleaned.id = response.id;
    } else if (response.id === null) {
      // Convert null to 0 for MCP compliance
      cleaned.id = 0;
    } else {
      // Ensure id is always present for responses
      cleaned.id = 0;
    }
    
    // Handle result vs error - only one should be present
    if (response.result !== undefined) {
      cleaned.result = response.result;
    } else if (response.error !== undefined) {
      cleaned.error = response.error;
    }
    
    // Only include defined values
    return Object.fromEntries(
      Object.entries(cleaned).filter(([_, value]) => value !== undefined)
    );
  }

  private async callTool(toolName: string, args: any): Promise<any> {
    switch (toolName) {
      case 'index_codebase':
        return await this.indexCodebase(args);
      case 'search_codebase':
        return await this.searchCodebase(args);
      case 'search_code':
        return await this.searchCode(args);
      case 'search_docs':
        return await this.searchDocs(args);
      case 'analyze_dependencies':
        return await this.analyzeDependencies(args);
      case 'find_symbol':
        return await this.findSymbol(args);
      case 'get_project_structure':
        return await this.getProjectStructure(args);
      default:
        throw new Error(`Unknown tool: ${toolName}`);
    }
  }

  private async indexCodebase(args: any): Promise<any> {
    try {
      const projectPath = args.project_path;
      const projectName = args.project_name;

      if (!projectPath) {
        throw new Error('project_path is required');
      }

      if (!process.env.OPENAI_API_KEY) {
        throw new Error('OPENAI_API_KEY environment variable is required');
      }

      logger.info(`Indexing codebase: ${projectPath}`);

      // Step 1: Scan project
      const extractedContent = await this.scanner.scanProject(projectPath, projectName);
      logger.info(`Scanned ${extractedContent.length} files`);

      // Step 2: AST Analysis and Graph Storage
      logger.info('Starting AST analysis and graph storage...');
      let totalEntities = 0;
      let totalRelationships = 0;

      for (const file of extractedContent) {
        if (this.astParser.getSupportedLanguages().includes(file.language.toLowerCase())) {
          try {
            const astAnalysis = this.astParser.parseFile(file.content, file.path, file.language);
            
            if (astAnalysis.entities.length > 0) {
              await this.codeGraphService.storeCodeStructure(
                astAnalysis,
                file.path,
                file.repo || (projectName || require('path').basename(projectPath)),
                file.language
              );
              
              totalEntities += astAnalysis.entities.length;
              totalRelationships += astAnalysis.relationships.length;
            }
          } catch (error) {
            logger.warn(`Error processing AST for ${file.path}:`, error);
          }
        }
      }

      logger.info(`AST analysis completed: ${totalEntities} entities, ${totalRelationships} relationships`);

      // Step 3: Process content (chunk and embed)
      const chunkingOptions = {
        preserveStructure: true,
        chunkSize: config.defaultChunkSize,
        chunkOverlap: config.defaultChunkOverlap
      };
      
      const { chunks } = await this.processor.processContent(
        extractedContent,
        chunkingOptions
      );

      logger.info(`Generated ${chunks.length} chunks`);

      // Step 4: Generate embeddings
      const embeddedVectors = await this.embeddingService.generateEmbeddings(chunks);
      logger.info(`Generated ${embeddedVectors.length} embeddings`);

      // Step 5: Store in vector database
      await this.milvusClient.insertVectors(embeddedVectors);

      // Store project info
      const finalProjectName = projectName || require('path').basename(projectPath);
      this.indexedProjects.set(finalProjectName, projectPath);

      return `Indexing completed successfully for project: ${finalProjectName}
Total files: ${extractedContent.length}
Total chunks: ${chunks.length}
Total embeddings: ${embeddedVectors.length}
Total AST entities: ${totalEntities}
Total AST relationships: ${totalRelationships}
Project path: ${projectPath}`;

    } catch (error) {
      logger.error('Error indexing codebase:', error);
      throw new Error(`Error indexing codebase: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async searchCodebase(args: any): Promise<any> {
    try {
      const originalQuery = args.query;
      logger.info(`Original search query: "${originalQuery}"`);

      // 1. Expand the query with terms from the knowledge graph
      const expansionTerms = await graphQueryService.expandQueryWithGraph(originalQuery);
      let expandedQuery = originalQuery;
      if (expansionTerms.length > 0) {
        expandedQuery = `${originalQuery} ${expansionTerms.join(' ')}`;
        logger.info(`Expanded search query with graph terms: "${expandedQuery}"`);
      }

      // 2. Create the search query object with the (potentially expanded) query
      const query: SearchQuery = {
        query: expandedQuery,
        language: args.language,
        repo: args.project,
        topK: args.top_k || 20,
        chunkType: args.content_type || 'both'
      };

      // 3. Perform the search
      const result = await this.hybridSearchService.search(query);
      
      return `Search completed for query: "${originalQuery}"
${expandedQuery !== originalQuery ? `Expanded query: "${expandedQuery}"` : ''}
Total results: ${result.finalResults.length}

Top results:
${result.finalResults.slice(0, 5).map((r, i) => `${i + 1}. ${r.path} (${r.language}) - Score: ${r.score.toFixed(3)}`).join('\n')}`;

    } catch (error) {
      logger.error('Error searching codebase:', error);
      throw new Error(`Error searching codebase: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async searchCode(args: any): Promise<any> {
    return this.searchCodebase({ ...args, content_type: 'code', top_k: args.top_k || 10 });
  }

  private async searchDocs(args: any): Promise<any> {
    return this.searchCodebase({ ...args, content_type: 'doc', top_k: args.top_k || 10 });
  }

  private async analyzeDependencies(args: any): Promise<any> {
    try {
      const entityName = args.entity_name;
      const maxHops = args.max_hops || 5;
      const project = args.project;

      const dependencies = await this.codeGraphService.findUpstreamDependencies(entityName, maxHops);
      const impact = await this.codeGraphService.findDownstreamImpact(entityName, maxHops);

      return `Dependency analysis completed for entity: ${entityName}
Project: ${project || 'all'}
Upstream dependencies: ${dependencies.length} items
Downstream impact: ${impact.length} items

Upstream dependencies:
${dependencies.slice(0, 10).map((dep, i) => `${i + 1}. ${dep}`).join('\n')}
${dependencies.length > 10 ? `... and ${dependencies.length - 10} more` : ''}

Downstream impact:
${impact.slice(0, 10).map((imp, i) => `${i + 1}. ${imp}`).join('\n')}
${impact.length > 10 ? `... and ${impact.length - 10} more` : ''}`;

    } catch (error) {
      logger.error('Error analyzing dependencies:', error);
      throw new Error(`Error analyzing dependencies: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async findSymbol(args: any): Promise<any> {
    try {
      const symbolName = args.symbol_name;
      const project = args.project;

      const results = await this.milvusClient.searchSymbols(symbolName, project);
      
      const formattedResults = results.map(result => ({
        project: result.repo,
        path: result.path,
        content: result.content.substring(0, 600) + (result.content.length > 600 ? '...' : ''),
        language: result.language,
        startLine: result.startLine,
        endLine: result.endLine
      }));

      return `Symbol lookup completed for: ${symbolName}
Project: ${project || 'all'}
Total results: ${formattedResults.length}

Results:
${formattedResults.slice(0, 10).map((r, i) => `${i + 1}. ${r.path} (${r.language}) - Lines ${r.startLine}-${r.endLine}`).join('\n')}
${formattedResults.length > 10 ? `... and ${formattedResults.length - 10} more results` : ''}`;

    } catch (error) {
      logger.error('Error finding symbol:', error);
      throw new Error(`Error finding symbol: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private async getProjectStructure(args: any): Promise<any> {
    try {
      const project = args.project;
      if (!project) {
        throw new Error('project parameter is required');
      }

      const structure = await this.codeGraphService.getProjectStructure(project);
      
      const totalFiles = structure.length;
      const totalEntities = structure.reduce((sum: number, file: any) => sum + file.entities.length, 0);

      return `Project structure for: ${project}
Total files: ${totalFiles}
Total entities: ${totalEntities}

Files and their entities:
${structure.slice(0, 10).map((file: any, i: number) => 
  `${i + 1}. ${file.filePath}
   Entities: ${file.entities.map((e: any) => `${e.name}(${e.type})`).join(', ')}`
).join('\n')}
${structure.length > 10 ? `... and ${structure.length - 10} more files` : ''}`;

    } catch (error) {
      logger.error('Error getting project structure:', error);
      throw new Error(`Error getting project structure: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  private defineTools(): MCPTool[] {
    return [
      {
        name: 'index_codebase',
        description: 'Scan and index a local codebase for search and analysis. Automatically scans files, generates chunks, creates embeddings, and stores in vector database.',
        inputSchema: {
          type: 'object',
          properties: {
            project_path: {
              type: 'string',
              description: 'Path to the local project directory'
            },
            project_name: {
              type: 'string',
              description: 'Optional name for the project (defaults to directory name)'
            }
          },
          required: ['project_path']
        }
      },
      {
        name: 'search_codebase',
        description: 'Search across indexed local projects using hybrid search (vector + BM25) with knowledge graph enhancement',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query'
            },
            project: {
              type: 'string',
              description: 'Specific project to search (optional, searches all if not provided)'
            },
            language: {
              type: 'string',
              description: 'Programming language filter (optional)'
            },
            content_type: {
              type: 'string',
              enum: ['code', 'doc', 'both'],
              description: 'Type of content to search (default: both)'
            },
            top_k: {
              type: 'number',
              description: 'Number of results to return (default: 20)'
            }
          },
          required: ['query']
        }
      },
      {
        name: 'search_code',
        description: 'Search for code snippets in indexed projects',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Code search query'
            },
            project: {
              type: 'string',
              description: 'Specific project to search (optional)'
            },
            language: {
              type: 'string',
              description: 'Programming language filter (optional)'
            },
            top_k: {
              type: 'number',
              description: 'Number of results to return (default: 10)'
            }
          },
          required: ['query']
        }
      },
      {
        name: 'search_docs',
        description: 'Search for documentation in indexed projects',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Documentation search query'
            },
            project: {
              type: 'string',
              description: 'Specific project to search (optional)'
            },
            top_k: {
              type: 'number',
              description: 'Number of results to return (default: 10)'
            }
          },
          required: ['query']
        }
      },
      {
        name: 'analyze_dependencies',
        description: 'Analyze dependencies and impact of a code entity using the knowledge graph',
        inputSchema: {
          type: 'object',
          properties: {
            entity_name: {
              type: 'string',
              description: 'Name of the function, class, or variable to analyze'
            },
            max_hops: {
              type: 'number',
              description: 'Maximum number of dependency hops to trace (default: 5)'
            }
          },
          required: ['entity_name']
        }
      },
      {
        name: 'find_symbol',
        description: 'Find specific symbols (functions, classes, variables) in indexed projects',
        inputSchema: {
          type: 'object',
          properties: {
            symbol_name: {
              type: 'string',
              description: 'Name of the symbol to find'
            },
            project: {
              type: 'string',
              description: 'Specific project to search (optional)'
            }
          },
          required: ['symbol_name']
        }
      },
      {
        name: 'get_project_structure',
        description: 'Get the complete code structure of a project including all files and entities',
        inputSchema: {
          type: 'object',
          properties: {
            project: {
              type: 'string',
              description: 'Name of the project to analyze'
            }
          },
          required: ['project']
        }
      }
    ];
  }
} 