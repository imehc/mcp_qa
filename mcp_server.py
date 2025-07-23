from argparse import ArgumentParser
import logging
import os
from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
from pydantic import BaseModel

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s  - %(message)s"
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()


class Config:
    """配置类"""
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8020))
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    FILE_PATH = os.getenv("FILE_PATH", "/Users/imehc/Downloads/JavaScript百炼成仙.pdf")


# 初始化MCP - 添加协议版本
mcp = FastMCP("file_reader", protocol_version="1.0")


# 定义工具调用参数模型
class ReadFileParams(BaseModel):
    pass  # 此工具不需要参数，但保留模型以符合协议


@mcp.tool()
async def read_file(params: ReadFileParams):
    """
    读取配置中文件的数据
    
    Args:
        params: 工具调用参数（即使不需要参数也要声明）
    
    Returns:
        文件内容或错误信息
    """
    file_path = Config.FILE_PATH
    try:
        logger.info(f"Reading file:{file_path}")
        # 使用二进制读取避免编码问题
        with open(file_path, "rb") as file:
            content = file.read()
            # 尝试UTF-8解码，失败则返回base64
            try:
                return content.decode("utf-8")
            except UnicodeDecodeError:
                import base64
                return {
                    "content": base64.b64encode(content).decode("utf-8"),
                    "encoding": "base64",
                    "message": "文件包含非UTF-8字符，已使用Base64编码"
                }
    except FileNotFoundError as e:
        logger.error(f"File not found: {file_path}")
        return {
            "error": "File not found",
            "details": str(e),
            "path": file_path
        }
    except Exception as e:
        logger.exception(f"Error reading file: {file_path}")
        return {
            "error": "Unexpected error",
            "details": str(e),
            "path": file_path
        }


def create_starlette_app(mcp_server: Server) -> Starlette:
    """
    创建基于Starlette的MCP服务器应用

    Args:
        mcp_server: MCP服务器实例

    Returns:
        Starlette应用实例
    """
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        # 添加请求日志以帮助调试
        logger.debug(f"Received SSE connection from {request.client.host}")
        
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            # 修复：直接使用InitializationOptions对象，不进行解包
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    # 添加健康检查端点
    async def health_check(request: Request):
        return JSONResponse({"status": "ok", "service": "mcp-server"})
    
    return Starlette(
        debug=Config.DEBUG,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/health", endpoint=health_check),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        on_startup=[lambda: logger.info("Server starting...")],
        on_shutdown=[lambda: logger.info("Server shutting down...")],
    )


def parse_arguments():
    """解析命令行参数"""
    parser = ArgumentParser(description="Run MCP SSE-based server")
    parser.add_argument("--host", default=Config.HOST, help="Host to bind to")
    parser.add_argument(
        "--port", type=int, default=Config.PORT, help="Port to listen on"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--file", default=Config.FILE_PATH, help="File path to read")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    # 更新配置
    Config.HOST = args.host
    Config.PORT = args.port
    Config.DEBUG = args.debug
    Config.FILE_PATH = args.file  # 添加命令行文件路径参数

    # 确保文件存在
    if not os.path.exists(Config.FILE_PATH):
        logger.warning(f"File does not exist: {Config.FILE_PATH}")
        logger.info("Using default file path if available...")
    
    # 启动服务器
    mcp_server = mcp._mcp_server
    starlette_app = create_starlette_app(mcp_server)

    logger.info(f"Starting server on {Config.HOST}:{Config.PORT}")
    logger.info(f"Serving file: {Config.FILE_PATH}")
    
    uvicorn.run(
        starlette_app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info" if not Config.DEBUG else "debug",
    )