"""
MCP 服务器自定义异常

该模块定义了在整个 MCP 服务器中使用的所有自定义异常，
以提供更好的错误处理和用户反馈。
"""

from typing import Optional, List, Dict, Any


class MCPServerError(Exception):
    """所有 MCP 服务器错误的基类异常"""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.suggestions = suggestions or []
    
    def to_dict(self) -> Dict[str, Any]:
        """将异常转换为字典以用于 API 响应"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
            "suggestions": self.suggestions
        }


# ============================================================================
# 配置异常
# ============================================================================

class ConfigurationError(MCPServerError):
    """配置错误时引发"""
    pass


class InvalidConfigError(ConfigurationError):
    """配置值无效时引发"""
    pass


class MissingConfigError(ConfigurationError):
    """缺少必需配置时引发"""
    pass


# ============================================================================
# 文件和路径异常
# ============================================================================

class FileError(MCPServerError):
    """文件相关错误的基类异常"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.file_path = file_path
        if file_path:
            self.details["file_path"] = file_path


class FileNotFoundError(FileError):
    """文件未找到时引发"""
    
    def __init__(self, file_path: str, searched_directories: Optional[List[str]] = None):
        message = f"文件未找到: {file_path}"
        suggestions = [
            "检查文件路径是否正确",
            "确保文件存在于允许的目录中"
        ]
        if searched_directories:
            suggestions.append(f"已在以下位置搜索: {', '.join(searched_directories)}")
        
        super().__init__(
            message=message,
            file_path=file_path,
            details={"searched_directories": searched_directories or []},
            suggestions=suggestions
        )


class FileAccessDeniedError(FileError):
    """由于安全限制文件访问被拒绝时引发"""
    
    def __init__(self, file_path: str, allowed_directories: Optional[List[str]] = None):
        message = f"文件访问被拒绝: {file_path}"
        suggestions = [
            "确保文件在允许的目录中",
            "检查文件权限"
        ]
        if allowed_directories:
            suggestions.append(f"允许的目录: {', '.join(allowed_directories)}")
        
        super().__init__(
            message=message,
            file_path=file_path,
            details={"allowed_directories": allowed_directories or []},
            suggestions=suggestions
        )


class FileSizeExceededError(FileError):
    """文件大小超过限制时引发"""
    
    def __init__(self, file_path: str, file_size: int, max_size: int):
        message = f"文件大小 ({file_size} 字节) 超过最大允许大小 ({max_size} 字节)"
        super().__init__(
            message=message,
            file_path=file_path,
            details={"file_size": file_size, "max_size": max_size},
            suggestions=[
                "使用较小的文件",
                "如有可能压缩文件",
                "联系管理员增加大小限制"
            ]
        )


class UnsupportedFileTypeError(FileError):
    """文件类型不受支持时引发"""
    
    def __init__(self, file_path: str, file_extension: str, supported_types: Optional[List[str]] = None):
        message = f"不支持的文件类型: {file_extension}"
        suggestions = ["使用支持的文件类型"]
        if supported_types:
            suggestions.append(f"支持的类型: {', '.join(supported_types)}")
        
        super().__init__(
            message=message,
            file_path=file_path,
            details={
                "file_extension": file_extension,
                "supported_types": supported_types or []
            },
            suggestions=suggestions
        )


# ============================================================================
# 解析异常
# ============================================================================

class ParsingError(MCPServerError):
    """文档解析错误的基类异常"""
    
    def __init__(self, message: str, file_path: Optional[str] = None, **kwargs):
        super().__init__(message, **kwargs)
        self.file_path = file_path
        if file_path:
            self.details["file_path"] = file_path


class DocumentCorruptedError(ParsingError):
    """文档似乎已损坏时引发"""
    
    def __init__(self, file_path: str, parser_name: str):
        message = f"文档似乎已损坏: {file_path}"
        super().__init__(
            message=message,
            file_path=file_path,
            details={"parser": parser_name},
            suggestions=[
                "尝试在原始应用程序中打开文件",
                "检查文件是否完全下载",
                "尝试将文件转换为不同格式"
            ]
        )


