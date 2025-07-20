from langchain_community.document_loaders import DirectoryLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def build_vector_store(doc_dir, index_path):
    loader = DirectoryLoader(doc_dir, glob="**/*.pdf")  # 如需支持txt/docx可调整
    docs = loader.load()
    embeddings = HuggingFaceEmbeddings(model_name="paraphrase-multilingual-MiniLM-L12-v2")
    vector_db = FAISS.from_documents(docs, embeddings)
    vector_db.save_local(index_path)
    print(f"FAISS index saved to {index_path}")

if __name__ == "__main__":
    build_vector_store("docs", "faiss_index")