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
import uvicorn

#  配置日志
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


# 初始化MCP
mcp = FastMCP("file_reader")


@mcp.tool()
async def read_file():
    """
    读取配置中文件的数据
    Returns:
        文件内容或错误信息
    """
    file_path = Config.FILE_PATH
    try:
        logger.info(f"Reading file:{file_path}")
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError as e:
        logger.error(f"File not found: {file_path}")
        return {
            "error": "File not found",
            "details": str(e),
        }
    except Exception as e:
        logger.exception(f"Error reading file: {file_path}")
        return {"error": "Unexpected error", "details": str(e)}


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
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=Config.DEBUG,
        routes=[
            Route("/sse", endpoint=handle_sse),
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
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    # 更新配置

    Config.HOST = args.host
    Config.PORT = args.port
    Config.DEBUG = args.debug

    # 启动服务器
    mcp_server = mcp._mcp_server
    starlette_app = create_starlette_app(mcp_server)

    logger.info(f"Starting server on {Config.HOST}:{Config.PORT}")
    uvicorn.run(
        starlette_app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info" if not Config.DEBUG else "debug",
    )
