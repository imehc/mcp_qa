"""
MCP 服务器配置模块

该模块包含 MCP 服务器的所有配置设置，
包括环境变量、默认值和验证。
"""

import os
from typing import List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class ServerConfig:
    """服务器配置设置"""
    
    HOST: str = os.getenv("MCP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("MCP_PORT", "8020"))
    DEBUG: bool = os.getenv("MCP_DEBUG", "False").lower() == "true"
    
    # 协议设置
    PROTOCOL_VERSION: str = "1.0"
    
    # 请求设置
    REQUEST_TIMEOUT: int = int(os.getenv("MCP_REQUEST_TIMEOUT", "120"))
    MAX_REQUEST_SIZE: int = int(os.getenv("MCP_MAX_REQUEST_SIZE", "10485760"))  # 10MB


class SecurityConfig:
    """安全和访问控制设置"""
    
    # 默认文档目录
    DEFAULT_DOCS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    
    # 允许访问文件的目录
    ALLOWED_DIRS: List[str] = [
        dir.strip() for dir in os.getenv("MCP_ALLOWED_DIRS", DEFAULT_DOCS_DIR).split(",")
        if dir.strip()
    ]
    
    # 文件大小限制
    MAX_FILE_SIZE: int = int(os.getenv("MCP_MAX_FILE_SIZE", "104857600"))  # 100MB
    
    # 支持的文件类型
    SUPPORTED_TEXT_EXTENSIONS: List[str] = [
        ".txt", ".py", ".js", ".json", ".yaml", ".yml", ".xml", ".csv", ".log"
    ]
    
    SUPPORTED_DOCUMENT_EXTENSIONS: List[str] = [
        ".pdf", ".docx", ".doc", ".md", ".markdown"
    ]
    
    SUPPORTED_OFFICE_EXTENSIONS: List[str] = [
        ".xlsx", ".xls", ".pptx", ".ppt"
    ]
    
    @classmethod
    def get_all_supported_extensions(cls) -> List[str]:
        """获取所有支持的文件扩展名"""
        return (cls.SUPPORTED_TEXT_EXTENSIONS + 
                cls.SUPPORTED_DOCUMENT_EXTENSIONS + 
                cls.SUPPORTED_OFFICE_EXTENSIONS)


class EmbeddingConfig:
    """嵌入模型和向量索引设置"""
    
    # 默认嵌入模型
    DEFAULT_MODEL: str = os.getenv(
        "MCP_EMBEDDING_MODEL", 
        "paraphrase-multilingual-MiniLM-L12-v2"
    )
    
    # 可用模型
    AVAILABLE_MODELS: List[str] = [
        "paraphrase-multilingual-MiniLM-L12-v2",
        "all-MiniLM-L6-v2",
        "all-mpnet-base-v2",
        "paraphrase-MiniLM-L6-v2"
    ]
    
    # 批处理设置
    BATCH_SIZE: int = int(os.getenv("MCP_EMBEDDING_BATCH_SIZE", "32"))
    
    # 文本分块设置
    CHUNK_SIZE: int = int(os.getenv("MCP_CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("MCP_CHUNK_OVERLAP", "200"))
    
    # 文本分块分隔符
    TEXT_SEPARATORS: List[str] = [
        "\n\n", "\n", "。", "！", "？", ";", ":", ".", "!", "?"
    ]


class IndexConfig:
    """向量索引存储设置"""
    
    # 索引目录
    INDEX_DIR: str = os.getenv(
        "MCP_INDEX_DIR", 
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "faiss_index")
    )
    
    # 索引文件名
    FAISS_INDEX_FILE: str = "index.faiss"
    DOCUMENT_STORE_FILE: str = "index.pkl"
    METADATA_FILE: str = "metadata.json"
    
    # 搜索设置
    DEFAULT_SEARCH_K: int = int(os.getenv("MCP_DEFAULT_SEARCH_K", "3"))
    MAX_SEARCH_K: int = int(os.getenv("MCP_MAX_SEARCH_K", "50"))


class LoggingConfig:
    """日志配置"""
    
    # 日志级别
    LOG_LEVEL: str = os.getenv("MCP_LOG_LEVEL", "INFO")
    
    # 日志格式
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 日志文件设置
    LOG_FILE: Optional[str] = os.getenv("MCP_LOG_FILE")
    LOG_MAX_SIZE: int = int(os.getenv("MCP_LOG_MAX_SIZE", "10485760"))  # 10MB
    LOG_BACKUP_COUNT: int = int(os.getenv("MCP_LOG_BACKUP_COUNT", "5"))


class CacheConfig:
    """缓存配置"""
    
    # 启用文件索引缓存
    ENABLE_INDEX_CACHE: bool = os.getenv("MCP_ENABLE_INDEX_CACHE", "True").lower() == "true"
    
    # 缓存 TTL（秒）
    CACHE_TTL: int = int(os.getenv("MCP_CACHE_TTL", "3600"))  # 1小时
    
    # 缓存目录
    CACHE_DIR: str = os.getenv(
        "MCP_CACHE_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
    )


class DocumentConfig:
    """文档解析配置"""
    
    # 转换超时时间
    CONVERSION_TIMEOUT: int = int(os.getenv("MCP_CONVERSION_TIMEOUT", "60"))
    
    # LibreOffice 文档转换路径
    LIBREOFFICE_PATHS: List[str] = [
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',  # macOS
        '/usr/bin/libreoffice',  # Linux
        '/usr/bin/soffice',  # Linux 替代方案
        'libreoffice',  # PATH
        'soffice'  # PATH 替代方案
    ]
    
    # 文本清理设置
    MIN_TEXT_LENGTH: int = int(os.getenv("MCP_MIN_TEXT_LENGTH", "50"))
    MIN_MEANINGFUL_CHARS: int = int(os.getenv("MCP_MIN_MEANINGFUL_CHARS", "20"))
    MAX_PRINTABLE_RATIO: float = float(os.getenv("MCP_MAX_PRINTABLE_RATIO", "0.8"))


class Config:
    """主配置类，聚合所有设置"""
    
    server = ServerConfig()
    security = SecurityConfig()
    embedding = EmbeddingConfig()
    index = IndexConfig()
    logging = LoggingConfig()
    cache = CacheConfig()
    document = DocumentConfig()
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置设置"""
        errors = []
        
        # 验证目录是否存在或可以创建
        for dir_path in [cls.index.INDEX_DIR, cls.cache.CACHE_DIR]:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建目录 {dir_path}: {e}")
        
        # 验证允许的目录
        for allowed_dir in cls.security.ALLOWED_DIRS:
            if not os.path.exists(allowed_dir):
                errors.append(f"允许的目录不存在: {allowed_dir}")
        
        # 验证端口范围
        if not (1 <= cls.server.PORT <= 65535):
            errors.append(f"无效的端口号: {cls.server.PORT}")
        
        # 验证嵌入模型
        if cls.embedding.DEFAULT_MODEL not in cls.embedding.AVAILABLE_MODELS:
            errors.append(f"未知的嵌入模型: {cls.embedding.DEFAULT_MODEL}")
        
        if errors:
            raise ValueError("配置验证失败:\n" + "\n".join(errors))
        
        return True
    
    @classmethod
    def get_summary(cls) -> dict:
        """获取配置摘要用于日志记录"""
        return {
            "server": {
                "host": cls.server.HOST,
                "port": cls.server.PORT,
                "debug": cls.server.DEBUG
            },
            "security": {
                "allowed_dirs": cls.security.ALLOWED_DIRS,
                "max_file_size": cls.security.MAX_FILE_SIZE
            },
            "embedding": {
                "model": cls.embedding.DEFAULT_MODEL,
                "chunk_size": cls.embedding.CHUNK_SIZE
            },
            "index": {
                "index_dir": cls.index.INDEX_DIR,
                "default_search_k": cls.index.DEFAULT_SEARCH_K
            }
        }


# 全局配置实例
config = Config()