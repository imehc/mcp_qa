"""
客户端初始化模块
自动配置所有可用的模型和MCP客户端
"""

from typing import List, Dict, Any
from ..config import UIConfig, ModelConfig, MCPServerConfig
from ..utils.logger import get_logger
from .model_adapter import unified_model_client
from .mcp_client import unified_mcp_client, create_mcp_client

logger = get_logger(__name__)

async def initialize_model_clients() -> Dict[str, Any]:
    """初始化所有模型客户端"""
    results = {
        "success": [],
        "failed": [],
        "total": 0
    }
    
    # 获取所有模型配置
    model_configs = UIConfig.get_model_configs()
    results["total"] = len(model_configs)
    
    for config in model_configs:
        try:
            # 创建适配器名称
            adapter_name = f"{config.provider.value}_{config.model_name.replace(':', '_').replace('.', '_')}"
            
            # 创建并添加适配器
            success = unified_model_client.create_adapter_from_config(
                config=config,
                name=adapter_name,
                is_default=(config.provider.value == UIConfig.DEFAULT_PROVIDER)
            )
            
            if success:
                results["success"].append({
                    "name": adapter_name,
                    "provider": config.provider.value,
                    "model": config.model_name
                })
                logger.info(f"成功初始化模型客户端: {adapter_name}")
            else:
                results["failed"].append({
                    "name": adapter_name,
                    "provider": config.provider.value,
                    "model": config.model_name,
                    "error": "创建适配器失败"
                })
                logger.error(f"初始化模型客户端失败: {adapter_name}")
                
        except Exception as e:
            results["failed"].append({
                "name": f"{config.provider.value}_{config.model_name}",
                "provider": config.provider.value,
                "model": config.model_name,
                "error": str(e)
            })
            logger.error(f"初始化模型客户端异常: {e}")
    
    logger.info(f"模型客户端初始化完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}")
    return results

async def initialize_mcp_clients() -> Dict[str, Any]:
    """初始化所有MCP客户端"""
    results = {
        "success": [],
        "failed": [],
        "total": 0
    }
    
    # 获取所有MCP服务器配置
    mcp_configs = UIConfig.get_mcp_server_configs()
    results["total"] = len(mcp_configs)
    
    for config in mcp_configs:
        try:
            # 创建MCP客户端
            client = create_mcp_client(config)
            
            # 添加到统一客户端管理器
            unified_mcp_client.add_client(
                name=config.name,
                client=client,
                is_default=(config.name == "local")
            )
            
            results["success"].append({
                "name": config.name,
                "type": config.server_type.value,
                "url": config.url
            })
            logger.info(f"成功初始化MCP客户端: {config.name}")
            
        except Exception as e:
            results["failed"].append({
                "name": config.name,
                "type": config.server_type.value,
                "url": config.url,
                "error": str(e)
            })
            logger.error(f"初始化MCP客户端异常: {e}")
    
    logger.info(f"MCP客户端初始化完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}")
    return results

async def health_check_all_clients() -> Dict[str, Any]:
    """健康检查所有客户端"""
    results = {
        "models": {},
        "mcp_servers": {},
        "summary": {
            "models_healthy": 0,
            "models_total": 0,
            "mcp_healthy": 0,
            "mcp_total": 0
        }
    }
    
    # 检查模型客户端
    try:
        model_health = await unified_model_client.health_check_all()
        results["models"] = model_health
        results["summary"]["models_total"] = len(model_health)
        results["summary"]["models_healthy"] = sum(1 for status in model_health.values() if status)
    except Exception as e:
        logger.error(f"模型客户端健康检查失败: {e}")
    
    # 检查MCP客户端
    try:
        mcp_health = await unified_mcp_client.health_check_all()
        results["mcp_servers"] = mcp_health
        results["summary"]["mcp_total"] = len(mcp_health)
        results["summary"]["mcp_healthy"] = sum(1 for status in mcp_health.values() if status)
    except Exception as e:
        logger.error(f"MCP客户端健康检查失败: {e}")
    
    return results

async def get_all_available_models() -> Dict[str, List[str]]:
    """获取所有可用模型列表"""
    try:
        return await unified_model_client.list_all_models()
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return {}

async def get_all_mcp_tools() -> Dict[str, Any]:
    """获取所有MCP工具列表"""
    try:
        return await unified_mcp_client.list_all_tools()
    except Exception as e:
        logger.error(f"获取MCP工具列表失败: {e}")
        return {}

async def initialize_all_clients() -> Dict[str, Any]:
    """初始化所有客户端"""
    logger.info("开始初始化所有客户端...")
    
    results = {
        "models": await initialize_model_clients(),
        "mcp_servers": await initialize_mcp_clients(),
        "health_check": await health_check_all_clients()
    }
    
    # 记录初始化摘要
    models_success = len(results["models"]["success"])
    models_total = results["models"]["total"]
    mcp_success = len(results["mcp_servers"]["success"])
    mcp_total = results["mcp_servers"]["total"]
    
    logger.info(f"客户端初始化完成:")
    logger.info(f"  模型客户端: {models_success}/{models_total}")
    logger.info(f"  MCP客户端: {mcp_success}/{mcp_total}")
    logger.info(f"  健康检查: 模型 {results['health_check']['summary']['models_healthy']}/{results['health_check']['summary']['models_total']}, MCP {results['health_check']['summary']['mcp_healthy']}/{results['health_check']['summary']['mcp_total']}")
    
    return results

def get_client_status_summary() -> Dict[str, Any]:
    """获取客户端状态摘要"""
    return {
        "model_adapters": {
            "total": len(unified_model_client.adapters),
            "default": unified_model_client.default_adapter.provider if unified_model_client.default_adapter else None,
            "providers": list(set(adapter.provider for adapter in unified_model_client.adapters.values()))
        },
        "mcp_clients": {
            "total": len(unified_mcp_client.clients),
            "default": unified_mcp_client.default_client.config.name if unified_mcp_client.default_client else None,
            "types": list(set(client.server_type.value for client in unified_mcp_client.clients.values()))
        }
    }