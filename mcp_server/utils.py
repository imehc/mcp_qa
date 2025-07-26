"""
MCP 服务器工具函数

该模块包含整个应用程序中使用的通用工具函数。
"""

import os
import hashlib
import tempfile
import shutil
import mimetypes
import time
from typing import List, Optional, Dict, Any, Union, Tuple
from pathlib import Path
from datetime import datetime
import re

from .config import config
from .types import FileType, FileInfo
from .exceptions import (
    FileNotFoundError, 
    FileAccessDeniedError, 
    FileSizeExceededError,
    UnsupportedFileTypeError
)


# ============================================================================
# 文件和路径工具
# ============================================================================

def normalize_path(path: str) -> str:
    """
    规范化文件路径以保持一致的处理。
    
    参数:
        path: 要规范化的文件路径
        
    返回:
        规范化的绝对路径
    """
    return os.path.normpath(os.path.abspath(path))


def is_path_allowed(path: str) -> bool:
    """
    检查路径是否在允许的目录内。
    
    参数:
        path: 要检查的路径
        
    返回:
        如果路径被允许则返回 True，否则返回 False
    """
    abs_path = normalize_path(path)
    
    for allowed_dir in config.security.ALLOWED_DIRS:
        allowed_abs = normalize_path(allowed_dir)
        if abs_path.startswith(allowed_abs):
            return True
    
    return False


def validate_file_access(file_path: str) -> None:
    """
    根据安全策略验证文件是否可以访问。
    
    参数:
        file_path: 文件路径
        
    引发:
        FileNotFoundError: 如果文件不存在
        FileAccessDeniedError: 如果访问被拒绝
        FileSizeExceededError: 如果文件过大
        UnsupportedFileTypeError: 如果文件类型不受支持
    """
    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            file_path=file_path,
            searched_directories=config.security.ALLOWED_DIRS
        )
    
    # 检查路径是否被允许
    if not is_path_allowed(file_path):
        raise FileAccessDeniedError(
            file_path=file_path,
            allowed_directories=config.security.ALLOWED_DIRS
        )
    
    # 检查文件大小
    file_size = os.path.getsize(file_path)
    if file_size > config.security.MAX_FILE_SIZE:
        raise FileSizeExceededError(
            file_path=file_path,
            file_size=file_size,
            max_size=config.security.MAX_FILE_SIZE
        )
    
    # 检查文件类型
    file_ext = get_file_extension(file_path)
    supported_types = config.security.get_all_supported_extensions()
    if file_ext not in supported_types:
        raise UnsupportedFileTypeError(
            file_path=file_path,
            file_extension=file_ext,
            supported_types=supported_types
        )


def get_file_extension(file_path: str) -> str:
    """
    获取小写的文件扩展名。
    
    参数:
        file_path: 文件路径
        
    返回:
        文件扩展名包括点号（例如 '.pdf'）
    """
    return os.path.splitext(file_path)[1].lower()


def get_file_type(file_path: str) -> FileType:
    """
    根据扩展名确定文件类型。
    
    参数:
        file_path: 文件路径
        
    返回:
        FileType 枚举值
    """
    ext = get_file_extension(file_path)
    
    if ext == '.pdf':
        return FileType.PDF
    elif ext in ['.docx', '.doc']:
        return FileType.DOCX if ext == '.docx' else FileType.DOC
    elif ext in ['.md', '.markdown']:
        return FileType.MARKDOWN
    elif ext in config.security.SUPPORTED_TEXT_EXTENSIONS:
        return FileType.TEXT
    elif ext in ['.xlsx', '.xls']:
        return FileType.EXCEL
    elif ext in ['.pptx', '.ppt']:
        return FileType.POWERPOINT
    else:
        return FileType.UNKNOWN


def get_file_info(file_path: str) -> FileInfo:
    """
    获取文件的综合信息。
    
    参数:
        file_path: 文件路径
        
    返回:
        包含文件详细信息的 FileInfo 对象
    """
    stat = os.stat(file_path)
    
    return FileInfo(
        path=normalize_path(file_path),
        name=os.path.basename(file_path),
        size=stat.st_size,
        modified_time=datetime.fromtimestamp(stat.st_mtime),
        file_type=get_file_type(file_path)
    )


