"""
MCP 服务器路径验证和安全工具

该模块提供全面的路径验证和安全检查，
以防止路径遍历攻击和未授权文件访问。
"""

import os
import re
import logging
from typing import List, Optional
from pathlib import Path

from ..config import config
from ..exceptions import (
    PathTraversalError, 
    FileAccessDeniedError, 
    SecurityError
)

logger = logging.getLogger(__name__)


class PathValidator:
    """
    全面的路径验证和安全实施。
    
    该类提供验证文件路径、防止路径遍历攻击和实施访问控制策略的方法。
    """
    
    def __init__(self, allowed_directories: Optional[List[str]] = None):
        """
        初始化路径验证器。
        
        参数:
            allowed_directories: 允许的目录路径列表
        """
        self.allowed_directories = allowed_directories or config.security.ALLOWED_DIRS
        self.normalized_allowed_dirs = [
            os.path.normpath(os.path.abspath(d)) for d in self.allowed_directories
        ]
        
        # 应该被阻止的危险路径组件
        self.dangerous_components = {
            '..',
            '~',
            '$',
            '%',
            '&',
            '|',
            ';',
            '`',
            '$(',
            '${',
            '<!--',
            '-->',
            '<script',
            '</script>',
            'javascript:',
            'data:',
            'file://',
            'ftp://',
            'http://',
            'https://'
        }
        
        # 应该被阻止的危险文件扩展名
        self.dangerous_extensions = {
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr',
            '.vbs', '.vbe', '.js', '.jse', '.wsf', '.wsh',
            '.msc', '.jar', '.app', '.deb', '.pkg', '.dmg',
            '.iso', '.img', '.bin', '.run', '.sh', '.bash',
            '.ps1', '.psm1', '.psd1', '.ps1xml', '.psc1',
            '.reg', '.inf', '.sys', '.dll', '.ocx',
            '.cpl', '.drv', '.scf', '.lnk', '.url'
        }
        
        # 文件路径中的可疑模式
        self.suspicious_patterns = [
            r'\.\.[\\/]',           # 路径遍历
            r'[\\/]\.\.[\\/]',      # 中间路径遍历
            r'^\.\.',               # 以 .. 开头
            r'[\\/]\.[\\/]',        # 当前目录引用 (./或\.)
            r'[<>:"|?*]',           # 无效文件名字符
            r'\$\{[^}]*\}',         # Shell 变量展开
            r'\$\([^)]*\)',         # 命令替换
            r'[`´]',                # 反引号
            r'\\x[0-9a-fA-F]{2}',   # 十六进制转义序列
            r'%[0-9a-fA-F]{2}',     # URL 编码
            r'[\x00-\x1f\x7f-\x9f]' # 控制字符
        ]
        
        self.compiled_patterns = [re.compile(pattern) for pattern in self.suspicious_patterns]
    
    def validate_path(self, path: str, check_existence: bool = True) -> str:
        """
        验证文件路径的安全性和访问控制。
        
        参数:
            path: 要验证的文件路径
            check_existence: 是否检查路径是否存在
            
        返回:
            规范化和验证后的路径
            
        引发:
            PathTraversalError: 如果检测到路径遍历
            FileAccessDeniedError: 如果访问被拒绝
            SecurityError: 如果发现其他安全问题
        """
        if not path or not isinstance(path, str):
            raise SecurityError("无效路径: 路径必须是非空字符串")
        
        # 检查危险组件
        self._check_dangerous_components(path)
        
        # 检查可疑模式
        self._check_suspicious_patterns(path)
        
        # 规范化路径
        normalized_path = self._normalize_path(path)
        
        # 检查路径遍历
        self._check_path_traversal(normalized_path, path)
        
        # 检查路径是否在允许的目录内
        self._check_allowed_directories(normalized_path)
        
        # 检查文件扩展名
        self._check_file_extension(normalized_path)
        
        # 如果请求则检查存在性
        if check_existence and not os.path.exists(normalized_path):
            raise FileAccessDeniedError(
                file_path=normalized_path,
                allowed_directories=self.allowed_directories
            )
        
        return normalized_path
    
    def _normalize_path(self, path: str) -> str:
        """
        规范化文件路径。
        
        参数:
            path: 要规范化的文件路径
            
        返回:
            规范化的绝对路径
        """
        try:
            # 移除任何 URL 编码
            path = self._decode_url_encoding(path)
            
            # 转换为绝对路径并规范化
            abs_path = os.path.abspath(path)
            normalized = os.path.normpath(abs_path)
            
            # 使用 pathlib 进行额外规范化
            pathlib_path = Path(normalized)
            resolved = pathlib_path.resolve()
            
            return str(resolved)
        except (OSError, ValueError) as e:
            raise SecurityError(f"路径规范化失败: {str(e)}")
    
    def _decode_url_encoding(self, path: str) -> str:
        """
        解码路径中的 URL 编码。
        
        参数:
            path: 可能包含 URL 编码的路径
            
        返回:
            解码后的路径
        """
        import urllib.parse
        
        try:
            # 仅在包含 URL 编码模式时解码
            if '%' in path:
                decoded = urllib.parse.unquote(path)
                # 防止双重解码攻击
                if decoded != path and '%' in decoded:
                    raise SecurityError("检测到多层 URL 编码")
                return decoded
            return path
        except Exception:
            # 如果解码失败，返回原始路径 (更安全)
            return path
    
    def _check_dangerous_components(self, path: str) -> None:
        """
        检查危险的路径组件。
        
        参数:
            path: 要检查的路径
            
        引发:
            SecurityError: 如果发现危险组件
        """
        path_lower = path.lower()
        
        for dangerous in self.dangerous_components:
            if dangerous in path_lower:
                raise SecurityError(
                    f"检测到危险路径组件: {dangerous}",
                    details={"component": dangerous, "path": path}
                )
    
    def _check_suspicious_patterns(self, path: str) -> None:
        """
        检查路径中的可疑模式。
        
        参数:
            path: 要检查的路径
            
        引发:
            SecurityError: 如果发现可疑模式
        """
        for pattern in self.compiled_patterns:
            if pattern.search(path):
                raise SecurityError(
                    f"在路径中检测到可疑模式: {pattern.pattern}",
                    details={"pattern": pattern.pattern, "path": path}
                )
    
    def _check_path_traversal(self, normalized_path: str, original_path: str) -> None:
        """
        检查路径遍历尝试。
        
        参数:
            normalized_path: 规范化路径
            original_path: 规范化前的原始路径
            
        引发:
            PathTraversalError: 如果检测到路径遍历
        """
        # 检查规范化路径与原始路径是否有显著差异
        # 这可能表明路径遍历尝试
        
        # 转换路径以使用正斜杠进行比较
        norm_forward = normalized_path.replace('\\', '/')
        orig_forward = original_path.replace('\\', '/')
        
        # 检查明显的遍历模式
        if '..' in orig_forward:
            # 计算向上目录的次数
            up_count = orig_forward.count('../') + orig_forward.count('..\\')
            if up_count > 0:
                raise PathTraversalError(original_path)
        
        # 检查规范化路径是否在任何允许的目录之外
        is_within_allowed = False
        for allowed_dir in self.normalized_allowed_dirs:
            if normalized_path.startswith(allowed_dir):
                is_within_allowed = True
                break
        
        if not is_within_allowed:
            # 额外检查: 查看原始路径是否试图逃逸
            for allowed_dir in self.normalized_allowed_dirs:
                if original_path.startswith(allowed_dir):
                    # 原始路径在允许目录内但规范化后不在 - 遍历尝试
                    raise PathTraversalError(original_path)
    
    def _check_allowed_directories(self, path: str) -> None:
        """
        检查路径是否在允许的目录内。
        
        参数:
            path: 要检查的路径
            
        引发:
            FileAccessDeniedError: 如果路径不在允许的目录内
        """
        for allowed_dir in self.normalized_allowed_dirs:
            if path.startswith(allowed_dir):
                return
        
        raise FileAccessDeniedError(
            file_path=path,
            allowed_directories=self.allowed_directories
        )
    
    def _check_file_extension(self, path: str) -> None:
        """
        检查文件扩展名是否被允许。
        
        参数:
            path: 要检查的路径
            
        引发:
            SecurityError: 如果文件扩展名危险
        """
        ext = os.path.splitext(path)[1].lower()
        
        if ext in self.dangerous_extensions:
            raise SecurityError(
                f"不允许的危险文件扩展名: {ext}",
                details={"extension": ext, "path": path}
            )
    
    def is_path_safe(self, path: str) -> bool:
        """
        检查路径是否安全而不引发异常。
        
        参数:
            path: 要检查的路径
            
        返回:
            如果路径安全则返回 True，否则返回 False
        """
        try:
            self.validate_path(path, check_existence=False)
            return True
        except Exception:
            return False
    
    def get_safe_filename(self, filename: str) -> str:
        """
        通过移除危险字符生成安全的文件名。
        
        参数:
            filename: 原始文件名
            
        返回:
            消毒后的文件名
        """
        # 移除路径分隔符
        safe_name = filename.replace('/', '_').replace('\\', '_')
        
        # 移除危险字符
        safe_name = re.sub(r'[<>:"|?*\x00-\x1f\x7f-\x9f]', '_', safe_name)
        
        # 移除开头/结尾的点和空格
        safe_name = safe_name.strip('. ')
        
        # 确保文件名不为空
        if not safe_name:
            safe_name = '未命名文件'
        
        # 如果太长则截断 (保留扩展名)
        max_length = 200
        if len(safe_name) > max_length:
            name, ext = os.path.splitext(safe_name)
            available_length = max_length - len(ext)
            safe_name = name[:available_length] + ext
        
        return safe_name
    
    def check_directory_listing_allowed(self, directory: str) -> bool:
        """
        检查是否允许列出给定目录。
        
        参数:
            directory: 要检查的目录路径
            
        返回:
            如果允许列出则返回 True，否则返回 False
        """
        try:
            normalized_dir = self._normalize_path(directory)
            
            # 检查是否在允许的目录内
            for allowed_dir in self.normalized_allowed_dirs:
                if normalized_dir.startswith(allowed_dir):
                    return True
            
            return False
        except Exception:
            return False
    
    def get_relative_path(self, path: str, base_dir: Optional[str] = None) -> str:
        """
        获取相对于基础目录的路径。
        
        参数:
            path: 绝对路径
            base_dir: 基础目录 (如果为 None 则使用第一个允许的目录)
            
        返回:
            相对路径
        """
        if base_dir is None:
            base_dir = self.normalized_allowed_dirs[0] if self.normalized_allowed_dirs else os.getcwd()
        
        try:
            normalized_path = self._normalize_path(path)
            normalized_base = self._normalize_path(base_dir)
            
            return os.path.relpath(normalized_path, normalized_base)
        except Exception:
            return os.path.basename(path)
    
    def validate_batch_paths(self, paths: List[str]) -> List[str]:
        """
        验证多个路径并仅返回安全的路径。
        
        参数:
            paths: 要验证的路径列表
            
        返回:
            验证后的路径列表
        """
        safe_paths = []
        
        for path in paths:
            try:
                validated_path = self.validate_path(path)
                safe_paths.append(validated_path)
            except Exception as e:
                logger.warning(f"路径验证失败 {path}: {str(e)}")
                continue
        
        return safe_paths


# 全局路径验证器实例
path_validator = PathValidator()


# 便利函数
def validate_path(path: str, check_existence: bool = True) -> str:
    """
    使用全局验证器验证文件路径。
    
    参数:
        path: 要验证的文件路径
        check_existence: 是否检查路径是否存在
        
    返回:
        规范化和验证后的路径
    """
    return path_validator.validate_path(path, check_existence)


def is_path_safe(path: str) -> bool:
    """
    使用全局验证器检查路径是否安全。
    
    参数:
        path: 要检查的路径
        
    返回:
        如果路径安全则返回 True，否则返回 False
    """
    return path_validator.is_path_safe(path)


def get_safe_filename(filename: str) -> str:
    """
    使用全局验证器生成安全的文件名。
    
    参数:
        filename: 原始文件名
        
    返回:
        消毒后的文件名
    """
    return path_validator.get_safe_filename(filename)


def check_directory_listing_allowed(directory: str) -> bool:
    """
    使用全局验证器检查是否允许目录列出。
    
    参数:
        directory: 要检查的目录路径
        
    返回:
        如果允许列出则返回 True，否则返回 False
    """
    return path_validator.check_directory_listing_allowed(directory)