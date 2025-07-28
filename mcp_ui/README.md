# MCP UI - 智能知识库交互界面

基于Chainlit构建的MCP (Model Context Protocol) 智能知识库交互界面，提供直观的Web界面来管理文档、构建索引、进行智能问答。

## 🌟 功能特性

### 🎯 核心功能
- **📁 文档管理**: 支持PDF、Word、Excel、PPT、Markdown等多种格式
- **🔍 智能搜索**: 基于向量相似度的语义搜索
- **🧠 多模型支持**: 统一支持本地和远程大语言模型
- **🌐 远程MCP**: 支持本地和远程MCP工具服务器
- **📊 过程可视化**: 实时展示思考和处理过程
- **🛠️ 工具集成**: 完整的MCP工具调用与状态反馈

### 🏗️ 架构特点
- **模块化设计**: 按功能分层的清晰架构
- **异步处理**: 高性能的异步IO处理
- **配置驱动**: 灵活的配置管理系统
- **适配器模式**: 可扩展的模型提供商支持
- **统一接口**: 屏蔽不同服务的API差异
- **日志追踪**: 完整的操作日志和错误追踪

### 🤖 支持的模型提供商
- **Ollama**: 本地大语言模型服务
- **OpenAI**: GPT系列模型（包括兼容接口）
- **Anthropic**: Claude系列模型
- **Google**: Gemini系列模型  
- **Azure**: Azure OpenAI服务
- **DeepSeek**: DeepSeek系列模型
- **Qwen**: 通义千问系列模型
- **自定义**: 支持添加新的模型适配器

### 🔗 支持的MCP服务器
- **本地MCP**: 项目内置的MCP服务器
- **远程MCP**: 支持HTTP API的远程MCP服务器
- **认证支持**: Bearer Token和API Key认证
- **多服务器**: 同时连接多个MCP服务器

## 🚀 快速开始

### 1. 环境准备
```bash
# 安装依赖
make install

# 启动Ollama服务 (macOS)
make ollama-start
```

### 2. 启动服务

#### 方式一：使用Makefile (推荐)
```bash
# 启动UI界面 (会自动启动MCP服务器)
make ui-start

# 或者以开发模式启动
make ui-dev
```

#### 方式二：直接运行
```bash
# 直接运行启动脚本
python start_ui.py
```

### 3. 访问界面
打开浏览器访问: http://localhost:8000

## 📖 使用指南

### 基本操作

1. **上传文档**: 使用界面上传按钮添加文档到知识库
2. **构建索引**: 执行 `/build` 命令构建文档索引
3. **智能问答**: 直接提问，系统会自动搜索相关内容并回答
4. **工具调用**: 使用 `/help` 查看所有可用命令

### 命令系统

#### 索引管理
- `/build [目录]` - 构建知识库索引 (默认: docs)
- `/search 关键词 [数量]` - 搜索文档内容

#### 文档处理
- `/parse 文件路径` - 解析单个文档
- `/list [目录路径]` - 列出目录内容
- `/read 文件路径` - 读取文件内容

#### 系统信息
- `/models` - 查看可用模型列表
- `/status` - 查看系统运行状态
- `/config` - 查看系统配置信息
- `/help` - 显示帮助信息

### 环境配置

#### 基础配置
```bash
# UI应用配置
export UI_HOST=0.0.0.0
export UI_PORT=8000
export UI_DEBUG=false

# 默认模型设置
export DEFAULT_PROVIDER=ollama  # ollama, openai, anthropic, google, azure, deepseek, qwen
export DEFAULT_MODEL=qwen3:4b
```

#### 远程模型配置

**统一JSON配置方式（推荐）**：
```bash
# 所有远程模型使用统一JSON配置
export REMOTE_MODELS='[
  {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://api.openai.com/v1"
  },
  {
    "provider": "anthropic", 
    "model": "claude-3-sonnet-20240229",
    "api_key": "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  },
  {
    "provider": "google",
    "model": "gemini-pro", 
    "api_key": "AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  },
  {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://api.deepseek.com"
  },
  {
    "provider": "qwen",
    "model": "qwen-turbo",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
  },
  {
    "provider": "azure",
    "model": "gpt-4",
    "api_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://your-resource.openai.azure.com/",
    "api_version": "2024-02-15-preview"
  }
]'
```

**向后兼容的单独配置**：
```bash
# OpenAI配置
export OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export OPENAI_MODEL=gpt-4

# Anthropic配置  
export ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Google配置
export GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export GOOGLE_MODEL=gemini-pro

# Azure配置
export AZURE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export AZURE_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_DEPLOYMENT=gpt-4
```

#### 远程MCP服务器配置
```bash
# 远程MCP服务器（JSON格式）  
export REMOTE_MCP_SERVERS='[
  {
    "name": "remote-qa",
    "url": "https://api.example.com/mcp",
    "api_key": "your-api-key",
    "enabled": true
  }
]'
```

