#!/usr/bin/env python3
"""
MCP服务器CLI入口点
提供命令行界面来启动和管理MCP服务器
"""

import sys
import os
import argparse
import signal
from typing import Optional, List
from pathlib import Path

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_server.server import run_server, create_server
from mcp_server.config import Config
from mcp_server.monitoring.logger import setup_logger, set_log_level

logger = setup_logger(__name__)


def signal_handler(signum, frame):
    """信号处理器"""
    logger.info(f"收到信号 {signum}，正在关闭服务器...")
    sys.exit(0)


def validate_directories(directories: List[str]) -> List[str]:
    """验证目录列表"""
    valid_dirs = []
    for directory in directories:
        dir_path = Path(directory).resolve()
        if dir_path.exists() and dir_path.is_dir():
            valid_dirs.append(str(dir_path))
            logger.info(f"已添加白名单目录: {dir_path}")
        else:
            logger.warning(f"目录不存在或不是有效目录: {directory}")
    
    if not valid_dirs:
        # 如果没有有效目录，使用默认的docs目录
        default_docs = Path("./docs").resolve()
        if default_docs.exists():
            valid_dirs.append(str(default_docs))
            logger.info(f"使用默认文档目录: {default_docs}")
        else:
            # 创建默认目录
            default_docs.mkdir(exist_ok=True)
            valid_dirs.append(str(default_docs))
            logger.info(f"创建并使用默认文档目录: {default_docs}")
    
    return valid_dirs


