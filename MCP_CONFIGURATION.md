# Codex7 MCP 配置指南

## 📋 概述

Codex7 是一个本地代码库RAG系统，现已修复JSON-RPC 2.0协议兼容性问题。此指南将指导您在Cursor或其他MCP平台中正确配置。

## 🔧 在 Cursor 中配置

### 1. 创建MCP配置文件

**位置 (macOS/Linux):**
```
~/.config/claude-desktop/claude_desktop_config.json
```

**位置 (Windows):**
```
%APPDATA%\Claude\claude_desktop_config.json
```

### 2. 配置文件内容

```json
{
  "mcpServers": {
    "codex7-local-rag": {
      "command": "node",
      "args": ["/Users/zilliz/Codex7/dist/index.js"],
      "env": {
        "OPENAI_API_KEY": "your_openai_api_key_here",
        "MILVUS_HOST": "localhost",
        "MILVUS_PORT": "19530",
        "MILVUS_DATABASE": "codex7_local",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "codex7password",
        "PORT": "3000",
        "EMBEDDING_PROVIDER": "openai",
        "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small"
      }
    }
  }
}
```

## 🚀 部署步骤

### 1. 安装依赖
```bash
cd /Users/zilliz/Codex7
npm install
```

### 2. 环境配置
```bash
cp env.example .env
# 编辑 .env 文件，设置您的API密钥和数据库配置
```

### 3. 启动数据库
```bash
docker-compose up -d
```

### 4. 构建和启动
```bash
npm run build
npm start
```

## 🛠️ 可用的MCP工具

Codex7 提供6个核心工具，涵盖代码库索引、搜索、分析等核心功能：

### 1. **`index_codebase`** - 代码库索引

扫描并索引本地代码库，自动进行文件扫描、内容分块、向量嵌入和存储。

```json
{
  "name": "index_codebase",
  "arguments": {
    "project_path": "/path/to/your/project",
    "project_name": "my-project"
  }
}
```

**参数说明：**
- `project_path`: 项目目录路径（必需）
- `project_name`: 项目名称（可选，默认使用目录名）

### 2. **`search_codebase`** - 混合搜索

使用混合搜索（向量+BM25）和知识图谱增强，搜索已索引的代码库。

```json
{
  "name": "search_codebase",
  "arguments": {
    "query": "authentication function",
    "project": "my-project",
    "language": "TypeScript",
    "content_type": "both",
    "top_k": 20
  }
}
```

**参数说明：**
- `query`: 搜索查询（必需）
- `project`: 指定项目名称（可选，不提供则搜索所有项目）
- `language`: 编程语言过滤（可选）
- `content_type`: 内容类型 - `code`、`doc`、`both`（可选，默认both）
- `top_k`: 返回结果数量（可选，默认20）

### 3. **`search_code`** - 代码搜索

专门搜索代码片段，自动过滤为代码内容。

```json
{
  "name": "search_code",
  "arguments": {
    "query": "async function error handling",
    "project": "my-project",
    "language": "TypeScript",
    "top_k": 10
  }
}
```

**参数说明：**
- `query`: 代码搜索查询（必需）
- `project`: 指定项目（可选）
- `language`: 编程语言过滤（可选）
- `top_k`: 返回结果数量（可选，默认10）

### 4. **`search_docs`** - 文档搜索

专门搜索文档内容，如README、注释等。

```json
{
  "name": "search_docs",
  "arguments": {
    "query": "installation guide",
    "project": "my-project",
    "top_k": 10
  }
}
```

**参数说明：**
- `query`: 文档搜索查询（必需）
- `project`: 指定项目（可选）
- `top_k`: 返回结果数量（可选，默认10）

### 5. **`analyze_dependencies`** - 依赖分析

使用知识图谱分析代码实体的依赖关系和影响范围。

```json
{
  "name": "analyze_dependencies",
  "arguments": {
    "entity_name": "UserService",
    "max_hops": 5
  }
}
```

**参数说明：**
- `entity_name`: 要分析的函数、类或变量名称（必需）
- `max_hops`: 最大依赖跟踪跳数（可选，默认5）

### 6. **`find_symbol`** - 符号查找

查找特定的符号（函数、类、变量）在项目中的定义和使用。

```json
{
  "name": "find_symbol",
  "arguments": {
    "symbol_name": "authenticate",
    "project": "my-project"
  }
}
```

**参数说明：**
- `symbol_name`: 符号名称（必需）
- `project`: 指定项目（可选）

## 🔍 修复的问题

### JSON-RPC 2.0 协议支持
- ✅ 正确的 `jsonrpc: "2.0"` 字段
- ✅ 必需的 `id` 字段处理
- ✅ 标准的错误响应格式
- ✅ 初始化协议支持

### MCP协议兼容性
- ✅ `initialize` 方法处理
- ✅ `notifications/initialized` 支持
- ✅ `tools/list` 标准响应
- ✅ `tools/call` 正确调用

## 🔧 在其他平台配置

### VS Code 扩展
```json
{
  "mcp.servers": [
    {
      "name": "codex7-local-rag",
      "command": "node",
      "args": ["/Users/zilliz/Codex7/dist/index.js"],
      "cwd": "/Users/zilliz/Codex7"
    }
  ]
}
```

### 自定义MCP客户端
```typescript
import { MCPClient } from '@modelcontextprotocol/sdk/client/index.js';

const client = new MCPClient({
  name: "codex7-client",
  version: "1.0.0"
});

await client.connect({
  command: "node",
  args: ["/Users/zilliz/Codex7/dist/index.js"]
});
```

## ✅ 验证配置

### 1. 检查服务器启动
```bash
# 检查MCP服务器是否正常启动
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' | node dist/index.js
```

### 2. 检查工具列表
```bash
# 检查可用工具
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | node dist/index.js
```

### 3. 测试代码库索引
```bash
# 测试索引功能
echo '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"index_codebase","arguments":{"project_path":"/Users/zilliz/Codex7"}}}' | node dist/index.js
```

## ⚠️ 故障排除

### 常见错误及解决方案

1. **"Unexpected non-whitespace character after JSON"**
   - ✅ 已修复：确保输出正确的JSON格式

2. **"Invalid literal value, expected '2.0'"**
   - ✅ 已修复：添加正确的JSON-RPC版本字段

3. **"Required" 错误**
   - ✅ 已修复：添加必需的id字段处理

### 检查日志
```bash
# 查看详细日志
LOG_LEVEL=debug npm start
```

## 🎯 最佳实践

1. **确保数据库运行**: 先启动Milvus和Neo4j
2. **设置API密钥**: 配置正确的OpenAI API密钥
3. **逐步索引**: 先用`index_codebase`索引小项目测试功能
4. **合理使用搜索**: 根据需求选择合适的搜索工具
5. **监控内存**: 大项目可能需要较多内存
6. **定期清理**: 清理不需要的索引数据

## 📞 支持

如果您在配置过程中遇到问题：
1. 检查环境变量配置
2. 验证数据库连接
3. 查看日志输出
4. 确认API密钥有效

配置完成后，您就可以在Cursor或其他MCP客户端中使用强大的本地代码库RAG功能了！ 