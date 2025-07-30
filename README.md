# Code Retrieval System - MCP Server

A comprehensive code retrieval system built in Python that combines vector search with graph-based relationships for intelligent code analysis and search, implemented as a Model Context Protocol (MCP) server.

## 🌟 Features

- **🔍 Local Codebase Analysis**: Scan and index your local projects for intelligent search
- **📚 Multi-Content Support**: Analyze code, documentation, configuration files, and more
- **⚡ Semantic Search**: Advanced hybrid search combining vector similarity and BM25
- **🤖 MCP Integration**: Model Context Protocol server for seamless AI IDE integration
- **🎯 Multi-language Support**: AST Splitter for JavaScript, TypeScript, Python, Go, Rust, Java, C++, and more
- **📊 Knowledge Graph**: Build code dependency graphs for impact analysis
- **🗄️ Milvus Vector Database**: High-performance vector similarity search
- **🕸️ Neo4j Graph Database**: Rich relationship modeling and querying

## 🏗️ Architecture

The system is built entirely in Python with a clean, modular architecture:

### Core Components
- **Scanner**: Local codebase file system scanner (`src/scanner/`)
- **Processor**: Content chunking and embedding generation (`src/processor/`)
- **Vector Database**: Milvus client for fast similarity search (`src/query/`)
- **Graph Database**: Neo4j client for code relationships (`src/graph/`)
- **Embedding Service**: OpenAI embedding generation optimized for Milvus (`src/embedding/`)
- **Search Engine**: Hybrid search with BM25 and reranking (`src/search/`)
- **MCP Server**: FastMCP-based server for AI tool integration (`src/mcp/`)

### Processing Pipeline
1. **Scan** → Discover and categorize local project files
2. **Extract** → Parse code and documentation content
3. **Chunk** → Intelligent text segmentation with context preservation
4. **Embed** → Generate semantic embeddings using OpenAI
5. **Index** → Store in Milvus vector database and Neo4j graph database
6. **Search** → Hybrid search with reranking for optimal results

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker (for Milvus and Neo4j)
- OpenAI API key for embeddings

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd code-retrieval-system
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your OpenAI API key and database settings
```

4. Start databases with Docker:
```bash
docker-compose up -d
```

5. Run the MCP server:
```bash
# Using stdio transport (default)
python main.py --stdio

# Using SSE transport
python main.py --sse --port 8000
```

### Configuration

Edit the `.env` file to configure:

- **Database Settings**: Milvus and Neo4j connection parameters
- **OpenAI Settings**: API key and embedding model
- **Search Parameters**: BM25 weights, reranking thresholds
- **File Processing**: Chunk sizes, supported extensions

## 📖 MCP Tools

The system provides the following MCP tools:

### Core Tools
- `index_codebase` - Index a codebase for search
- `search_code` - Hybrid search with reranking
- `search_in_file` - Search within specific files
- `clear_database` - Clear all data from databases

### Graph Analysis Tools
- `get_function_dependencies` - Get function dependency graph
- `get_class_hierarchy` - Get class inheritance hierarchy
- `get_file_structure` - Get file structure analysis

### System Tools
- `get_system_stats` - Get system statistics and health

### Example Usage

#### Index a Codebase
```python
# Using MCP client
result = await client.call_tool("index_codebase", {
    "root_path": "/path/to/your/code",
    "max_workers": 4
})
```

#### Search Code
```python
# Using MCP client
result = await client.call_tool("search_code", {
    "query": "how to implement authentication",
    "top_k": 10,
    "use_graph": true,
    "use_reranking": true
})
```

#### Get Function Dependencies
```python
# Using MCP client
result = await client.call_tool("get_function_dependencies", {
    "function_name": "user.authenticate"
})
```

#### Search in File
```python
# Using MCP client
result = await client.call_tool("search_in_file", {
    "file_path": "src/main.py",
    "query": "database connection"
})
```

## 🔧 Advanced Configuration

### OpenAI Embeddings
```env
# Required for vector search
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=text-embedding-ada-002
```

### Search Parameters

- `BM25_K1`: BM25 parameter for term frequency saturation (default: 1.2)
- `BM25_B`: BM25 parameter for document length normalization (default: 0.75)
- `TOP_K_RESULTS`: Number of results to return (default: 10)
- `RERANK_THRESHOLD`: Threshold for graph-based reranking (default: 0.5)

## 🛠️ Development

### Project Structure
```
code-retrieval-system/
├── src/
│   ├── config.py              # Configuration management
│   ├── types.py               # Data models and types
│   ├── scanner/               # File system scanning
│   ├── processor/             # Content processing and chunking
│   ├── query/                 # Vector database (Milvus)
│   ├── graph/                 # Graph database (Neo4j)
│   ├── embedding/             # OpenAI embedding service
│   ├── search/                # Search and reranking
│   ├── mcp/                   # FastMCP server
│   └── utils/                 # Utilities and logging
├── main.py                    # MCP server entry point
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Database setup
├── .env.example              # Environment template
└── README.md                 # This file
```

### Testing

Run tests with:
```bash
pytest tests/
```

### Code Quality

```bash
# Format code
black src/

# Lint code
flake8 src/

# Type checking
mypy src/
```

## 📊 Performance

The system is designed for performance with:

- **Parallel Processing**: Multi-threaded file scanning and processing
- **Efficient Indexing**: Optimized chunking and OpenAI embedding generation
- **Fast Search**: Milvus vector similarity search with BM25 fallback
- **Graph Acceleration**: Neo4j for relationship queries
- **Caching**: Intelligent caching for frequently accessed data

## 🔍 Search Flow

The search process follows this sophisticated flow:

1. **Vector Search**: Semantic similarity using OpenAI embeddings in Milvus
2. **BM25 Search**: Keyword-based exact matching
3. **Hybrid Combination**: Weighted combination of both approaches
4. **Graph Enhancement**: Enrich results with code relationships
5. **Reranking**: Reorder results based on graph context
6. **Final Ranking**: Produce optimally ordered results

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Milvus for vector database capabilities
- Neo4j for graph database functionality
- OpenAI for embedding services
- FastMCP for MCP server framework
- The open-source community for various tools and libraries