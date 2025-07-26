"""
MCP 服务器 PDF 文档解析器

该模块使用 PyMuPDF (fitz) 提供 PDF 解析功能。
"""

import os
import logging
from typing import Dict, Any, List, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from ..types import ParseResult, FileType, ParserStatus
from ..exceptions import ParsingError, EmptyDocumentError
from .base import StructuredParser

logger = logging.getLogger(__name__)


class PDFParser(StructuredParser):
    """
    使用 PyMuPDF (fitz) 的 PDF 文档解析器。
    
    此解析器从 PDF 文件中提取文本内容，并提供有关页面的结构化信息。
    """
    
    def __init__(self):
        """初始化 PDF 解析器。"""
        super().__init__(FileType.PDF)
        self.supported_extensions = ['.pdf']
    
    def supports_file(self, file_path: str) -> bool:
        """
        检查此解析器是否支持给定文件。
        
        参数:
            file_path: 要检查的文件路径
            
        返回:
            如果文件是 PDF 则返回 True，否则返回 False
        """
        return os.path.splitext(file_path)[1].lower() in self.supported_extensions
    
    def parse(self, file_path: str) -> ParseResult:
        """
        解析 PDF 文档并提取其内容。
        
        参数:
            file_path: PDF 文件路径
            
        返回:
            包含提取内容和元数据的 ParseResult
            
        引发:
            ParsingError: 如果 PDF 解析失败
        """
        if fitz is None:
            return self.create_error_result(
                file_path=file_path,
                error="PyMuPDF (fitz) 未安装。使用以下命令安装: pip install pymupdf",
                status=ParserStatus.ERROR
            )
        
        try:
            # 提取结构化内容
            structured_content = self.extract_structured_content(file_path)
            
            # 合并为完整文本
            full_text = self.combine_structured_content(structured_content)
            
            if not full_text.strip():
                raise EmptyDocumentError(file_path, "PDFParser")
            
            # 创建元数据
            metadata = {
                "total_pages": structured_content.get("total_pages", 0),
                "pages": structured_content.get("pages", []),
                "file_size": os.path.getsize(file_path)
            }
            
            return self.create_success_result(
                file_path=file_path,
                content=full_text,
                metadata=metadata,
                parsing_method="PyMuPDF"
            )
            
        except Exception as e:
            logger.error(f"PDF 解析失败 {file_path}: {str(e)}")
            return self.create_error_result(
                file_path=file_path,
                error=f"PDF 解析失败: {str(e)}"
            )
    
    def extract_structured_content(self, file_path: str) -> Dict[str, Any]:
        """
        从 PDF 文档中提取结构化内容。
        
        参数:
            file_path: PDF 文件路径
            
        返回:
            包含结构化 PDF 内容的字典
            
        引发:
            ParsingError: 如果提取失败
        """
        try:
            doc = fitz.open(file_path)
            pages_content = []
            full_text = ""
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text()
                
                # 清理页面文本
                cleaned_text = page_text.replace('\x0c', '').strip()
                
                if cleaned_text:
                    page_info = {
                        "page_number": page_num + 1,
                        "content": cleaned_text,
                        "char_count": len(cleaned_text),
                        "bbox": page.rect  # 页面边界框
                    }
                    pages_content.append(page_info)
                    full_text += cleaned_text + "\n\n"
            
            doc.close()
            
            return {
                "total_pages": len(pages_content),
                "pages": pages_content,
                "full_text": full_text.strip()
            }
            
        except Exception as e:
            raise ParsingError(
                message=f"从 PDF 提取内容失败: {str(e)}",
                file_path=file_path
            )
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        从 PDF 文档中提取元数据。
        
        参数:
            file_path: PDF 文件路径
            
        返回:
            包含 PDF 元数据的字典
        """
        if fitz is None:
            return {}
        
        try:
            doc = fitz.open(file_path)
            metadata = doc.metadata
            doc.close()
            
            # 清理元数据并转换为可序列化格式
            clean_metadata = {}
            for key, value in metadata.items():
                if value:  # 仅包含非空值
                    clean_metadata[key.lower()] = str(value)
            
            return clean_metadata
            
        except Exception as e:
            logger.warning(f"从 {file_path} 提取 PDF 元数据失败: {str(e)}")
            return {}
    
    def extract_page_text(self, file_path: str, page_number: int) -> str:
        """
        从特定页面提取文本。
        
        参数:
            file_path: PDF 文件路径
            page_number: 页码 (从 1 开始)
            
        返回:
            指定页面的文本内容
            
        引发:
            ParsingError: 如果页面提取失败
        """
        if fitz is None:
            raise ParsingError(
                message="PyMuPDF (fitz) 未安装",
                file_path=file_path
            )
        
        try:
            doc = fitz.open(file_path)
            
            if page_number < 1 or page_number > len(doc):
                raise ParsingError(
                    message=f"页码 {page_number} 超出范围 (1-{len(doc)})",
                    file_path=file_path
                )
            
            page = doc[page_number - 1]  # 转换为从 0 开始的索引
            page_text = page.get_text()
            doc.close()
            
            return page_text.replace('\x0c', '').strip()
            
        except Exception as e:
            raise ParsingError(
                message=f"提取第 {page_number} 页失败: {str(e)}",
                file_path=file_path
            )
    
    def get_page_count(self, file_path: str) -> int:
        """
        获取 PDF 文档中的页数。
        
        参数:
            file_path: PDF 文件路径
            
        返回:
            文档中的页数
            
        引发:
            ParsingError: 如果无法确定页数
        """
        if fitz is None:
            raise ParsingError(
                message="PyMuPDF (fitz) 未安装",
                file_path=file_path
            )
        
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            doc.close()
            return page_count
            
        except Exception as e:
            raise ParsingError(
                message=f"获取页数失败: {str(e)}",
                file_path=file_path
            )
    
    def extract_images(self, file_path: str, output_dir: Optional[str] = None) -> List[str]:
        """
        从 PDF 文档中提取图像。
        
        参数:
            file_path: PDF 文件路径
            output_dir: 保存提取图像的目录 (可选)
            
        返回:
            提取的图像文件路径列表
            
        引发:
            ParsingError: 如果图像提取失败
        """
        if fitz is None:
            raise ParsingError(
                message="PyMuPDF (fitz) 未安装",
                file_path=file_path
            )
        
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        extracted_images = []
        
        try:
            doc = fitz.open(file_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    # 获取图像数据
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    # 跳过 CMYK 图像 (PIL 不支持)
                    if pix.n - pix.alpha < 4:
                        if output_dir:
                            img_name = f"page_{page_num + 1}_img_{img_index + 1}.png"
                            img_path = os.path.join(output_dir, img_name)
                            pix.save(img_path)
                            extracted_images.append(img_path)
                        else:
                            # 如果没有输出目录，则只计算图像
                            extracted_images.append(f"page_{page_num + 1}_img_{img_index + 1}")
                    
                    pix = None  # 释放内存
            
            doc.close()
            return extracted_images
            
        except Exception as e:
            raise ParsingError(
                message=f"提取图像失败: {str(e)}",
                file_path=file_path
            )
    
    def is_searchable(self, file_path: str) -> bool:
        """
        检查 PDF 是否包含可搜索文本。
        
        参数:
            file_path: PDF 文件路径
            
        返回:
            如果 PDF 包含可搜索文本则返回 True，否则返回 False
        """
        if fitz is None:
            return False
        
        try:
            doc = fitz.open(file_path)
            
            # 检查前几页是否有文本内容
            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                text = page.get_text().strip()
                if text:
                    doc.close()
                    return True
            
            doc.close()
            return False
            
        except Exception:
            return False
    
    def combine_structured_content(self, structured_content: Dict[str, Any]) -> str:
        """
        将结构化的 PDF 内容合并为单个文本字符串。
        
        参数:
            structured_content: 包含结构化 PDF 内容的字典
            
        返回:
            合并的文本内容
        """
        if "full_text" in structured_content:
            return structured_content["full_text"]
        
        # 备用方法：合并页面内容
        text_parts = []
        if "pages" in structured_content:
            for page in structured_content["pages"]:
                if isinstance(page, dict) and "content" in page:
                    text_parts.append(page["content"])
        
        return "\n\n".join(text_parts)