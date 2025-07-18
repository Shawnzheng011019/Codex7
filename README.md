# Codex7 - Local Codebase RAG System

An intelligent RAG (Retrieval-Augmented Generation) system specifically designed for analyzing and searching local codebases. Built entirely with TypeScript, it provides semantic search capabilities, code analysis, and MCP integration for AI IDEs.

## 🌟 Features

- **🔍 Local Codebase Analysis**: Scan and index your local projects for intelligent search
- **📚 Multi-Content Support**: Analyze code, documentation, configuration files, and more
- **⚡ Semantic Search**: Advanced hybrid search combining vector similarity and BM25
- **🤖 MCP Integration**: Model Context Protocol server for seamless AI IDE integration
- **🎯 Multi-language Support**: JavaScript, TypeScript, Python, Go, Rust, Java, C++, and more
- **📊 Knowledge Graph**: Build code dependency graphs for impact analysis
- **🌐 Flexible Embeddings**: Support for OpenAI, Hugging Face, and local embedding models

## 🏗️ Architecture

The system is built entirely in TypeScript with a clean, modular architecture:

### Core Components
- **Scanner**: Local codebase file system scanner (`src/scanner/`)
- **Processor**: Content chunking and embedding generation (`src/processor/`)
- **Vector Database**: Milvus client for fast similarity search (`src/query/`)
- **Graph Database**: Neo4j client for code relationships (`src/graph/`)
- **MCP Server**: Tools for AI IDE integration (`src/mcp/`)
- **Embedding Service**: Multi-provider embedding generation (`src/embedding/`)
- **Search Engine**: Hybrid search with BM25 and reranking (`src/search/`)

### Processing Pipeline
1. **Scan** → Discover and categorize local project files
2. **Extract** → Parse code and documentation content
3. **Chunk** → Intelligent text segmentation with context preservation
4. **Embed** → Generate semantic embeddings using your preferred model
5. **Index** → Store in vector and graph databases for fast retrieval
6. **Search** → Hybrid search with reranking for optimal results

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Milvus 2.3+ (vector database)
- Neo4j 5+ (graph database, optional but recommended)

### 1. Installation

```bash
git clone https://github.com/your-org/codex7.git
cd codex7
npm install
```

### 2. Configuration

Copy and configure the environment file:

```bash
cp env.example .env
```

Edit `.env` with your settings:

```env
# Server Configuration
PORT=3000
LOG_LEVEL=info

# Database Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_DATABASE=codex7_local

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Embedding Configuration
DEFAULT_EMBEDDING_PROVIDER=local  # or 'openai', 'huggingface'
DEFAULT_EMBEDDING_MODEL=mock     # or your preferred model
OPENAI_API_KEY=your_openai_key   # if using OpenAI
HUGGINGFACE_API_KEY=your_hf_key  # if using Hugging Face

# Processing Configuration
MAX_FILE_SIZE_MB=5
MAX_PROJECT_SIZE_MB=500
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=200
```

### 3. Start the System

```bash
# Development mode with auto-reload
npm run dev

# Production build and start
npm run build
npm start
```

The MCP server will start on `http://localhost:3000` by default.

## 📖 Usage

### MCP Tools

The system provides comprehensive MCP tools for local codebase analysis:

#### `scan_project`
Analyze project structure and content types:
```json
{
  "name": "scan_project",
  "arguments": {
    "project_path": "/path/to/your/project",
    "project_name": "my-project"
  }
}
```

#### `index_project`
Index a project for search and analysis:
```json
{
  "name": "index_project",
  "arguments": {
    "project_path": "/path/to/your/project",
    "project_name": "my-project",
    "embedding_provider": "openai",
    "embedding_model": "text-embedding-3-small",
    "api_key": "your_api_key"
  }
}
```

#### `search_codebase`
Hybrid search across indexed projects:
```json
{
  "name": "search_codebase",
  "arguments": {
    "query": "authentication function",
    "project": "my-project",
    "language": "TypeScript",
    "content_type": "code",
    "top_k": 10
  }
}
```

#### `search_code`
Specialized code search:
```json
{
  "name": "search_code",
  "arguments": {
    "query": "async function with error handling",
    "language": "JavaScript",
    "top_k": 5
  }
}
```

#### `search_docs`
Documentation-focused search:
```json
{
  "name": "search_docs",
  "arguments": {
    "query": "installation guide",
    "project": "my-project"
  }
}
```

#### `analyze_dependencies`
Trace code dependencies and impact:
```json
{
  "name": "analyze_dependencies",
  "arguments": {
    "entity_name": "UserService",
    "max_hops": 3
  }
}
```

