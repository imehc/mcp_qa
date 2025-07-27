"""
MCP 服务器文件操作工具

该模块提供与 MCP 兼容的文件系统操作工具，
包括读取、写入、列出和管理文件及目录。
"""

import os
import logging
import shutil
from typing import Dict, Any, Optional
from datetime import datetime
import pytz

from ..config import config
from ..security.path_validator import validate_path
from ..security.permissions import (
    Permission, AccessLevel, 
    require_permission
)
from ..exceptions import (
    FileAccessDeniedError
)
from ..utils import Timer, calculate_file_hash

logger = logging.getLogger(__name__)


class FileOperationTools:
    """
    MCP 服务器文件操作工具
    
    该类提供安全的文件操作，包含权限检查和路径验证，
    可作为 MCP 工具使用。
    """
    
    def __init__(self, access_level: AccessLevel = AccessLevel.USER):
        """
        初始化文件操作工具。
        
        参数:
            access_level: 操作的默认访问级别
        """
        self.access_level = access_level
        self.operation_stats = {
            "read_operations": 0,
            "write_operations": 0,
            "list_operations": 0,
            "delete_operations": 0,
            "copy_operations": 0,
            "move_operations": 0,
            "total_operations": 0
        }
    
    def read_file(
        self, 
        file_path: str, 
        encoding: str = "utf-8",
        max_size_mb: float = 50.0
    ) -> Dict[str, Any]:
        """
        从文件中读取内容。
        
        参数:
            file_path: 要读取的文件路径
            encoding: 使用的文本编码
            max_size_mb: 最大文件大小(MB)
            
        返回:
            包含文件内容和元数据的字典
            
        引发:
            FileAccessDeniedError: 如果文件访问被拒绝
            PermissionDeniedError: 如果权限被拒绝
        """
        timer = Timer()
        timer.start()
        
        try:
            # 验证路径和检查权限
            validated_path = validate_path(file_path)
            
            require_permission(Permission.READ_FILE, validated_path, self.access_level)
            
            # 检查文件大小
            file_size = os.path.getsize(validated_path)
            max_size_bytes = max_size_mb * 1024 * 1024
            
            if file_size > max_size_bytes:
                raise FileAccessDeniedError(
                    file_path=validated_path,
                    reason=f"文件大小 ({file_size / 1024 / 1024:.1f}MB) 超过限制 ({max_size_mb}MB)"
                )
            
            # 读取文件内容
            try:
                with open(validated_path, 'r', encoding=encoding) as f:
                    content = f.read()
            except UnicodeDecodeError:
                # 为非文本文件尝试二进制模式
                with open(validated_path, 'rb') as f:
                    content = f.read()
                    # 转换为 base64 用于二进制内容
                    import base64
                    content = base64.b64encode(content).decode('ascii')
                    encoding = "binary"
            
            read_time = timer.stop()
            
            # 更新统计信息
            self.operation_stats["read_operations"] += 1
            self.operation_stats["total_operations"] += 1
            
            # 获取文件元数据
            stat_info = os.stat(validated_path)
            
            # 使用Shanghai时区格式化时间
            shanghai_tz = pytz.timezone('Asia/Shanghai')
            modified_dt = datetime.fromtimestamp(stat_info.st_mtime, tz=shanghai_tz)
            created_dt = datetime.fromtimestamp(stat_info.st_ctime, tz=shanghai_tz)
            
            result = {
                "success": True,
                "content": content,
                "metadata": {
                    "file_path": validated_path,
                    "encoding": encoding,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / 1024 / 1024, 2),
                    "modified_time": modified_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "created_time": created_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "modified_timestamp": stat_info.st_mtime,
                    "created_timestamp": stat_info.st_ctime,
                    "read_time": read_time,
                    "file_hash": calculate_file_hash(validated_path)
                }
            }
            
            logger.info(f"文件读取成功: {validated_path} ({file_size} 字节)")
            return result
            
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def write_file(
        self,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
        create_directories: bool = True,
        backup_existing: bool = True
    ) -> Dict[str, Any]:
        """
        将内容写入文件。
        
        参数:
            file_path: 要写入的文件路径
            content: 要写入的内容
            encoding: 使用的文本编码
            create_directories: 是否创建父目录
            backup_existing: 是否备份现有文件
            
        返回:
            包含操作结果的字典
            
        引发:
            FileAccessDeniedError: 如果文件访问被拒绝
            PermissionDeniedError: 如果权限被拒绝
        """
        timer = Timer()
        timer.start()
        
        try:
            # 验证路径和检查权限
            validated_path = validate_path(file_path, check_existence=False)
            
            require_permission(Permission.WRITE_FILE, validated_path, self.access_level)
            
            # 如需要则创建父目录
            if create_directories:
                parent_dir = os.path.dirname(validated_path)
                if parent_dir and not os.path.exists(parent_dir):
                    # 检查目录创建权限
                    require_permission(Permission.CREATE_DIRECTORY, parent_dir, self.access_level)
                    os.makedirs(parent_dir, exist_ok=True)
            
            backup_path = None
            
            # 如请求则备份现有文件
            if backup_existing and os.path.exists(validated_path):
                backup_path = f"{validated_path}.backup"
                shutil.copy2(validated_path, backup_path)
            
            # 写入内容
            if encoding == "binary":
                # 处理二进制内容 (base64 编码)
                import base64
                binary_content = base64.b64decode(content)
                with open(validated_path, 'wb') as f:
                    f.write(binary_content)
            else:
                with open(validated_path, 'w', encoding=encoding) as f:
                    f.write(content)
            
            write_time = timer.stop()
            
            # 更新统计信息
            self.operation_stats["write_operations"] += 1
            self.operation_stats["total_operations"] += 1
            
            # 获取文件元数据
            file_size = os.path.getsize(validated_path)
            
            result = {
                "success": True,
                "metadata": {
                    "file_path": validated_path,
                    "encoding": encoding,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / 1024 / 1024, 2),
                    "write_time": write_time,
                    "backup_created": backup_path is not None,
                    "backup_path": backup_path,
                    "file_hash": calculate_file_hash(validated_path)
                }
            }
            
            logger.info(f"文件写入成功: {validated_path} ({file_size} 字节)")
            return result
            
        except Exception as e:
            logger.error(f"写入文件失败 {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def list_directory(
        self,
        directory_path: str,
        recursive: bool = False,
        include_hidden: bool = False,
        file_pattern: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        列出目录内容。
        
        参数:
            directory_path: 要列出的目录路径
            recursive: 是否递归列出
            include_hidden: 是否包含隐藏文件
            file_pattern: 用于过滤文件的模式 (通配符模式)
            
        返回:
            包含目录内容的字典
            
        引发:
            FileAccessDeniedError: 如果目录访问被拒绝
            PermissionDeniedError: 如果权限被拒绝
        """
        timer = Timer()
        timer.start()
        
        try:
            # 验证路径和检查权限
            validated_path = validate_path(directory_path)
            
            require_permission(Permission.LIST_DIRECTORY, validated_path, self.access_level)
            
            if not os.path.isdir(validated_path):
                return {
                    "success": False,
                    "error": f"路径不是目录: {validated_path}",
                    "directory_path": directory_path
                }
            
            files = []
            directories = []
            total_size = 0
            
            try:
                if recursive:
                    # 递归列出
                    for root, dirs, filenames in os.walk(validated_path):
                        # 如果不包含隐藏文件则过滤隐藏目录
                        if not include_hidden:
                            dirs[:] = [d for d in dirs if not d.startswith('.')]
                        
                        for filename in filenames:
                            if not include_hidden and filename.startswith('.'):
                                continue
                            
                            file_path = os.path.join(root, filename)
                            
                            # 应用文件模式过滤器
                            if file_pattern:
                                import fnmatch
                                if not fnmatch.fnmatch(filename, file_pattern):
                                    continue
                            
                            try:
                                stat_info = os.stat(file_path)
                                
                                # 使用Shanghai时区格式化时间
                                shanghai_tz = pytz.timezone('Asia/Shanghai')
                                modified_dt = datetime.fromtimestamp(stat_info.st_mtime, tz=shanghai_tz)
                                created_dt = datetime.fromtimestamp(stat_info.st_ctime, tz=shanghai_tz)
                                
                                file_info = {
                                    "name": filename,
                                    "path": file_path,
                                    "relative_path": os.path.relpath(file_path, validated_path),
                                    "size": stat_info.st_size,
                                    "modified_time": modified_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                    "created_time": created_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                    "modified_timestamp": stat_info.st_mtime,
                                    "created_timestamp": stat_info.st_ctime,
                                    "is_file": True,
                                    "extension": os.path.splitext(filename)[1].lower()
                                }
                                files.append(file_info)
                                total_size += stat_info.st_size
                            except (OSError, PermissionError):
                                # 跳过无法访问的文件
                                continue
                        
                        for dirname in dirs:
                            if not include_hidden and dirname.startswith('.'):
                                continue
                            
                            dir_path = os.path.join(root, dirname)
                            try:
                                stat_info = os.stat(dir_path)
                                
                                # 使用Shanghai时区格式化时间
                                shanghai_tz = pytz.timezone('Asia/Shanghai')
                                modified_dt = datetime.fromtimestamp(stat_info.st_mtime, tz=shanghai_tz)
                                created_dt = datetime.fromtimestamp(stat_info.st_ctime, tz=shanghai_tz)
                                
                                dir_info = {
                                    "name": dirname,
                                    "path": dir_path,
                                    "relative_path": os.path.relpath(dir_path, validated_path),
                                    "modified_time": modified_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                    "created_time": created_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                    "modified_timestamp": stat_info.st_mtime,
                                    "created_timestamp": stat_info.st_ctime,
                                    "is_directory": True
                                }
                                directories.append(dir_info)
                            except (OSError, PermissionError):
                                # 跳过无法访问的目录
                                continue
                else:
                    # 非递归列出
                    for item in os.listdir(validated_path):
                        if not include_hidden and item.startswith('.'):
                            continue
                        
                        item_path = os.path.join(validated_path, item)
                        
                        try:
                            stat_info = os.stat(item_path)
                            
                            if os.path.isfile(item_path):
                                # 应用文件模式过滤器
                                if file_pattern:
                                    import fnmatch
                                    if not fnmatch.fnmatch(item, file_pattern):
                                        continue
                                
                                # 使用Shanghai时区格式化时间
                                shanghai_tz = pytz.timezone('Asia/Shanghai')
                                modified_dt = datetime.fromtimestamp(stat_info.st_mtime, tz=shanghai_tz)
                                created_dt = datetime.fromtimestamp(stat_info.st_ctime, tz=shanghai_tz)
                                
                                file_info = {
                                    "name": item,
                                    "path": item_path,
                                    "size": stat_info.st_size,
                                    "modified_time": modified_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                    "created_time": created_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                    "modified_timestamp": stat_info.st_mtime,
                                    "created_timestamp": stat_info.st_ctime,
                                    "is_file": True,
                                    "extension": os.path.splitext(item)[1].lower()
                                }
                                files.append(file_info)
                                total_size += stat_info.st_size
                            
                            elif os.path.isdir(item_path):
                                # 使用Shanghai时区格式化时间
                                shanghai_tz = pytz.timezone('Asia/Shanghai')
                                modified_dt = datetime.fromtimestamp(stat_info.st_mtime, tz=shanghai_tz)
                                created_dt = datetime.fromtimestamp(stat_info.st_ctime, tz=shanghai_tz)
                                
                                dir_info = {
                                    "name": item,
                                    "path": item_path,
                                    "modified_time": modified_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                    "created_time": created_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                                    "modified_timestamp": stat_info.st_mtime,
                                    "created_timestamp": stat_info.st_ctime,
                                    "is_directory": True
                                }
                                directories.append(dir_info)
                        
                        except (OSError, PermissionError):
                            # 跳过无法访问的项目
                            continue
                
                list_time = timer.stop()
                
                # 更新统计信息
                self.operation_stats["list_operations"] += 1
                self.operation_stats["total_operations"] += 1
                
                # 排序结果
                files.sort(key=lambda x: x["name"].lower())
                directories.sort(key=lambda x: x["name"].lower())
                
                result = {
                    "success": True,
                    "directory_path": validated_path,
                    "files": files,
                    "directories": directories,
                    "summary": {
                        "total_files": len(files),
                        "total_directories": len(directories),
                        "total_size_bytes": total_size,
                        "total_size_mb": round(total_size / 1024 / 1024, 2),
                        "list_time": list_time,
                        "recursive": recursive,
                        "include_hidden": include_hidden,
                        "file_pattern": file_pattern
                    }
                }
                
                logger.info(f"目录已列出: {validated_path} ({len(files)} 个文件, {len(directories)} 个目录)")
                return result
            
            except PermissionError:
                return {
                    "success": False,
                    "error": f"访问目录权限被拒绝: {validated_path}",
                    "directory_path": directory_path
                }
            
        except Exception as e:
            logger.error(f"列出目录失败 {directory_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "directory_path": directory_path
            }
    
    def delete_file(self, file_path: str, confirm: bool = False) -> Dict[str, Any]:
        """
        删除文件。
        
        参数:
            file_path: 要删除的文件路径
            confirm: 安全确认标志
            
        返回:
            包含操作结果的字典
            
        引发:
            FileAccessDeniedError: 如果文件访问被拒绝
            PermissionDeniedError: 如果权限被拒绝
        """
        timer = Timer()
        timer.start()
        
        try:
            if not confirm:
                return {
                    "success": False,
                    "error": "删除操作需要将确认标志设置为 True",
                    "file_path": file_path
                }
            
            # 验证路径和检查权限
            validated_path = validate_path(file_path)
            
            require_permission(Permission.DELETE_FILE, validated_path, self.access_level)
            
            if not os.path.exists(validated_path):
                return {
                    "success": False,
                    "error": f"文件不存在: {validated_path}",
                    "file_path": file_path
                }
            
            # 删除前获取文件信息
            file_size = os.path.getsize(validated_path)
            
            # 删除文件
            os.remove(validated_path)
            
            delete_time = timer.stop()
            
            # 更新统计信息
            self.operation_stats["delete_operations"] += 1
            self.operation_stats["total_operations"] += 1
            
            result = {
                "success": True,
                "file_path": validated_path,
                "metadata": {
                    "deleted_size_bytes": file_size,
                    "delete_time": delete_time
                }
            }
            
            logger.info(f"文件已删除: {validated_path} ({file_size} 字节)")
            return result
            
        except Exception as e:
            logger.error(f"删除文件失败 {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def copy_file(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        将文件从源复制到目标。
        
        参数:
            source_path: 源文件路径
            destination_path: 目标路径
            overwrite: 是否覆盖现有文件
            
        返回:
            包含操作结果的字典
        """
        timer = Timer()
        timer.start()
        
        try:
            # 验证源路径和检查读取权限
            validated_source = validate_path(source_path)
            
            require_permission(Permission.READ_FILE, validated_source, self.access_level)
            
            # 验证目标路径和检查写入权限
            validated_dest = validate_path(destination_path, check_existence=False)
            
            require_permission(Permission.WRITE_FILE, validated_dest, self.access_level)
            
            if not os.path.exists(validated_source):
                return {
                    "success": False,
                    "error": f"源文件不存在: {validated_source}",
                    "source_path": source_path
                }
            
            if os.path.exists(validated_dest) and not overwrite:
                return {
                    "success": False,
                    "error": f"目标文件已存在且 overwrite 为 False: {validated_dest}",
                    "destination_path": destination_path
                }
            
            # 如需要则创建目标目录
            dest_dir = os.path.dirname(validated_dest)
            if dest_dir and not os.path.exists(dest_dir):
                os.makedirs(dest_dir, exist_ok=True)
            
            # 复制文件
            shutil.copy2(validated_source, validated_dest)
            
            copy_time = timer.stop()
            
            # 更新统计信息
            self.operation_stats["copy_operations"] += 1
            self.operation_stats["total_operations"] += 1
            
            # 获取文件大小
            source_size = os.path.getsize(validated_source)
            dest_size = os.path.getsize(validated_dest)
            
            result = {
                "success": True,
                "source_path": validated_source,
                "destination_path": validated_dest,
                "metadata": {
                    "source_size_bytes": source_size,
                    "destination_size_bytes": dest_size,
                    "copy_time": copy_time,
                    "overwrite_used": overwrite and os.path.exists(validated_dest)
                }
            }
            
            logger.info(f"文件已复制: {validated_source} -> {validated_dest} ({source_size} 字节)")
            return result
            
        except Exception as e:
            logger.error(f"复制文件失败 {source_path} 到 {destination_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "source_path": source_path,
                "destination_path": destination_path
            }
    
    def move_file(
        self,
        source_path: str,
        destination_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        将文件从源移动到目标。
        
        参数:
            source_path: 源文件路径
            destination_path: 目标路径
            overwrite: 是否覆盖现有文件
            
        返回:
            包含操作结果的字典
        """
        timer = Timer()
        timer.start()
        
        try:
            # 首先复制文件
            copy_result = self.copy_file(source_path, destination_path, overwrite)
            
            if not copy_result["success"]:
                return copy_result
            
            # 然后删除源文件
            delete_result = self.delete_file(source_path, confirm=True)
            
            if not delete_result["success"]:
                # 如果删除失败，尝试移除复制的文件
                try:
                    os.remove(copy_result["destination_path"])
                except Exception:
                    pass
                
                return {
                    "success": False,
                    "error": f"复制后删除源文件失败: {delete_result['error']}",
                    "source_path": source_path,
                    "destination_path": destination_path
                }
            
            move_time = timer.stop()
            
            # 更新统计信息
            self.operation_stats["move_operations"] += 1
            self.operation_stats["total_operations"] += 1
            
            result = {
                "success": True,
                "source_path": copy_result["source_path"],
                "destination_path": copy_result["destination_path"],
                "metadata": {
                    "file_size_bytes": copy_result["metadata"]["source_size_bytes"],
                    "move_time": move_time,
                    "copy_time": copy_result["metadata"]["copy_time"],
                    "delete_time": delete_result["metadata"]["delete_time"]
                }
            }
            
            logger.info(f"文件已移动: {source_path} -> {destination_path}")
            return result
            
        except Exception as e:
            logger.error(f"移动文件失败 {source_path} 到 {destination_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "source_path": source_path,
                "destination_path": destination_path
            }
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        获取文件的详细信息。
        
        参数:
            file_path: 文件路径
            
        返回:
            包含文件信息的字典
        """
        try:
            # 验证路径和检查权限
            validated_path = validate_path(file_path)
            
            require_permission(Permission.READ_FILE, validated_path, self.access_level)
            
            if not os.path.exists(validated_path):
                return {
                    "success": False,
                    "error": f"文件不存在: {validated_path}",
                    "file_path": file_path
                }
            
            stat_info = os.stat(validated_path)
            
            # 使用Shanghai时区格式化时间
            shanghai_tz = pytz.timezone('Asia/Shanghai')
            created_dt = datetime.fromtimestamp(stat_info.st_ctime, tz=shanghai_tz)
            modified_dt = datetime.fromtimestamp(stat_info.st_mtime, tz=shanghai_tz)
            accessed_dt = datetime.fromtimestamp(stat_info.st_atime, tz=shanghai_tz)
            
            file_info = {
                "success": True,
                "file_path": validated_path,
                "name": os.path.basename(validated_path),
                "extension": os.path.splitext(validated_path)[1].lower(),
                "size_bytes": stat_info.st_size,
                "size_mb": round(stat_info.st_size / 1024 / 1024, 2),
                "created_time": created_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "modified_time": modified_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "accessed_time": accessed_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "created_timestamp": stat_info.st_ctime,
                "modified_timestamp": stat_info.st_mtime,
                "accessed_timestamp": stat_info.st_atime,
                "is_file": os.path.isfile(validated_path),
                "is_directory": os.path.isdir(validated_path),
                "is_readable": os.access(validated_path, os.R_OK),
                "is_writable": os.access(validated_path, os.W_OK),
                "file_hash": calculate_file_hash(validated_path) if os.path.isfile(validated_path) else None
            }
            
            # 如可能则添加 MIME 类型
            try:
                import mimetypes
                mime_type, _ = mimetypes.guess_type(validated_path)
                file_info["mime_type"] = mime_type
            except Exception:
                file_info["mime_type"] = None
            
            return file_info
            
        except Exception as e:
            logger.error(f"获取文件信息失败 {file_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "file_path": file_path
            }
    
    def get_operation_statistics(self) -> Dict[str, Any]:
        """
        获取文件操作统计信息。
        
        返回:
            包含操作统计信息的字典
        """
        return self.operation_stats.copy()
    
    def reset_statistics(self) -> None:
        """重置操作统计信息。"""
        self.operation_stats = {
            "read_operations": 0,
            "write_operations": 0,
            "list_operations": 0,
            "delete_operations": 0,
            "copy_operations": 0,
            "move_operations": 0,
            "total_operations": 0
        }


# 全局文件操作工具实例
file_ops = FileOperationTools()


# MCP 工具定义
MCP_FILE_TOOLS = {
    "read_file": {
        "name": "read_file",
        "description": "从文件中读取内容",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要读取的文件路径"
                },
                "encoding": {
                    "type": "string",
                    "description": "使用的文本编码 (默认: utf-8)",
                    "default": "utf-8"
                },
                "max_size_mb": {
                    "type": "number",
                    "description": "最大文件大小(MB) (默认: 50.0)",
                    "default": 50.0
                }
            },
            "required": ["file_path"]
        }
    },
    
    "write_file": {
        "name": "write_file",
        "description": "将内容写入文件",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要写入的文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "要写入文件的内容"
                },
                "encoding": {
                    "type": "string",
                    "description": "使用的文本编码 (默认: utf-8)",
                    "default": "utf-8"
                },
                "create_directories": {
                    "type": "boolean",
                    "description": "是否创建父目录 (默认: true)",
                    "default": True
                },
                "backup_existing": {
                    "type": "boolean",
                    "description": "是否备份现有文件 (默认: true)",
                    "default": True
                }
            },
            "required": ["file_path", "content"]
        }
    },
    
    "list_directory": {
        "name": "list_directory",
        "description": "列出目录内容",
        "parameters": {
            "type": "object",
            "properties": {
                "directory_path": {
                    "type": "string",
                    "description": "要列出的目录路径"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出 (默认: false)",
                    "default": False
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "是否包含隐藏文件 (默认: false)",
                    "default": False
                },
                "file_pattern": {
                    "type": "string",
                    "description": "用于过滤文件的模式 (通配符模式)"
                }
            },
            "required": ["directory_path"]
        }
    },
    
    "delete_file": {
        "name": "delete_file",
        "description": "删除文件",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要删除的文件路径"
                },
                "confirm": {
                    "type": "boolean",
                    "description": "安全确认标志 (必需)",
                    "default": False
                }
            },
            "required": ["file_path", "confirm"]
        }
    },
    
    "copy_file": {
        "name": "copy_file",
        "description": "将文件从源复制到目标",
        "parameters": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "源文件路径"
                },
                "destination_path": {
                    "type": "string",
                    "description": "目标路径"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "是否覆盖现有文件 (默认: false)",
                    "default": False
                }
            },
            "required": ["source_path", "destination_path"]
        }
    },
    
    "move_file": {
        "name": "move_file",
        "description": "将文件从源移动到目标",
        "parameters": {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "源文件路径"
                },
                "destination_path": {
                    "type": "string",
                    "description": "目标路径"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "是否覆盖现有文件 (默认: false)",
                    "default": False
                }
            },
            "required": ["source_path", "destination_path"]
        }
    },
    
    "get_file_info": {
        "name": "get_file_info",
        "description": "获取文件的详细信息",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径"
                }
            },
            "required": ["file_path"]
        }
    }
}


