"""
MCP 服务器类型定义

该模块包含在整个 MCP 服务器应用程序中使用的所有类型定义、数据类和枚举。
"""

from typing import Dict, List, Optional, Union, Any, Literal, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from pydantic import BaseModel


# ============================================================================
# 枚举
# ============================================================================

class FileType(Enum):
    """支持的文件类型"""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    MARKDOWN = "markdown"
    TEXT = "text"
    EXCEL = "excel"
    POWERPOINT = "powerpoint"
    UNKNOWN = "unknown"


class ParserStatus(Enum):
    """文档解析状态"""
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"
    CONVERSION_FAILED = "conversion_failed"
    UNSUPPORTED = "unsupported"


class IndexStatus(Enum):
    """向量索引状态"""
    NOT_INDEXED = "not_indexed"
    NOT_BUILT = "not_built"  # 兼容性别名
    BUILDING = "building" 
    INDEXING = "indexing"  # 兼容性别名
    READY = "ready"
    UPDATING = "updating"
    ERROR = "error"
    OUTDATED = "outdated"


class ConversionMethod(Enum):
    """文档转换方法"""
    PYPANDOC = "pypandoc"
    LIBREOFFICE = "libreoffice"
    TEXTUTIL = "textutil"
    DIRECT = "direct"
    FALLBACK = "fallback"


# ============================================================================
# MCP 工具的基础模型
# ============================================================================

class MCPToolParams(BaseModel):
    """所有 MCP 工具参数的基类"""
    pass


class ListDirParams(MCPToolParams):
    """list_dir 工具的参数"""
    directory: str


class GetMtimeParams(MCPToolParams):
    """get_mtime 工具的参数"""
    file_path: str


class ReadFileParams(MCPToolParams):
    """read_file 工具的参数"""
    file_name: str
    force_reindex: bool = False


class SearchDocumentsParams(MCPToolParams):
    """search_documents 工具的参数"""
    query: str
    top_k: Optional[int] = 3


class BuildIndexParams(MCPToolParams):
    """build_document_index 工具的参数"""
    files: Optional[List[str]] = None
    directory: Optional[str] = None


# ============================================================================
# 解析器特定参数
# ============================================================================

class ParsePdfParams(MCPToolParams):
    """PDF 解析的参数"""
    file_path: str


class ParseDocxParams(MCPToolParams):
    """DOCX/DOC 解析的参数"""
    file_path: str


class ParseMdParams(MCPToolParams):
    """Markdown 解析的参数"""
    file_path: str


class ParseExcelParams(MCPToolParams):
    """Excel 解析的参数"""
    file_path: str
    sheet_name: Optional[str] = None


class ParsePptxParams(MCPToolParams):
    """PowerPoint 解析的参数"""
    file_path: str


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class FileInfo:
    """文件信息"""
    path: str
    name: str
    size: int
    modified_time: datetime
    file_type: FileType
    is_indexed: bool = False
    index_status: IndexStatus = IndexStatus.NOT_INDEXED


@dataclass
class TextChunk:
    """文本块及其元数据"""
    content: str
    chunk_id: int
    source: str
    metadata: Dict[str, Any]
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None


@dataclass
class ParseResult:
    """文档解析结果"""
    success: bool
    file_path: str
    file_type: FileType
    status: ParserStatus
    content: Optional[str] = None
    chunks: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    parsing_method: Optional[str] = None
    conversion_method: Optional[ConversionMethod] = None


@dataclass
class ConversionResult:
    """文档转换结果"""
    success: bool
    method: ConversionMethod
    converted_path: Optional[str] = None
    temp_dir: Optional[str] = None
    error: Optional[str] = None
    tried_methods: Optional[List[str]] = None


@dataclass
class SearchResult:
    """向量搜索结果"""
    content: str
    source: str
    score: float
    metadata: Dict[str, Any]
    rank: int = 0
    distance: float = 0.0
    chunk_id: int = 0
    search_type: str = "semantic"
    highlight: str = ""


