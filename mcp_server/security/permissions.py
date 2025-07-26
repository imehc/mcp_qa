"""
MCP 服务器权限控制和访问管理

该模块为 MCP 服务器中的各种操作和资源提供细粒度的权限控制。
"""

import os
import logging
from typing import Dict, List, Set, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..config import config
from ..exceptions import PermissionDeniedError, SecurityError
from .path_validator import path_validator

logger = logging.getLogger(__name__)


class Permission(Enum):
    """系统中可用的权限。"""
    
    # 文件操作
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    DELETE_FILE = "delete_file"
    LIST_DIRECTORY = "list_directory"
    CREATE_DIRECTORY = "create_directory"
    
    # 文档操作
    PARSE_DOCUMENT = "parse_document"
    CONVERT_DOCUMENT = "convert_document"
    EXTRACT_METADATA = "extract_metadata"
    
    # 索引操作
    BUILD_INDEX = "build_index"
    SEARCH_INDEX = "search_index"
    DELETE_INDEX = "delete_index"
    
    # 系统操作
    GET_SYSTEM_INFO = "get_system_info"
    MODIFY_CONFIG = "modify_config"
    ACCESS_LOGS = "access_logs"
    
    # 管理操作
    MANAGE_PERMISSIONS = "manage_permissions"
    SYSTEM_ADMIN = "system_admin"


class AccessLevel(Enum):
    """用户/角色的访问级别。"""
    
    GUEST = "guest"          # 对基本操作的只读访问
    USER = "user"            # 标准用户操作
    POWER_USER = "power_user" # 高级操作
    ADMIN = "admin"          # 完整的管理访问


@dataclass
class AccessRule:
    """表示访问控制规则。"""
    
    permission: Permission
    resource_pattern: Optional[str] = None  # 用于资源匹配的正则表达式模式
    conditions: Optional[Dict[str, Any]] = None  # 附加条件
    expires_at: Optional[datetime] = None  # 过期时间
    description: Optional[str] = None