# 工具执行函数
def execute_file_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行文件操作工具。
    
    参数:
        tool_name: 要执行的工具名称
        arguments: 工具参数
        
    返回:
        工具执行结果
    """
    try:
        if tool_name == "read_file":
            return file_ops.read_file(**arguments)
        elif tool_name == "write_file":
            return file_ops.write_file(**arguments)
        elif tool_name == "list_directory":
            return file_ops.list_directory(**arguments)
        elif tool_name == "delete_file":
            return file_ops.delete_file(**arguments)
        elif tool_name == "copy_file":
            return file_ops.copy_file(**arguments)
        elif tool_name == "move_file":
            return file_ops.move_file(**arguments)
        elif tool_name == "get_file_info":
            return file_ops.get_file_info(**arguments)
        else:
            return {
                "success": False,
                "error": f"未知文件操作工具: {tool_name}"
            }
    except Exception as e:
        logger.error(f"文件工具执行失败: {tool_name} - {str(e)}")
        return {
            "success": False,
            "error": f"工具执行失败: {str(e)}"
        }


def register_file_tools(mcp):
    """注册文件操作工具到MCP"""
    
    @mcp.tool()
    async def list_dir(params: dict):
        """列出目录中的文件和子目录"""
        # Handle parameter mapping: 'dir' or 'directory' -> 'directory_path'
        if 'dir' in params:
            params['directory_path'] = params.pop('dir')
        elif 'directory' in params:
            params['directory_path'] = params.pop('directory')
        
        # Intelligent directory handling for whitelist directories
        if 'directory_path' not in params or not params['directory_path']:
            import os
            allowed_dirs = config.security.ALLOWED_DIRS
            
            # Filter to only existing directories
            existing_dirs = [d for d in allowed_dirs if os.path.exists(d) and os.path.isdir(d)]
            
            if len(existing_dirs) == 1:
                # Only one whitelist directory exists, automatically use it
                params['directory_path'] = existing_dirs[0]
                logger.info(f"自动选择唯一的白名单目录: {existing_dirs[0]}")
            elif len(existing_dirs) > 1:
                # Multiple whitelist directories exist, present them for user selection
                return {
                    "success": False,
                    "error": "需要指定目录路径，有多个白名单目录可选",
                    "available_directories": existing_dirs,
                    "message": "请从以下白名单目录中选择一个:",
                    "usage": "在参数中添加 'directory_path' 或 'dir' 来指定要列出的目录"
                }
            else:
                # No whitelist directories exist
                return {
                    "success": False,
                    "error": "没有可用的白名单目录",
                    "allowed_directories": allowed_dirs,
                    "message": "配置的白名单目录都不存在或无法访问",
                    "suggestions": [
                        "检查配置的白名单目录是否存在",
                        "确保目录具有适当的访问权限"
                    ]
                }
        
        return file_ops.list_directory(**params)
    
    @mcp.tool()
    async def get_mtime(params: dict):
        """获取文件的修改时间"""
        return file_ops.get_file_info(**params)

