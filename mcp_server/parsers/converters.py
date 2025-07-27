"""
MCP 服务器文档转换工具

该模块提供用于在不同文档格式之间转换的工具，
特别是处理旧版 .doc 文件和其他格式转换。
"""

import os
import subprocess
import tempfile
import shutil
import logging
from typing import Optional, List, Dict

from ..config import config
from ..types import ConversionResult, ConversionMethod
from ..exceptions import ConversionError
from ..utils import cleanup_temp_path, Timer

logger = logging.getLogger(__name__)


def auto_convert_doc_to_docx(file_path: str) -> ConversionResult:
    """
    使用多种方法自动将 .doc 文件转换为 .docx 格式。
    
    此函数按优先顺序尝试不同的转换方法：
    1. pypandoc - 通用文档转换器
    2. LibreOffice - 带命令行界面的办公套件
    3. textutil + pypandoc (仅 macOS) - 系统工具 + pandoc
    
    参数:
        file_path: 要转换的 .doc 文件路径
        
    返回:
        包含成功状态和转换文件路径的 ConversionResult
        
    引发:
        ConversionError: 如果所有转换方法都失败
    """
    timer = Timer()
    timer.start()
    
    temp_dir = None
    tried_methods = []
    
    try:
        # 创建临时目录用于转换
        temp_dir = tempfile.mkdtemp(prefix="mcp_doc_conversion_")
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        temp_docx_path = os.path.join(temp_dir, f"{base_name}_converted.docx")
        
        # 方法 1: 尝试 pypandoc 转换
        try:
            logger.info(f"尝试 pypandoc 转换: {file_path}")
            tried_methods.append("pypandoc")
            
            import pypandoc
            pypandoc.convert_file(file_path, 'docx', outputfile=temp_docx_path)
            
            if os.path.exists(temp_docx_path) and os.path.getsize(temp_docx_path) > 0:
                logger.info(f"使用 pypandoc 成功转换，耗时 {timer.elapsed():.2f} 秒")
                return ConversionResult(
                    success=True,
                    method=ConversionMethod.PYPANDOC,
                    converted_path=temp_docx_path,
                    temp_dir=temp_dir
                )
        except ImportError:
            logger.debug("pypandoc 不可用")
        except Exception as e:
            logger.debug(f"pypandoc 转换失败: {e}")
        
        # 方法 2: 尝试 LibreOffice 转换
        libreoffice_result = _try_libreoffice_conversion(file_path, temp_dir, base_name)
        if libreoffice_result.success:
            tried_methods.extend(libreoffice_result.tried_methods or [])
            libreoffice_result.tried_methods = tried_methods
            return libreoffice_result
        else:
            tried_methods.extend(libreoffice_result.tried_methods or [])
        
        # 方法 3: 尝试 textutil + pypandoc (仅 macOS)
        if os.name == 'posix':
            textutil_result = _try_textutil_conversion(file_path, temp_dir, base_name, temp_docx_path)
            if textutil_result.success:
                tried_methods.extend(textutil_result.tried_methods or [])
                textutil_result.tried_methods = tried_methods
                return textutil_result
            else:
                tried_methods.extend(textutil_result.tried_methods or [])
        
        # 所有方法都失败
        if temp_dir:
            cleanup_temp_path(temp_dir)
        
        return ConversionResult(
            success=False,
            method=ConversionMethod.FALLBACK,
            error="所有转换方法都失败",
            tried_methods=tried_methods
        )
        
    except Exception as e:
        if temp_dir:
            cleanup_temp_path(temp_dir)
        
        return ConversionResult(
            success=False,
            method=ConversionMethod.FALLBACK,
            error=f"转换失败: {str(e)}",
            tried_methods=tried_methods
        )


