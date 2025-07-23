import asyncio
import argparse
from mcp import ClientSession
from mcp.client.sse import sse_client


async def main():
    parser = argparse.ArgumentParser(description="MCP 文件读取客户端")
    parser.add_argument("--url", default="http://localhost:8020", help="MCP 服务器地址")
    parser.add_argument("--file", help="可选：指定要读取的文件路径")
    args = parser.parse_args()

    print(f"正在连接到 MCP 服务器: {args.url}")

    try:
        async with sse_client(args.url + "/sse") as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("✅ 会话初始化成功")

                tools = await session.list_tools()
                print("📦 可用工具:")
                for name, tool in tools:
                    desc = getattr(tool, "description", None) or "无描述"
                    print(f"  - {name}: {desc}")

                print("\n📂 调用 read_file 工具...")
                params = (
                    {"params": {"file_path": args.file}}
                    if args.file
                    else {"params": {}}
                )
                result = await session.call_tool("read_file", params)

                if result.content:
                    content = result.content[0].text
                    print("\n📄 文件内容预览（前500字符）:")
                    print(content[:500])
                else:
                    print("⚠️ 无返回内容")

    except Exception as e:
        print(f"❌ 客户端错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
