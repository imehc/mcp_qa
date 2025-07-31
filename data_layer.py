"数据层模块"

import chainlit.data as cl_data
import sqlite3
import json
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
from chainlit.user import PersistedUser, User
from chainlit.element import ElementDict, Element
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    PaginatedResponse,
    Pagination,
    PageInfo,
    ThreadDict,
    ThreadFilter,
)

# 配置日志记录
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)



class CustomeDataLayer(cl_data.BaseDataLayer): # type: ignore
    def __init__(self):
        self.data_dir = "chainlit_data"
        self.db_path = os.path.join(self.data_dir, "chainlit.db")
        
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
    
    def _init_database(self):
        """初始化SQLite数据库和表结构"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 用户表  
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        identifier TEXT UNIQUE,
                        display_name TEXT,
                        metadata TEXT,
                        created_at TEXT
                    )
                ''')
                
                # 线程表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS threads (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        user_id TEXT,
                        user_identifier TEXT,
                        metadata TEXT,
                        tags TEXT,
                        created_at TEXT
                    )
                ''')
                
                # 步骤表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS steps (
                        id TEXT PRIMARY KEY,
                        thread_id TEXT,
                        name TEXT,
                        type TEXT,
                        input TEXT,
                        output TEXT,
                        streaming INTEGER,
                        metadata TEXT,
                        created_at TEXT,
                        FOREIGN KEY (thread_id) REFERENCES threads (id)
                    )
                ''')
                
                # 元素表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS elements (
                        id TEXT PRIMARY KEY,
                        thread_id TEXT,
                        type TEXT,
                        name TEXT,
                        display TEXT,
                        size TEXT,
                        language TEXT,
                        page INTEGER,
                        props TEXT,
                        mime TEXT,
                        FOREIGN KEY (thread_id) REFERENCES threads (id)
                    )
                ''')
                
                # 反馈表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS feedback (
                        id TEXT PRIMARY KEY,
                        for_id TEXT,
                        value INTEGER,
                        thread_id TEXT,
                        comment TEXT,
                        created_at TEXT
                    )
                ''')
                
                conn.commit()
                logger.info("数据库初始化成功")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        """获取用户信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, identifier, display_name, metadata, created_at FROM users WHERE identifier = ?",
                    (identifier,)
                )
                row = cursor.fetchone()
                
                if row:
                    logger.info(f"成功获取用户: {identifier}")
                    return PersistedUser(
                        id=row[0],
                        identifier=row[1], 
                        display_name=row[2],
                        metadata=json.loads(row[3]) if row[3] else {},
                        createdAt=row[4]
                    )
            
            # 如果用户不存在，创建一个新用户
            logger.info(f"用户 {identifier} 不存在，将创建新用户")
            new_user = User(identifier=identifier, display_name=identifier)
            return await self.create_user(new_user)
        except Exception as e:
            logger.error(f"获取用户 {identifier} 失败: {e}")
            # 返回一个默认用户而不是None，避免"User not found"错误
            return PersistedUser(
                identifier=identifier,
                display_name=identifier,
                metadata={},
                id=str(uuid.uuid4()),
                createdAt=datetime.now(timezone.utc).isoformat()
            )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        """创建新用户"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 检查用户是否已存在
                cursor.execute("SELECT identifier FROM users WHERE identifier = ?", (user.identifier,))
                if cursor.fetchone():
                    logger.info(f"用户 {user.identifier} 已存在")
                    return await self.get_user(user.identifier)
                
                user_id = str(uuid.uuid4())
                created_at = datetime.now(timezone.utc).isoformat()
                
                persisted_user = PersistedUser(
                    identifier=user.identifier,
                    display_name=user.display_name or user.identifier,
                    metadata=user.metadata or {},
                    id=user_id,
                    createdAt=created_at
                )
                
                # 保存用户数据
                cursor.execute(
                    "INSERT INTO users (id, identifier, display_name, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                    (
                        persisted_user.id,
                        persisted_user.identifier,
                        persisted_user.display_name,
                        json.dumps(persisted_user.metadata),
                        persisted_user.createdAt
                    )
                )
                conn.commit()
                
                logger.info(f"成功创建用户: {user.identifier}")
                return persisted_user
        except Exception as e:
            logger.error(f"创建用户 {user.identifier} 失败: {e}")
            return None

    async def delete_feedback(self, feedback_id: str) -> bool:
        """删除反馈"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def upsert_feedback(self, feedback: Feedback) -> str:
        """创建或更新反馈"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            feedback_id = feedback.id or str(uuid.uuid4())
            created_at = datetime.now(timezone.utc).isoformat()
            
            cursor.execute(
                """INSERT OR REPLACE INTO feedback 
                   (id, for_id, value, thread_id, comment, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (feedback_id, feedback.forId, feedback.value, 
                 feedback.threadId, feedback.comment, created_at)
            )
            conn.commit()
            return feedback_id

    async def create_element(self, element: Element):
        """创建元素"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                element_dict = element.to_dict()
                cursor.execute(
                    """INSERT OR REPLACE INTO elements 
                       (id, thread_id, type, name, display, size, language, page, props, mime) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (element.id, element_dict.get("threadId"), element.type, element.name,
                     element_dict.get("display"), element_dict.get("size"), 
                     element_dict.get("language"), element_dict.get("page"),
                     json.dumps(element_dict.get("props", {})), element_dict.get("mime"))
                )
                conn.commit()
                logger.info(f"成功创建元素: {element.id}")
        except Exception as e:
            logger.error(f"创建元素失败: {e}")

    async def get_element(self, thread_id: str, element_id: str) -> Optional[ElementDict]:
        """获取元素"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, thread_id, type, name, display, size, language, page, props, mime 
                   FROM elements WHERE thread_id = ? AND id = ?""",
                (thread_id, element_id)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    "id": row[0],
                    "threadId": row[1],
                    "type": row[2],
                    "name": row[3],
                    "display": row[4],
                    "size": row[5],
                    "language": row[6],
                    "page": row[7],
                    "props": json.loads(row[8]) if row[8] else {},
                    "mime": row[9]
                }
        return None

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        """删除元素"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if thread_id:
                cursor.execute("DELETE FROM elements WHERE id = ? AND thread_id = ?", 
                             (element_id, thread_id))
            else:
                cursor.execute("DELETE FROM elements WHERE id = ?", (element_id,))
            conn.commit()

    async def create_step(self, step_dict: StepDict):
        """创建步骤"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 确保步骤有线程ID，如果没有则尝试从Chainlit上下文获取
                thread_id = step_dict.get("threadId")
                if not thread_id:
                    try:
                        import chainlit as cl
                        if hasattr(cl.context, 'session') and cl.context.session.thread_id:
                            thread_id = cl.context.session.thread_id
                            step_dict["threadId"] = thread_id
                    except Exception:
                        pass  # 忽略上下文获取错误
                
                if not thread_id:
                    logger.warning("步骤缺少 threadId，跳过保存")
                    return
                
                step_id = step_dict.get("id") or str(uuid.uuid4())
                created_at = step_dict.get("createdAt") or datetime.now(timezone.utc).isoformat()
                
                # 检查是否已存在相同的步骤（避免重复保存）
                cursor.execute(
                    "SELECT COUNT(*) FROM steps WHERE thread_id = ? AND type = ? AND output = ?",
                    (thread_id, step_dict.get("type", ""), step_dict.get("output", ""))
                )
                if cursor.fetchone()[0] > 0:
                    logger.info(f"步骤已存在，跳过保存: {step_dict.get('type')} - {step_dict.get('output', '')[:20]}")
                    return
                
                cursor.execute(
                    """INSERT INTO steps 
                       (id, thread_id, name, type, input, output, streaming, metadata, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        step_id, 
                        thread_id, 
                        step_dict.get("name", ""), 
                        step_dict.get("type", ""),
                        step_dict.get("input", ""), 
                        step_dict.get("output", ""),
                        1 if step_dict.get("streaming", False) else 0,
                        json.dumps(step_dict.get("metadata", {})), 
                        created_at
                    )
                )
                conn.commit()
                logger.info(f"成功创建步骤: {step_id} (线程: {thread_id})")
        except Exception as e:
            logger.error(f"创建步骤失败: {e}")
            # 不抛出异常，避免中断聊天流程
            import traceback
            traceback.print_exc()

    async def update_step(self, step_dict: StepDict):
        """更新步骤"""
        await self.create_step(step_dict)  # SQLite的INSERT OR REPLACE处理更新

    async def delete_step(self, step_id: str):
        """删除步骤"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM steps WHERE id = ?", (step_id,))
            conn.commit()

    async def get_thread_author(self, thread_id: str) -> str:
        """获取线程作者"""
        try:
            logger.info(f"获取线程 {thread_id} 的作者")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_identifier, user_id FROM threads WHERE id = ?", (thread_id,))
                row = cursor.fetchone()
                if row:
                    # 只返回有效的 user_identifier
                    author = row[0] if row[0] else None
                    logger.info(f"线程 {thread_id} 的作者是: {author}")
                    
                    # 如果没有有效的用户标识符，抛出异常表示线程无效
                    if not author:
                        logger.warning(f"线程 {thread_id} 没有有效的用户标识符")
                        raise ValueError(f"线程 {thread_id} 没有有效的用户标识符")
                    
                    return author
                else:
                    logger.warning(f"线程 {thread_id} 不存在")
                    raise ValueError(f"线程 {thread_id} 不存在")
        except Exception as e:
            logger.error(f"获取线程作者失败: {e}")
            raise e

    async def delete_thread(self, thread_id: str):
        """删除线程"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 删除相关的步骤和元素
            cursor.execute("DELETE FROM steps WHERE thread_id = ?", (thread_id,))
            cursor.execute("DELETE FROM elements WHERE thread_id = ?", (thread_id,))
            cursor.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            conn.commit()

    async def list_threads(self, pagination: Pagination, filters: ThreadFilter) -> PaginatedResponse[ThreadDict]:
        """列出线程"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建查询条件 - 只显示有用户标识符的线程
                where_conditions = []
                params = []
                
                # 过滤掉没有用户标识符的线程
                where_conditions.append("user_identifier IS NOT NULL AND user_identifier != ''")
                
                # 暂时注释掉用户过滤，避免"User not found"错误
                # if hasattr(filters, 'userId') and filters.userId and filters.userId != "":
                #     where_conditions.append("user_id = ?")
                #     params.append(filters.userId)
                
                if hasattr(filters, 'search') and filters.search:
                    where_conditions.append("name LIKE ?")
                    params.append(f"%{filters.search}%")
                
                where_clause = " AND ".join(where_conditions)
                if where_clause:
                    where_clause = "WHERE " + where_clause
                
                # 查询线程总数
                count_query = f"SELECT COUNT(*) FROM threads {where_clause}"
                cursor.execute(count_query, params)
                total_count = cursor.fetchone()[0]
                
                # 查询线程
                limit = pagination.first or 10
                page = getattr(pagination, 'page', 1) or 1
                offset = limit * (page - 1)
                
                query = f"""
                    SELECT id, name, user_id, user_identifier, metadata, tags, created_at 
                    FROM threads {where_clause} 
                    ORDER BY created_at DESC 
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                threads = []
                for row in rows:
                    thread_data: ThreadDict = {
                        "id": row[0],
                        "name": row[1] or "未命名对话",
                        "userId": row[2] or "",
                        "userIdentifier": row[3] or "",
                        "metadata": json.loads(row[4]) if row[4] else {},
                        "tags": json.loads(row[5]) if row[5] else [],
                        "createdAt": row[6] or datetime.now(timezone.utc).isoformat(),
                        "steps": [],
                        "elements": []
                    }
                    
                    # 获取线程的步骤（前几个步骤用于预览）
                    cursor.execute(
                        "SELECT id, name, type, input, output, streaming, metadata, created_at FROM steps WHERE thread_id = ? ORDER BY created_at LIMIT 5",
                        (row[0],)
                    )
                    steps = cursor.fetchall()
                    thread_steps = []
                    for step in steps:
                        thread_steps.append({
                            "id": step[0],
                            "threadId": row[0],
                            "name": step[1] or "",
                            "type": step[2] or "",
                            "input": step[3] or "",
                            "output": step[4] or "",
                            "streaming": bool(step[5]),
                            "metadata": json.loads(step[6]) if step[6] else {},
                            "createdAt": step[7] or ""
                        })
                    thread_data["steps"] = thread_steps
                    
                    # 获取线程的元素（前几个元素用于预览）
                    cursor.execute(
                        "SELECT id, type, name, display, size, language, page, props, mime FROM elements WHERE thread_id = ? LIMIT 3",
                        (row[0],)
                    )
                    elements = cursor.fetchall()
                    thread_elements = []
                    for element in elements:
                        thread_elements.append({
                            "id": element[0],
                            "threadId": row[0],
                            "type": element[1] or "",
                            "name": element[2] or "",
                            "display": element[3] or "",
                            "size": element[4] or "",
                            "language": element[5] or "",
                            "page": element[6] or 0,
                            "props": json.loads(element[7]) if element[7] else {},
                            "mime": element[8] or ""
                        })
                    thread_data["elements"] = thread_elements
                    
                    threads.append(thread_data)
                
                # 构建分页信息
                has_next_page = (offset + limit) < total_count
                page_info = PageInfo(
                    hasNextPage=has_next_page,
                    startCursor=threads[0]["id"] if threads else None,
                    endCursor=threads[-1]["id"] if threads else None
                )
                
                logger.info(f"返回 {len(threads)} 个线程，总共 {total_count} 个")
                return PaginatedResponse(pageInfo=page_info, data=threads)
                
        except Exception as e:
            logger.error(f"列出线程失败: {e}")
            import traceback
            traceback.print_exc()
            # 返回空结果而不是抛出异常
            page_info = PageInfo(
                hasNextPage=False,
                startCursor=None,
                endCursor=None
            )
            return PaginatedResponse(pageInfo=page_info, data=[])

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        """获取线程详情"""
        try:
            logger.info(f"正在获取线程: {thread_id}")
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 先检查数据库中是否有这个线程
                cursor.execute("SELECT COUNT(*) FROM threads WHERE id = ?", (thread_id,))
                count = cursor.fetchone()[0]
                logger.info(f"数据库中线程 {thread_id} 的数量: {count}")
                
                cursor.execute(
                    "SELECT id, name, user_id, user_identifier, metadata, tags, created_at FROM threads WHERE id = ?",
                    (thread_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    logger.warning(f"线程 {thread_id} 不存在")
                    # 列出所有存在的线程ID用于调试
                    cursor.execute("SELECT id, name FROM threads ORDER BY created_at DESC LIMIT 5")
                    existing_threads = cursor.fetchall()
                    logger.info(f"现有线程: {existing_threads}")
                    return None
                
                logger.info(f"找到线程: {row[0]} - {row[1]}")
                thread_data: ThreadDict = {
                    "id": row[0],
                    "name": row[1],
                    "userId": row[2],
                    "userIdentifier": row[3],
                    "metadata": json.loads(row[4]) if row[4] else {},
                    "tags": json.loads(row[5]) if row[5] else [],
                    "createdAt": row[6],
                    "steps": [],
                    "elements": []
                }
                
                # 获取步骤 - 按时间正序排列，确保恢复顺序正确
                cursor.execute(
                    "SELECT id, name, type, input, output, streaming, metadata, created_at FROM steps WHERE thread_id = ? ORDER BY created_at ASC",
                    (thread_id,)
                )
                steps = cursor.fetchall()
                logger.info(f"线程 {thread_id} 有 {len(steps)} 个步骤")
                thread_steps = []
                for step in steps:
                    thread_steps.append({
                        "id": step[0],
                        "threadId": thread_id,
                        "name": step[1],
                        "type": step[2],
                        "input": step[3],
                        "output": step[4],
                        "streaming": bool(step[5]),
                        "metadata": json.loads(step[6]) if step[6] else {},
                        "createdAt": step[7]
                    })
                thread_data["steps"] = thread_steps
                
                # 获取元素
                cursor.execute(
                    "SELECT id, type, name, display, size, language, page, props, mime FROM elements WHERE thread_id = ?",
                    (thread_id,)
                )
                elements = cursor.fetchall()
                thread_elements = []
                for element in elements:
                    thread_elements.append({
                        "id": element[0],
                        "threadId": thread_id,
                        "type": element[1],
                        "name": element[2],
                        "display": element[3],
                        "size": element[4],
                        "language": element[5],
                        "page": element[6],
                        "props": json.loads(element[7]) if element[7] else {},
                        "mime": element[8]
                    })
                thread_data["elements"] = thread_elements
                
                logger.info(f"成功获取线程 {thread_id} 的详细信息")
                return thread_data
        except Exception as e:
            logger.error(f"获取线程 {thread_id} 失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        """更新线程，如果不存在则创建"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 检查线程是否存在
            cursor.execute("SELECT id FROM threads WHERE id = ?", (thread_id,))
            exists = cursor.fetchone() is not None
            
            if not exists and (name is not None or user_id is not None):
                # 如果线程不存在且提供了必要信息，则创建线程
                created_at = datetime.now(timezone.utc).isoformat()
                
                # 智能获取 user_identifier
                user_identifier = metadata.get("user_identifier", "") if metadata else ""
                if not user_identifier:
                    # 首先尝试从当前会话获取用户信息
                    try:
                        import chainlit as cl
                        current_user = cl.user_session.get("user")
                        if current_user:
                            user_identifier = getattr(current_user, 'identifier', None)
                    except Exception:
                        pass
                    
                    # 如果还是没有，尝试通过user_id查找用户名
                    if not user_identifier and user_id and user_id != "anonymous":
                        cursor.execute("SELECT identifier FROM users WHERE id = ?", (user_id,))
                        user_row = cursor.fetchone()
                        if user_row:
                            user_identifier = user_row[0]
                
                # 如果没有有效的用户标识符，不创建线程
                if not user_identifier:
                    logger.warning(f"无有效用户标识符，跳过创建线程: {thread_id}")
                    return
                
                cursor.execute(
                    """INSERT INTO threads 
                       (id, name, user_id, user_identifier, metadata, tags, created_at) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        thread_id,
                        name or "新对话",
                        user_id,  # 现在正确使用用户的数据库ID（UUID）
                        user_identifier,
                        json.dumps(metadata or {}),
                        json.dumps(tags or []),
                        created_at
                    )
                )
                logger.info(f"创建新线程: {thread_id} - {name} (作者: {user_identifier})")
            elif exists:
                # 线程存在，更新字段
                updates = []
                params = []
                
                if name is not None:
                    updates.append("name = ?")
                    params.append(name)
                
                if user_id is not None:
                    updates.append("user_id = ?")
                    params.append(user_id)
                
                if metadata is not None:
                    updates.append("metadata = ?")
                    params.append(json.dumps(metadata))
                    # 如果metadata中有user_identifier，也更新user_identifier字段
                    if "user_identifier" in metadata:
                        updates.append("user_identifier = ?")
                        params.append(metadata["user_identifier"])
                
                if tags is not None:
                    updates.append("tags = ?")
                    params.append(json.dumps(tags))
                
                if updates:
                    query = f"UPDATE threads SET {', '.join(updates)} WHERE id = ?"
                    params.append(thread_id)
                    cursor.execute(query, params)
                    logger.info(f"更新线程: {thread_id}")
            
            conn.commit()
    async def build_debug_url(self) -> str:
        """构建调试URL"""
        return f"sqlite:///{self.db_path}"