class ConversionError(ParsingError):
    """文档转换失败时引发"""
    
    def __init__(
        self, 
        file_path: str, 
        from_format: str, 
        to_format: str,
        tried_methods: Optional[List[str]] = None,
        last_error: Optional[str] = None
    ):
        message = f"无法将 {from_format} 转换为 {to_format}: {file_path}"
        suggestions = [
            f"尝试手动将 {from_format} 转换为 {to_format}",
            "确保已安装所需的转换工具 (LibreOffice, pandoc 等)",
            "如果可能，尝试不同的文件格式"
        ]
        
        super().__init__(
            message=message,
            file_path=file_path,
            details={
                "from_format": from_format,
                "to_format": to_format,
                "tried_methods": tried_methods or [],
                "last_error": last_error
            },
            suggestions=suggestions
        )


class EncodingError(ParsingError):
    """文本编码错误时引发"""
    
    def __init__(self, file_path: str, encoding: str, error_details: Optional[str] = None):
        message = f"文本编码错误 ({encoding}): {file_path}"
        super().__init__(
            message=message,
            file_path=file_path,
            details={"encoding": encoding, "error_details": error_details},
            suggestions=[
                "尝试以 UTF-8 编码保存文件",
                "检查文件编码是否正确",
                "使用文本编辑器转换文件编码"
            ]
        )


class EmptyDocumentError(ParsingError):
    """文档为空或不包含有意义内容时引发"""
    
    def __init__(self, file_path: str, parser_name: str):
        message = f"文档为空或不包含有意义的内容: {file_path}"
        super().__init__(
            message=message,
            file_path=file_path,
            details={"parser": parser_name},
            suggestions=[
                "检查文档是否实际包含内容",
                "尝试在原始应用程序中打开文件",
                "确保文件未损坏"
            ]
        )


# ============================================================================
# 索引异常
# ============================================================================

class IndexingError(MCPServerError):
    """索引相关错误的基类异常"""
    pass


class EmbeddingModelError(IndexingError):
    """嵌入模型出现错误时引发"""
    
    def __init__(self, model_name: str, error_details: Optional[str] = None):
        message = f"嵌入模型错误: {model_name}"
        super().__init__(
            message=message,
            details={"model_name": model_name, "error_details": error_details},
            suggestions=[
                "检查模型是否正确安装",
                "尝试使用不同的嵌入模型",
                "确保有足够的内存可用"
            ]
        )


class IndexNotFoundError(IndexingError):
    """向量索引未找到时引发"""
    
    def __init__(self, index_path: Optional[str] = None):
        message = "向量索引未找到"
        suggestions = [
            "首先构建文档索引",
            "检查索引文件是否存在",
            "验证索引目录权限"
        ]
        if index_path:
            suggestions.append(f"预期索引位置: {index_path}")
        
        super().__init__(
            message=message,
            details={"index_path": index_path},
            suggestions=suggestions
        )


class IndexCorruptedError(IndexingError):
    """向量索引已损坏时引发"""
    
    def __init__(self, index_path: str, error_details: Optional[str] = None):
        message = f"向量索引已损坏: {index_path}"
        super().__init__(
            message=message,
            details={"index_path": index_path, "error_details": error_details},
            suggestions=[
                "重新构建向量索引",
                "检查索引文件完整性",
                "确保索引操作有足够的磁盘空间"
            ]
        )


class SearchError(IndexingError):
    """向量搜索失败时引发"""
    
    def __init__(self, query: str, error_details: Optional[str] = None):
        message = f"查询搜索失败: {query}"
        super().__init__(
            message=message,
            details={"query": query, "error_details": error_details},
            suggestions=[
                "检查索引是否正确构建",
                "尝试更简单的搜索查询",
                "确保嵌入模型正常工作"
            ]
        )