def find_file_in_allowed_dirs(file_name: str) -> Optional[str]:
    """
    在所有允许的目录中搜索文件。
    
    参数:
        file_name: 要查找的文件名
        
    返回:
        如果找到则返回完整路径，否则返回 None
    """
    for allowed_dir in config.security.ALLOWED_DIRS:
        potential_paths = [
            os.path.join(allowed_dir, file_name),
            os.path.join(allowed_dir, os.path.basename(file_name))
        ]
        
        for potential_path in potential_paths:
            if os.path.exists(potential_path) and os.path.isfile(potential_path):
                return normalize_path(potential_path)
    
    return None


def list_files_in_directory(
    directory: str, 
    recursive: bool = False,
    filter_extensions: Optional[List[str]] = None
) -> List[str]:
    """
    列出目录中的文件。
    
    参数:
        directory: 要列出的目录
        recursive: 是否递归搜索
        filter_extensions: 可选的扩展名过滤列表
        
    返回:
        文件路径列表
    """
    files = []
    
    if recursive:
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                if not filter_extensions or get_file_extension(file_path) in filter_extensions:
                    files.append(normalize_path(file_path))
    else:
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isfile(item_path):
                if not filter_extensions or get_file_extension(item_path) in filter_extensions:
                    files.append(normalize_path(item_path))
    
    return sorted(files)


# ============================================================================
# 文本处理工具
# ============================================================================

def clean_text(text: str) -> str:
    """
    清理和规范化文本内容。
    
    参数:
        text: 要清理的文本
        
    返回:
        清理后的文本
    """
    if not text:
        return ""
    
    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    
    # 移除控制字符，但保留换行符和制表符
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # 规范化换行符
    text = re.sub(r'\r\n|\r', '\n', text)
    
    return text.strip()


def is_meaningful_text(text: str) -> bool:
    """
    检查文本是否包含有意义的内容。
    
    参数:
        text: 要检查的文本
        
    返回:
        如果文本有意义则返回 True，否则返回 False
    """
    if not text or len(text) < config.document.MIN_TEXT_LENGTH:
        return False
    
    # 检查最小有意义字符数
    meaningful_chars = len(re.findall(r'[a-zA-Z\u4e00-\u9fff]', text))
    if meaningful_chars < config.document.MIN_MEANINGFUL_CHARS:
        return False
    
    # 检查可打印字符比例
    printable_chars = sum(1 for c in text if c.isprintable())
    if len(text) > 0 and printable_chars / len(text) < config.document.MAX_PRINTABLE_RATIO:
        return False
    
    return True


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    将文本截断到最大长度。
    
    参数:
        text: 要截断的文本
        max_length: 最大长度
        suffix: 截断时添加的后缀
        
    返回:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def extract_keywords(text: str, min_length: int = 3, max_keywords: int = 10) -> List[str]:
    """
    从文本中提取关键词。
    
    参数:
        text: 要提取关键词的文本
        min_length: 关键词最小长度
        max_keywords: 关键词最大数量
        
    返回:
        关键词列表
    """
    # 简单关键词提取 - 可以使用 NLP 库增强
    words = re.findall(r'\b[a-zA-Z\u4e00-\u9fff]{' + str(min_length) + ',}\b', text.lower())
    
    # 统计词频
    word_count = {}
    for word in words:
        word_count[word] = word_count.get(word, 0) + 1
    
    # 按频率排序并返回前几个关键词
    keywords = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in keywords[:max_keywords]]


# ============================================================================
# 哈希和校验和工具
# ============================================================================

def calculate_file_hash(file_path: str, algorithm: str = 'md5') -> str:
    """
    计算文件的哈希值。
    
    参数:
        file_path: 文件路径
        algorithm: 哈希算法 ('md5', 'sha1', 'sha256')
        
    返回:
        哈希的十六进制摘要
    """
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def calculate_text_hash(text: str, algorithm: str = 'md5') -> str:
    """
    计算文本内容的哈希值。
    
    参数:
        text: 要哈希的文本
        algorithm: 哈希算法
        
    返回:
        哈希的十六进制摘要
    """
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(text.encode('utf-8'))
    return hash_obj.hexdigest()


# ============================================================================
# 临时文件工具
# ============================================================================

def create_temp_file(suffix: str = '', prefix: str = 'mcp_', content: Optional[str] = None) -> str:
    """
    创建临时文件。
    
    参数:
        suffix: 文件后缀
        prefix: 文件前缀
        content: 可选的写入内容
        
    返回:
        临时文件的路径
    """
    fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    
    try:
        if content:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            os.close(fd)
    except Exception:
        os.close(fd)
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    
    return temp_path


