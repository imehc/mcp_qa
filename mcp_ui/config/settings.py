"""
MCP UI配置管理
支持本地和远程模型，多种MCP工具服务器
"""

import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from ..utils.logger import get_logger

logger = get_logger(__name__)

class ModelProvider(Enum):
    """模型提供商枚举"""
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"

class MCPServerType(Enum):
    """MCP服务器类型枚举"""
    LOCAL = "local"
    REMOTE = "remote"
    SSH = "ssh"

@dataclass
class ModelConfig:
    """模型配置类"""
    provider: ModelProvider
    model_name: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    api_version: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: float = 60.0

@dataclass
class MCPServerConfig:
    """MCP服务器配置类"""
    name: str
    server_type: MCPServerType
    url: str
    api_key: Optional[str] = None
    timeout: float = 30.0
    enabled: bool = True

@dataclass
class UIConfig:
    """UI应用配置类"""
    
    # 应用配置
    APP_HOST: str = os.getenv("UI_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("UI_PORT", "8000"))
    DEBUG: bool = os.getenv("UI_DEBUG", "false").lower() == "true"
    
    # 本地MCP服务器配置
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8020")
    
    # 本地Ollama配置
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # 远程模型配置（统一JSON格式）
    REMOTE_MODELS: str = os.getenv("REMOTE_MODELS", "")  # JSON格式的模型配置
    
    # 向后兼容的单独配置（优先级低于REMOTE_MODELS）
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")
    
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
    
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_MODEL: str = os.getenv("GOOGLE_MODEL", "gemini-pro")
    
    AZURE_API_KEY: str = os.getenv("AZURE_API_KEY", "")
    AZURE_ENDPOINT: str = os.getenv("AZURE_ENDPOINT", "")
    AZURE_API_VERSION: str = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")
    AZURE_DEPLOYMENT: str = os.getenv("AZURE_DEPLOYMENT", "")
    
    # 远程MCP服务器配置
    REMOTE_MCP_SERVERS: str = os.getenv("REMOTE_MCP_SERVERS", "")  # JSON格式
    
    # 超时配置
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "30.0"))
    MODEL_TIMEOUT: float = float(os.getenv("MODEL_TIMEOUT", "60.0"))
    
    # 文件上传配置
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "docs")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", "104857600"))  # 100MB
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf", ".docx", ".doc", ".txt", ".md", ".markdown",
        ".xlsx", ".xls", ".pptx", ".ppt", ".json", ".yaml", ".yml"
    ]
    
    # 默认模型配置
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "ollama")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen3:4b")
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))
    
    # 搜索配置
    DEFAULT_SEARCH_K: int = int(os.getenv("DEFAULT_SEARCH_K", "5"))
    MAX_SEARCH_K: int = int(os.getenv("MAX_SEARCH_K", "20"))
    
    # 日志配置
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/mcp_ui.log")
    
    # UI界面配置
    THEME: str = os.getenv("UI_THEME", "light")
    LANGUAGE: str = os.getenv("UI_LANGUAGE", "zh")
    
    # 缓存配置
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1小时
    
    @classmethod
    def get_model_configs(cls) -> List[ModelConfig]:
        """获取所有可用的模型配置"""
        configs = []
        
        # 1. 添加本地Ollama模型
        configs.append(ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name=cls.DEFAULT_MODEL,
            base_url=cls.OLLAMA_BASE_URL,
            max_tokens=cls.MAX_TOKENS,
            temperature=cls.TEMPERATURE,
            timeout=cls.MODEL_TIMEOUT
        ))
        
        # 2. 解析统一的远程模型配置（优先级高）
        if cls.REMOTE_MODELS:
            configs.extend(cls._parse_remote_models_config())
        
        # 3. 向后兼容的单独配置（优先级低）
        else:
            # OpenAI模型
            if cls.OPENAI_API_KEY:
                configs.append(ModelConfig(
                    provider=ModelProvider.OPENAI,
                    model_name=cls.OPENAI_MODEL,
                    api_key=cls.OPENAI_API_KEY,
                    base_url=cls.OPENAI_BASE_URL,
                    max_tokens=cls.MAX_TOKENS,
                    temperature=cls.TEMPERATURE,
                    timeout=cls.MODEL_TIMEOUT
                ))
            
            # Anthropic模型
            if cls.ANTHROPIC_API_KEY:
                configs.append(ModelConfig(
                    provider=ModelProvider.ANTHROPIC,
                    model_name=cls.ANTHROPIC_MODEL,
                    api_key=cls.ANTHROPIC_API_KEY,
                    max_tokens=cls.MAX_TOKENS,
                    temperature=cls.TEMPERATURE,
                    timeout=cls.MODEL_TIMEOUT
                ))
            
            # Google模型
            if cls.GOOGLE_API_KEY:
                configs.append(ModelConfig(
                    provider=ModelProvider.GOOGLE,
                    model_name=cls.GOOGLE_MODEL,
                    api_key=cls.GOOGLE_API_KEY,
                    max_tokens=cls.MAX_TOKENS,
                    temperature=cls.TEMPERATURE,
                    timeout=cls.MODEL_TIMEOUT
                ))
            
            # Azure模型
            if cls.AZURE_API_KEY and cls.AZURE_ENDPOINT:
                configs.append(ModelConfig(
                    provider=ModelProvider.AZURE,
                    model_name=cls.AZURE_DEPLOYMENT,
                    api_key=cls.AZURE_API_KEY,
                    base_url=cls.AZURE_ENDPOINT,
                    api_version=cls.AZURE_API_VERSION,
                    max_tokens=cls.MAX_TOKENS,
                    temperature=cls.TEMPERATURE,
                    timeout=cls.MODEL_TIMEOUT
                ))
        
        return configs
    
    @classmethod
    def _parse_remote_models_config(cls) -> List[ModelConfig]:
        """解析统一的远程模型配置"""
        configs = []
        
        try:
            import json
            remote_models = json.loads(cls.REMOTE_MODELS)
            
            for model_config in remote_models:
                provider_str = model_config.get("provider", "").lower()
                
                # 验证提供商
                try:
                    provider = ModelProvider(provider_str)
                except ValueError:
                    logger.warning(f"不支持的模型提供商: {provider_str}")
                    continue
                
                # 构建配置
                config = ModelConfig(
                    provider=provider,
                    model_name=model_config.get("model", ""),
                    api_key=model_config.get("api_key"),
                    base_url=model_config.get("base_url"),
                    api_version=model_config.get("api_version"),
                    max_tokens=model_config.get("max_tokens", cls.MAX_TOKENS),
                    temperature=model_config.get("temperature", cls.TEMPERATURE),
                    timeout=model_config.get("timeout", cls.MODEL_TIMEOUT)
                )
                
                # 验证必要字段
                if not config.model_name:
                    logger.warning(f"模型配置缺少model字段: {model_config}")
                    continue
                
                if provider != ModelProvider.OLLAMA and not config.api_key:
                    logger.warning(f"远程模型配置缺少api_key字段: {model_config}")
                    continue
                
                configs.append(config)
                logger.info(f"加载远程模型配置: {provider_str} - {config.model_name}")
                
        except json.JSONDecodeError as e:
            logger.error(f"远程模型配置JSON解析失败: {e}")
        except Exception as e:
            logger.error(f"解析远程模型配置时发生错误: {e}")
        
        return configs
    
    @classmethod
    def get_mcp_server_configs(cls) -> List[MCPServerConfig]:
        """获取所有MCP服务器配置"""
        configs = []
        
        # 本地MCP服务器
        configs.append(MCPServerConfig(
            name="local",
            server_type=MCPServerType.LOCAL,
            url=cls.MCP_SERVER_URL,
            timeout=cls.REQUEST_TIMEOUT
        ))
        
        # 远程MCP服务器
        if cls.REMOTE_MCP_SERVERS:
            import json
            try:
                remote_servers = json.loads(cls.REMOTE_MCP_SERVERS)
                for server_config in remote_servers:
                    configs.append(MCPServerConfig(
                        name=server_config.get("name", "remote"),
                        server_type=MCPServerType.REMOTE,
                        url=server_config.get("url"),
                        api_key=server_config.get("api_key"),
                        timeout=server_config.get("timeout", cls.REQUEST_TIMEOUT),
                        enabled=server_config.get("enabled", True)
                    ))
            except json.JSONDecodeError:
                pass
        
        return configs
    
    @classmethod
    def ensure_directories(cls):
        """确保必要的目录存在"""
        dirs = [
            cls.UPLOAD_DIR,
            Path(cls.LOG_FILE).parent
        ]
        
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """验证配置并返回状态"""
        issues = []
        
        # 检查端口范围
        if not (1024 <= cls.APP_PORT <= 65535):
            issues.append(f"应用端口 {cls.APP_PORT} 不在有效范围内")
        
        # 检查超时设置
        if cls.REQUEST_TIMEOUT <= 0:
            issues.append("请求超时时间必须大于0")
        
        if cls.MODEL_TIMEOUT <= 0:
            issues.append("模型超时时间必须大于0")
        
        # 检查文件大小限制
        if cls.MAX_FILE_SIZE <= 0:
            issues.append("最大文件大小必须大于0")
        
        # 检查搜索配置
        if cls.DEFAULT_SEARCH_K <= 0 or cls.DEFAULT_SEARCH_K > cls.MAX_SEARCH_K:
            issues.append("默认搜索数量配置无效")
        
        # 检查模型配置
        model_configs = cls.get_model_configs()
        if not model_configs:
            issues.append("未配置任何可用的模型")
        
        # 检查MCP服务器配置
        mcp_configs = cls.get_mcp_server_configs()
        if not mcp_configs:
            issues.append("未配置任何MCP服务器")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "model_configs": len(model_configs),
            "mcp_configs": len(mcp_configs),
            "config": {
                "app_host": cls.APP_HOST,
                "app_port": cls.APP_PORT,
                "debug": cls.DEBUG,
                "upload_dir": cls.UPLOAD_DIR,
                "default_provider": cls.DEFAULT_PROVIDER,
                "default_model": cls.DEFAULT_MODEL,
                "log_level": cls.LOG_LEVEL,
                "available_providers": [config.provider.value for config in model_configs]
            }
        }