更多配置选项请参考 [CONFIG_EXAMPLES.md](./CONFIG_EXAMPLES.md)。

## 🏗️ 项目结构

```
mcp_ui/
├── __init__.py              # 模块初始化
├── app.py                   # 主应用文件
├── CONFIG_EXAMPLES.md       # 配置示例文档
├── clients/                 # 客户端模块
│   ├── mcp_client.py        # MCP服务器客户端
│   ├── ollama_client.py     # Ollama客户端（兼容性）
│   ├── model_adapter.py     # 统一模型适配器系统
│   └── client_manager.py    # 客户端管理器
├── config/                  # 配置模块
│   └── settings.py          # 配置管理和枚举
├── handlers/                # 命令处理器
│   ├── base.py              # 基础处理器和注册表
│   ├── index_handlers.py    # 索引管理处理器
│   ├── document_handlers.py # 文档处理处理器
│   └── system_handlers.py   # 系统信息处理器
└── utils/                   # 工具模块
    └── logger.py            # 日志工具和追踪
```

## 🔧 Makefile 命令

### UI模块命令
```bash
# 启动/停止UI服务
make ui-start          # 启动UI服务
make ui-stop           # 停止UI服务
make ui-restart        # 重启UI服务
make ui-status         # 查看UI状态
make ui-logs           # 查看UI日志
make ui-dev            # 开发模式启动

# 或使用完整命令名
make mcp-ui-start
make mcp-ui-stop
```

### 通用命令
```bash
# 指定模块操作
make start CURRENT_MODULE=mcp_ui    # 启动UI模块
make status CURRENT_MODULE=mcp_ui   # 查看UI状态

# 项目管理
make install           # 安装依赖
make clean            # 清理临时文件
make info             # 显示项目信息
```

### 服务管理
```bash
# MCP服务器
make mcp-server-start  # 启动MCP服务器
make mcp-server-status # 查看MCP服务器状态

# Ollama服务 (macOS)
make ollama-start      # 启动Ollama服务
make ollama-status     # 查看Ollama状态
```

## 📊 监控和诊断

### 日志系统
- **彩色日志**: 开发友好的控制台输出
- **文件日志**: 结构化的日志文件记录
- **操作追踪**: 完整的用户操作和系统事件记录

### 状态监控
```bash
# 查看系统状态
make ui-status

# 查看实时日志
make ui-logs

# 系统诊断
make diagnose CURRENT_MODULE=mcp_ui
```

## ⚙️ 配置选项

### UI配置类 (UIConfig)
- **服务端点**: MCP服务器和Ollama服务的连接地址
- **应用配置**: 主机、端口、调试模式等
- **文件处理**: 上传目录、大小限制、支持格式
- **模型设置**: 默认模型、温度、最大令牌数
- **搜索配置**: 搜索结果数量限制

### 系统提示词 (SystemPrompts)
- **QA_SYSTEM_PROMPT**: 问答系统提示词
- **SEARCH_SYSTEM_PROMPT**: 搜索专家提示词
- **INDEX_SYSTEM_PROMPT**: 索引专家提示词

## 🛡️ 安全考虑

1. **文件验证**: 严格的文件类型和大小验证
2. **路径安全**: 防止路径遍历攻击
3. **权限控制**: 基于MCP服务器的安全机制
4. **资源限制**: 合理的内存和CPU使用限制

## 🐛 故障排除

### 常见问题

1. **端口冲突**
   ```bash
   # 检查端口占用
   lsof -i :8000
   # 或使用不同端口
   make ui-start MCP_UI_PORT=8001
   ```

2. **MCP服务器连接失败**
   ```bash
   # 检查MCP服务器状态
   make mcp-server-status
   # 手动启动MCP服务器
   make mcp-server-start
   ```

3. **Ollama服务不可用**
   ```bash
   # 启动Ollama服务 (macOS)
   make ollama-start
   # 检查Ollama状态
   make ollama-status
   ```

4. **依赖问题**
   ```bash
   # 重新安装依赖
   make install
   # 检查Python环境
   make info
   ```

### 日志分析
```bash
# 查看错误日志
make ui-logs | grep ERROR

# 查看完整系统状态
make diagnose CURRENT_MODULE=mcp_ui
```

## 🤝 开发指南

### 添加新命令
1. 在 `handlers/` 目录下创建处理器类
2. 继承 `BaseCommandHandler`
3. 在 `handlers/__init__.py` 中注册处理器

### 扩展客户端
1. 在 `clients/` 目录下创建新的客户端类
2. 实现异步方法
3. 在 `__init__.py` 中导出

### 自定义配置
1. 在 `config/settings.py` 中添加配置项
2. 支持环境变量覆盖
3. 添加配置验证逻辑

## 📄 许可证

本项目遵循项目根目录的许可证条款。

## 🔗 相关链接

- [MCP Server 文档](../mcp_server/README.md)
- [Chainlit 官方文档](https://docs.chainlit.io)
- [Ollama 官方网站](https://ollama.ai)