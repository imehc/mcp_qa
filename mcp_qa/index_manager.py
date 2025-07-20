from langchain_core.documents import Document
from .embeddings import embeddings
from langchain_community.vectorstores import FAISS

# 全局变量用于存储上传文件内容和自定义索引
gu_uploaded_file_content = ""
gu_uploaded_vector_db = None
gu_uploaded_retriever = None

def set_uploaded_file_content(content):
    global gu_uploaded_file_content
    gu_uploaded_file_content = content

def get_uploaded_file_content():
    return gu_uploaded_file_content

def get_uploaded_retriever():
    return gu_uploaded_retriever

def create_uploaded_index():
    global gu_uploaded_file_content, gu_uploaded_vector_db, gu_uploaded_retriever
    if not gu_uploaded_file_content.strip():
        return "未检测到有效文件内容，无法创建索引。"
    # 按段落分割文本，生成Document对象
    docs = [Document(page_content=chunk) for chunk in gu_uploaded_file_content.split("\n\n") if chunk.strip()]
    if not docs:
        return "文件内容为空，无法创建索引。"
    gu_uploaded_vector_db = FAISS.from_documents(docs, embeddings)
    gu_uploaded_retriever = gu_uploaded_vector_db.as_retriever(search_kwargs={"k": 3})
    return "上传内容已创建向量索引，后续问答将优先基于该内容。" 