#### `find_symbol`
Locate specific functions, classes, or variables:
```json
{
  "name": "find_symbol",
  "arguments": {
    "symbol_name": "authenticate",
    "project": "my-project"
  }
}
```

### Additional Tools

- `get_project_files` - List all indexed files in a project
- `get_file_content` - Retrieve specific file content
- `get_indexed_projects` - Show all indexed projects
- `configure_embedding` - Change embedding provider/model

## 🛠️ Development

### Project Structure

```
Codex7/
├── src/
│   ├── scanner/           # Local codebase scanning
│   │   └── local-codebase-scanner.ts
│   ├── processor/         # Content processing and chunking
│   │   └── content-processor.ts
│   ├── embedding/         # Embedding generation service
│   │   └── embedding-service.ts
│   ├── query/            # Database query clients
│   │   └── milvus-client.ts
│   ├── search/           # Hybrid search implementation
│   │   ├── hybrid-search.ts
│   │   ├── bm25-search.ts
│   │   └── rerank-service.ts
│   ├── graph/            # Knowledge graph operations
│   │   ├── neo4j-client.ts
│   │   └── graph-query-service.ts
│   ├── mcp/              # MCP protocol implementation
│   │   ├── server.ts
│   │   └── local-codebase-server.ts
│   ├── server/           # Express server
│   │   └── app.ts
│   ├── types/            # TypeScript type definitions
│   │   └── index.ts
│   └── utils/            # Configuration and utilities
│       ├── config.ts
│       └── logger.ts
├── public/               # Web interface assets (optional)
│   └── index.html
└── package.json
```

### Available Scripts

```bash
# Development with watch mode
npm run dev

# Build TypeScript to JavaScript
npm run build

# Start production server
npm start

# Run tests
npm test

# Lint code
npm run lint
```

### Building Components

Each component can be run independently for development:

```bash
# Run local codebase scanner
tsx src/scanner/local-codebase-scanner.ts

# Run content processor
tsx src/processor/content-processor.ts

# Run embedding service
tsx src/embedding/embedding-service.ts

# Run MCP server
tsx src/mcp/server.ts
```

## 🔧 Configuration

### Embedding Providers

**OpenAI** (Recommended for production):
```env
DEFAULT_EMBEDDING_PROVIDER=openai
DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your_key
```

**Hugging Face** (Good balance of cost/quality):
```env
DEFAULT_EMBEDDING_PROVIDER=huggingface
DEFAULT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
HUGGINGFACE_API_KEY=your_key
```

**Local** (No cost, for development):
```env
DEFAULT_EMBEDDING_PROVIDER=local
DEFAULT_EMBEDDING_MODEL=mock
```

### Supported Languages

The system automatically detects and processes these languages:
- **JavaScript/TypeScript** - Node.js, React, Vue.js projects
- **Python** - Django, Flask, FastAPI, data science projects
- **Go** - Microservices, CLI tools
- **Rust** - System programming, web assembly
- **Java** - Spring Boot, Maven projects
- **C/C++** - System software, embedded projects
- **PHP** - Laravel, Symfony web applications
- **Ruby** - Rails applications
- **Swift** - iOS/macOS applications
- **Kotlin** - Android, server-side development
- **Scala** - Big data, functional programming
- **R** - Data science and analytics
- **Shell** - Bash, Zsh scripts
- **SQL** - Database queries and schemas
- **HTML/CSS** - Web frontend
- **Markdown** - Documentation

## 📊 Performance

- **Indexing Speed**: ~100-500 files/minute (depending on size and embedding provider)
- **Search Latency**: <100ms for semantic search across millions of chunks
- **Memory Usage**: ~2-4GB for typical project (depends on chunk count)
- **Storage**: ~100-200MB per 10k chunks in vector database

## 🔍 Search Features

### Hybrid Search
Combines vector similarity search with BM25 keyword matching:
- **Vector Search**: Semantic understanding using embeddings
- **BM25 Search**: Traditional keyword-based relevance
- **Reranking**: Smart combination of both approaches
- **Graph Enhancement**: Uses knowledge graph to expand queries

### Search Types
- **Code Search**: Optimized for finding functions, classes, and code patterns
- **Documentation Search**: Focused on README files, comments, and docs
- **Hybrid Search**: Combines code and documentation results
- **Symbol Search**: Finds specific identifiers across projects

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes with proper TypeScript types
4. Add tests for new functionality: `npm test`
5. Lint your code: `npm run lint`
6. Build the project: `npm run build`
7. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **OpenAI** for embedding models and API
- **Milvus** for the high-performance vector database
- **Neo4j** for graph database capabilities
- **Model Context Protocol** for AI IDE integration standard
- **Hugging Face** for open-source embedding models
- **TypeScript** for type-safe development
- **Tree-sitter** for robust code parsing