def create_argument_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="MCP文档问答服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s                              # 使用默认配置启动
  %(prog)s --host 0.0.0.0 --port 8080   # 指定监听地址和端口
  %(prog)s --debug                      # 启用调试模式
  %(prog)s --allowed-dirs /path/to/docs,/another/path  # 指定白名单目录
  %(prog)s --log-level DEBUG            # 设置日志级别
  %(prog)s --log-file /path/to/log.txt  # 指定日志文件
        """
    )
    
    # 服务器配置参数
    server_group = parser.add_argument_group('服务器配置')
    server_group.add_argument(
        '--host',
        default=Config.HOST,
        help=f'服务器监听地址 (默认: {Config.HOST})'
    )
    server_group.add_argument(
        '--port',
        type=int,
        default=Config.PORT,
        help=f'服务器监听端口 (默认: {Config.PORT})'
    )
    server_group.add_argument(
        '--debug',
        action='store_true',
        default=Config.DEBUG,
        help='启用调试模式'
    )
    
    # 安全配置参数
    security_group = parser.add_argument_group('安全配置')
    security_group.add_argument(
        '--allowed-dirs',
        help='白名单目录列表，用逗号分隔 (例: /path/to/docs,/another/path)'
    )
    
    # 日志配置参数
    log_group = parser.add_argument_group('日志配置')
    log_group.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='日志级别 (默认: INFO)'
    )
    log_group.add_argument(
        '--log-file',
        help='日志文件路径'
    )
    log_group.add_argument(
        '--log-dir',
        help='日志目录路径'
    )
    log_group.add_argument(
        '--json-logs',
        action='store_true',
        help='启用JSON格式日志'
    )
    
    # 功能配置参数
    feature_group = parser.add_argument_group('功能配置')
    feature_group.add_argument(
        '--embedding-model',
        default=Config.EMBEDDING_MODEL,
        help=f'嵌入模型名称 (默认: {Config.EMBEDDING_MODEL})'
    )
    feature_group.add_argument(
        '--index-dir',
        default=Config.INDEX_DIR,
        help=f'索引文件目录 (默认: {Config.INDEX_DIR})'
    )
    
    # 操作参数
    action_group = parser.add_argument_group('操作')
    action_group.add_argument(
        '--version',
        action='version',
        version='MCP QA Server 1.0.0'
    )
    action_group.add_argument(
        '--check-config',
        action='store_true',
        help='检查配置并退出'
    )
    action_group.add_argument(
        '--list-dirs',
        action='store_true',
        help='列出当前白名单目录并退出'
    )
    
    return parser


def check_dependencies():
    """检查依赖项"""
    missing_deps = []
    
    try:
        import faiss
    except ImportError:
        missing_deps.append('faiss-cpu')
    
    try:
        import sentence_transformers
    except ImportError:
        missing_deps.append('sentence-transformers')
    
    try:
        import fitz  # PyMuPDF
    except ImportError:
        missing_deps.append('PyMuPDF')
    
    try:
        import docx
    except ImportError:
        missing_deps.append('python-docx')
    
    try:
        import pandas
    except ImportError:
        missing_deps.append('pandas')
    
    try:
        import openpyxl
    except ImportError:
        missing_deps.append('openpyxl')
    
    try:
        import pptx
    except ImportError:
        missing_deps.append('python-pptx')
    
    if missing_deps:
        logger.error("缺少以下依赖项:")
        for dep in missing_deps:
            logger.error(f"  - {dep}")
        logger.error("请运行: pip install " + " ".join(missing_deps))
        return False
    
    return True


def main():
    """主函数"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 解析命令行参数
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # 设置日志级别
    set_log_level(args.log_level)
    
    # 如果指定了日志文件或目录，配置文件日志
    if args.log_file:
        from mcp_server.monitoring.logger import add_file_logging
        add_file_logging(args.log_file)
    
    if args.log_dir:
        Config.LOG_DIR = args.log_dir
        os.makedirs(args.log_dir, exist_ok=True)
    
    if args.json_logs:
        from mcp_server.monitoring.logger import add_json_logging
        json_file = os.path.join(args.log_dir or './logs', 'mcp_server.json')
        add_json_logging(json_file)
    
    logger.info("MCP文档问答服务器启动中...")
    
    # 检查依赖项
    if not check_dependencies():
        sys.exit(1)
    
    # 更新配置
    Config.HOST = args.host
    Config.PORT = args.port
    Config.DEBUG = args.debug
    Config.EMBEDDING_MODEL = args.embedding_model
    Config.INDEX_DIR = args.index_dir
    
    # 处理白名单目录
    if args.allowed_dirs:
        directories = [d.strip() for d in args.allowed_dirs.split(',')]
        Config.ALLOWED_DIRS = validate_directories(directories)
    else:
        Config.ALLOWED_DIRS = validate_directories(Config.ALLOWED_DIRS)
    
    # 检查配置
    if args.check_config:
        print("配置检查:")
        print(f"  主机: {Config.HOST}")
        print(f"  端口: {Config.PORT}")
        print(f"  调试模式: {Config.DEBUG}")
        print(f"  嵌入模型: {Config.EMBEDDING_MODEL}")
        print(f"  索引目录: {Config.INDEX_DIR}")
        print(f"  白名单目录: {Config.ALLOWED_DIRS}")
        print(f"  日志级别: {args.log_level}")
        if args.log_file:
            print(f"  日志文件: {args.log_file}")
        if args.log_dir:
            print(f"  日志目录: {args.log_dir}")
        print("配置检查完成")
        return
    
    # 列出目录
    if args.list_dirs:
        print("当前白名单目录:")
        for i, directory in enumerate(Config.ALLOWED_DIRS, 1):
            print(f"  {i}. {directory}")
        return
    
    # 确保必要的目录存在
    os.makedirs(Config.INDEX_DIR, exist_ok=True)
    
    # 启动服务器
    try:
        logger.info(f"服务器配置:")
        logger.info(f"  监听地址: {Config.HOST}:{Config.PORT}")
        logger.info(f"  调试模式: {Config.DEBUG}")
        logger.info(f"  白名单目录: {len(Config.ALLOWED_DIRS)} 个目录")
        logger.info(f"  嵌入模型: {Config.EMBEDDING_MODEL}")
        logger.info(f"  索引目录: {Config.INDEX_DIR}")
        
        # 运行服务器
        run_server(
            host=Config.HOST,
            port=Config.PORT,
            debug=Config.DEBUG
        )
        
    except KeyboardInterrupt:
        logger.info("收到中断信号，服务器正在关闭...")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        if Config.DEBUG:
            logger.exception("详细错误信息:")
        sys.exit(1)
    finally:
        logger.info("服务器已关闭")


def cli_main():
    """CLI入口点"""
    try:
        main()
    except Exception as e:
        print(f"启动失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli_main()