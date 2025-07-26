"""
日志记录模块
提供统一的日志配置和管理功能
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import threading
from pathlib import Path

from ..config import config


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }
    
    def format(self, record):
        """格式化日志记录"""
        # 添加颜色
        if hasattr(record, 'levelname') and record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """JSON格式化器"""
    
    def format(self, record):
        """格式化为JSON"""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName,
            'process': record.process
        }
        
        # 添加异常信息
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, ensure_ascii=False)


class LogManager:
    """日志管理器"""
    
    def __init__(self):
        """初始化日志管理器"""
        self.loggers = {}
        self.handlers = {}
        self._lock = threading.Lock()
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """设置根日志记录器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if config.server.DEBUG else logging.INFO)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加控制台处理器
        console_handler = self._create_console_handler()
        root_logger.addHandler(console_handler)
        
        # 添加文件处理器（如果配置了日志目录）
        if hasattr(config.logging, 'LOG_DIR') and config.logging.LOG_DIR:
            file_handler = self._create_file_handler()
            root_logger.addHandler(file_handler)
    
    def _create_console_handler(self) -> logging.StreamHandler:
        """创建控制台处理器"""
        handler = logging.StreamHandler(sys.stdout)
        
        # 根据是否为TTY决定是否使用彩色输出
        if sys.stdout.isatty():
            formatter = ColoredFormatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            formatter = logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG if config.server.DEBUG else logging.INFO)
        
        self.handlers['console'] = handler
        return handler
    
    def _create_file_handler(self, log_file: Optional[str] = None) -> logging.Handler:
        """创建文件处理器"""
        if log_file is None:
            log_dir = getattr(config.logging, 'LOG_DIR', './logs')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'mcp_server.log')
        
        # 使用RotatingFileHandler进行日志轮转
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        
        self.handlers['file'] = handler
        return handler
    
    def _create_json_handler(self, log_file: str) -> logging.Handler:
        """创建JSON文件处理器"""
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        
        formatter = JSONFormatter()
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        
        return handler
    
    def get_logger(self, name: str, **kwargs) -> logging.Logger:
        """获取日志记录器"""
        with self._lock:
            if name in self.loggers:
                return self.loggers[name]
            
            logger = logging.getLogger(name)
            
            # 设置日志级别
            level = kwargs.get('level', logging.DEBUG if config.server.DEBUG else logging.INFO)
            logger.setLevel(level)
            
            # 添加自定义处理器
            if kwargs.get('json_output'):
                json_file = kwargs.get('json_file', f'./logs/{name}.json')
                os.makedirs(os.path.dirname(json_file), exist_ok=True)
                json_handler = self._create_json_handler(json_file)
                logger.addHandler(json_handler)
            
            if kwargs.get('separate_file'):
                file_path = kwargs.get('file_path', f'./logs/{name}.log')
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file_handler = self._create_file_handler(file_path)
                logger.addHandler(file_handler)
            
            # 防止重复输出
            logger.propagate = not kwargs.get('no_propagate', False)
            
            self.loggers[name] = logger
            return logger
    
    def set_level(self, level: str, logger_name: Optional[str] = None):
        """设置日志级别"""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        
        log_level = level_map.get(level.upper(), logging.INFO)
        
        if logger_name:
            logger = logging.getLogger(logger_name)
            logger.setLevel(log_level)
        else:
            # 设置根日志记录器级别
            logging.getLogger().setLevel(log_level)
            # 更新所有处理器的级别
            for handler in self.handlers.values():
                handler.setLevel(log_level)
    
    def add_file_output(self, log_file: str, logger_name: Optional[str] = None):
        """添加文件输出"""
        handler = self._create_file_handler(log_file)
        
        if logger_name:
            logger = logging.getLogger(logger_name)
            logger.addHandler(handler)
        else:
            logging.getLogger().addHandler(handler)
        
        self.handlers[f'file_{log_file}'] = handler
    
    def add_json_output(self, log_file: str, logger_name: Optional[str] = None):
        """添加JSON文件输出"""
        handler = self._create_json_handler(log_file)
        
        if logger_name:
            logger = logging.getLogger(logger_name)
            logger.addHandler(handler)
        else:
            logging.getLogger().addHandler(handler)
        
        self.handlers[f'json_{log_file}'] = handler
    
    def get_log_stats(self) -> Dict[str, Any]:
        """获取日志统计信息"""
        stats = {
            'loggers_count': len(self.loggers),
            'handlers_count': len(self.handlers),
            'root_level': logging.getLogger().level,
            'loggers': {},
            'handlers': []
        }
        
        # 统计各个日志记录器信息
        for name, logger in self.loggers.items():
            stats['loggers'][name] = {
                'level': logger.level,
                'handlers_count': len(logger.handlers),
                'propagate': logger.propagate
            }
        
        # 统计处理器信息
        for name, handler in self.handlers.items():
            handler_info = {
                'name': name,
                'type': type(handler).__name__,
                'level': handler.level
            }
            
            if hasattr(handler, 'baseFilename'):
                handler_info['file'] = handler.baseFilename
                if os.path.exists(handler.baseFilename):
                    handler_info['file_size'] = os.path.getsize(handler.baseFilename)
            
            stats['handlers'].append(handler_info)
        
        return stats
    
    def cleanup_old_logs(self, days: int = 7) -> Dict[str, Any]:
        """清理旧日志文件"""
        cleaned_files = []
        total_size = 0
        
        log_dir = getattr(Config, 'LOG_DIR', './logs')
        if not os.path.exists(log_dir):
            return {
                'cleaned_files': [],
                'total_size': 0,
                'message': 'Log directory does not exist'
            }
        
        cutoff_time = datetime.now().timestamp() - (days * 24 * 3600)
        
        try:
            for root, dirs, files in os.walk(log_dir):
                for file in files:
                    if file.endswith(('.log', '.json')):
                        file_path = os.path.join(root, file)
                        if os.path.getmtime(file_path) < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_files.append(file_path)
                            total_size += file_size
        
        except Exception as e:
            return {
                'error': f'清理日志失败: {str(e)}',
                'cleaned_files': cleaned_files,
                'total_size': total_size
            }
        
        return {
            'cleaned_files': cleaned_files,
            'total_size': total_size,
            'cleaned_count': len(cleaned_files),
            'message': f'已清理 {len(cleaned_files)} 个日志文件，释放 {total_size} 字节空间'
        }


