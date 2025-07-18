# 快速入门指南：基于 TypeScript 的本地代码库 RAG 系统

本指南将引导您完成 Codex7 项目的设置和使用。这是一个完全基于 TypeScript 构建的先进 RAG（检索增强生成）系统，专门用于分析和搜索本地代码库，并通过知识图谱进行增强。

## 前置要求

请确保您已安装以下软件：
- **Node.js**（v18 或更高版本）和 **npm**
- **Git**
- **Docker** 和 **Docker Compose**（用于数据库）

---

## 第一步：安装与配置

### 1. 克隆仓库
```bash
git clone <your-repository-url>
cd Codex7
```

### 2. 安装依赖
```bash
npm install
```

### 3. 配置环境变量
通过复制示例文件创建 `.env` 文件：
```bash
cp env.example .env
```

编辑 `.env` 文件，填入您的配置：
```env
# 服务器配置
PORT=3000
LOG_LEVEL=info

# 数据库配置
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_DATABASE=codex7_local

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# 嵌入模型配置
DEFAULT_EMBEDDING_PROVIDER=openai  # 或 'huggingface', 'local'
DEFAULT_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your_openai_api_key

# 处理配置
MAX_FILE_SIZE_MB=5
MAX_PROJECT_SIZE_MB=500
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=200
```

---

## 第二步：启动后端服务

### 1. 启动所需数据库
使用 Docker 启动 Milvus（向量数据库）和 Neo4j（图数据库）：

**方法 A：使用 Docker Compose（推荐）**
```bash
# 创建或使用提供的 docker-compose.yml 文件
docker-compose up -d
```

**方法 B：手动 Docker 设置**
```bash
# 启动 Milvus
docker run -d --name milvus-standalone -p 19530:19530 -p 9091:9091 milvusdb/milvus:latest

# 启动 Neo4j
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_neo4j_password \
  neo4j:latest
```

### 2. 验证数据库连接
- **Milvus**：在端口 19530 上可用（默认无 Web UI）
- **Neo4j**：
  - Web 界面：`http://localhost:7474`
  - Bolt 连接：`bolt://localhost:7687`
  - 登录凭据：`neo4j` / `your_neo4j_password`

---

## 第三步：启动应用程序

### 1. 开发模式（推荐）
```bash
npm run dev
```
这将在 `http://localhost:3000` 上启动带有自动重载功能的 MCP 服务器。

### 2. 生产模式
```bash
npm run build
npm start
```

### 3. 验证服务器运行状态
检查服务器是否正常响应：
```bash
curl http://localhost:3000/health
```

---

## 第四步：索引您的第一个项目

### 方法 1：使用 MCP API

**首先扫描项目：**
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

**索引项目：**
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

### 方法 2：使用直接 TypeScript 脚本

您也可以直接运行各个组件：

```bash
# 扫描和处理本地代码库
tsx src/scanner/local-codebase-scanner.ts --project-path /path/to/your/project

# 处理内容并生成嵌入
tsx src/processor/content-processor.ts --project my-awesome-project

# 构建知识图谱
tsx src/graph/graph-query-service.ts --build-graph my-awesome-project
```

---

## 第五步：搜索和查询

### 1. 混合搜索（结合向量 + BM25）
在代码和文档中搜索：
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

### 2. 代码专用搜索
查找特定的代码模式：
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

### 3. 文档搜索
在 README 文件、注释和文档中搜索：
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

### 4. 知识图谱查询

**查找依赖关系和影响分析：**
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

**查找特定符号：**
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

## 第六步：高级使用

### 1. 多项目支持
索引多个项目以进行跨项目搜索：
```bash
# 索引项目 A
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

# 索引项目 B
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

# 跨所有项目搜索（省略 project 参数）
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

### 2. 配置不同的嵌入提供商

**切换到 Hugging Face：**
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

**使用本地嵌入（用于开发）：**
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

### 3. 监控和管理项目

**列出所有已索引的项目：**
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

**获取项目文件列表：**
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

## 故障排除

### 常见问题

**1. 数据库连接错误**
- 确保 Milvus 在端口 19530 上运行
- 检查 Neo4j 在端口 7687 上可访问
- 验证 `.env` 文件中的凭据

**2. 嵌入提供商问题**
- 验证 OpenAI/Hugging Face 的 API 密钥
- 检查速率限制和配额
- 使用本地提供商进行测试

**3. 内存问题**
- 为大型项目减少 `MAX_PROJECT_SIZE_MB`
- 将 `DEFAULT_CHUNK_SIZE` 调整为较小值
- 监控系统内存使用情况

**4. 性能问题**
- 为数据库使用 SSD 存储
- 逐步增加 `MAX_SEARCH_RESULTS`
- 考虑使用更快的嵌入模型

### 调试模式
启用详细日志记录：
```env
LOG_LEVEL=debug
```

### 健康检查
```bash
# 检查服务器健康状态
curl http://localhost:3000/health

# 检查数据库连接
curl http://localhost:3000/api/health/databases
```

---

## 后续步骤

1. **与 AI IDE 集成**：使用 MCP 协议连接 Claude、GPT 或其他 AI 助手
2. **自定义搜索**：在配置中调整搜索权重和算法
3. **添加更多项目**：索引您的整个代码库以进行全面搜索
4. **探索图查询**：使用 Neo4j 浏览器探索代码关系
5. **性能调优**：为您的用例优化嵌入模型和数据库设置

## 支持

- 查看主要的 [README.md](README.md) 获取详细文档
- 查看 `src/` 目录中的 TypeScript 源代码
- 启用调试日志记录进行故障排除
- 在项目仓库中开启 issue
