# MCP Server 模块

MCP QA项目中的核心服务器模块，提供基于Model Context Protocol (MCP)的文档问答服务。该模块集成了文档解析、向量搜索、智能问答等功能，支持多种文档格式的处理和索引构建。

## 🚀 快速开始

### 启动服务器

```bash
# 在项目根目录下
make start                    # 启动默认配置的服务器
make mcp-server-start         # 明确启动 mcp_server 模块
make dev                      # 开发模式启动（前台运行）
```

### 环境配置

```bash
# 可选的环境变量配置
export MCP_HOST=0.0.0.0       # 服务器监听地址
export MCP_PORT=8020          # 服务器端口
export MCP_DEBUG=true         # 调试模式
export MCP_ALLOWED_DIRS=docs  # 安全白名单目录
```

### 安全目录配置

```bash
# 使用默认安全目录 (docs)
make start

# 自定义单个安全目录
make start MCP_SERVER_ALLOWED_DIRS="data"

# 自定义多个安全目录（逗号分隔）
make start MCP_SERVER_ALLOWED_DIRS="docs,data,tmp"

# 明确指定模块并配置安全目录
make mcp-server-start MCP_SERVER_ALLOWED_DIRS="custom,secure"

# 开发模式也支持安全目录参数
make dev MCP_SERVER_ALLOWED_DIRS="docs,test"
```

### 查看状态

```bash
make status                   # 查看服务器运行状态
make logs                     # 查看实时日志
make diagnose                 # 全面诊断服务器问题
make info                     # 查看详细配置信息
```

## 📁 目录结构

```
mcp_server/
├── README.md                 # 本文档
├── __init__.py              # 模块初始化
├── server.py                # 主服务器入口
├── config.py                # 配置管理
├── types.py                 # 类型定义
├── utils.py                 # 工具函数
├── exceptions.py            # 异常定义
├── cli.py                   # 命令行接口
│
├── api/                     # HTTP API接口
│   ├── __init__.py
│   └── http_server.py       # HTTP服务器实现
│
├── tools/                   # MCP工具集
│   ├── __init__.py
│   ├── file_ops.py          # 文件操作工具
│   ├── search.py            # 搜索工具
│   ├── parsers.py           # 解析工具
│   ├── cache.py             # 缓存工具
│   └── time.py              # 时间工具
│
├── parsers/                 # 文档解析器
│   ├── __init__.py
│   ├── base.py              # 解析器基类
│   ├── pdf.py               # PDF解析器
│   ├── docx.py              # Word文档解析器
│   ├── excel.py             # Excel解析器
│   ├── pptx.py              # PowerPoint解析器
│   ├── markdown.py          # Markdown解析器
│   ├── text.py              # 纯文本解析器
│   └── converters.py        # 格式转换器
│
├── indexing/                # 索引和搜索
│   ├── __init__.py
│   ├── manager.py           # 索引管理器
│   ├── embeddings.py        # 向量嵌入
│   ├── search.py            # 搜索引擎
│   └── storage.py           # 向量存储
│
├── security/                # 安全模块
│   ├── __init__.py
│   ├── permissions.py       # 权限管理
│   └── path_validator.py    # 路径验证
│
├── monitoring/              # 监控和日志
│   ├── __init__.py
│   └── logger.py            # 日志管理
│
└── storage/                 # 存储模块
    └── __init__.py
```

## 🔧 核心功能

### 1. 文档解析 (Parsers)
- **支持格式**: PDF, DOCX, XLSX, PPTX, Markdown, TXT
- **智能提取**: 自动提取文本、表格、图片信息
- **结构化处理**: 保持文档原有结构和格式
- **错误处理**: 完善的异常处理和错误恢复

### 2. 向量索引 (Indexing)
- **嵌入模型**: 支持多种向量嵌入模型
- **FAISS索引**: 高效的向量搜索和存储
- **增量更新**: 支持索引的增量构建和更新
- **多索引管理**: 支持多个独立的索引实例

### 3. 智能搜索 (Search)
- **语义搜索**: 基于向量相似度的语义搜索
- **关键词搜索**: 传统的关键词匹配搜索
- **混合搜索**: 结合语义和关键词的综合搜索
- **结果排序**: 智能的相关性排序算法