# 全局日志管理器实例
_log_manager = LogManager()


def setup_logger(name: str, **kwargs) -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        **kwargs: 配置参数
            - level: 日志级别
            - json_output: 是否输出JSON格式
            - json_file: JSON文件路径
            - separate_file: 是否使用独立文件
            - file_path: 独立文件路径
            - no_propagate: 是否禁用传播
    
    Returns:
        配置好的日志记录器
    """
    return _log_manager.get_logger(name, **kwargs)


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return logging.getLogger(name)


def set_log_level(level: str, logger_name: Optional[str] = None):
    """设置日志级别"""
    _log_manager.set_level(level, logger_name)


def add_file_logging(log_file: str, logger_name: Optional[str] = None):
    """添加文件日志输出"""
    _log_manager.add_file_output(log_file, logger_name)


def add_json_logging(log_file: str, logger_name: Optional[str] = None):
    """添加JSON文件日志输出"""
    _log_manager.add_json_output(log_file, logger_name)


def get_logging_stats() -> Dict[str, Any]:
    """获取日志统计信息"""
    return _log_manager.get_log_stats()


def cleanup_logs(days: int = 7) -> Dict[str, Any]:
    """清理旧日志文件"""
    return _log_manager.cleanup_old_logs(days)


class LogContext:
    """日志上下文管理器"""
    
    def __init__(self, logger: logging.Logger, extra_fields: Dict[str, Any]):
        """初始化日志上下文"""
        self.logger = logger
        self.extra_fields = extra_fields
        self.old_adapter = None
    
    def __enter__(self):
        """进入上下文"""
        # 创建LoggerAdapter来添加额外字段
        self.old_adapter = getattr(self.logger, '_adapter', None)
        adapter = logging.LoggerAdapter(self.logger, self.extra_fields)
        self.logger._adapter = adapter
        return adapter
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        if self.old_adapter:
            self.logger._adapter = self.old_adapter
        else:
            delattr(self.logger, '_adapter')


def log_with_context(logger: logging.Logger, **extra_fields):
    """
    带上下文的日志记录
    
    Usage:
        with log_with_context(logger, user_id="123", request_id="456") as log:
            log.info("处理请求")
    """
    return LogContext(logger, extra_fields)


# 测试函数
def test_logger():
    """测试日志模块"""
    try:
        # 创建测试日志记录器
        logger = setup_logger('test_logger')
        
        # 测试各种级别的日志
        logger.debug("调试信息")
        logger.info("普通信息")
        logger.warning("警告信息")
        logger.error("错误信息")
        
        # 测试上下文日志
        with log_with_context(logger, test_id="123") as log:
            log.info("上下文测试")
        
        # 获取统计信息
        stats = get_logging_stats()
        print(f"日志统计: {stats}")
        
        print("日志模块测试通过")
        
    except Exception as e:
        print(f"日志模块测试失败: {e}")
        raise


if __name__ == "__main__":
    test_logger()