# 系统提示词配置
class SystemPrompts:
    """系统提示词配置"""
    
    QA_SYSTEM_PROMPT = """你是一个智能知识库助手。基于提供的文档内容回答用户问题。

要求:
1. 基于检索到的文档内容回答问题
2. 如果文档中没有相关信息，请明确说明
3. 回答要准确、详细且有帮助
4. 可以引用具体的文档内容
5. 保持回答的逻辑性和条理性
6. 如果涉及代码或技术内容，请提供清晰的解释
"""
    
    SEARCH_SYSTEM_PROMPT = """你是一个文档搜索专家。帮助用户理解搜索结果并提供相关建议。

要求:
1. 分析搜索结果的相关性
2. 总结关键信息
3. 提供进一步搜索的建议
4. 指出可能的信息缺失
"""
    
    INDEX_SYSTEM_PROMPT = """你是一个知识库索引专家。帮助用户理解索引构建过程和结果。

要求:
1. 解释索引构建的进度和状态
2. 分析文档处理结果
3. 提供优化建议
4. 说明可能的问题和解决方案
"""
    
    TOOL_CALL_SYSTEM_PROMPT = """你是一个MCP工具调用专家。帮助用户理解工具调用结果和状态。

要求:
1. 解释工具调用的结果
2. 分析执行状态和错误
3. 提供使用建议
4. 说明工具的功能和限制
"""

# 初始化配置
UIConfig.ensure_directories()