# MCP UI 配置示例

这个文件展示了如何配置MCP UI以支持多种模型提供商和远程MCP服务器。

## 🔧 环境变量配置

### 基础配置
```bash
# UI应用配置
export UI_HOST=0.0.0.0
export UI_PORT=8000
export UI_DEBUG=false

# 默认模型提供商和模型
export DEFAULT_PROVIDER=ollama
export DEFAULT_MODEL=qwen3:4b

# 超时设置
export REQUEST_TIMEOUT=30.0
export MODEL_TIMEOUT=60.0

# 文件上传配置
export UPLOAD_DIR=docs
export MAX_FILE_SIZE=104857600  # 100MB
```

### 本地服务配置
```bash
# 本地MCP服务器
export MCP_SERVER_URL=http://localhost:8020

# 本地Ollama服务
export OLLAMA_BASE_URL=http://localhost:11434
```

### 远程模型API配置

#### 统一JSON配置方式（推荐）

**优势**：
- ✅ 配置更简洁，避免环境变量数量爆炸
- ✅ 支持详细的模型参数配置
- ✅ 易于管理和维护多个模型提供商
- ✅ 支持同一提供商的多个模型配置
- ✅ 避免添加新提供商时需要修改代码

```bash
# 统一的远程模型配置
export REMOTE_MODELS='[
  {
    "provider": "openai",
    "model": "gpt-4", 
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://api.openai.com/v1",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "anthropic",
    "model": "claude-3-sonnet-20240229",
    "api_key": "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "google",
    "model": "gemini-pro",
    "api_key": "AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://api.deepseek.com",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "qwen",
    "model": "qwen-turbo",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "azure",
    "model": "gpt-4",
    "api_key": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://your-resource.openai.azure.com/",
    "api_version": "2024-02-15-preview",
    "max_tokens": 4096,
    "temperature": 0.7
  }
]'

# OpenAI兼容接口（如本地部署的vLLM）
export REMOTE_MODELS='[
  {
    "provider": "openai",
    "model": "llama2-7b-chat",
    "api_key": "dummy-key",
    "base_url": "http://localhost:8001/v1"
  }
]'

# DeepSeek专用配置示例
export REMOTE_MODELS='[
  {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://api.deepseek.com"
  },
  {
    "provider": "deepseek", 
    "model": "deepseek-coder",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://api.deepseek.com"
  }
]'

# Qwen专用配置示例  
export REMOTE_MODELS='[
  {
    "provider": "qwen",
    "model": "qwen-turbo",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
  },
  {
    "provider": "qwen",
    "model": "qwen-plus", 
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
  },
  {
    "provider": "qwen",
    "model": "qwen-max",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", 
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
  }
]'
```

#### 向后兼容的单独配置

> **注意**：如果设置了 `REMOTE_MODELS` 环境变量，系统将优先使用统一JSON配置，忽略单独的环境变量（如 `OPENAI_API_KEY` 等）。

```bash
# OpenAI API（仍然支持，但不推荐）
export OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export OPENAI_BASE_URL=https://api.openai.com/v1
export OPENAI_MODEL=gpt-4

# Anthropic Claude API
export ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Google Gemini API
export GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export GOOGLE_MODEL=gemini-pro

# Azure OpenAI服务
export AZURE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
export AZURE_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_API_VERSION=2024-02-15-preview
export AZURE_DEPLOYMENT=gpt-4
```

### 远程MCP服务器配置
```bash
# 远程MCP服务器配置（JSON格式）
export REMOTE_MCP_SERVERS='[
  {
    "name": "remote-qa",
    "url": "https://api.example.com/mcp",
    "api_key": "your-api-key-here",
    "timeout": 30.0,
    "enabled": true
  },
  {
    "name": "team-server",
    "url": "http://internal-server:8020",
    "timeout": 45.0,
    "enabled": true
  }
]'
```

## 🚀 快速启动配置

### 1. 仅本地模式
```bash
# 最小配置，仅使用本地服务
export DEFAULT_PROVIDER=ollama
export DEFAULT_MODEL=qwen3:4b
```

### 2. OpenAI + 本地MCP
```bash
# 使用OpenAI模型 + 本地MCP服务器
export DEFAULT_PROVIDER=openai
export REMOTE_MODELS='[{
  "provider": "openai",
  "model": "gpt-4",
  "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}]'
```

### 3. 多模型支持
```bash
# 配置多个模型提供商
export DEFAULT_PROVIDER=ollama
export DEFAULT_MODEL=qwen3:4b

# 统一配置多个远程模型
export REMOTE_MODELS='[
  {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  },
  {
    "provider": "anthropic", 
    "model": "claude-3-sonnet-20240229",
    "api_key": "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
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
  }
]'
```