@dataclass
class IndexResult:
    """索引操作结果"""
    success: bool
    total_documents: int
    total_chunks: int
    index_dimension: Optional[int] = None
    index_path: Optional[str] = None
    files_processed: Optional[int] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None


# ============================================================================
# 响应模型
# ============================================================================

class FileListResponse(BaseModel):
    """文件列表操作的响应"""
    directory: str
    items: List[Dict[str, Union[str, int]]]
    total_items: Optional[int] = None
    error: Optional[str] = None


class FileTimeResponse(BaseModel):
    """文件时间操作的响应"""
    file_path: str
    modified_time: str
    timestamp: float
    error: Optional[str] = None


class CurrentTimeResponse(BaseModel):
    """当前时间操作的响应"""
    current_time: str
    timestamp: float
    formatted: str
    date: str
    time: str


class DocumentParseResponse(BaseModel):
    """文档解析操作的响应"""
    file_path: str
    file_type: str
    success: bool
    total_pages: Optional[int] = None
    total_paragraphs: Optional[int] = None
    full_text: Optional[str] = None
    pages: Optional[List[Dict[str, Any]]] = None
    paragraphs: Optional[List[Dict[str, Any]]] = None
    chunks: Optional[List[str]] = None
    chunk_count: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    vector_index: Optional[Dict[str, Any]] = None
    conversion_method: Optional[str] = None
    parsing_method: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None
    suggestions: Optional[List[str]] = None
    from_cache: bool = False


class SearchResponse(BaseModel):
    """搜索操作的响应"""
    query: str
    total_results: int
    results: List[Dict[str, Any]]
    search_time: Optional[float] = None
    error: Optional[str] = None


class IndexBuildResponse(BaseModel):
    """索引构建操作的响应"""
    message: str
    total_documents: int
    index_dimension: Optional[int] = None
    index_path: Optional[str] = None
    files_processed: int
    processing_time: Optional[float] = None
    error: Optional[str] = None


# ============================================================================
# 配置类型
# ============================================================================

@dataclass
class EmbeddingModelInfo:
    """嵌入模型信息"""
    name: str
    dimension: int
    max_sequence_length: int
    multilingual: bool = False
    description: Optional[str] = None


@dataclass
class CacheInfo:
    """缓存数据信息"""
    file_path: str
    mtime: float
    indexed: bool
    cache_time: datetime
    chunks_count: int


# ============================================================================
# 错误类型
# ============================================================================

@dataclass
class ErrorInfo:
    """详细错误信息"""
    error_type: str
    message: str
    file_path: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


# ============================================================================
# 安全类型
# ============================================================================

@dataclass
class AccessControl:
    """访问控制信息"""
    allowed_paths: List[str]
    denied_paths: List[str] = None
    max_file_size: int = 104857600  # 100MB
    allowed_extensions: List[str] = None


# ============================================================================
# 监控类型
# ============================================================================

@dataclass
class PerformanceMetrics:
    """性能监控指标"""
    operation: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    memory_usage: Optional[int] = None
    success: bool = True
    error: Optional[str] = None
    
    def finish(self, success: bool = True, error: Optional[str] = None):
        """标记操作完成"""
        self.end_time = datetime.now()
        self.duration = (self.end_time - self.start_time).total_seconds()
        self.success = success
        self.error = error


# ============================================================================
# 类型别名
# ============================================================================

# 为了更好的可读性的常见类型别名
FilePath = str
DirectoryPath = str
EmbeddingVector = List[float]
DocumentContent = str
ChunkContent = str
SearchQuery = str
ErrorMessage = str
SuccessMessage = str

# API 响应的联合类型
APIResponse = Union[
    FileListResponse,
    FileTimeResponse,
    CurrentTimeResponse,
    DocumentParseResponse,
    SearchResponse,
    IndexBuildResponse,
    Dict[str, Any]  # 通用响应
]

# 解析器函数签名
ParserFunction = Callable[[str], ParseResult]

# 工具响应类型
ToolResponse = Dict[str, Any]