### 4. 安全控制 (Security)
- **路径验证**: 防止路径遍历攻击
- **权限控制**: 细粒度的文件访问权限
- **白名单机制**: 限制可访问的目录范围
- **访问日志**: 完整的访问审计日志

### 5. 监控日志 (Monitoring)
- **结构化日志**: JSON格式的结构化日志
- **性能监控**: 详细的性能指标记录
- **错误追踪**: 完整的错误堆栈追踪
- **彩色输出**: 开发友好的彩色日志输出

## 🛠️ MCP工具集

### 文件操作工具
- `list_directory`: 列出目录内容
- `read_file`: 读取文件内容
- `get_file_mtime`: 获取文件修改时间

### 文档解析工具
- `parse_pdf`: 解析PDF文档
- `parse_docx`: 解析Word文档
- `parse_excel`: 解析Excel表格
- `parse_pptx`: 解析PowerPoint演示文稿
- `parse_markdown`: 解析Markdown文档

### 搜索工具
- `search_documents`: 文档语义搜索
- `build_index`: 构建文档索引

### 缓存工具
- `cache_set`/`cache_get`: 内存缓存操作
- `file_cache`: 文件缓存功能
- `cache_stats`: 缓存统计信息

### 时间工具
- `get_current_time`: 获取当前时间
- `format_time`: 时间格式化
- `parse_time`: 时间解析

## ⚙️ 配置说明

### 服务器配置 (ServerConfig)
```python
HOST = "0.0.0.0"              # 监听地址
PORT = 8020                   # 监听端口
DEBUG = False                 # 调试模式
PROTOCOL_VERSION = "1.0"      # MCP协议版本
REQUEST_TIMEOUT = 120         # 请求超时时间(秒)
MAX_REQUEST_SIZE = 10485760   # 最大请求大小(10MB)
```

### 安全配置 (SecurityConfig)
```python
# 默认文档目录
DEFAULT_DOCS_DIR = "docs"

# 允许访问文件的目录（白名单）
ALLOWED_DIRS = ["docs"]       # 默认只允许访问docs目录
                              # 可通过 MCP_ALLOWED_DIRS 环境变量自定义
                              # 多个目录用逗号分隔："docs,data,tmp"

# 文件大小限制
MAX_FILE_SIZE = 104857600     # 最大文件大小(100MB)

# 支持的文件类型
SUPPORTED_TEXT_EXTENSIONS = [".txt", ".py", ".js", ".json", ".yaml", ".yml", ".xml", ".csv", ".log"]
SUPPORTED_DOCUMENT_EXTENSIONS = [".pdf", ".docx", ".doc", ".md", ".markdown"]
SUPPORTED_OFFICE_EXTENSIONS = [".xlsx", ".xls", ".pptx", ".ppt"]

# 路径安全设置
DENY_PATTERNS = [".*", "*/.*"]  # 拒绝访问隐藏文件和目录
```

### 索引配置 (IndexConfig)
```python
INDEX_DIR = "faiss_index"     # 索引存储目录
VECTOR_DIMENSION = 768        # 向量维度
INDEX_TYPE = "IVF_FLAT"      # 索引类型
NLIST = 100                   # 聚类中心数
```

### 嵌入配置 (EmbeddingConfig)
```python
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 32               # 批处理大小
MAX_LENGTH = 512              # 最大序列长度
DEVICE = "cpu"                # 运行设备
```

## 🛡️ 安全目录配置详解

### 配置方式优先级

1. **命令行参数** (最高优先级)
   ```bash
   make start MCP_SERVER_ALLOWED_DIRS="docs,data,tmp"
   ```

2. **环境变量**
   ```bash
   export MCP_ALLOWED_DIRS="docs,secure"
   make start
   ```

3. **默认配置** (最低优先级)
   ```bash
   # 使用默认的 docs 目录
   make start
   ```

### 安全目录示例

