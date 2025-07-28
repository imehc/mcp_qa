#!/usr/bin/env python3
"""
MCP UI启动脚本
"""

import sys
import subprocess
import time
import signal
import os
from pathlib import Path
import httpx

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp_ui.config import UIConfig
from mcp_ui.utils import get_logger

logger = get_logger(__name__)

def check_mcp_server():
    """检查MCP服务器是否运行"""
    try:
        response = httpx.get(f"{UIConfig.MCP_SERVER_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def start_mcp_server():
    """启动MCP服务器"""
    logger.info("启动MCP服务器...")
    try:
        # 使用项目根目录作为工作目录
        env = os.environ.copy()
        process = subprocess.Popen(
            [sys.executable, "-m", "mcp_server.cli"],
            cwd=project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # 等待服务器启动
        for _ in range(10):
            time.sleep(1)
            if check_mcp_server():
                logger.info("MCP服务器启动成功")
                return process
        
        logger.error("MCP服务器启动超时")
        process.terminate()
        return None
        
    except Exception as e:
        logger.error(f"启动MCP服务器失败: {e}")
        return None

def check_ollama_server():
    """检查Ollama服务器是否运行"""
    try:
        response = httpx.get(f"{UIConfig.OLLAMA_BASE_URL}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

def start_ui_server():
    """启动UI服务器"""
    logger.info(f"启动UI服务器 - {UIConfig.APP_HOST}:{UIConfig.APP_PORT}")
    
    try:
        # 构建启动命令
        cmd = [
            "chainlit", "run", 
            str(Path(__file__).parent / "app.py"),
            "--host", UIConfig.APP_HOST,
            "--port", str(UIConfig.APP_PORT)
        ]
        
        if UIConfig.DEBUG:
            cmd.append("--debug")
        
        # 启动Chainlit应用
        subprocess.run(cmd, cwd=project_root)
        
    except KeyboardInterrupt:
        logger.info("用户中断，正在关闭服务器...")
    except Exception as e:
        logger.error(f"启动UI服务器失败: {e}")

def main():
    """主函数"""
    logger.info("="*60)
    logger.info("MCP UI 启动中...")
    logger.info("="*60)
    
    mcp_process = None
    
    try:
        # 检查MCP服务器
        if not check_mcp_server():
            logger.info("MCP服务器未运行，正在启动...")
            mcp_process = start_mcp_server()
            if not mcp_process:
                logger.error("无法启动MCP服务器，退出")
                return 1
        else:
            logger.info("MCP服务器已运行")
        
        # 检查Ollama服务器
        if not check_ollama_server():
            logger.warning("Ollama服务器未运行，AI功能将不可用")
            logger.info("请运行: brew services start ollama")
        else:
            logger.info("Ollama服务器已运行")
        
        # 显示配置信息
        logger.info(f"MCP服务器: {UIConfig.MCP_SERVER_URL}")
        logger.info(f"Ollama服务器: {UIConfig.OLLAMA_BASE_URL}")
        logger.info(f"UI地址: http://{UIConfig.APP_HOST}:{UIConfig.APP_PORT}")
        logger.info(f"上传目录: {UIConfig.UPLOAD_DIR}")
        
        # 启动UI服务器
        start_ui_server()
        
    except KeyboardInterrupt:
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"启动失败: {e}")
        return 1
    finally:
        # 清理子进程
        if mcp_process:
            logger.info("关闭MCP服务器...")
            mcp_process.terminate()
            mcp_process.wait()
    
    logger.info("MCP UI 已关闭")
    return 0

if __name__ == "__main__":
    sys.exit(main())