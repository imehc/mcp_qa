mcp-server:
	@echo "Starting MCP server..."
	uv run mcp_server.py --host 0.0.0.0 --port 8020

mcp-client:
	@echo "Starting MCP client..."
	uv run mcp_client.py --url http://localhost:8020

.PHONY: mcp-server mcp-client