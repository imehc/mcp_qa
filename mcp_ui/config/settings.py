"""
MCP UI配置管理
"""

import os
from typing import List, Dict, Any
from pathlib import Path
from dataclasses import dataclass

@dataclass
class UIConfig:
    """UI应用配置类"""
    
    # 服务端点配置
    MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", "http://localhost:8020")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # 应用配置
    APP_HOST: str = os.getenv("UI_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("UI_PORT", "8000"))
    DEBUG: bool = os.getenv("UI_DEBUG", "false").lower() == "true"
    
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
    
    # 模型配置
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "qwen2.5:7b")
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
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "config": {
                "mcp_server_url": cls.MCP_SERVER_URL,
                "ollama_base_url": cls.OLLAMA_BASE_URL,
                "app_host": cls.APP_HOST,
                "app_port": cls.APP_PORT,
                "debug": cls.DEBUG,
                "upload_dir": cls.UPLOAD_DIR,
                "default_model": cls.DEFAULT_MODEL,
                "log_level": cls.LOG_LEVEL
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

# 初始化配置
UIConfig.ensure_directories()