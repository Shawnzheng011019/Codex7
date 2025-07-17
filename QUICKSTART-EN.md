# Quickstart Guide: Graph-Enhanced RAG for Code

This guide will walk you through setting up and using the Codex7 project, a sophisticated RAG (Retrieval-Augmented Generation) system enhanced with a Knowledge Graph to provide deep, structural understanding of codebases.

### Prerequisites

Ensure you have the following software installed:
- **Git**
- **Docker** and **Docker Compose**
- **Python** (3.9 or higher)
- **Node.js** (v18 or higher) and **npm**

---

### Step 1: Installation & Configuration

**1. Clone the Repository**
```bash
git clone <your-repository-url>
cd Codex7
```

**2. Configure Environment Variables**
Create a `.env` file in the Python directory by copying the example file:
```bash
cp python/env.example python/.env
```
Now, open the `python/.env` file and fill in the necessary credentials. At a minimum, you should set:
- `GITHUB_TOKEN`: A GitHub Personal Access Token is highly recommended for avoiding API rate limits during the crawling phase.
- `NEO4J_PASSWORD`: The password you will use for the Neo4j database.
- `NEO4J_DATABASE`: The database name to use within Neo4j (defaults to `neo4j`).

**3. Install Dependencies**
- **Python Dependencies**:
  ```bash
  pip install -r python/requirements.txt
  ```
- **Node.js Dependencies**:
  ```bash
  npm install
  ```

---

### Step 2: Launching Backend Services

We use Docker to run the required databases (Milvus and Neo4j).

**1. Start the Databases**
Run the following command from the project root:
```bash
docker-compose up -d
```
This will start:
- **Milvus**: A vector database for semantic search, available on its default ports.
- **Neo4j**: A graph database for knowledge graph storage and queries.
  - **Browser UI**: `http://localhost:7474`
  - **Bolt Port**: `bolt://localhost:7687`
  - **Credentials**: `neo4j` / `<your-neo4j-password>`

*Note: The provided Docker setup for Neo4j includes the APOC plugin, which is recommended for optimal performance but no longer a hard requirement thanks to recent code improvements.*

---

### Step 3: Building the Knowledge Base

This step runs the Python pipeline to crawl repositories, process their content, and populate both the vector and graph databases.

**1. Run the Full Pipeline**
Execute the main Python script with the `--full-pipeline` flag:
```bash
python python/main.py --full-pipeline
```
This script performs the following sequence of operations:
1.  `--crawl`: Discovers and clones top GitHub repositories.
2.  `--extract`: Reads the content of all relevant files from the cloned repos.
3.  `--chunk`: Splits code and documents into smaller, meaningful chunks.
4.  `--embed`: Converts text chunks into semantic vectors using an embedding model.
5.  `--store`: Stores these vectors in the Milvus database.
6.  `--build-graph`: Parses the code's structure (classes, functions, calls, inheritance) and stores it in the Neo4j database.

**2. Verify the Data (Optional)**
- **Neo4j**: Open the Neo4j Browser (`http://localhost:7474`), log in, and run a Cypher query to see if the graph was created:
  ```cypher
  MATCH (n) RETURN n LIMIT 25;
  ```
- **Milvus**: You can use a Milvus client like Attu (not included in docker-compose) to verify that collections have been created and populated.

---

### Step 4: Starting the Query Server

Now that the knowledge base is built, start the main application server.

**1. Run the Server**
```bash
npm run dev
```
This will start the MCP (Multi-Content Prompt) server, typically on `http://localhost:3000`. The server exposes a tool-based API for querying the system.

---

### Step 5: Querying the System

You can now interact with the server using any HTTP client (like `curl`) to call its powerful search and query tools.

**Example 1: Hybrid Search (with Automatic Graph Expansion)**
Ask a natural language question. The system will automatically use the knowledge graph to find relevant technical terms and add them to the query for better accuracy.

- **Request**:
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "hybrid_search",
    "arguments": {
      "query": "how is the hybrid search implemented?"
    }
  }
}'
```

Or use the direct hybrid search API:
```bash
curl -X POST http://localhost:3000/api/search/hybrid \
-H "Content-Type: application/json" \
-d '{
  "query": "how is the hybrid search implemented?",
  "chunk_type": "both",
  "top_k": 10
}'
```
- **What Happens**: The system finds terms like `HybridSearchService` and `hybrid-search.ts` in the graph and expands the query before sending it to Milvus and BM25.

**Example 2: Graph Traversal (Impact Analysis)**
Ask the knowledge graph directly to find out what might be affected by a change to a specific function.

- **Request**:
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "graph_query",
    "arguments": {
      "query_type": "downstream_impact",
      "entity_name": "hybridSearch"
    }
  }
}'
```
- **What Happens**: Neo4j traces the `CALLS` relationships backwards from the `hybridSearch` function to find all functions that call it.

**Example 3: Graph Traversal (Class Inheritance)**
Trace the full inheritance tree for a specific class.

- **Request**:
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "graph_query",
    "arguments": {
      "query_type": "inheritance_chain",
      "entity_name": "MCPServer"
    }
  }
}'
```
- **What Happens**: Neo4j follows the `INHERITS_FROM` relationships up and down the hierarchy from the `MCPServer` class.

```