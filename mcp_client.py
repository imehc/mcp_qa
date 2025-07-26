import asyncio
import argparse
import logging
from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)

class MCPClient:
    """MCP客户端类，用于与MCP服务器通信"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = None
        self.read_stream = None
        self.write_stream = None
        self._connection = None
    
    async def connect(self):
        """连接到MCP服务器"""
        try:
            self._connection = sse_client(self.server_url + "/sse")
            self.read_stream, self.write_stream = await self._connection.__aenter__()
            self.session = ClientSession(self.read_stream, self.write_stream)
            await self.session.__aenter__()
            await self.session.initialize()
            logger.info("Successfully connected to MCP server")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False
    
    async def close(self):
        """关闭连接"""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if self._connection:
                await self._connection.__aexit__(None, None, None)
            logger.info("MCP client connection closed")
        except Exception as e:
            logger.error(f"Error closing MCP client: {e}")
    
    async def list_tools(self):
        """列出可用工具"""
        if not self.session:
            await self.connect()
        
        try:
            tools = await self.session.list_tools()
            return tools
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []
    
    async def call_tool(self, tool_name: str, params: dict):
        """调用指定工具"""
        if not self.session:
            await self.connect()
        
        try:
            result = await self.session.call_tool(tool_name, {"params": params})
            
            if result.content:
                # 尝试解析结果
                content = result.content[0].text
                try:
                    import json
                    return json.loads(content)
                except json.JSONDecodeError:
                    return content
            else:
                return {"error": "No content returned"}
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

async def main():
    parser = argparse.ArgumentParser(description="MCP 文件读取客户端")
    parser.add_argument("--url", default="http://localhost:8020", help="MCP 服务器地址")
    parser.add_argument("--file-name", help="要读取的文件名（不需要完整路径）")
    args = parser.parse_args()

    print(f"正在连接到 MCP 服务器: {args.url}")

    try:
        async with MCPClient(args.url) as client:
            print("✅ 会话初始化成功")

            tools = await client.list_tools()
            if hasattr(tools, 'tools'):
                tool_list = tools.tools
                print("📦 可用工具:")
                for tool in tool_list:
                    desc = getattr(tool, "description", None) or "无描述"
                    print(f"  - {tool.name}: {desc}")
            else:
                print("获取工具列表失败")

            if args.file_name:
                print(f"\n📂 读取文件: {args.file_name}")
                result = await client.call_tool("read_file", {"file_name": args.file_name})
                
                if isinstance(result, dict):
                    if "error" in result:
                        print(f"❌ 错误: {result['error']}")
                        if "available_files" in result:
                            print("📋 可用文件:")
                            for file in result["available_files"]:
                                print(f"  - {file}")
                    elif "content" in result:
                        print(f"✅ 文件读取成功")
                        print(f"📄 文件名: {result['file_name']}")
                        print(f"📍 路径: {result['file_path']}")
                        print(f"🔤 编码: {result['encoding']}")
                        if result['encoding'] == 'utf-8':
                            print(f"📄 内容preview: {result['content'][:500]}...")
                        else:
                            print("📄 文件为二进制格式（Base64编码）")
                elif isinstance(result, str):
                    print(f"📄 文件内容preview: {result[:500]}...")
                else:
                    print(f"⚠️ 返回结果: {result}")
            else:
                print("\n💡 提示: 使用 --file-name 参数指定要读取的文件名")
                print("例如: python mcp_client.py --file-name example.txt")

    except Exception as e:
        print(f"❌ 客户端错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
