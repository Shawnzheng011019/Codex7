import { MCPTool, MCPRequest, MCPResponse, SearchQuery } from '../types/index.js';
import { MilvusQueryClient } from '../query/milvus-client.js';
import { HybridSearchService } from '../search/hybrid-search.js';
import { graphQueryService } from '../graph/graph-query-service.js';
import { logger } from '../utils/logger.js';

export class MCPServer {
  private milvusClient: MilvusQueryClient;
  private hybridSearchService: HybridSearchService;
  private tools: MCPTool[];

  constructor() {
    this.milvusClient = new MilvusQueryClient();
    this.hybridSearchService = new HybridSearchService({
      vectorWeight: 0.6,
      bm25Weight: 0.4,
      useReranking: true,
      rerankConfig: { model: 'reciprocal-rank-fusion' },
    });
    this.tools = this.defineMCPTools();
  }

  public getTools(): MCPTool[] {
    return this.tools;
  }

  public async handleRequest(request: MCPRequest): Promise<MCPResponse> {
    try {
      logger.debug('Handling MCP request:', request);

      if (request.method === 'tools/list') {
        return {
          content: [{
            type: 'text',
            text: JSON.stringify({
              tools: this.tools
            }, null, 2)
          }]
        };
      }

      if (request.method === 'tools/call' && request.params) {
        const toolName = request.params.name;
        const args = request.params.arguments || {};
        
        return await this.callTool(toolName, args);
      }

      return {
        content: [{
          type: 'text',
          text: 'Unknown method or invalid request format'
        }],
        isError: true
      };

    } catch (error) {
      logger.error('Error handling MCP request:', error);
      return {
        content: [{
          type: 'text',
          text: `Error: ${error instanceof Error ? error.message : String(error)}`
        }],
        isError: true
      };
    }
  }

  private async callTool(toolName: string, args: any): Promise<MCPResponse> {
    switch (toolName) {
      case 'hybrid_search':
        return await this.hybridSearch(args);
      
      case 'search_code':
        return await this.searchCode(args);
      
      case 'search_doc':
        return await this.searchDoc(args);
      
      case 'symbol_lookup':
        return await this.symbolLookup(args);
      
      case 'get_repository_files':
        return await this.getRepositoryFiles(args);
      
      case 'get_stats':
        return await this.getStats(args);
      
      case 'graph_query':
        return await this.graphQuery(args);

      default:
        return {
          content: [{
            type: 'text',
            text: `Unknown tool: ${toolName}`
          }],
          isError: true
        };
    }
  }

  private async hybridSearch(args: any): Promise<MCPResponse> {
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
        query: expandedQuery, // Use the expanded query
        language: args.language,
        repo: args.repo,
        topK: args.top_k || 20,
        chunkType: args.chunk_type || 'both'
      };

      // 3. Perform the search
      const result = await this.hybridSearchService.search(query);
      
      const formattedResult = {
        originalQuery: originalQuery,
        expandedQuery: expandedQuery, // Include the expanded query in the response for transparency
        searchType: 'hybrid',
        results: {
          // ... (rest of the result formatting)
          final: result.finalResults.map(r => ({
            repo: r.repo,
            path: r.path,
            content: r.content.substring(0, 600) + (r.content.length > 600 ? '...' : ''),
            language: r.language,
            startLine: r.startLine,
            endLine: r.endLine,
            score: r.score
          }))
        },
        totalResults: result.finalResults.length
      };