def create_temp_directory(prefix: str = 'mcp_') -> str:
    """
    创建临时目录。
    
    参数:
        prefix: 目录前缀
        
    返回:
        临时目录的路径
    """
    return tempfile.mkdtemp(prefix=prefix)


def cleanup_temp_path(path: str) -> None:
    """
    清理临时文件或目录。
    
    参数:
        path: 要清理的路径
    """
    try:
        if os.path.isfile(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
    except Exception:
        pass  # 忽略清理错误


# ============================================================================
# 时间和日期工具
# ============================================================================

def format_timestamp(timestamp: float, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """
    将时间戳格式化为可读字符串。
    
    参数:
        timestamp: Unix 时间戳
        format_str: 格式字符串
        
    返回:
        格式化的时间字符串
    """
    return datetime.fromtimestamp(timestamp).strftime(format_str)


def get_current_timestamp() -> float:
    """获取当前 Unix 时间戳。"""
    return time.time()


def format_duration(seconds: float) -> str:
    """
    将以秒为单位的持续时间格式化为可读字符串。
    
    参数:
        seconds: 以秒为单位的持续时间
        
    返回:
        格式化的持续时间字符串
    """
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


# ============================================================================
# 数据转换工具
# ============================================================================

def bytes_to_human_readable(bytes_size: int) -> str:
    """
    将字节转换为人类可读的格式。
    
    参数:
        bytes_size: 以字节为单位的大小
        
    返回:
        人类可读的大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f}{unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f}PB"


def safe_json_serialize(obj: Any) -> Any:
    """
    安全地将对象序列化为 JSON 兼容格式。
    
    参数:
        obj: 要序列化的对象
        
    返回:
        JSON 可序列化的对象
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (set, tuple)):
        return list(obj)
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='ignore')
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    else:
        return str(obj)


# ============================================================================
# 验证工具
# ============================================================================

def validate_query_string(query: str, min_length: int = 1, max_length: int = 1000) -> bool:
    """
    验证搜索查询字符串。
    
    参数:
        query: 要验证的查询字符串
        min_length: 最小长度
        max_length: 最大长度
        
    返回:
        如果有效则返回 True，否则返回 False
    """
    if not query or not isinstance(query, str):
        return False
    
    query = query.strip()
    return min_length <= len(query) <= max_length


def validate_file_path(file_path: str) -> bool:
    """
    验证文件路径的基本安全性。
    
    参数:
        file_path: 要验证的文件路径
        
    返回:
        如果有效则返回 True，否则返回 False
    """
    if not file_path or not isinstance(file_path, str):
        return False
    
    # 检查路径遍历尝试
    if '..' in file_path or file_path.startswith('/'):
        return False
    
    # 检查无效字符
    invalid_chars = ['<', '>', ':', '"', '|', '?', '*']
    if any(char in file_path for char in invalid_chars):
        return False
    
    return True


# ============================================================================
# 性能工具
# ============================================================================

class Timer:
    """用于测量执行时间的简单计时器"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
    
    def start(self):
        """启动计时器"""
        self.start_time = time.time()
        self.end_time = None
    
    def stop(self) -> float:
        """停止计时器并返回经过的时间"""
        self.end_time = time.time()
        return self.elapsed()
    
    def elapsed(self) -> float:
        """获取经过的时间"""
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.start_time
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()


def measure_memory_usage() -> Dict[str, int]:
    """
    测量当前内存使用情况。
    
    返回:
        包含内存统计信息的字典
    """
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        return {
            'rss': memory_info.rss,  # 常驻内存集
            'vms': memory_info.vms,  # 虚拟内存大小
            'percent': process.memory_percent()
        }
    except ImportError:
        return {}


# ============================================================================
# 系统工具
# ============================================================================

def check_disk_space(path: str) -> Dict[str, int]:
    """
    检查路径的可用磁盘空间。
    
    参数:
        path: 要检查的路径
        
    返回:
        包含磁盘空间信息的字典
    """
    stat = shutil.disk_usage(path)
    return {
        'total': stat.total,
        'used': stat.used,
        'free': stat.free,
        'percent_used': (stat.used / stat.total) * 100
    }


def get_mime_type(file_path: str) -> Optional[str]:
    """
    获取文件的 MIME 类型。
    
    参数:
        file_path: 文件路径
        
    返回:
        MIME 类型字符串或 None
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type