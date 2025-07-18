# Quickstart Guide: Local Codebase RAG with TypeScript

This guide will walk you through setting up and using Codex7, a sophisticated RAG (Retrieval-Augmented Generation) system built entirely in TypeScript for analyzing and searching local codebases with knowledge graph enhancement.

## Prerequisites

Ensure you have the following software installed:
- **Node.js** (v18 or higher) and **npm**
- **Git**
- **Docker** and **Docker Compose** (for databases)

---

## Step 1: Installation & Configuration

### 1. Clone the Repository
```bash
git clone <your-repository-url>
cd Codex7
```

### 2. Install Dependencies
```bash
npm install
```

### 3. Configure Environment Variables
Create a `.env` file by copying the example:
```bash
cp env.example .env
```

Edit the `.env` file with your settings:
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
NEO4J_PASSWORD=your_neo4j_password

# Embedding Configuration
DEFAULT_EMBEDDING_PROVIDER=openai  # or 'huggingface', 'local'
DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your_openai_api_key

# Processing Configuration
MAX_FILE_SIZE_MB=5
MAX_PROJECT_SIZE_MB=500
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=200
```

---

## Step 2: Launch Backend Services

### 1. Start Required Databases
Use Docker to start Milvus (vector database) and Neo4j (graph database):

**Option A: Using Docker Compose (Recommended)**
```bash
# Create a docker-compose.yml file or use the provided one
docker-compose up -d
```

**Option B: Manual Docker Setup**
```bash
# Start Milvus
docker run -d --name milvus-standalone -p 19530:19530 -p 9091:9091 milvusdb/milvus:latest

# Start Neo4j
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_neo4j_password \
  neo4j:latest
```

### 2. Verify Database Connections
- **Milvus**: Available on port 19530 (no web UI by default)
- **Neo4j**: 
  - Web interface: `http://localhost:7474`
  - Bolt connection: `bolt://localhost:7687`
  - Credentials: `neo4j` / `your_neo4j_password`

---

## Step 3: Start the Application

### 1. Development Mode (Recommended)
```bash
npm run dev
```
This starts the MCP server with auto-reload on `http://localhost:3000`.

### 2. Production Mode
```bash
npm run build
npm start
```

### 3. Verify Server is Running
Check that the server is responding:
```bash
curl http://localhost:3000/health
```

---

## Step 4: Index Your First Project

### Method 1: Using MCP API

**Scan a project first:**
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "scan_project",
    "arguments": {
      "project_path": "/path/to/your/project",
      "project_name": "my-awesome-project"
    }
  }
}'
```

**Index the project:**
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "index_project",
    "arguments": {
      "project_path": "/path/to/your/project",
      "project_name": "my-awesome-project",
      "embedding_provider": "openai",
      "embedding_model": "text-embedding-3-small"
    }
  }
}'
```

### Method 2: Using Direct TypeScript Scripts

You can also run individual components directly:

```bash
# Scan and process a local codebase
tsx src/scanner/local-codebase-scanner.ts --project-path /path/to/your/project

# Process content and generate embeddings
tsx src/processor/content-processor.ts --project my-awesome-project

# Build knowledge graph
tsx src/graph/graph-query-service.ts --build-graph my-awesome-project
```

---

## Step 5: Search and Query

### 1. Hybrid Search (Combines Vector + BM25)
Search across code and documentation:
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "search_codebase",
    "arguments": {
      "query": "authentication middleware function",
      "project": "my-awesome-project",
      "top_k": 10
    }
  }
}'
```

### 2. Code-Specific Search
Find specific code patterns:
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "search_code",
    "arguments": {
      "query": "async function error handling try catch",
      "language": "TypeScript",
      "top_k": 5
    }
  }
}'
```

### 3. Documentation Search
Search through README files, comments, and docs:
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "search_docs",
    "arguments": {
      "query": "installation setup guide",
      "project": "my-awesome-project"
    }
  }
}'
```

### 4. Knowledge Graph Queries

**Find dependencies and impact analysis:**
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "analyze_dependencies",
    "arguments": {
      "entity_name": "UserService",
      "max_hops": 3
    }
  }
}'
```

**Find specific symbols:**
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "find_symbol",
    "arguments": {
      "symbol_name": "authenticate",
      "project": "my-awesome-project"
    }
  }
}'
```

---

## Step 6: Advanced Usage

### 1. Multiple Projects
Index multiple projects for cross-project search:
```bash
# Index project A
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "index_project",
    "arguments": {
      "project_path": "/path/to/project-a",
      "project_name": "project-a"
    }
  }
}'

# Index project B
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "index_project",
    "arguments": {
      "project_path": "/path/to/project-b",
      "project_name": "project-b"
    }
  }
}'

# Search across all projects (omit project parameter)
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "search_codebase",
    "arguments": {
      "query": "database connection",
      "top_k": 20
    }
  }
}'
```

### 2. Configure Different Embedding Providers

**Switch to Hugging Face:**
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "configure_embedding",
    "arguments": {
      "provider": "huggingface",
      "model": "sentence-transformers/all-MiniLM-L6-v2",
      "api_key": "your_huggingface_api_key"
    }
  }
}'
```

**Use local embeddings (for development):**
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "configure_embedding",
    "arguments": {
      "provider": "local",
      "model": "mock"
    }
  }
}'
```

### 3. Monitor and Manage Projects

**List all indexed projects:**
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "get_indexed_projects",
    "arguments": {}
  }
}'
```

**Get project file list:**
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "get_project_files",
    "arguments": {
      "project": "my-awesome-project"
    }
  }
}'
```

---

## Troubleshooting

### Common Issues

**1. Database Connection Errors**
- Ensure Milvus is running on port 19530
- Check Neo4j is accessible on port 7687
- Verify credentials in `.env` file

**2. Embedding Provider Issues**
- Validate API keys for OpenAI/Hugging Face
- Check rate limits and quotas
- Use local provider for testing

**3. Memory Issues**
- Reduce `MAX_PROJECT_SIZE_MB` for large projects
- Adjust `DEFAULT_CHUNK_SIZE` to smaller values
- Monitor system memory usage

**4. Performance Issues**
- Use SSD storage for databases
- Increase `MAX_SEARCH_RESULTS` gradually
- Consider using faster embedding models

### Debug Mode
Enable detailed logging:
```env
LOG_LEVEL=debug
```

### Health Checks
```bash
# Check server health
curl http://localhost:3000/health

# Check database connections
curl http://localhost:3000/api/health/databases
```

---

## Next Steps

1. **Integrate with AI IDEs**: Use the MCP protocol to connect with Claude, GPT, or other AI assistants
2. **Customize Search**: Adjust search weights and algorithms in the configuration
3. **Add More Projects**: Index your entire codebase for comprehensive search
4. **Explore Graph Queries**: Use Neo4j browser to explore code relationships
5. **Performance Tuning**: Optimize embedding models and database settings for your use case

## Support

- Check the main [README.md](README.md) for detailed documentation
- Review TypeScript source code in the `src/` directory
- Enable debug logging for troubleshooting
- Open issues on the project repository