def _try_libreoffice_conversion(file_path: str, temp_dir: str, base_name: str) -> ConversionResult:
    """
    尝试使用 LibreOffice 转换文档。
    
    参数:
        file_path: 源文件路径
        temp_dir: 临时目录
        base_name: 输出文件的基本名称
        
    返回:
        包含转换状态的 ConversionResult
    """
    tried_methods = []
    
    for soffice_path in config.document.LIBREOFFICE_PATHS:
        try:
            tried_methods.append(f"LibreOffice ({soffice_path})")
            
            # 检查 LibreOffice 是否可用
            if not shutil.which(soffice_path) and not os.path.exists(soffice_path):
                continue
            
            logger.info(f"尝试 LibreOffice 转换: {soffice_path}")
            
            # 构建转换命令
            cmd = [
                soffice_path,
                '--headless',
                '--convert-to', 'docx',
                '--outdir', temp_dir,
                file_path
            ]
            
            # 运行转换并设置超时
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=config.document.CONVERSION_TIMEOUT
            )
            
            # 检查转换后的文件
            expected_docx = os.path.join(temp_dir, f"{base_name}.docx")
            if os.path.exists(expected_docx) and os.path.getsize(expected_docx) > 0:
                logger.info(f"使用 LibreOffice 成功转换: {soffice_path}")
                return ConversionResult(
                    success=True,
                    method=ConversionMethod.LIBREOFFICE,
                    converted_path=expected_docx,
                    temp_dir=temp_dir,
                    tried_methods=tried_methods
                )
            else:
                logger.debug(f"LibreOffice 转换未产生输出: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.debug(f"LibreOffice 转换超时: {soffice_path}")
        except (FileNotFoundError, Exception) as e:
            logger.debug(f"LibreOffice 转换失败 {soffice_path}: {e}")
            continue
    
    return ConversionResult(
        success=False,
        method=ConversionMethod.LIBREOFFICE,
        error="LibreOffice 转换失败",
        tried_methods=tried_methods
    )


def _try_textutil_conversion(file_path: str, temp_dir: str, base_name: str, temp_docx_path: str) -> ConversionResult:
    """
    尝试使用 textutil 转换文档 (仅 macOS)。
    
    参数:
        file_path: 源文件路径
        temp_dir: 临时目录
        base_name: 输出文件的基本名称
        temp_docx_path: 目标 docx 文件路径
        
    返回:
        包含转换状态的 ConversionResult
    """
    tried_methods = ["textutil + pypandoc"]
    
    try:
        # 检查 textutil 是否可用
        if subprocess.run(['which', 'textutil'], capture_output=True).returncode != 0:
            return ConversionResult(
                success=False,
                method=ConversionMethod.TEXTUTIL,
                error="textutil 不可用",
                tried_methods=tried_methods
            )
        
        logger.info(f"尝试 textutil 转换: {file_path}")
        temp_rtf = os.path.join(temp_dir, f"{base_name}.rtf")
        
        # 首先转换为 RTF
        subprocess.run([
            'textutil', '-convert', 'rtf', 
            '-output', temp_rtf,
            file_path
        ], check=True, timeout=config.document.CONVERSION_TIMEOUT)
        
        if os.path.exists(temp_rtf):
            # 使用 pypandoc 将 RTF 转换为 DOCX
            import pypandoc
            pypandoc.convert_file(temp_rtf, 'docx', outputfile=temp_docx_path)
            
            if os.path.exists(temp_docx_path) and os.path.getsize(temp_docx_path) > 0:
                logger.info("使用 textutil + pypandoc 成功转换")
                return ConversionResult(
                    success=True,
                    method=ConversionMethod.TEXTUTIL,
                    converted_path=temp_docx_path,
                    temp_dir=temp_dir,
                    tried_methods=tried_methods
                )
        
    except subprocess.TimeoutExpired:
        logger.debug("textutil 转换超时")
    except ImportError:
        logger.debug("pypandoc 不可用于 textutil 方法")
    except Exception as e:
        logger.debug(f"textutil 转换失败: {e}")
    
    return ConversionResult(
        success=False,
        method=ConversionMethod.TEXTUTIL,
        error="textutil 转换失败",
        tried_methods=tried_methods
    )


def convert_document(
    source_path: str, 
    target_format: str, 
    output_path: Optional[str] = None
) -> ConversionResult:
    """
    将文档从一种格式转换为另一种格式。
    
    参数:
        source_path: 源文档路径
        target_format: 目标格式 (例如 'docx', 'pdf', 'txt')
        output_path: 可选的输出路径 (如果未提供，则创建临时文件)
        
    返回:
        包含转换状态的 ConversionResult
        
    引发:
        ConversionError: 如果转换失败
    """
    source_ext = os.path.splitext(source_path)[1].lower()
    
    # 特殊处理 .doc 到 .docx 的转换
    if source_ext == '.doc' and target_format.lower() == 'docx':
        return auto_convert_doc_to_docx(source_path)
    
    # 使用 pypandoc 进行通用转换
    try:
        import pypandoc
        
        if output_path is None:
            temp_dir = tempfile.mkdtemp(prefix="mcp_conversion_")
            base_name = os.path.splitext(os.path.basename(source_path))[0]
            output_path = os.path.join(temp_dir, f"{base_name}.{target_format}")
        else:
            temp_dir = None
        
        pypandoc.convert_file(source_path, target_format, outputfile=output_path)
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return ConversionResult(
                success=True,
                method=ConversionMethod.PYPANDOC,
                converted_path=output_path,
                temp_dir=temp_dir
            )
        else:
            return ConversionResult(
                success=False,
                method=ConversionMethod.PYPANDOC,
                error="转换未产生输出"
            )
            
    except ImportError:
        raise ConversionError(
            file_path=source_path,
            from_format=source_ext,
            to_format=target_format,
            last_error="pypandoc 不可用"
        )
    except Exception as e:
        raise ConversionError(
            file_path=source_path,
            from_format=source_ext,
            to_format=target_format,
            last_error=str(e)
        )


def is_conversion_supported(source_format: str, target_format: str) -> bool:
    """
    检查两种格式之间的转换是否受支持。
    
    参数:
        source_format: 源格式 (例如 'doc', 'pdf')
        target_format: 目标格式 (例如 'docx', 'txt')
        
    返回:
        如果支持转换则返回 True，否则返回 False
    """
    # 定义支持的转换
    supported_conversions = {
        'doc': ['docx', 'txt', 'rtf'],
        'docx': ['txt', 'rtf', 'html'],
        'rtf': ['docx', 'txt', 'html'],
        'html': ['docx', 'txt', 'rtf'],
        'md': ['docx', 'html', 'txt'],
        'markdown': ['docx', 'html', 'txt']
    }
    
    source_format = source_format.lower().lstrip('.')
    target_format = target_format.lower().lstrip('.')
    
    return target_format in supported_conversions.get(source_format, [])


def get_available_converters() -> Dict[str, List[str]]:
    """
    获取可用文档转换器的信息。
    
    返回:
        将转换器名称映射到其功能的字典
    """
    converters = {}
    
    # 检查 pypandoc
    try:
        import pypandoc
        converters['pypandoc'] = ['可用']
    except ImportError:
        converters['pypandoc'] = ['未安装']
    
    # 检查 LibreOffice
    libreoffice_status = []
    for path in config.document.LIBREOFFICE_PATHS:
        if shutil.which(path) or os.path.exists(path):
            libreoffice_status.append(f'在 {path} 可用')
            break
    else:
        libreoffice_status.append('未找到')
    converters['libreoffice'] = libreoffice_status
    
    # 检查 textutil (仅 macOS)
    if os.name == 'posix':
        if subprocess.run(['which', 'textutil'], capture_output=True).returncode == 0:
            converters['textutil'] = ['可用 (macOS)']
        else:
            converters['textutil'] = ['不可用']
    else:
        converters['textutil'] = ['在此平台上不受支持']
    
    return converters


def batch_convert_documents(
    file_paths: List[str], 
    target_format: str,
    output_dir: Optional[str] = None
) -> List[ConversionResult]:
    """
    将多个文档转换为相同的目標格式。
    
    参数:
        file_paths: 源文件路径列表
        target_format: 所有转换的目标格式
        output_dir: 可选的输出目录
        
    返回:
        ConversionResult 对象列表
    """
    results = []
    
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for file_path in file_paths:
        try:
            if output_dir:
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_path = os.path.join(output_dir, f"{base_name}.{target_format}")
            else:
                output_path = None
            
            result = convert_document(file_path, target_format, output_path)
            results.append(result)
            
        except Exception as e:
            results.append(ConversionResult(
                success=False,
                method=ConversionMethod.FALLBACK,
                error=str(e)
            ))
    
    return results


def cleanup_conversion_temps(results: List[ConversionResult]) -> None:
    """
    清理转换结果中的临时目录。
    
    参数:
        results: ConversionResult 对象列表
    """
    for result in results:
        if result.temp_dir:
            cleanup_temp_path(result.temp_dir)