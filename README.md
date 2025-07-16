# Codex7 - GitHub RAG System

An intelligent RAG (Retrieval-Augmented Generation) system that provides semantic search capabilities across the top 100 GitHub repositories. Built with TypeScript (MCP Server) and Python (AI Processing Pipeline).

## 🌟 Features

- **🔍 Semantic Code Search**: Search for code patterns across 100+ top GitHub repositories
- **📚 Documentation Search**: Find relevant documentation and guides
- **⚡ Symbol Lookup**: Quick lookup of functions, classes, and variables
- **🤖 MCP Integration**: Model Context Protocol server for AI IDE integration
- **🎯 Multi-language Support**: JavaScript, TypeScript, Python, Go, Rust, Java, C++, and more
- **📊 Vector Database**: Powered by Milvus for fast similarity search
- **🌐 Web Interface**: Beautiful demo interface for testing and exploration

## 🏗️ Architecture

The system is split into two main components:

### Python Processing Pipeline
- **Crawling**: Extract top repositories from gitstar-ranking.com
- **Content Extraction**: Parse documentation and code files
- **Text Chunking**: Intelligent chunking for optimal retrieval
- **Embedding**: BGE (Chinese) and code-specific embedding models
- **Vector Storage**: Milvus database with hybrid search capabilities

### TypeScript MCP Server
- **Query Interface**: Direct connection to vector database
- **MCP Tools**: `search_code`, `search_doc`, `symbol_lookup`
- **Web API**: RESTful endpoints for web interface
- **Demo Interface**: Interactive web UI for testing

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- Milvus 2.3+ (vector database)
- GitHub API token

### 1. Setup Python Environment

```bash
cd python
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Setup TypeScript Environment

```bash
npm install
```

### 3. Configuration

Copy environment files and configure:

```bash
# Python configuration
cp python/env.example python/.env
# Edit python/.env with your tokens and database settings

# TypeScript configuration
cp env.example .env
# Edit .env with your settings
```

### 4. Run the Processing Pipeline

```bash
cd python
python main.py --full-pipeline
```

This will:
1. Crawl top 100 GitHub repositories
2. Extract and clean content
3. Generate embeddings
4. Store in vector database
5. Build search indices

### 5. Start the MCP Server

```bash
npm run dev
```

The server will start on `http://localhost:3000` with the demo interface.

## 📖 Usage

### Web Interface

Visit `http://localhost:3000` to access the demo interface with:
- **Code Search**: Find code snippets by description
- **Documentation Search**: Search through README files and docs
- **Symbol Lookup**: Find specific functions or classes

### MCP Tools

The system provides 5 MCP tools for AI IDE integration:

#### `search_code`
```json
{
  "name": "search_code",
  "arguments": {
    "query": "authentication function",
    "language": "Python",
    "repo": "django/django",
    "top_k": 10
  }
}
```

#### `search_doc`
```json
{
  "name": "search_doc",
  "arguments": {
    "query": "installation guide",
    "repo": "facebook/react",
    "top_k": 5
  }
}
```

#### `symbol_lookup`
```json
{
  "name": "symbol_lookup",
  "arguments": {
    "symbol_name": "useState",
    "repo": "facebook/react"
  }
}
```

#### `get_repository_files`
```json
{
  "name": "get_repository_files",
  "arguments": {
    "repo": "microsoft/vscode"
  }
}
```

#### `get_stats`
```json
{
  "name": "get_stats",
  "arguments": {}
}
```

### API Endpoints

- `GET /api/health` - Health check
- `GET /api/tools` - List available MCP tools
- `POST /api/search/code` - Code search
- `POST /api/search/doc` - Documentation search
- `POST /api/search/symbol` - Symbol lookup
- `GET /api/stats` - System statistics

## 🛠️ Development

### Project Structure

```
Codex7/
├── python/                 # AI Processing Pipeline
│   ├── crawler/           # GitHub repository crawling
│   ├── extractor/         # Content extraction and cleaning
│   ├── chunking/          # Text chunking strategies
│   ├── embedding/         # Embedding generation
│   ├── vectordb/          # Vector database operations
│   ├── search/            # Hybrid search implementation
│   └── utils/             # Configuration and models
├── src/                   # TypeScript MCP Server
│   ├── mcp/              # MCP protocol implementation
│   ├── query/            # Database query clients
│   ├── server/           # Web server and API
│   ├── types/            # TypeScript type definitions
│   └── utils/            # Configuration and utilities
├── public/               # Web interface assets
└── data/                 # Processed data and cache
```

### Running Individual Pipeline Steps

```bash
# Crawl repositories only
python main.py --crawl

# Extract content only
python main.py --extract

# Generate embeddings only
python main.py --embed

# Store vectors only
python main.py --store

# Build search indices only
python main.py --index
```

### TypeScript Development

```bash
# Watch mode for development
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run tests
npm test
```

## 🔧 Configuration

### Python Configuration (python/.env)

```env
# GitHub API
GITHUB_TOKEN=your_github_token

# Vector Database
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_DATABASE=codex7

# Processing
MAX_REPOS=100
CHUNK_SIZE=512
MAX_FILE_SIZE_MB=1

# Models
BGE_MODEL_NAME=BAAI/bge-large-zh-v1.5
CODE_MODEL_NAME=jinaai/jina-embeddings-v2-base-code
```

### TypeScript Configuration (.env)

```env
# Server
PORT=3000
LOG_LEVEL=info

# Database
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_DATABASE=codex7
```

## 📊 Performance

- **Repositories Indexed**: 100+ top GitHub repositories
- **Content Chunks**: 1M+ code and documentation chunks
- **Search Latency**: <100ms for semantic search
- **Embedding Models**: BGE-large-zh-v1.5 (docs), Jina-v2-base-code (code)
- **Vector Database**: Milvus with HNSW indexing

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **BGE Team** for the excellent embedding models
- **Milvus** for the vector database
- **GitHub** for the API access
- **Model Context Protocol** for the integration standard
- **GitStar Ranking** for repository rankings
