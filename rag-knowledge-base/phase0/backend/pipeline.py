"""
Phase 0：PDF → Markdown → 分块 → Embedding → ChromaDB
使用 LangChain + Unstructured 实现

⚠️ Phase 0 使用 ChromaDB（内嵌式，无需 Docker）
⚠️ 生产环境（Phase 1+）切换为 Qdrant（Docker/集群部署）
"""

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import chromadb
from chromadb.config import Settings as ChromaSettings


# ─── PDF 解析 ──────────────────────────────────────────
def parse_pdf(pdf_path: str) -> list[Document]:
    """
    使用 Unstructured 解析 PDF，保留公式/表格/段落结构
    Returns: List of LangChain Documents
    """
    from langchain_community.document_loaders import UnstructuredFileLoader

    loader = UnstructuredFileLoader(
        pdf_path,
        mode="elements",  # 按页面/段落返回
        strategy="fast",   # fast=低成本，hi_res=高精度(贵)
    )
    docs = loader.load()
    return docs


# ─── 分块 ─────────────────────────────────────────────
def chunk_documents(documents: list[Document], chunk_size: int = 512) -> list[Document]:
    """
    将 LangChain Documents 按 token 数分块
    chunk_size=512 tokens（约 2000 字符）
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=64,  # 64 tokens 重叠，防止切断语义
        separators=["\n\n", "\n", "。", "！", "？", " "],
        # 粗略估算 token（中文约 2 字符/token）
        length_function=lambda x: len(x) // 2,
    )

    chunks = splitter.split_documents(documents)
    return chunks


# ─── 向量化 + 存入 ChromaDB ───────────────────────────
async def process_pdf(
    pdf_path: str,
    paper_id: str,
    collection_name: str,
    openai_api_key: str,
    persist_directory: str = "/tmp/chromadb",
) -> dict[str, Any]:
    """
    完整 pipeline：PDF → 解析 → 分块 → 向量 → ChromaDB
    Phase 0 用 ChromaDB（内嵌式，pip 安装，无需 Docker）

    生产环境（Phase 1+）切换 Qdrant：
    - 改用 langchain_qdrant.Qdrant
    - 启动 Qdrant Docker 容器
    - collection_name 改为 user_{user_id}

    Returns: {chunks_count}
    """
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY 未设置")

    # 1. 解析 PDF
    raw_docs = parse_pdf(pdf_path)
    print(f"[{paper_id}] 解析完成，共 {len(raw_docs)} 个元素")

    if not raw_docs:
        raise ValueError(f"PDF 解析失败，文档为空: {pdf_path}")

    # 2. 分块
    chunks = chunk_documents(raw_docs)
    print(f"[{paper_id}] 分块完成，共 {len(chunks)} 个 chunks")

    if not chunks:
        raise ValueError(f"PDF 分块失败，chunks 为空: {pdf_path}")

    # 3. 初始化 Embedding
    embeddings = OpenAIEmbeddings(
        api_key=openai_api_key,
        model="text-embedding-3-small",  # 1536 维
    )

    # 4. 初始化 ChromaDB（内嵌式，持久化到磁盘）
    os.makedirs(persist_directory, exist_ok=True)

    # ChromaDB 的 collection 名称只允许字母数字下划线
    safe_collection_name = re.sub(r"[^a-zA-Z0-9_]", "_", collection_name)

    vectorstore = Chroma(
        collection_name=safe_collection_name,
        embedding_function=embeddings,  # LangChain Chroma 会自动用这个做嵌入
        persist_directory=persist_directory,
    )

    # 5. 写入向量
    texts = [c.page_content for c in chunks]
    metadatas = [
        {
            "paper_id": paper_id,
            "chunk_index": i,
            "page_number": c.metadata.get("page_number", 0),
            "text": c.page_content[:200],  # 前 200 字符用于展示
        }
        for i, c in enumerate(chunks)
    ]

    vectorstore.add_texts(texts=texts, metadatas=metadatas)

    print(f"[{paper_id}] 向量写入完成，{len(chunks)} 个 chunks → collection '{safe_collection_name}'")

    return {"chunks_count": len(chunks)}


# ─── 语义检索 ──────────────────────────────────────────
async def search_chunks(
    query: str,
    collection_name: str,
    top_k: int = 5,
    openai_api_key: str = "",
    persist_directory: str = "/tmp/chromadb",
) -> list[dict]:
    """
    将问题向量化 → ChromaDB 检索 → 返回相关 chunks
    """
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY 未设置")

    safe_collection_name = re.sub(r"[^a-zA-Z0-9_]", "_", collection_name)

    embeddings = OpenAIEmbeddings(
        api_key=openai_api_key,
        model="text-embedding-3-small",
    )

    vectorstore = Chroma(
        collection_name=safe_collection_name,
        embedding_function=embeddings,
        persist_directory=persist_directory,
    )

    results = vectorstore.similarity_search(query, k=top_k)

    chunks = []
    for r in results:
        chunks.append({
            "content": r.page_content,
            "paper_id": r.metadata.get("paper_id", ""),
            "chunk_index": r.metadata.get("chunk_index", 0),
            "page_number": r.metadata.get("page_number", 0),
            "text": r.metadata.get("text", ""),
        })

    return chunks
