"""
日志工具模块
提供统一的日志记录功能
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler
import colorlog
from ..config.settings import UIConfig

def setup_logger(name: str, log_file: Optional[str] = None, level: str = None) -> logging.Logger:
    """设置日志记录器"""
    
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 设置日志级别
    log_level = getattr(logging, (level or UIConfig.LOG_LEVEL).upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 日志格式
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 控制台处理器 (彩色输出)
    console_handler = colorlog.StreamHandler(sys.stdout)
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt=date_format,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    file_path = log_file or UIConfig.LOG_FILE
    if file_path:
        # 确保日志目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter(log_format, datefmt=date_format)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return setup_logger(name)

class ProgressLogger:
    """进度日志记录器"""
    
    def __init__(self, name: str, total_steps: int = 100):
        self.logger = get_logger(name)
        self.total_steps = total_steps
        self.current_step = 0
        self.last_progress = -1
    
    def update(self, step: int = None, message: str = ""):
        """更新进度"""
        if step is not None:
            self.current_step = step
        else:
            self.current_step += 1
        
        progress = int((self.current_step / self.total_steps) * 100)
        
        # 只在进度变化时记录
        if progress != self.last_progress:
            self.logger.info(f"进度: {progress}% ({self.current_step}/{self.total_steps}) {message}")
            self.last_progress = progress
    
    def finish(self, message: str = "完成"):
        """完成进度"""
        self.current_step = self.total_steps
        self.logger.info(f"进度: 100% ({self.total_steps}/{self.total_steps}) {message}")

class UILogger:
    """UI专用日志记录器"""
    
    def __init__(self):
        self.logger = get_logger("mcp_ui")
    
    def log_user_action(self, action: str, details: dict = None):
        """记录用户操作"""
        msg = f"用户操作: {action}"
        if details:
            msg += f" | 详情: {details}"
        self.logger.info(msg)
    
    def log_model_call(self, model: str, prompt_length: int, response_length: int, duration: float):
        """记录模型调用"""
        self.logger.info(
            f"模型调用: {model} | "
            f"提示长度: {prompt_length} | "
            f"回答长度: {response_length} | "
            f"耗时: {duration:.2f}s"
        )
    
    def log_mcp_call(self, tool: str, params: dict, success: bool, duration: float):
        """记录MCP工具调用"""
        status = "成功" if success else "失败"
        self.logger.info(
            f"MCP调用: {tool} | "
            f"参数: {params} | "
            f"状态: {status} | "
            f"耗时: {duration:.2f}s"
        )
    
    def log_file_operation(self, operation: str, file_path: str, success: bool):
        """记录文件操作"""
        status = "成功" if success else "失败"
        self.logger.info(f"文件操作: {operation} | 文件: {file_path} | 状态: {status}")
    
    def log_error(self, error: Exception, context: str = ""):
        """记录错误"""
        msg = f"错误: {str(error)}"
        if context:
            msg += f" | 上下文: {context}"
        self.logger.error(msg, exc_info=True)

# 全局UI日志记录器
ui_logger = UILogger()