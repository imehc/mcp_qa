"""
MCP 服务器 Markdown 文档解析器

该模块提供 Markdown 解析功能，支持各种 Markdown 扩展和元数据提取。
"""

import os
import logging
from typing import Dict, Any, List

try:
    import markdown
    from markdown.extensions import meta, toc, tables, codehilite
except ImportError:
    markdown = None

from ..types import ParseResult, FileType, ParserStatus
from ..exceptions import ParsingError, EmptyDocumentError
from .base import TextBasedParser

logger = logging.getLogger(__name__)


class MarkdownParser(TextBasedParser):
    """
    Markdown 文档解析器 (.md, .markdown 文件)。
    
    此解析器从 Markdown 文件中提取文本内容，并提供有关标题、链接和元数据的结构化信息。
    """
    
    def __init__(self):
        """初始化 Markdown 解析器。"""
        super().__init__(FileType.MARKDOWN, ['.md', '.markdown'])
        
        # 配置 markdown 扩展
        self.extensions = [
            'meta',          # 用于 YAML 前置内容
            'toc',           # 目录
            'tables',        # GitHub 风格的表格
            'codehilite',    # 代码高亮
            'fenced_code',   # 围栏代码块
            'nl2br',         # 换行转为断行
            'attr_list',     # 属性列表
            'def_list',      # 定义列表
            'footnotes',     # 脚注
            'admonition'     # 警告框
        ]
        
        # 初始化 markdown 处理器
        if markdown is not None:
            self.md = markdown.Markdown(extensions=self.extensions)
        else:
            self.md = None
    
    def parse(self, file_path: str, use_cache: bool = True) -> ParseResult:
        """
        解析 Markdown 文档并提取其内容。
        
        参数:
            file_path: Markdown 文件路径
            use_cache: 是否使用缓存（默认True）
            
        返回:
            包含提取内容和元数据的 ParseResult
            
        引发:
            ParsingError: 如果 Markdown 解析失败
        """
        # 如果启用缓存且支持缓存，先检查缓存
        if use_cache and self.cache_aware:
            try:
                from ..indexing.cache import is_file_indexed_and_current, file_index_cache
                
                if is_file_indexed_and_current(file_path):
                    cached_info = file_index_cache.get_cached_file_info(file_path)
                    if cached_info and cached_info.get("parse_content"):
                        logger.info(f"使用Markdown解析缓存: {file_path}")
                        
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
                                "parsing_method": "Cached-MarkdownParser",
                                **(cached_info.get("metadata", {}))
                            },
                            parsing_method="Cached-MarkdownParser"
                        )
                        
            except ImportError:
                logger.debug("缓存模块不可用，执行常规Markdown解析")
            except Exception as e:
                logger.warning(f"Markdown缓存检查失败: {e}，执行常规解析")
        
        # 缓存未命中或禁用缓存，执行常规解析
        return self._parse_markdown_content(file_path)
    
    def _parse_markdown_content(self, file_path: str) -> ParseResult:
        """
        执行Markdown内容的实际解析。
        
        参数:
            file_path: Markdown 文件路径
            
        返回:
            包含提取内容和元数据的 ParseResult
        """
        if markdown is None:
            return self.create_error_result(
                file_path=file_path,
                error="Markdown 库未安装。使用以下命令安装: pip install markdown",
                status=ParserStatus.ERROR
            )
        
        try:
            # 提取原始内容
            raw_content = self.extract_text_from_file(file_path)
            
            if not raw_content.strip():
                raise EmptyDocumentError(file_path, "MarkdownParser")
            
            # 解析 markdown 内容
            structured_content = self.extract_structured_content(file_path)
            
            # 使用原始内容进行索引 (更适合搜索)
            text_content = raw_content
            
            # 创建元数据
            metadata = {
                "raw_content": raw_content,
                "html_content": structured_content.get("html_content", ""),
                "metadata": structured_content.get("metadata", {}),
                "toc": structured_content.get("toc", ""),
                "headers": structured_content.get("headers", []),
                "links": structured_content.get("links", []),
                "code_blocks": structured_content.get("code_blocks", []),
                "file_size": os.path.getsize(file_path),
                "parsing_method": "markdown"
            }
            
            logger.info(f"Markdown解析完成: {file_path} ({len(metadata['headers'])} 个标题)")
            
            return self.create_success_result(
                file_path=file_path,
                content=text_content,
                metadata=metadata,
                parsing_method="markdown"
            )
            
        except Exception as e:
            logger.error(f"Markdown 解析失败 {file_path}: {str(e)}")
            return self.create_error_result(
                file_path=file_path,
                error=f"Markdown 解析失败: {str(e)}"
            )
    
    def extract_structured_content(self, file_path: str) -> Dict[str, Any]:
        """
        从 Markdown 文档中提取结构化内容。
        
        参数:
            file_path: Markdown 文件路径
            
        返回:
            包含结构化 Markdown 内容的字典
            
        引发:
            ParsingError: 如果提取失败
        """
        try:
            raw_content = self.extract_text_from_file(file_path)
            
            # 重置 markdown 处理器
            self.md.reset()
            
            # 转换为 HTML
            html_content = self.md.convert(raw_content)
            
            # 提取元数据 (来自 YAML 前置内容)
            metadata = getattr(self.md, 'Meta', {})
            
            # 提取目录
            toc = getattr(self.md, 'toc', '')
            
            # 提取标题
            headers = self._extract_headers(raw_content)
            
            # 提取链接
            links = self._extract_links(raw_content)
            
            # 提取代码块
            code_blocks = self._extract_code_blocks(raw_content)
            
            # 提取表格
            tables = self._extract_tables(raw_content)
            
            return {
                "raw_content": raw_content,
                "html_content": html_content,
                "metadata": metadata,
                "toc": toc,
                "headers": headers,
                "links": links,
                "code_blocks": code_blocks,
                "tables": tables,
                "total_headers": len(headers),
                "total_links": len(links),
                "total_code_blocks": len(code_blocks),
                "total_tables": len(tables)
            }
            
        except Exception as e:
            raise ParsingError(
                message=f"从 Markdown 提取结构化内容失败: {str(e)}",
                file_path=file_path
            )
    
    def _extract_headers(self, content: str) -> List[Dict[str, Any]]:
        """
        从 Markdown 内容中提取标题。
        
        参数:
            content: 原始 Markdown 内容
            
        返回:
            标题字典列表
        """
        import re
        headers = []
        
        # 匹配 ATX (###) 和 Setext (===) 风格的标题
        atx_pattern = r'^(#{1,6})\s+(.+)$'
        setext_pattern = r'^(.+)\n([=-]+)$'
        
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # ATX 标题
            atx_match = re.match(atx_pattern, line.strip())
            if atx_match:
                level = len(atx_match.group(1))
                text = atx_match.group(2).strip()
                headers.append({
                    "level": level,
                    "text": text,
                    "line_number": i + 1,
                    "type": "atx"
                })
            
            # Setext 标题
            elif i + 1 < len(lines):
                setext_match = re.match(setext_pattern, line + '\n' + lines[i + 1])
                if setext_match:
                    text = setext_match.group(1).strip()
                    underline = setext_match.group(2)
                    level = 1 if underline.startswith('=') else 2
                    headers.append({
                        "level": level,
                        "text": text,
                        "line_number": i + 1,
                        "type": "setext"
                    })
        
        return headers
    
    def _extract_links(self, content: str) -> List[Dict[str, Any]]:
        """
        从 Markdown 内容中提取链接。
        
        参数:
            content: 原始 Markdown 内容
            
        返回:
            链接字典列表
        """
        import re
        links = []
        
        # 行内链接: [text](url)
        inline_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        for match in re.finditer(inline_pattern, content):
            links.append({
                "text": match.group(1),
                "url": match.group(2),
                "type": "inline",
                "position": match.start()
            })
        
        # 引用链接: [text][ref]
        ref_pattern = r'\[([^\]]+)\]\[([^\]]*)\]'
        for match in re.finditer(ref_pattern, content):
            links.append({
                "text": match.group(1),
                "reference": match.group(2) or match.group(1),
                "type": "reference",
                "position": match.start()
            })
        
        # 链接定义: [ref]: url
        def_pattern = r'^\s*\[([^\]]+)\]:\s*(.+)$'
        for i, line in enumerate(content.split('\n')):
            match = re.match(def_pattern, line)
            if match:
                links.append({
                    "reference": match.group(1),
                    "url": match.group(2).strip(),
                    "type": "definition",
                    "line_number": i + 1
                })
        
        # 自动链接: <url>
        auto_pattern = r'<(https?://[^>]+)>'
        for match in re.finditer(auto_pattern, content):
            links.append({
                "url": match.group(1),
                "type": "auto",
                "position": match.start()
            })
        
        return links
    
    def _extract_code_blocks(self, content: str) -> List[Dict[str, Any]]:
        """
        从 Markdown 内容中提取代码块。
        
        参数:
            content: 原始 Markdown 内容
            
        返回:
            代码块字典列表
        """
        import re
        code_blocks = []
        
        # 围栏代码块: ```language
        fenced_pattern = r'^```(\w*)\n(.*?)\n```$'
        for match in re.finditer(fenced_pattern, content, re.MULTILINE | re.DOTALL):
            language = match.group(1) or "text"
            code = match.group(2)
            code_blocks.append({
                "language": language,
                "code": code,
                "type": "fenced",
                "position": match.start()
            })
        
        # 缩进代码块 (4+ 个空格)
        lines = content.split('\n')
        in_code_block = False
        current_code = []
        start_line = 0
        
        for i, line in enumerate(lines):
            if line.startswith('    ') or line.startswith('\t'):
                if not in_code_block:
                    in_code_block = True
                    start_line = i + 1
                current_code.append(line[4:] if line.startswith('    ') else line[1:])
            else:
                if in_code_block and line.strip() == '':
                    current_code.append('')
                elif in_code_block:
                    # 代码块结束
                    code_blocks.append({
                        "language": "text",
                        "code": '\n'.join(current_code).rstrip(),
                        "type": "indented",
                        "start_line": start_line
                    })
                    in_code_block = False
                    current_code = []
        
        # 处理文件末尾的代码块
        if in_code_block and current_code:
            code_blocks.append({
                "language": "text",
                "code": '\n'.join(current_code).rstrip(),
                "type": "indented",
                "start_line": start_line
            })
        
        return code_blocks
    
    def _extract_tables(self, content: str) -> List[Dict[str, Any]]:
        """
        从 Markdown 内容中提取表格。
        
        参数:
            content: 原始 Markdown 内容
            
        返回:
            表格字典列表
        """
        import re
        tables = []
        
        lines = content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # 检查这是否看起来像表格标题
            if '|' in line and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # 检查分隔行 (仅包含 |, -, :, 和空格)
                if re.match(r'^[\|\-\:\s]+$', next_line) and '|' in next_line:
                    # 找到表格
                    table_lines = [line]
                    table_start = i + 1
                    
                    # 添加分隔行
                    table_lines.append(next_line)
                    i += 2
                    
                    # 添加剩余的表格行
                    while i < len(lines) and '|' in lines[i].strip():
                        table_lines.append(lines[i].strip())
                        i += 1
                    
                    # 解析表格结构
                    headers = [cell.strip() for cell in table_lines[0].split('|') if cell.strip()]
                    rows = []
                    
                    for row_line in table_lines[2:]:  # 跳过标题和分隔行
                        if row_line.strip():
                            cells = [cell.strip() for cell in row_line.split('|') if cell.strip()]
                            if cells:
                                rows.append(cells)
                    
                    tables.append({
                        "headers": headers,
                        "rows": rows,
                        "total_rows": len(rows),
                        "total_columns": len(headers),
                        "start_line": table_start,
                        "raw_table": '\n'.join(table_lines)
                    })
                    
                    continue
            
            i += 1
        
        return tables
    
    def get_front_matter(self, file_path: str) -> Dict[str, Any]:
        """
        从 Markdown 文件中提取 YAML 前置内容。
        
        参数:
            file_path: Markdown 文件路径
            
        返回:
            包含前置内容元数据的字典
        """
        try:
            structured_content = self.extract_structured_content(file_path)
            return structured_content.get("metadata", {})
        except Exception as e:
            logger.warning(f"从 {file_path} 提取前置内容失败: {str(e)}")
            return {}
    
    def get_table_of_contents(self, file_path: str) -> str:
        """
        从 Markdown 文件生成目录。
        
        参数:
            file_path: Markdown 文件路径
            
        返回:
            目录作为 HTML 或空字符串
        """
        try:
            structured_content = self.extract_structured_content(file_path)
            return structured_content.get("toc", "")
        except Exception as e:
            logger.warning(f"为 {file_path} 生成目录失败: {str(e)}")
            return ""
    
    def combine_structured_content(self, structured_content: Dict[str, Any]) -> str:
        """
        将结构化的 Markdown 内容合并为单个文本字符串。
        
        参数:
            structured_content: 包含结构化内容的字典
            
        返回:
            合并的文本内容 (原始 markdown 更适合搜索)
        """
        return structured_content.get("raw_content", "")