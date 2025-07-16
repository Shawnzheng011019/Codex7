import express from 'express';
import cors from 'cors';
import path from 'path';
import { fileURLToPath } from 'url';
import { MCPServer } from '../mcp/server.js';
import { HybridSearchService } from '../search/hybrid-search.js';
import { logger } from '../utils/logger.js';
import { config } from '../utils/config.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class WebServer {
  private app: express.Application;
  private mcpServer: MCPServer;
  private hybridSearchService: HybridSearchService;
  private server: any;

  constructor() {
    this.app = express();
    this.mcpServer = new MCPServer();
    this.hybridSearchService = new HybridSearchService({
      vectorWeight: 0.6,
      bm25Weight: 0.4,
      useReranking: true,
      rerankConfig: { model: 'reciprocal-rank-fusion' },
      enableCaching: true,
      cacheSize: 200,
    });
    
    this.setupMiddleware();
    this.setupRoutes();
  }

  private setupMiddleware(): void {
    // CORS configuration
    this.app.use(cors({
      origin: '*',
      methods: ['GET', 'POST', 'OPTIONS'],
      allowedHeaders: ['Content-Type', 'Authorization'],
    }));

    // Body parsing
    this.app.use(express.json({ limit: '10mb' }));
    this.app.use(express.urlencoded({ extended: true }));

    // Static files
    this.app.use(express.static(path.join(__dirname, '../../public')));

    // Request logging
    this.app.use((req, res, next) => {
      logger.debug(`${req.method} ${req.path}`, { body: req.body });
      next();
    });
  }

  private setupRoutes(): void {
    // API Routes
    this.app.get('/api/health', this.healthCheck.bind(this));
    this.app.get('/api/tools', this.getTools.bind(this));
    this.app.post('/api/mcp/request', this.handleMCPRequest.bind(this));
    
    // Enhanced Search API with Hybrid Search
    this.app.post('/api/search/hybrid', this.hybridSearch.bind(this));
    this.app.post('/api/search/code', this.searchCode.bind(this));
    this.app.post('/api/search/doc', this.searchDoc.bind(this));
    this.app.post('/api/search/symbol', this.searchSymbol.bind(this));
    
    // Repository and Stats API
    this.app.get('/api/repository/:repo/files', this.getRepositoryFiles.bind(this));
    this.app.get('/api/stats', this.getStats.bind(this));
    this.app.get('/api/stats/search', this.getSearchStats.bind(this));
    
    // Configuration API
    this.app.get('/api/config/search', this.getSearchConfig.bind(this));
    this.app.post('/api/config/search', this.updateSearchConfig.bind(this));
    
    // Demo page
    this.app.get('/', (req, res) => {
      res.sendFile(path.join(__dirname, '../../public/index.html'));
    });
    
    // 404 handler
    this.app.use((req, res) => {
      res.status(404).json({ error: 'Not found' });
    });
    
    // Error handler
    this.app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
      logger.error('Express error:', err);
      res.status(500).json({ error: 'Internal server error' });
    });
  }

  public async start(): Promise<void> {
    try {
      // Initialize services
      await this.hybridSearchService.initialize();
      
      const port = config.server.port;
      this.server = this.app.listen(port, () => {
        logger.info(`Codex7 RAG System running on port ${port}`);
        logger.info(`Demo interface: http://localhost:${port}`);
        logger.info(`API endpoint: http://localhost:${port}/api`);
      });
    } catch (error) {
      logger.error('Failed to start web server:', error);
      throw error;
    }
  }

  public async stop(): Promise<void> {
    try {
      if (this.server) {
        this.server.close();
      }
      await this.hybridSearchService.shutdown();
      logger.info('Web server stopped');
    } catch (error) {
      logger.error('Error stopping web server:', error);
    }
  }

  private async healthCheck(req: express.Request, res: express.Response): Promise<void> {
    try {
      const stats = this.hybridSearchService.getStats();
      res.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        version: '1.0.0',
        services: {
          hybridSearch: stats.isInitialized ? 'healthy' : 'initializing',
          bm25: stats.bm25Stats.isIndexed ? 'indexed' : 'building',
          cache: `${stats.cacheSize} entries`,
        }
      });
    } catch (error) {
      res.status(500).json({
        status: 'unhealthy',
        error: error instanceof Error ? error.message : String(error)
      });
    }
  }

  private async getTools(req: express.Request, res: express.Response): Promise<void> {
    try {
      const tools = this.mcpServer.getTools();
      res.json({ tools });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async handleMCPRequest(req: express.Request, res: express.Response): Promise<void> {
    try {
      const response = await this.mcpServer.handleRequest(req.body);
      res.json(response);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async hybridSearch(req: express.Request, res: express.Response): Promise<void> {
    try {
      const { query, language, repo, chunk_type, top_k } = req.body;
      
      if (!query) {
        res.status(400).json({ error: 'Query parameter is required' });
        return;
      }

      const searchQuery = {
        query,
        language,
        repo,
        chunkType: chunk_type || 'both',
        topK: top_k || 20,
      };

      const result = await this.hybridSearchService.search(searchQuery);
      
      res.json({
        query,
        searchType: 'hybrid',
        results: {
          vector: result.embeddingResults.slice(0, 10), // Limit for API response
          bm25: result.bm25Results.slice(0, 10),
          reranked: result.rerankedResults.slice(0, 10),
          final: result.finalResults,
        },
        totalResults: result.finalResults.length,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      logger.error('Error in hybrid search:', error);
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async searchCode(req: express.Request, res: express.Response): Promise<void> {
    try {
      const { query, language, repo, top_k } = req.body;
      
      const mcpRequest = {
        method: 'tools/call',
        params: {
          name: 'search_code',
          arguments: { query, language, repo, top_k }
        }
      };
      
      const response = await this.mcpServer.handleRequest(mcpRequest);
      const result = JSON.parse(response.content[0].text);
      
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async searchDoc(req: express.Request, res: express.Response): Promise<void> {
    try {
      const { query, repo, top_k } = req.body;
      
      const mcpRequest = {
        method: 'tools/call',
        params: {
          name: 'search_doc',
          arguments: { query, repo, top_k }
        }
      };
      
      const response = await this.mcpServer.handleRequest(mcpRequest);
      const result = JSON.parse(response.content[0].text);
      
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async searchSymbol(req: express.Request, res: express.Response): Promise<void> {
    try {
      const { symbol_name, repo } = req.body;
      
      const mcpRequest = {
        method: 'tools/call',
        params: {
          name: 'symbol_lookup',
          arguments: { symbol_name, repo }
        }
      };
      
      const response = await this.mcpServer.handleRequest(mcpRequest);
      const result = JSON.parse(response.content[0].text);
      
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async getRepositoryFiles(req: express.Request, res: express.Response): Promise<void> {
    try {
      const { repo } = req.params;
      
      const mcpRequest = {
        method: 'tools/call',
        params: {
          name: 'get_repository_files',
          arguments: { repo }
        }
      };
      
      const response = await this.mcpServer.handleRequest(mcpRequest);
      const result = JSON.parse(response.content[0].text);
      
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async getStats(req: express.Request, res: express.Response): Promise<void> {
    try {
      const mcpRequest = {
        method: 'tools/call',
        params: {
          name: 'get_stats',
          arguments: {}
        }
      };
      
      const response = await this.mcpServer.handleRequest(mcpRequest);
      const result = JSON.parse(response.content[0].text);
      
      res.json(result);
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async getSearchStats(req: express.Request, res: express.Response): Promise<void> {
    try {
      const stats = this.hybridSearchService.getStats();
      res.json({
        searchEngine: 'Hybrid Search (Vector + BM25 + Rerank)',
        ...stats,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async getSearchConfig(req: express.Request, res: express.Response): Promise<void> {
    try {
      const stats = this.hybridSearchService.getStats();
      res.json({
        currentConfig: stats.config,
        availableModels: {
          rerank: ['reciprocal-rank-fusion', 'bge-reranker', 'colbert', 'cross-encoder'],
          weights: {
            vectorWeight: 'Weight for vector search (0.0-1.0)',
            bm25Weight: 'Weight for BM25 search (0.0-1.0)',
          }
        }
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async updateSearchConfig(req: express.Request, res: express.Response): Promise<void> {
    try {
      const newConfig = req.body;
      
      // Validate configuration
      if (newConfig.vectorWeight !== undefined && (newConfig.vectorWeight < 0 || newConfig.vectorWeight > 1)) {
        res.status(400).json({ error: 'vectorWeight must be between 0 and 1' });
        return;
      }
      
      if (newConfig.bm25Weight !== undefined && (newConfig.bm25Weight < 0 || newConfig.bm25Weight > 1)) {
        res.status(400).json({ error: 'bm25Weight must be between 0 and 1' });
        return;
      }

      this.hybridSearchService.updateConfig(newConfig);
      
      res.json({
        message: 'Search configuration updated successfully',
        newConfig: this.hybridSearchService.getStats().config,
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      res.status(500).json({ error: error instanceof Error ? error.message : String(error) });
    }
  }
} 