@dataclass
class AccessRequest:
    """表示对资源的访问请求。"""
    
    permission: Permission
    resource: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    client_info: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class PermissionManager:
    """
    管理 MCP 服务器的权限和访问控制。
    
    该类提供了一个灵活的权限系统，可以扩展用户管理、角色和细粒度访问控制。
    """
    
    def __init__(self):
        """初始化权限管理器。"""
        self.access_rules: Dict[str, List[AccessRule]] = {}
        self.role_permissions: Dict[AccessLevel, Set[Permission]] = {}
        self.user_roles: Dict[str, AccessLevel] = {}
        self.session_permissions: Dict[str, Set[Permission]] = {}
        self.access_log: List[Dict[str, Any]] = []
        
        # 初始化默认角色权限
        self._initialize_default_roles()
        
        # 速率限制
        self.rate_limits: Dict[str, List[datetime]] = {}
        self.max_requests_per_minute = 60
    
    def _initialize_default_roles(self) -> None:
        """初始化默认角色权限。"""
        
        # 访客权限 (只读)
        self.role_permissions[AccessLevel.GUEST] = {
            Permission.READ_FILE,
            Permission.LIST_DIRECTORY,
            Permission.PARSE_DOCUMENT,
            Permission.SEARCH_INDEX,
            Permission.GET_SYSTEM_INFO
        }
        
        # 用户权限 (标准操作)
        self.role_permissions[AccessLevel.USER] = (
            self.role_permissions[AccessLevel.GUEST] | {
                Permission.CONVERT_DOCUMENT,
                Permission.EXTRACT_METADATA,
                Permission.BUILD_INDEX
            }
        )
        
        # 高级用户权限 (高级操作)
        self.role_permissions[AccessLevel.POWER_USER] = (
            self.role_permissions[AccessLevel.USER] | {
                Permission.WRITE_FILE,
                Permission.CREATE_DIRECTORY,
                Permission.DELETE_INDEX,
                Permission.ACCESS_LOGS
            }
        )
        
        # 管理员权限 (所有权限)
        self.role_permissions[AccessLevel.ADMIN] = set(Permission)
    
    def check_permission(
        self, 
        request: AccessRequest, 
        access_level: AccessLevel = AccessLevel.GUEST
    ) -> bool:
        """
        检查是否应授予权限请求。
        
        参数:
            request: 要检查的访问请求
            access_level: 请求者的访问级别
            
        返回:
            如果授予权限则返回 True，否则返回 False
        """
        try:
            # 记录访问尝试
            self._log_access_attempt(request, access_level)
            
            # 检查速率限制
            if not self._check_rate_limit(request):
                return False
            
            # 检查基本角色权限
            if not self._check_role_permission(request.permission, access_level):
                return False
            
            # 检查资源特定规则
            if not self._check_resource_access(request, access_level):
                return False
            
            # 检查会话特定权限
            if request.session_id and not self._check_session_permission(request):
                return False
            
            # 检查附加条件
            if not self._check_additional_conditions(request, access_level):
                return False
            
            # 所有检查通过
            self._log_access_granted(request, access_level)
            return True
            
        except Exception as e:
            logger.error(f"权限检查失败: {str(e)}")
            self._log_access_denied(request, access_level, str(e))
            return False
    
    def require_permission(
        self, 
        request: AccessRequest, 
        access_level: AccessLevel = AccessLevel.GUEST
    ) -> None:
        """
        要求权限或引发异常。
        
        参数:
            request: 要检查的访问请求
            access_level: 请求者的访问级别
            
        引发:
            PermissionDeniedError: 如果权限被拒绝
        """
        if not self.check_permission(request, access_level):
            raise PermissionDeniedError(
                operation=request.permission.value,
                resource=request.resource or "system",
                reason=f"{access_level.value} 权限不足"
            )
    
    def _check_role_permission(self, permission: Permission, access_level: AccessLevel) -> bool:
        """检查访问级别是否具有所需权限。"""
        allowed_permissions = self.role_permissions.get(access_level, set())
        return permission in allowed_permissions
    
    def _check_resource_access(self, request: AccessRequest, access_level: AccessLevel) -> bool:
        """检查资源特定的访问规则。"""
        
        # 文件系统访问检查
        if request.resource and request.permission in [
            Permission.READ_FILE, Permission.WRITE_FILE, Permission.DELETE_FILE
        ]:
            return self._check_file_access(request.resource, request.permission, access_level)
        
        # 目录访问检查
        if request.resource and request.permission in [
            Permission.LIST_DIRECTORY, Permission.CREATE_DIRECTORY
        ]:
            return self._check_directory_access(request.resource, request.permission, access_level)
        
        # 索引访问检查
        if request.permission in [Permission.BUILD_INDEX, Permission.DELETE_INDEX]:
            return self._check_index_access(request, access_level)
        
        return True
    
    def _check_file_access(self, file_path: str, permission: Permission, access_level: AccessLevel) -> bool:
        """检查文件特定的访问权限。"""
        
        # 验证路径安全
        if not path_validator.is_path_safe(file_path):
            return False
        
        # 检查文件是否在允许的目录中
        try:
            path_validator.validate_path(file_path, check_existence=False)
        except Exception:
            return False
        
        # 基于扩展名的附加文件特定规则
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # 限制某些文件类型的写入/删除操作
        if permission in [Permission.WRITE_FILE, Permission.DELETE_FILE]:
            if access_level == AccessLevel.GUEST:
                return False
            
            # 系统文件应仅由管理员访问
            system_extensions = {'.sys', '.dll', '.exe', '.bat', '.cmd'}
            if file_ext in system_extensions and access_level != AccessLevel.ADMIN:
                return False
        
        return True
    
    def _check_directory_access(self, dir_path: str, permission: Permission, access_level: AccessLevel) -> bool:
        """检查目录特定的访问权限。"""
        
        # 验证目录路径
        if not path_validator.check_directory_listing_allowed(dir_path):
            return False
        
        # 目录创建需要提升的权限
        if permission == Permission.CREATE_DIRECTORY and access_level == AccessLevel.GUEST:
            return False
        
        return True
    
    def _check_index_access(self, request: AccessRequest, access_level: AccessLevel) -> bool:
        """检查索引操作权限。"""
        
        # 构建索引需要大量资源
        if request.permission == Permission.BUILD_INDEX:
            # 检查是否有正在进行的构建
            # 这是更复杂逻辑的占位符
            return access_level in [AccessLevel.USER, AccessLevel.POWER_USER, AccessLevel.ADMIN]
        
        # 删除索引是一项破坏性操作
        if request.permission == Permission.DELETE_INDEX:
            return access_level in [AccessLevel.POWER_USER, AccessLevel.ADMIN]
        
        return True
    
    def _check_session_permission(self, request: AccessRequest) -> bool:
        """检查会话特定权限。"""
        if request.session_id in self.session_permissions:
            session_perms = self.session_permissions[request.session_id]
            return request.permission in session_perms
        return True  # 默认情况下无会话限制
    
    def _check_additional_conditions(self, request: AccessRequest, access_level: AccessLevel) -> bool:
        """检查附加条件如基于时间的限制。"""
        
        # 基于时间的限制 (示例: 维护窗口期间无管理操作)
        current_hour = datetime.now().hour
        if (access_level == AccessLevel.ADMIN and 
            request.permission == Permission.SYSTEM_ADMIN and
            2 <= current_hour <= 4):  # 维护窗口 2-4 AM
            return False
        
        # 资源大小限制
        if request.resource and os.path.exists(request.resource):
            file_size = os.path.getsize(request.resource)
            max_size = config.security.MAX_FILE_SIZE
            
            if file_size > max_size and access_level != AccessLevel.ADMIN:
                return False
        
        return True
    
    def _check_rate_limit(self, request: AccessRequest) -> bool:
        """检查请求的速率限制。"""
        
        # 使用 session_id 或 user_id 进行速率限制
        key = request.session_id or request.user_id or "anonymous"
        now = datetime.now()
        
        # 清理旧条目
        if key in self.rate_limits:
            self.rate_limits[key] = [
                timestamp for timestamp in self.rate_limits[key]
                if now - timestamp < timedelta(minutes=1)
            ]
        else:
            self.rate_limits[key] = []
        
        # 检查是否超出速率限制
        if len(self.rate_limits[key]) >= self.max_requests_per_minute:
            return False
        
        # 添加当前请求
        self.rate_limits[key].append(now)
        return True
    
    def _log_access_attempt(self, request: AccessRequest, access_level: AccessLevel) -> None:
        """记录访问尝试。"""
        log_entry = {
            "timestamp": request.timestamp.isoformat(),
            "permission": request.permission.value,
            "resource": request.resource,
            "access_level": access_level.value,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "status": "attempted"
        }
        self.access_log.append(log_entry)
        
        # 保持日志大小可管理
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-500:]
    
    def _log_access_granted(self, request: AccessRequest, access_level: AccessLevel) -> None:
        """记录成功的访问授权。"""
        if self.access_log:
            self.access_log[-1]["status"] = "granted"
        
        logger.info(
            f"访问已授予: {request.permission.value} 给 {access_level.value} "
            f"在 {request.resource or 'system'} 上"
        )
    
    def _log_access_denied(self, request: AccessRequest, access_level: AccessLevel, reason: str) -> None:
        """记录访问拒绝。"""
        if self.access_log:
            self.access_log[-1]["status"] = "denied"
            self.access_log[-1]["reason"] = reason
        
        logger.warning(
            f"访问被拒绝: {request.permission.value} 给 {access_level.value} "
            f"在 {request.resource or 'system'} 上 - {reason}"
        )
    
    def add_access_rule(self, rule: AccessRule) -> None:
        """添加自定义访问规则。"""
        permission_key = rule.permission.value
        if permission_key not in self.access_rules:
            self.access_rules[permission_key] = []
        self.access_rules[permission_key].append(rule)
    
    def set_user_role(self, user_id: str, role: AccessLevel) -> None:
        """为用户设置角色。"""
        self.user_roles[user_id] = role
    
    def set_session_permissions(self, session_id: str, permissions: Set[Permission]) -> None:
        """为会话设置特定权限。"""
        self.session_permissions[session_id] = permissions
    
    def get_access_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的访问日志条目。"""
        return self.access_log[-limit:]
    
    def clear_expired_rules(self) -> None:
        """移除过期的访问规则。"""
        now = datetime.now()
        
        for permission_key in self.access_rules:
            self.access_rules[permission_key] = [
                rule for rule in self.access_rules[permission_key]
                if rule.expires_at is None or rule.expires_at > now
            ]


# 全局权限管理器实例
permission_manager = PermissionManager()


# 便利函数
def check_permission(
    permission: Permission, 
    resource: Optional[str] = None,
    access_level: AccessLevel = AccessLevel.GUEST,
    **kwargs
) -> bool:
    """
    使用全局管理器检查是否授予权限。
    
    参数:
        permission: 要检查的权限
        resource: 正在访问的资源
        access_level: 请求者的访问级别
        **kwargs: 附加请求参数
        
    返回:
        如果授予权限则返回 True，否则返回 False
    """
    request = AccessRequest(
        permission=permission,
        resource=resource,
        **kwargs
    )
    return permission_manager.check_permission(request, access_level)


def require_permission(
    permission: Permission, 
    resource: Optional[str] = None,
    access_level: AccessLevel = AccessLevel.GUEST,
    **kwargs
) -> None:
    """
    要求权限或使用全局管理器引发异常。
    
    参数:
        permission: 要求的权限
        resource: 正在访问的资源
        access_level: 请求者的访问级别
        **kwargs: 附加请求参数
        
    引发:
        PermissionDeniedError: 如果权限被拒绝
    """
    request = AccessRequest(
        permission=permission,
        resource=resource,
        **kwargs
    )
    permission_manager.require_permission(request, access_level)