"""
Phase 0：PDF → Markdown → 分块 → Embedding → Qdrant
使用 LangChain + Unstructured 实现
"""

import hashlib
import re
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from langchain_community.document_loaders import UnstructuredFileLoader
import uuid


# ─── PDF 解析 ──────────────────────────────────────────
def parse_pdf(pdf_path: str) -> list[Document]:
    """
    使用 Unstructured 解析 PDF，保留公式/表格/段落结构
    Returns: List of LangChain Documents
    """
    loader = UnstructuredFileLoader(
        pdf_path,
        mode="elements",          # 按页面/段落返回
        strategy="fast",          # fast=低成本，hi_res=高精度(贵)
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
        chunk_overlap=64,          # 64 tokens 重叠，防止切断语义
        separators=["\n\n", "\n", "。", "！", "？", " "],
        length_function=lambda x: len(x) // 4,  # 粗略估算 token
    )

    chunks = splitter.split_documents(documents)
    return chunks


# ─── 向量化 + 存入 Qdrant ──────────────────────────────
async def process_pdf(
    pdf_path: str,
    paper_id: str,
    collection_name: str,
    openai_api_key: str,
    qdrant_url: str = "http://localhost:6333",
) -> dict[str, Any]:
    """
    完整 pipeline：PDF → 解析 → 分块 → 向量 → Qdrant
    Returns: {chunks_count}
    """
    # 1. 解析 PDF
    raw_docs = parse_pdf(pdf_path)
    print(f"[{paper_id}] 解析完成，共 {len(raw_docs)} 个元素")

    # 2. 分块
    chunks = chunk_documents(raw_docs)
    print(f"[{paper_id}] 分块完成，共 {len(chunks)} 个 chunks")

    # 3. 初始化 Embedding
    embeddings = OpenAIEmbeddings(
        api_key=openai_api_key,
        model="text-embedding-3-small",  # 1536 维
    )

    # 4. 连接 Qdrant
    qdrant = QdrantClient(url=qdrant_url)

    # 确保 collection 存在
    try:
        qdrant.get_collection(collection_name)
    except Exception:
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )
        print(f"[{paper_id}] 创建 Qdrant collection: {collection_name}")

    # 5. 向量化 + 写入（批量）
    from langchain_community.vectorstores import Qdrant as LangChainQdrant

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

    LangChainQdrant.from_texts(
        texts=texts,
        embedding=embeddings,
        metadatas=metadatas,
        collection_name=collection_name,
        url=qdrant_url,
        force_recreate=False,
    )

    print(f"[{paper_id}] 向量写入完成，{len(chunks)} 个 chunks")

    return {"chunks_count": len(chunks)}


# ─── 语义检索 ──────────────────────────────────────────
async def search_chunks(
    query: str,
    collection_name: str,
    top_k: int = 5,
    openai_api_key: str = "",
    qdrant_url: str = "http://localhost:6333",
) -> list[dict]:
    """
    将问题向量化 → Qdrant 检索 → 返回相关 chunks
    """
    from langchain_community.vectorstores import Qdrant as LangChainQdrant
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(api_key=openai_api_key, model="text-embedding-3-small")

    vectorstore = LangChainQdrant(
        collection_name=collection_name,
        embedding_function=embeddings.embed_query,
        url=qdrant_url,
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
