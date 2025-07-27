"""
MCP 服务器文本文档解析器

该模块提供各种纯文本格式的文本文件解析功能，
包括源代码文件。
"""

import os
import logging
from typing import Dict, Any

from ..types import ParseResult, FileType
from ..exceptions import ParsingError, EmptyDocumentError, EncodingError
from .base import TextBasedParser
from ..config import config

logger = logging.getLogger(__name__)


class TextParser(TextBasedParser):
    """
    纯文本文档和源代码文件的解析器。
    
    此解析器处理各种基于文本的文件格式，包括
    源代码、配置文件、日志和纯文本文档。
    """
    
    def __init__(self):
        """初始化文本解析器。"""
        super().__init__(FileType.TEXT, config.security.SUPPORTED_TEXT_EXTENSIONS)
        
        # 定义语言映射以提供语法高亮提示
        self.language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'jsx',
            '.tsx': 'tsx',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.r': 'r',
            '.sql': 'sql',
            '.sh': 'bash',
            '.bash': 'bash',
            '.zsh': 'zsh',
            '.fish': 'fish',
            '.ps1': 'powershell',
            '.bat': 'batch',
            '.cmd': 'batch',
            '.html': 'html',
            '.htm': 'html',
            '.xml': 'xml',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.less': 'less',
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.cfg': 'ini',
            '.conf': 'ini',
            '.log': 'log',
            '.txt': 'text',
            '.csv': 'csv'
        }
    
    def parse(self, file_path: str, use_cache: bool = True) -> ParseResult:
        """
        解析文本文档并提取其内容。
        
        参数:
            file_path: 文本文件路径
            use_cache: 是否使用缓存（默认True）
            
        返回:
            包含提取内容和元数据的 ParseResult
            
        引发:
            ParsingError: 如果文本解析失败
        """
        # 如果启用缓存且支持缓存，先检查缓存
        if use_cache and self.cache_aware:
            try:
                from ..indexing.cache import is_file_indexed_and_current, file_index_cache
                
                if is_file_indexed_and_current(file_path):
                    cached_info = file_index_cache.get_cached_file_info(file_path)
                    if cached_info and cached_info.get("parse_content"):
                        logger.info(f"使用文本解析缓存: {file_path}")
                        
                        # 从缓存构造结果
                        from ..types import ParserStatus
                        return ParseResult(
                            success=True,
                            file_path=file_path,
                            file_type=self.file_type,
                            status=ParserStatus.SUCCESS,
                            content=cached_info["parse_content"],
                            chunks=[],  # 空的，因为主要内容来自缓存
                            metadata={
                                "from_cache": True,
                                "cached_at": cached_info.get("indexed_at"),
                                "file_size": cached_info.get("size", 0),
                                "chunks_count": cached_info.get("chunks_count", 0),
                                "parsing_method": "Cached-TextParser",
                                **(cached_info.get("metadata", {}))
                            },
                            parsing_method="Cached-TextParser"
                        )
                        
            except ImportError:
                logger.debug("缓存模块不可用，执行常规文本解析")
            except Exception as e:
                logger.warning(f"文本缓存检查失败: {e}，执行常规解析")
        
        # 缓存未命中或禁用缓存，执行常规解析
        return self._parse_text_content(file_path)
    
    def _parse_text_content(self, file_path: str) -> ParseResult:
        """
        执行文本内容的实际解析。
        
        参数:
            file_path: 文本文件路径
            
        返回:
            包含提取内容和元数据的 ParseResult
        """
        try:
            # 尝试不同编码
            content = None
            encoding_used = None
            
            for encoding in ['utf-8', 'utf-16', 'latin1', 'cp1252', 'gbk', 'gb2312']:
                try:
                    content = self.extract_text_from_file(file_path, encoding)
                    encoding_used = encoding
                    break
                except (UnicodeDecodeError, EncodingError):
                    continue
            
            if content is None:
                raise EncodingError(
                    file_path=file_path,
                    encoding="unknown",
                    error_details="无法使用任何支持的编码解码文件"
                )
            
            if not content.strip():
                raise EmptyDocumentError(file_path, "TextParser")
            
            # 提取结构化信息
            structured_content = self._analyze_text_content(content, file_path)
            
            # 创建元数据
            metadata = {
                "encoding": encoding_used,
                "file_type": "text",
                "language": self._detect_language(file_path),
                "line_count": structured_content.get("line_count", 0),
                "char_count": len(content),
                "word_count": structured_content.get("word_count", 0),
                "non_empty_lines": structured_content.get("non_empty_lines", 0),
                "file_size": os.path.getsize(file_path),
                "statistics": structured_content.get("statistics", {}),
                "language_features": structured_content.get("language_features", {}),
                "parsing_method": f"TextParser ({encoding_used})"
            }
            
            logger.info(f"文本解析完成: {file_path} ({metadata['line_count']} 行, {encoding_used} 编码)")
            
            return self.create_success_result(
                file_path=file_path,
                content=content,
                metadata=metadata,
                parsing_method=f"TextParser ({encoding_used})"
            )
            
        except Exception as e:
            logger.error(f"文本解析失败 {file_path}: {str(e)}")
            return self.create_error_result(
                file_path=file_path,
                error=f"文本解析失败: {str(e)}"
            )
    
    def _analyze_text_content(self, content: str, file_path: str) -> Dict[str, Any]:
        """
        分析文本内容并提取统计信息。
        
        参数:
            content: 要分析的文本内容
            file_path: 源文件路径
            
        返回:
            包含文本分析结果的字典
        """
        lines = content.split('\n')
        words = content.split()
        
        # 基本统计
        line_count = len(lines)
        word_count = len(words)
        char_count = len(content)
        non_empty_lines = len([line for line in lines if line.strip()])
        
        # 高级统计
        avg_line_length = sum(len(line) for line in lines) / line_count if line_count > 0 else 0
        max_line_length = max(len(line) for line in lines) if lines else 0
        avg_word_length = sum(len(word) for word in words) / word_count if word_count > 0 else 0
        
        # 语言特定分析
        language = self._detect_language(file_path)
        language_features = self._analyze_language_features(content, language)
        
        statistics = {
            "line_count": line_count,
            "word_count": word_count,
            "char_count": char_count,
            "non_empty_lines": non_empty_lines,
            "empty_lines": line_count - non_empty_lines,
            "avg_line_length": round(avg_line_length, 2),
            "max_line_length": max_line_length,
            "avg_word_length": round(avg_word_length, 2)
        }
        
        return {
            "line_count": line_count,
            "word_count": word_count,
            "non_empty_lines": non_empty_lines,
            "statistics": statistics,
            "language_features": language_features
        }
    
    def _detect_language(self, file_path: str) -> str:
        """
        根据文件扩展名检测编程语言。
        
        参数:
            file_path: 文件路径
            
        返回:
            语言标识符字符串
        """
        ext = os.path.splitext(file_path)[1].lower()
        return self.language_map.get(ext, 'text')
    
    def _analyze_language_features(self, content: str, language: str) -> Dict[str, Any]:
        """
        分析内容中的语言特定功能。
        
        参数:
            content: 要分析的文本内容
            language: 检测到的语言
            
        返回:
            包含语言特定功能的字典
        """
        features = {}
        
        if language == 'python':
            features = self._analyze_python_features(content)
        elif language in ['javascript', 'typescript', 'jsx', 'tsx']:
            features = self._analyze_javascript_features(content)
        elif language in ['java', 'c', 'cpp', 'csharp']:
            features = self._analyze_c_like_features(content)
        elif language == 'json':
            features = self._analyze_json_features(content)
        elif language in ['yaml', 'yml']:
            features = self._analyze_yaml_features(content)
        elif language == 'csv':
            features = self._analyze_csv_features(content)
        elif language == 'log':
            features = self._analyze_log_features(content)
        else:
            features = self._analyze_generic_features(content)
        
        return features
    
    def _analyze_python_features(self, content: str) -> Dict[str, Any]:
        """分析 Python 特定功能。"""
        import re
        
        # 计算导入语句
        import_count = len(re.findall(r'^(?:from\s+\S+\s+)?import\s+', content, re.MULTILINE))
        
        # 计算函数定义
        function_count = len(re.findall(r'^def\s+\w+\s*\(', content, re.MULTILINE))
        
        # 计算类定义
        class_count = len(re.findall(r'^class\s+\w+', content, re.MULTILINE))
        
        # 计算注释
        comment_count = len(re.findall(r'#.*$', content, re.MULTILINE))
        
        # 计算文档字符串
        docstring_count = len(re.findall(r'""".*?"""', content, re.DOTALL))
        docstring_count += len(re.findall(r"'''.*?'''", content, re.DOTALL))
        
        return {
            "imports": import_count,
            "functions": function_count,
            "classes": class_count,
            "comments": comment_count,
            "docstrings": docstring_count
        }
    
    def _analyze_javascript_features(self, content: str) -> Dict[str, Any]:
        """分析 JavaScript/TypeScript 特定功能。"""
        import re
        
        # 计算函数定义
        function_count = len(re.findall(r'function\s+\w+\s*\(', content))
        arrow_function_count = len(re.findall(r'\w+\s*=\s*\([^)]*\)\s*=>', content))
        
        # 计算导入/需要语句
        import_count = len(re.findall(r'^(?:import|const\s+\w+\s*=\s*require)', content, re.MULTILINE))
        
        # 计算注释
        single_comment_count = len(re.findall(r'//.*$', content, re.MULTILINE))
        multi_comment_count = len(re.findall(r'/\*.*?\*/', content, re.DOTALL))
        
        return {
            "functions": function_count,
            "arrow_functions": arrow_function_count,
            "imports": import_count,
            "single_line_comments": single_comment_count,
            "multi_line_comments": multi_comment_count
        }
    
    def _analyze_c_like_features(self, content: str) -> Dict[str, Any]:
        """分析类 C 语言功能。"""
        import re
        
        # 计算函数定义 (简化)
        function_count = len(re.findall(r'\w+\s+\w+\s*\([^)]*\)\s*{', content))
        
        # 计算包含语句
        include_count = len(re.findall(r'^#include\s*<[^>]+>', content, re.MULTILINE))
        include_count += len(re.findall(r'^#include\s*"[^"]+"', content, re.MULTILINE))
        
        # 计算注释
        single_comment_count = len(re.findall(r'//.*$', content, re.MULTILINE))
        multi_comment_count = len(re.findall(r'/\*.*?\*/', content, re.DOTALL))
        
        return {
            "functions": function_count,
            "includes": include_count,
            "single_line_comments": single_comment_count,
            "multi_line_comments": multi_comment_count
        }
    
    def _analyze_json_features(self, content: str) -> Dict[str, Any]:
        """分析 JSON 特定功能。"""
        import json
        
        try:
            data = json.loads(content)
            
            def count_items(obj):
                if isinstance(obj, dict):
                    return len(obj) + sum(count_items(v) for v in obj.values())
                elif isinstance(obj, list):
                    return len(obj) + sum(count_items(item) for item in obj)
                else:
                    return 1
            
            total_items = count_items(data)
            
            return {
                "valid_json": True,
                "total_items": total_items,
                "root_type": type(data).__name__
            }
        except (json.JSONDecodeError, Exception):
            return {
                "valid_json": False,
                "error": "无效的 JSON 格式"
            }
    
    def _analyze_yaml_features(self, content: str) -> Dict[str, Any]:
        """分析 YAML 特定功能。"""
        import re
        
        # 计算键值对 (简化)
        kv_pairs = len(re.findall(r'^\s*\w+\s*:', content, re.MULTILINE))
        
        # 计算列表项
        list_items = len(re.findall(r'^\s*-\s+', content, re.MULTILINE))
        
        # 计算注释
        comments = len(re.findall(r'#.*$', content, re.MULTILINE))
        
        return {
            "key_value_pairs": kv_pairs,
            "list_items": list_items,
            "comments": comments
        }
    
    def _analyze_csv_features(self, content: str) -> Dict[str, Any]:
        """分析 CSV 特定功能。"""
        lines = content.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        if not non_empty_lines:
            return {"rows": 0, "columns": 0}
        
        # 估算分隔符
        first_line = non_empty_lines[0]
        comma_count = first_line.count(',')
        semicolon_count = first_line.count(';')
        tab_count = first_line.count('\t')
        
        delimiter = ','
        if semicolon_count > comma_count and semicolon_count > tab_count:
            delimiter = ';'
        elif tab_count > comma_count and tab_count > semicolon_count:
            delimiter = '\t'
        
        # 计算列数 (从第一行)
        columns = len(first_line.split(delimiter))
        
        return {
            "rows": len(non_empty_lines),
            "columns": columns,
            "estimated_delimiter": delimiter
        }
    
    def _analyze_log_features(self, content: str) -> Dict[str, Any]:
        """分析日志文件功能。"""
        import re
        
        lines = content.split('\n')
        
        # 计算不同日志级别
        error_count = len(re.findall(r'\b(?:ERROR|ERR)\b', content, re.IGNORECASE))
        warning_count = len(re.findall(r'\b(?:WARNING|WARN)\b', content, re.IGNORECASE))
        info_count = len(re.findall(r'\b(?:INFO|INF)\b', content, re.IGNORECASE))
        debug_count = len(re.findall(r'\b(?:DEBUG|DBG)\b', content, re.IGNORECASE))
        
        # 尝试检测时间戳模式
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}:\d{2}:\d{2}',  # HH:MM:SS
        ]
        
        timestamps = 0
        for pattern in timestamp_patterns:
            timestamps += len(re.findall(pattern, content))
        
        return {
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "debug_count": debug_count,
            "timestamp_count": timestamps
        }
    
    def _analyze_generic_features(self, content: str) -> Dict[str, Any]:
        """分析通用文本功能。"""
        import re
        
        # 计算 URL
        url_count = len(re.findall(r'https?://[^\s]+', content))
        
        # 计算电子邮件地址
        email_count = len(re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content))
        
        # 计算数字
        number_count = len(re.findall(r'\b\d+\.?\d*\b', content))
        
        return {
            "urls": url_count,
            "emails": email_count,
            "numbers": number_count
        }
    
    def extract_structured_content(self, file_path: str) -> Dict[str, Any]:
        """
        从文本文件中提取结构化内容。
        
        参数:
            file_path: 文本文件路径
            
        返回:
            包含结构化内容的字典
            
        引发:
            ParsingError: 如果提取失败
        """
        parse_result = self.parse(file_path)
        
        if not parse_result.success:
            raise ParsingError(
                message=parse_result.error or "提取结构化内容失败",
                file_path=file_path
            )
        
        return parse_result.metadata or {}
    
    def combine_structured_content(self, structured_content: Dict[str, Any]) -> str:
        """
        对于文本文件，内容已处于最佳格式。
        
        参数:
            structured_content: 包含结构化内容的字典
            
        返回:
            原样返回文本内容
        """
        # 对于文本文件，我们不需要合并任何内容
        # 内容已处于最佳格式
        return structured_content.get("content", "")