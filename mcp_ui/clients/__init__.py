"""
客户端模块初始化
"""

from .mcp_client import MCPClient, UnifiedMCPClient, mcp_client, unified_mcp_client, create_mcp_client
from .ollama_client import OllamaClient, ollama_client
from .model_adapter import (
    ModelAdapter, 
    ModelResponse,
    UnifiedModelClient, 
    ModelAdapterRegistry,
    unified_model_client, 
    model_adapter_registry
)

__all__ = [
    "MCPClient",
    "UnifiedMCPClient", 
    "mcp_client",
    "unified_mcp_client",
    "create_mcp_client",
    "OllamaClient",
    "ollama_client",
    "ModelAdapter",
    "ModelResponse", 
    "UnifiedModelClient",
    "ModelAdapterRegistry",
    "unified_model_client",
    "model_adapter_registry"
]