### 4. 完整配置（生产环境）
```bash
# 应用配置
export UI_HOST=0.0.0.0
export UI_PORT=8000
export UI_DEBUG=false

# 模型配置
export DEFAULT_PROVIDER=openai
export DEFAULT_MODEL=gpt-4
export TEMPERATURE=0.7
export MAX_TOKENS=4096

# 统一的远程模型配置
export REMOTE_MODELS='[
  {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "anthropic",
    "model": "claude-3-sonnet-20240229", 
    "api_key": "sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "google",
    "model": "gemini-pro",
    "api_key": "AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://api.deepseek.com",
    "max_tokens": 4096,
    "temperature": 0.7
  },
  {
    "provider": "qwen",
    "model": "qwen-turbo",
    "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "max_tokens": 4096,
    "temperature": 0.7
  }
]'

# 远程MCP服务器
export REMOTE_MCP_SERVERS='[
  {
    "name": "production-qa",
    "url": "https://mcp-api.company.com",
    "api_key": "prod-api-key-xxxxx",
    "timeout": 30.0,
    "enabled": true
  }
]'

# 安全和性能
export REQUEST_TIMEOUT=30.0
export MODEL_TIMEOUT=60.0
export MAX_FILE_SIZE=104857600
export LOG_LEVEL=INFO
```

## 📝 配置文件方式

你也可以创建一个 `.env` 文件来存储配置：

```bash
# .env 文件示例
UI_HOST=0.0.0.0
UI_PORT=8000
UI_DEBUG=false

DEFAULT_PROVIDER=openai
DEFAULT_MODEL=gpt-4

# 统一的远程模型配置
REMOTE_MODELS=[{"provider":"openai","model":"gpt-4","api_key":"sk-xxx"},{"provider":"anthropic","model":"claude-3-sonnet-20240229","api_key":"sk-ant-xxx"},{"provider":"deepseek","model":"deepseek-chat","api_key":"sk-xxx","base_url":"https://api.deepseek.com"},{"provider":"qwen","model":"qwen-turbo","api_key":"sk-xxx","base_url":"https://dashscope.aliyuncs.com/compatible-mode/v1"}]

# 远程MCP服务器配置
REMOTE_MCP_SERVERS=[{"name":"remote","url":"https://api.example.com/mcp","api_key":"xxx"}]
```

## 🔒 安全注意事项

1. **API密钥安全**:
   - 永远不要将API密钥提交到版本控制系统
   - 使用环境变量或安全的密钥管理系统
   - 定期轮换API密钥

2. **网络安全**:
   - 在生产环境中使用HTTPS
   - 配置适当的防火墙规则
   - 限制对敏感端点的访问

3. **访问控制**:
   - 为远程MCP服务器配置适当的认证
   - 使用最小权限原则
   - 监控API使用情况

## 🔍 配置验证

启动应用后，你可以使用以下命令验证配置：

- `/status` - 查看所有服务状态
- `/models` - 查看可用模型列表
- `/config` - 查看完整配置信息

## 🆘 故障排除

### 常见问题

1. **模型无法加载**:
   ```bash
   # 检查API密钥是否正确
   echo $OPENAI_API_KEY
   
   # 检查网络连接
   curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
   ```

2. **远程MCP服务器连接失败**:
   ```bash
   # 检查JSON格式是否正确
   echo $REMOTE_MCP_SERVERS | python -m json.tool
   
   # 测试连接
   curl -H "Authorization: Bearer your-api-key" https://your-mcp-server/health
   ```

3. **权限问题**:
   ```bash
   # 检查文件权限
   ls -la docs/
   
   # 确保日志目录可写
   mkdir -p logs && chmod 755 logs
   ```

## 🌟 新增模型提供商说明

### DeepSeek配置
- **官网**: https://platform.deepseek.com/
- **API文档**: https://platform.deepseek.com/api-docs/
- **支持模型**: deepseek-chat, deepseek-coder
- **API地址**: https://api.deepseek.com
- **认证方式**: Bearer Token (API Key)

### Qwen配置  
- **官网**: https://help.aliyun.com/zh/dashscope/
- **API文档**: https://help.aliyun.com/zh/dashscope/developer-reference/compatibility-of-openai-with-dashscope/
- **支持模型**: qwen-turbo, qwen-plus, qwen-max, qwen-long
- **API地址**: https://dashscope.aliyuncs.com/compatible-mode/v1
- **认证方式**: Bearer Token (API Key)

### 配置注意事项
1. **DeepSeek**: 使用标准的OpenAI兼容API，支持聊天和代码生成
2. **Qwen**: 通过阿里云DashScope提供OpenAI兼容接口
3. **API密钥**: 需要在各自官网注册获取API密钥
4. **模型名称**: 请使用官方文档中的准确模型名称

## 🚀 启动方式

配置完成后，使用以下方式启动应用：

```bash
# 方式1: 使用Makefile
make ui-start

# 方式2: 直接运行
python start_ui.py

# 方式3: 开发模式
make ui-dev
```