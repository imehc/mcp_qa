"""
解析器基础接口和通用功能

该模块定义了所有文档解析器的抽象基类
并提供通用工具函数。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import os
import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter

from ..config import config
from ..types import ParseResult, FileType, ParserStatus, TextChunk
from ..exceptions import ParsingError, FileNotFoundError, UnsupportedFileTypeError
from ..utils import get_file_type, validate_file_access, clean_text, Timer

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """
    所有文档解析器的抽象基类。
    
    该类定义了所有解析器必须实现的接口
    并提供用于文本处理和分块的通用功能。
    """
    
    def __init__(self, file_type: FileType):
        """
        初始化解析器。
        
        参数:
            file_type: 此解析器处理的文件类型
        """
        self.file_type = file_type
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.embedding.CHUNK_SIZE,
            chunk_overlap=config.embedding.CHUNK_OVERLAP,
            separators=config.embedding.TEXT_SEPARATORS
        )
    
    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """
        解析文档并提取其内容。
        
        参数:
            file_path: 要解析的文件路径
            
        返回:
            包含提取内容和元数据的 ParseResult
            
        引发:
            ParsingError: 如果解析失败
        """
        pass
    
    @abstractmethod
    def supports_file(self, file_path: str) -> bool:
        """
        检查此解析器是否支持给定文件。
        
        参数:
            file_path: 要检查的文件路径
            
        返回:
            如果解析器支持此文件则返回 True，否则返回 False
        """
        pass
    
    def validate_file(self, file_path: str) -> None:
        """
        验证文件是否可以解析。
        
        参数:
            file_path: 要验证的文件路径
            
        引发:
            FileNotFoundError: 如果文件不存在
            UnsupportedFileTypeError: 如果文件类型不受支持
            ParsingError: 如果文件验证失败
        """
        # 检查文件存在性和访问权限
        validate_file_access(file_path)
        
        # 检查此解析器是否支持该文件
        if not self.supports_file(file_path):
            raise UnsupportedFileTypeError(
                file_path=file_path,
                file_extension=os.path.splitext(file_path)[1],
                supported_types=[self.file_type.value]
            )
    
    def create_chunks(self, text: str) -> List[str]:
        """
        将文本分割成用于向量索引的块。
        
        参数:
            text: 要分块的文本
            
        返回:
            文本块列表
        """
        if not text:
            return []
        
        # 首先清理文本
        cleaned_text = clean_text(text)
        
        # 分割成块
        chunks = self.text_splitter.split_text(cleaned_text)
        
        # 过滤掉非常短的块
        min_chunk_length = 10  # 最小块长度
        filtered_chunks = [chunk for chunk in chunks if len(chunk.strip()) >= min_chunk_length]
        
        return filtered_chunks
    
    def create_text_chunks(self, text: str, source: str) -> List[TextChunk]:
        """
        创建带有元数据的 TextChunk 对象。
        
        参数:
            text: 要分块的文本
            source: 源文件路径
            
        返回:
            TextChunk 对象列表
        """
        chunks = self.create_chunks(text)
        text_chunks = []
        
        for i, chunk_content in enumerate(chunks):
            text_chunk = TextChunk(
                content=chunk_content,
                chunk_id=i,
                source=source,
                metadata={
                    "parser": self.__class__.__name__,
                    "file_type": self.file_type.value,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "char_count": len(chunk_content)
                }
            )
            text_chunks.append(text_chunk)
        
        return text_chunks
    
    def create_success_result(
        self,
        file_path: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        parsing_method: Optional[str] = None
    ) -> ParseResult:
        """
        创建成功的 ParseResult。
        
        参数:
            file_path: 已解析的文件路径
            content: 提取的内容
            metadata: 可选的元数据
            parsing_method: 用于解析的方法
            
        返回:
            表示成功的 ParseResult
        """
        chunks = self.create_chunks(content)
        
        return ParseResult(
            success=True,
            file_path=file_path,
            file_type=self.file_type,
            status=ParserStatus.SUCCESS,
            content=content,
            chunks=chunks,
            metadata=metadata or {},
            parsing_method=parsing_method or self.__class__.__name__
        )
    
    def create_error_result(
        self,
        file_path: str,
        error: str,
        status: ParserStatus = ParserStatus.ERROR,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ParseResult:
        """
        创建错误的 ParseResult。
        
        参数:
            file_path: 解析失败的文件路径
            error: 错误消息
            status: 解析器状态
            metadata: 可选的元数据
            
        返回:
            表示失败的 ParseResult
        """
        return ParseResult(
            success=False,
            file_path=file_path,
            file_type=self.file_type,
            status=status,
            error=error,
            metadata=metadata or {}
        )
    
    def safe_parse(self, file_path: str) -> ParseResult:
        """
        带有错误处理的安全文件解析。
        
        参数:
            file_path: 要解析的文件路径
            
        返回:
            包含成功或错误信息的 ParseResult
        """
        timer = Timer()
        timer.start()
        
        try:
            # 首先验证文件
            self.validate_file(file_path)
            
            # 解析文件
            result = self.parse(file_path)
            
            # 添加计时信息
            if result.metadata is None:
                result.metadata = {}
            result.metadata['parsing_time'] = timer.elapsed()
            
            logger.info(f"成功解析 {file_path}，耗时 {timer.elapsed():.2f} 秒")
            return result
            
        except Exception as e:
            logger.error(f"解析 {file_path} 失败: {str(e)}")
            return self.create_error_result(
                file_path=file_path,
                error=str(e),
                metadata={'parsing_time': timer.elapsed()}
            )


class TextBasedParser(BaseParser):
    """
    基于文本格式的解析器基类。
    
    该类为从文档中提取纯文本内容的解析器提供通用功能。
    """
    
    def __init__(self, file_type: FileType, supported_extensions: List[str]):
        """
        初始化基于文本的解析器。
        
        参数:
            file_type: 此解析器处理的文件类型
            supported_extensions: 支持的文件扩展名列表
        """
        super().__init__(file_type)
        self.supported_extensions = [ext.lower() for ext in supported_extensions]
    
    def supports_file(self, file_path: str) -> bool:
        """
        根据扩展名检查此解析器是否支持给定文件。
        
        参数:
            file_path: 要检查的文件路径
            
        返回:
            如果解析器支持此文件则返回 True，否则返回 False
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        return file_ext in self.supported_extensions
    
    def extract_text_from_file(self, file_path: str, encoding: str = 'utf-8') -> str:
        """
        从文本文件中提取文本内容。
        
        参数:
            file_path: 文本文件路径
            encoding: 文件编码
            
        返回:
            提取的文本内容
            
        引发:
            ParsingError: 如果文本提取失败
        """
        try:
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read()
            
            # 清理和验证内容
            cleaned_content = clean_text(content)
            
            if not cleaned_content.strip():
                raise ParsingError(
                    message=f"文件不包含可读文本: {file_path}",
                    file_path=file_path
                )
            
            return cleaned_content
            
        except UnicodeDecodeError as e:
            raise ParsingError(
                message=f"{file_path} 中的文本编码错误: {str(e)}",
                file_path=file_path
            )
        except Exception as e:
            raise ParsingError(
                message=f"读取文本文件 {file_path} 失败: {str(e)}",
                file_path=file_path
            )