```bash
# 单个目录
make start MCP_SERVER_ALLOWED_DIRS="documents"

# 多个相对路径目录
make start MCP_SERVER_ALLOWED_DIRS="docs,data,uploads"

# 包含绝对路径（谨慎使用）
make start MCP_SERVER_ALLOWED_DIRS="docs,/safe/shared/files"

# 开发环境配置
make dev MCP_SERVER_ALLOWED_DIRS="docs,test,samples"

# 结合其他配置参数
make start MCP_SERVER_ALLOWED_DIRS="docs,data" MCP_SERVER_PORT=8021 MCP_SERVER_DEBUG=true
```

### 配置验证

启动后可在日志中确认配置：
```
2025-07-27 04:27:41 - __main__ - INFO - 白名单目录: ['docs', 'data', 'tmp']
```

或使用诊断命令查看完整配置：
```bash
make info  # 查看当前配置信息
make diagnose  # 全面诊断系统状态
```

## 🚨 注意事项

### 性能优化
1. **内存管理**: 大文件处理时注意内存使用，建议设置合适的文件大小限制
2. **批处理**: 大量文档索引时建议使用批处理模式
3. **缓存策略**: 合理配置缓存大小，避免内存溢出
4. **并发控制**: 服务器支持异步处理，但要注意资源竞争

### 安全考虑
1. **安全目录配置**: 
   - 谨慎配置白名单目录，只允许访问确实需要的目录
   - 避免使用根目录（/）或用户主目录作为白名单目录
   - 优先使用相对路径，避免绝对路径配置
   - 定期审查和更新安全目录列表

2. **路径安全**: 
   - 严格限制可访问的目录范围，使用白名单机制
   - 服务器会自动阻止路径遍历攻击（../）
   - 隐藏文件和目录默认被拒绝访问

3. **文件验证**: 
   - 对上传的文件进行类型和大小验证
   - 只允许预定义的安全文件扩展名
   - 设置合理的文件大小限制（默认100MB）

4. **权限控制**: 
   - 确保服务器运行用户具有适当的文件访问权限
   - 不要以root用户运行服务器

5. **网络安全**: 
   - 生产环境建议配置防火墙和访问控制
   - 考虑使用HTTPS加密传输
   - 限制监听地址，避免不必要的外部访问

### 故障排除
1. **端口冲突**: 确保配置的端口未被其他程序占用
2. **依赖问题**: 检查Python依赖是否正确安装
3. **权限问题**: 确保对日志目录和索引目录有写入权限
4. **内存不足**: 大文件处理可能需要更多内存
5. **安全目录配置问题**:
   - **目录不存在**: 确保指定的安全目录实际存在
   - **权限拒绝**: 确保服务器进程有权访问指定目录
   - **路径格式**: 使用正确的路径分隔符（Unix: /，Windows: \）
   - **配置验证**: 检查日志中的"白名单目录"信息确认配置是否正确
   ```bash
   # 查看当前配置
   make info
   
   # 诊断配置问题
   make diagnose
   
   # 查看启动日志
   make logs-static | grep "白名单目录"
   ```

### 开发调试
1. **调试模式**: 使用 `DEBUG=true` 启用详细日志
2. **日志查看**: 使用 `make logs` 查看实时日志
3. **性能分析**: 开启性能监控获取详细指标
4. **错误追踪**: 查看异常日志定位问题根源

## 📚 API 接口

### HTTP 接口
- `GET /health`: 健康检查
- `POST /parse`: 文档解析
- `POST /search`: 文档搜索
- `POST /index`: 构建索引

### MCP 工具接口
所有工具都通过MCP协议暴露，客户端可以通过MCP客户端库调用。

## 🔍 监控和维护

### 日志文件
- **位置**: `logs/mcp_server.log`
- **格式**: 结构化JSON或彩色文本
- **轮转**: 支持日志轮转和归档

### 性能指标
- **响应时间**: 各API接口的响应时间
- **内存使用**: 服务器内存使用情况
- **索引大小**: 向量索引的存储大小
- **缓存命中率**: 缓存系统的命中率

### 健康检查
```bash
# 服务器状态检查
make status

# 网络连接测试
make test-server

# 全面诊断
make diagnose
```

## 🤝 贡献指南

1. 遵循现有的代码结构和命名规范
2. 新增功能需要完整的类型注解
3. 添加相应的异常处理和日志记录
4. 编写必要的单元测试
5. 更新相关文档

## 📄 许可证

本项目遵循项目根目录的许可证条款。