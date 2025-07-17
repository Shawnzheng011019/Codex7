# 快速入门指南：图增强的代码 RAG 系统

本指南将引导您完成 Codex7 项目的设置和使用。这是一个先进的检索增强生成（RAG）系统，通过知识图谱增强，实现了对代码库深层次、结构化的理解。

### 先决条件

请确保您已安装以下软件：
- **Git**
- **Docker** 和 **Docker Compose**
- **Python** (3.9 或更高版本)
- **Node.js** (v18 或更高版本) 和 **npm**

---

### 第一步：安装与配置

**1. 克隆仓库**
```bash
git clone <your-repository-url>
cd Codex7
```

**2. 配置环境变量**
通过复制示例文件，在Python目录中创建一个 `.env` 文件：
```bash
cp python/env.example python/.env
```
现在，打开 `python/.env` 文件并填写必要的凭据。您至少应设置：
- `GITHUB_TOKEN`: 强烈建议使用 GitHub 个人访问令牌，以避免在抓取阶段触发 API 速率限制。
- `NEO4J_PASSWORD`: 您将用于 Neo4j 数据库的密码。
- `NEO4J_DATABASE`: 在 Neo4j 中使用的数据库名称（默认为 `neo4j`）。

**3. 安装依赖**
- **Python 依赖**:
  ```bash
  pip install -r python/requirements.txt
  ```
- **Node.js 依赖**:
  ```bash
  npm install
  ```

---

### 第二步：启动后端服务

我们使用 Docker 来运行所需的数据库（Milvus 和 Neo4j）。

**1. 启动数据库**
在项目根目录中运行以下命令：
```bash
docker-compose up -d
```
这将启动：
- **Milvus**: 一个用于语义搜索的向量数据库，在其默认端口上可用。
- **Neo4j**: 一个用于知识图谱存储和查询的图数据库。
  - **浏览器界面**: `http://localhost:7474`
  - **Bolt 端口**: `bolt://localhost:7687`
  - **登录凭据**: `neo4j` / `<your-neo4j-password>`

*注意：我们为 Neo4j 提供的 Docker 配置包含了 APOC 插件，推荐使用以获得最佳性能，但由于最近的代码改进，它已不再是强制要求。*

---

### 第三步：构建知识库

此步骤运行 Python 流水线，以抓取仓库、处理其内容，并填充向量和图数据库。

**1. 运行完整流水线**
使用 `--full-pipeline` 标志执行主要的 Python 脚本：
```bash
python python/main.py --full-pipeline
```
该脚本按顺序执行以下操作：
1.  `--crawl`: 发现并克隆顶级的 GitHub 仓库。
2.  `--extract`: 从克隆的仓库中读取所有相关文件的内容。
3.  `--chunk`: 将代码和文档分割成更小的、有意义的块。
4.  `--embed`: 使用嵌入模型将文本块转换为语义向量。
5.  `--store`: 将这些向量存储到 Milvus 数据库中。
6.  `--build-graph`: 解析代码的结构（类、函数、调用、继承）并将其存储到 Neo4j 数据库中。

**2. 验证数据 (可选)**
- **Neo4j**: 打开 Neo4j 浏览器 (`http://localhost:7474`)，登录并运行一个 Cypher 查询来查看图是否已创建：
  ```cypher
  MATCH (n) RETURN n LIMIT 25;
  ```
- **Milvus**: 您可以使用像 Attu 这样的 Milvus 客户端（未包含在 docker-compose 中）来验证集合是否已创建并填充了数据。

---

### 第四步：启动查询服务器

知识库构建完成后，启动主应用服务器。

**1. 运行服务器**
```bash
npm run dev
```
这将启动 MCP (Multi-Content Prompt) 服务器，通常在 `http://localhost:3000` 上。该服务器通过一个基于工具的 API 来提供系统查询功能。

---

### 第五步：查询系统

您现在可以使用任何 HTTP 客户端（如 `curl`）与服务器交互，调用其强大的搜索和查询工具。

**示例 1: 混合搜索 (带自动图谱扩展)**
提出一个自然语言问题。系统将自动使用知识图谱查找相关的技术术语，并将其添加到查询中以提高准确性。

- **请求**:
```bash
curl -X POST http://localhost:3000/api/mcp/request \
-H "Content-Type: application/json" \
-d '{
  "method": "tools/call",
  "params": {
    "name": "hybrid_search",
    "arguments": {
      "query": "混合搜索是如何实现的？"
    }
  }
}'
```

或者直接使用混合搜索API：
```bash
curl -X POST http://localhost:3000/api/search/hybrid \
-H "Content-Type: application/json" \
-d '{
  "query": "混合搜索是如何实现的？",
  "chunk_type": "both",
  "top_k": 10
}'
```
- **工作原理**: 系统在图谱中找到像 `HybridSearchService` 和 `hybrid-search.ts` 这样的术语，并在将查询发送到 Milvus 和 BM25 之前对其进行扩展。

**示例 2: 图遍历 (影响分析)**
直接向知识图谱提问，以找出对特定函数的更改可能会影响到哪些部分。

- **请求**:
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
- **工作原理**: Neo4j 从 `hybridSearch` 函数开始，反向追踪 `CALLS` 关系，以找到所有调用它的函数。

**示例 3: 图遍历 (类继承)**
追踪特定类的完整继承树。

- **请求**:
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
- **工作原理**: Neo4j 从 `MCPServer` 类开始，沿着 `INHERITS_FROM` 关系在继承层次结构中向上和向下追踪。