class StructuredParser(BaseParser):
    """
    结构化文档格式的解析器基类。
    
    该类为从文档中提取结构化内容（如段落、章节等）的解析器提供通用功能。
    """
    
    def __init__(self, file_type: FileType):
        """
        初始化结构化解析器。
        
        参数:
            file_type: 此解析器处理的文件类型
        """
        super().__init__(file_type)
    
    def extract_structured_content(self, file_path: str) -> Dict[str, Any]:
        """
        从文档中提取结构化内容。
        
        子类应重写此方法以提供特定格式的结构化提取。
        
        参数:
            file_path: 文档路径
            
        返回:
            包含结构化内容的字典
            
        引发:
            NotImplementedError: 如果子类未实现
        """
        raise NotImplementedError("子类必须实现 extract_structured_content")
    
    def combine_structured_content(self, structured_content: Dict[str, Any]) -> str:
        """
        将结构化内容合并为单个文本字符串。
        
        参数:
            structured_content: 包含结构化内容的字典
            
        返回:
            合并的文本内容
        """
        # 默认实现 - 可由子类重写
        text_parts = []
        
        # 从常见结构类型中提取文本
        if 'pages' in structured_content:
            for page in structured_content['pages']:
                if isinstance(page, dict) and 'content' in page:
                    text_parts.append(page['content'])
                elif isinstance(page, str):
                    text_parts.append(page)
        
        if 'paragraphs' in structured_content:
            for paragraph in structured_content['paragraphs']:
                if isinstance(paragraph, dict) and 'content' in paragraph:
                    text_parts.append(paragraph['content'])
                elif isinstance(paragraph, str):
                    text_parts.append(paragraph)
        
        if 'sections' in structured_content:
            for section in structured_content['sections']:
                if isinstance(section, dict) and 'content' in section:
                    text_parts.append(section['content'])
                elif isinstance(section, str):
                    text_parts.append(section)
        
        # 如果未找到结构化内容，则尝试提取任何文本
        if not text_parts and isinstance(structured_content, dict):
            for value in structured_content.values():
                if isinstance(value, str) and len(value.strip()) > 10:
                    text_parts.append(value)
        
        return '\n\n'.join(text_parts)


def get_parser_for_file(file_path: str) -> Optional[BaseParser]:
    """
    获取适合给定文件的解析器。
    
    参数:
        file_path: 文件路径
        
    返回:
        解析器实例，如果没有合适的解析器则返回 None
    """
    # 创建特定解析器后将实现此函数
    # 目前，它是一个占位符
    file_type = get_file_type(file_path)
    
    # 在此处导入解析器以避免循环导入
    from .pdf import PDFParser
    from .docx import DocxParser
    from .markdown import MarkdownParser
    from .text import TextParser
    
    parser_map = {
        FileType.PDF: PDFParser(),
        FileType.DOCX: DocxParser(),
        FileType.DOC: DocxParser(),  # DocxParser 处理 .doc 和 .docx
        FileType.MARKDOWN: MarkdownParser(),
        FileType.TEXT: TextParser()
    }
    
    return parser_map.get(file_type)


def parse_document(file_path: str) -> ParseResult:
    """
    使用适当的解析器解析文档。
    
    参数:
        file_path: 要解析的文档路径
        
    返回:
        包含解析内容的 ParseResult
        
    引发:
        UnsupportedFileTypeError: 如果没有适用于该文件类型的解析器
    """
    parser = get_parser_for_file(file_path)
    
    if parser is None:
        file_type = get_file_type(file_path)
        raise UnsupportedFileTypeError(
            file_path=file_path,
            file_extension=os.path.splitext(file_path)[1],
            supported_types=[ft.value for ft in FileType if ft != FileType.UNKNOWN]
        )
    
    return parser.safe_parse(file_path)


def get_supported_extensions():
    """获取所有支持的文件扩展名"""
    return config.security.get_all_supported_extensions()