      return {
        content: [{
          type: 'text',
          text: JSON.stringify(formattedResult, null, 2)
        }]
      };
    } catch (error) {
      logger.error('Error in hybrid_search:', error);
      return {
        content: [{
          type: 'text',
          text: `Error in hybrid search: ${error instanceof Error ? error.message : String(error)}`
        }],
        isError: true
      };
    }
  }

  private async searchCode(args: any): Promise<MCPResponse> {
    // This tool now implicitly uses the graph-expanded hybrid search
    return this.hybridSearch({ ...args, chunk_type: 'code', top_k: args.top_k || 10 });
  }

  private async searchDoc(args: any): Promise<MCPResponse> {
    // This tool also implicitly uses the graph-expanded hybrid search
    return this.hybridSearch({ ...args, chunk_type: 'doc', top_k: args.top_k || 10 });
  }

  private async symbolLookup(args: any): Promise<MCPResponse> {
    try {
      const symbolName = args.symbol_name;
      const repo = args.repo;

      const results = await this.milvusClient.searchSymbols(symbolName, repo);
      
      const formattedResults = results.map(result => ({
        repo: result.repo,
        path: result.path,
        content: result.content.substring(0, 600) + (result.content.length > 600 ? '...' : ''),
        language: result.language,
        startLine: result.startLine,
        endLine: result.endLine
      }));

      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            symbol: symbolName,
            repo: repo || 'all',
            searchType: 'symbol lookup',
            results: formattedResults,
            total: formattedResults.length
          }, null, 2)
        }]
      };
    } catch (error) {
      logger.error('Error in symbol_lookup:', error);
      return {
        content: [{
          type: 'text',
          text: `Error looking up symbol: ${error instanceof Error ? error.message : String(error)}`
        }],
        isError: true
      };
    }
  }

  private async getRepositoryFiles(args: any): Promise<MCPResponse> {
    try {
      const repoName = args.repo;
      if (!repoName) {
        throw new Error('Repository name is required');
      }

      const results = await this.milvusClient.getRepositoryFiles(repoName);
      
      const formattedResults = results.map(result => ({
        repo: result.repo,
        path: result.path,
        chunkType: result.chunkType,
        language: result.language,
        startLine: result.startLine,
        endLine: result.endLine
      }));

      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            repo: repoName,
            files: formattedResults,
            total: formattedResults.length
          }, null, 2)
        }]
      };
    } catch (error) {
      logger.error('Error in get_repository_files:', error);
      return {
        content: [{
          type: 'text',
          text: `Error getting repository files: ${error instanceof Error ? error.message : String(error)}`
        }],
        isError: true
      };
    }
  }

  private async getStats(_args: any): Promise<MCPResponse> {
    try {
      const hybridStats = this.hybridSearchService.getStats();
      
      const stats = {
        hybridSearch: hybridStats,
        timestamp: new Date().toISOString(),
        version: '1.0.0'
      };

      return {
        content: [{
          type: 'text',
          text: JSON.stringify(stats, null, 2)
        }]
      };
    } catch (error) {
      logger.error('Error in get_stats:', error);
      return {
        content: [{
          type: 'text',
          text: `Error getting stats: ${error instanceof Error ? error.message : String(error)}`
        }],
        isError: true
      };
    }
  }

  private async graphQuery(args: any): Promise<MCPResponse> {
    try {
      const queryType = args.query_type;
      const entityName = args.entity_name;
      const maxHops = args.max_hops || 5;
      let results;

      switch (queryType) {
        case 'downstream_impact':
          results = await graphQueryService.findDownstreamImpact(entityName, maxHops);
          break;
        case 'upstream_dependencies':
          results = await graphQueryService.findUpstreamDependencies(entityName, maxHops);
          break;
        case 'inheritance_chain':
          results = await graphQueryService.getClassInheritance(entityName);
          break;
        default:
          throw new Error(`Unknown graph query type: ${queryType}`);
      }

      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            query: {
              type: queryType,
              entity: entityName,
            },
            results: results,
            total: results.length,
          }, null, 2)
        }]
      };

    } catch (error) {
      logger.error('Error in graph_query:', error);
      return {
        content: [{
          type: 'text',
          text: `Error performing graph query: ${error instanceof Error ? error.message : String(error)}`
        }],
        isError: true
      };
    }
  }

  private defineMCPTools(): MCPTool[] {
    return [
      {
        name: 'hybrid_search',
        description: 'Perform hybrid search combining vector search, BM25, and reranking for optimal results. Returns detailed breakdown of each search method.',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query (e.g., "authentication function", "installation guide")'
            },
            language: {
              type: 'string',
              description: 'Programming language filter (optional, e.g., "Python", "JavaScript")'
            },
            repo: {
              type: 'string',
              description: 'Repository filter (optional, e.g., "facebook/react")'
            },
            chunk_type: {
              type: 'string',
              enum: ['doc', 'code', 'both'],
              description: 'Type of content to search (default: "both")'
            },
            top_k: {
              type: 'number',
              description: 'Number of results to return (default: 20, max: 50)'
            }
          },
          required: ['query']
        }
      },
      {
        name: 'search_code',
        description: 'Search for code snippets across GitHub repositories using hybrid search. Returns relevant code chunks with context.',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query for code (e.g., "authentication function", "database connection")'
            },
            language: {
              type: 'string',
              description: 'Programming language filter (optional, e.g., "Python", "JavaScript")'
            },
            repo: {
              type: 'string',
              description: 'Repository filter (optional, e.g., "facebook/react")'
            },
            top_k: {
              type: 'number',
              description: 'Number of results to return (default: 10, max: 50)'
            }
          },
          required: ['query']
        }
      },
      {
        name: 'search_doc',
        description: 'Search for documentation across GitHub repositories. Returns relevant documentation chunks.',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: 'Search query for documentation (e.g., "installation guide", "API reference")'
            },
            repo: {
              type: 'string',
              description: 'Repository filter (optional, e.g., "facebook/react")'
            },
            top_k: {
              type: 'number',
              description: 'Number of results to return (default: 10, max: 50)'
            }
          },
          required: ['query']
        }
      },
      {
        name: 'symbol_lookup',
        description: 'Look up specific symbols (functions, classes, variables) in code repositories.',
        inputSchema: {
          type: 'object',
          properties: {
            symbol_name: {
              type: 'string',
              description: 'Name of the symbol to look up (e.g., "useState", "Component", "authenticate")'
            },
            repo: {
              type: 'string',
              description: 'Repository filter (optional, e.g., "facebook/react")'
            }
          },
          required: ['symbol_name']
        }
      },
      {
        name: 'get_repository_files',
        description: 'Get the file structure and available content for a specific repository.',
        inputSchema: {
          type: 'object',
          properties: {
            repo: {
              type: 'string',
              description: 'Repository name (e.g., "facebook/react")'
            }
          },
          required: ['repo']
        }
      },
      {
        name: 'get_stats',
        description: 'Get statistics about the RAG system database and available repositories.',
        inputSchema: {
          type: 'object',
          properties: {},
          required: []
        }
      },
      {
        name: 'graph_query',
        description: 'Perform complex queries on the code knowledge graph. Can trace dependencies, find impact of changes, and show class inheritance.',
        inputSchema: {
          type: 'object',
          properties: {
            query_type: {
              type: 'string',
              enum: ['downstream_impact', 'upstream_dependencies', 'inheritance_chain'],
              description: 'The type of graph query to perform.'
            },
            entity_name: {
              type: 'string',
              description: 'The name of the starting entity (e.g., a function or class name).'
            },
            max_hops: {
              type: 'number',
              description: 'For dependency/impact queries, the max number of hops to traverse (default: 5).'
            }
          },
          required: ['query_type', 'entity_name']
        }
      }
    ];
  }
} 