# ============================================================================
# 安全异常
# ============================================================================

class SecurityError(MCPServerError):
    """安全相关错误的基类异常"""
    pass


class PathTraversalError(SecurityError):
    """检测到路径遍历时引发"""
    
    def __init__(self, requested_path: str):
        message = f"检测到路径遍历尝试: {requested_path}"
        super().__init__(
            message=message,
            details={"requested_path": requested_path},
            suggestions=[
                "在允许的目录中使用相对路径",
                "避免在文件路径中使用 '..'",
                "如果是合法用例，请联系管理员"
            ]
        )


class PermissionDeniedError(SecurityError):
    """操作不被允许时引发"""
    
    def __init__(self, operation: str, resource: str, reason: Optional[str] = None):
        message = f"对 {resource} 的 {operation} 操作被拒绝"
        if reason:
            message += f": {reason}"
        
        super().__init__(
            message=message,
            details={"operation": operation, "resource": resource, "reason": reason},
            suggestions=[
                "检查是否具有所需权限",
                "联系管理员获取访问权限",
                "确保资源在允许范围内"
            ]
        )


# ============================================================================
# 网络和服务器异常
# ============================================================================

class ServerError(MCPServerError):
    """服务器相关错误的基类异常"""
    pass


class RequestTimeoutError(ServerError):
    """请求超时时引发"""
    
    def __init__(self, operation: str, timeout_seconds: int):
        message = f"请求在 {timeout_seconds} 秒后超时: {operation}"
        super().__init__(
            message=message,
            details={"operation": operation, "timeout_seconds": timeout_seconds},
            suggestions=[
                "尝试使用较小的文件或数据集",
                "如有需要，增加超时配置",
                "检查服务器性能和资源"
            ]
        )


class ResourceExhaustedError(ServerError):
    """服务器资源耗尽时引发"""
    
    def __init__(self, resource_type: str, details: Optional[str] = None):
        message = f"服务器资源耗尽: {resource_type}"
        if details:
            message += f" - {details}"
        
        super().__init__(
            message=message,
            details={"resource_type": resource_type, "details": details},
            suggestions=[
                "稍后再试",
                "尝试使用较小的文件或请求",
                "联系管理员了解资源限制"
            ]
        )


# ============================================================================
# 工具函数
# ============================================================================

def handle_exception(exc: Exception, context: Optional[str] = None) -> Dict[str, Any]:
    """
    将任何异常转换为标准化的错误响应。
    
    参数:
        exc: 要处理的异常
        context: 可选的上下文信息
        
    返回:
        标准化错误字典
    """
    if isinstance(exc, MCPServerError):
        error_dict = exc.to_dict()
    else:
        # 处理标准 Python 异常
        error_dict = {
            "error": exc.__class__.__name__,
            "message": str(exc),
            "details": {"context": context} if context else {},
            "suggestions": []
        }
        
        # 为常见异常添加特定建议
        if isinstance(exc, FileNotFoundError):
            error_dict["suggestions"] = ["检查文件路径是否正确"]
        elif isinstance(exc, PermissionError):
            error_dict["suggestions"] = ["检查文件权限"]
        elif isinstance(exc, UnicodeDecodeError):
            error_dict["suggestions"] = ["检查文件编码，尝试 UTF-8"]
        elif isinstance(exc, MemoryError):
            error_dict["suggestions"] = ["尝试使用较小的文件", "释放系统内存"]
        elif isinstance(exc, TimeoutError):
            error_dict["suggestions"] = ["稍后再试", "使用较小的文件"]
    
    return error_dict


def create_error_response(
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    suggestions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    创建标准化的错误响应。
    
    参数:
        error_type: 错误类型
        message: 错误消息
        details: 附加错误详情
        suggestions: 建议的解决方案
        
    返回:
        标准化错误字典
    """
    return {
        "error": error_type,
        "message": message,
        "details": details or {},
        "suggestions": suggestions or []
    }