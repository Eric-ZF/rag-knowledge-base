"""
Phase 0：PDF → 分块 → 本地 Embedding → ChromaDB

Embedding: shibing624/text2vec-base-chinese（本地运行，零 API 成本）
  - 768 维，中文语义效果好
  - 首次运行自动下载模型（约 400MB）
  - 之后从本地缓存加载
"""

import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from langchain_core.documents import Document
from langchain_chroma import Chroma

from config import EMBEDDING_MODEL, EMBEDDING_DIM, CHROMADB_DIR


# ─── 本地 Embedding 模型（全局单例）────────────────────
_embedding_model = None


def get_embedding_model():
    """
    获取本地 Embedding 模型（单例）
    shibing624/text2vec-base-chinese: 中文语义模型，768 维
    首次下载后从本地缓存加载
    """
    global _embedding_model
    if _embedding_model is None:
        print(f"📥 首次加载 Embedding 模型: {EMBEDDING_MODEL}（约 400MB，首次下载后缓存）")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"✅ 模型加载完成，向量维度: {EMBEDDING_DIM}")
    return _embedding_model


# ─── LangChain Embedding Wrapper ──────────────────────
class LocalEmbeddingWrapper:
    """
    将 sentence-transformers 封装为 LangChain 兼容的 Embedding 接口
    用于 Chroma 的 embedding_function 参数
    """

    def __init__(self):
        self.model = get_embedding_model()
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed_query(self, text: str) -> list[float]:
        """单条 query 嵌入（用于检索）"""
        vec = self.model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量文档嵌入（用于索引）"""
        vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()

    def __call__(self, text: str) -> list[float]:
        """LangChain Chroma 直接调用时走 embed_query"""
        return self.embed_query(text)


# ─── LangChain Chroma Embedding Function ─────────────
def get_chroma_embedding_fn():
    """返回 LangChain Chroma 所需的 embedding_function"""
    return LocalEmbeddingWrapper()


# ─── PDF 解析 ──────────────────────────────────────────
def parse_pdf(pdf_path: str) -> list[Document]:
    """
    使用 Unstructured 解析 PDF，保留公式/表格/段落结构
    """
    from langchain_community.document_loaders import UnstructuredFileLoader

    loader = UnstructuredFileLoader(
        pdf_path,
        mode="elements",
        strategy="fast",  # fast=低成本，hi_res=高精度(贵)
    )
    docs = loader.load()
    return docs


# ─── 分块 ─────────────────────────────────────────────
def chunk_documents(documents: list[Document], chunk_size: int = 2000) -> list[Document]:
    """
    将 LangChain Documents 分块
    chunk_size=2000 字（中文，约 1000 tokens），学术论文需要更大上下文
    """
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=200,  # 200 字重叠，学术论述连贯性更强
        separators=["\n\n\n", "\n\n", "\n", "。", "！", "？"],
        length_function=lambda x: len(x),  # 中文字符数
    )

    chunks = splitter.split_documents(documents)
    return chunks


# ─── 向量化 + 存入 ChromaDB ───────────────────────────
async def process_pdf(
    pdf_path: str,
    paper_id: str,
    collection_name: str,
    openai_api_key: str = "",  # 保留参数签名兼容
    persist_directory: str = CHROMADB_DIR,
) -> dict[str, Any]:
    """
    完整 pipeline：PDF → 解析 → 分块 → 本地向量 → ChromaDB

    Returns: {chunks_count}
    """
    # 1. 解析 PDF
    print(f"[{paper_id}] 开始解析 PDF...")
    raw_docs = parse_pdf(pdf_path)
    print(f"[{paper_id}] 解析完成，共 {len(raw_docs)} 个元素")

    if not raw_docs:
        raise ValueError(f"PDF 解析失败，文档为空: {pdf_path}")

    # 2. 分块
    chunks = chunk_documents(raw_docs)
    print(f"[{paper_id}] 分块完成，共 {len(chunks)} 个 chunks")

    if not chunks:
        raise ValueError(f"PDF 分块失败，chunks 为空: {pdf_path}")

    # 3. 初始化 MiniMax Embedding
    embedding_fn = get_chroma_embedding_fn()

    # 4. 初始化 ChromaDB
    os.makedirs(persist_directory, exist_ok=True)
    safe_collection_name = re.sub(r"[^a-zA-Z0-9_]", "_", collection_name)

    vectorstore = Chroma(
        collection_name=safe_collection_name,
        embedding_function=embedding_fn,
        persist_directory=persist_directory,
    )

    # 5. 写入向量
    texts = [c.page_content for c in chunks]
    metadatas = [
        {
            "paper_id": paper_id,
            "chunk_index": i,
            "page_number": c.metadata.get("page_number", 0),
            "text": c.page_content[:200],
        }
        for i, c in enumerate(chunks)
    ]

    vectorstore.add_texts(texts=texts, metadatas=metadatas)

    print(f"[{paper_id}] ✅ 向量写入完成，{len(chunks)} 个 chunks → collection '{safe_collection_name}'")
    print(f"[{paper_id}]    Embedding 模型: {EMBEDDING_MODEL}（本地，{EMBEDDING_DIM} 维）")

    return {"chunks_count": len(chunks)}


# ─── Hybrid Search（向量 + 关键词）────────────────────
def hybrid_search(vectorstore, query: str, query_embedding_fn, k: int = 10) -> list[dict]:
    """
    混合检索：向量相似度 + BM25 关键词匹配，融合排序

    学术问答中，专业术语（CBAM、碳边境调节机制）精确匹配比语义相似更重要，
    因此关键词权重设为 0.4，向量权重 0.6
    """
    try:
        import rank_bm25
    except ImportError:
        # BM25 不可用时降级为纯向量
        results = vectorstore.similarity_search(query, k=k)
        return [{"doc": r, "vector_score": 1.0, "bm25_score": 0.0} for r in results]

    # 1. 向量检索
    query_vec = query_embedding_fn.embed_query(query)
    vector_results = vectorstore.similarity_search_by_vector(query_vec, k=k)

    # 2. BM25 关键词检索（从 vector 结果的文本中构建）
    all_texts = [r.page_content for r in vector_results]
    if not all_texts:
        return []

    # 分词（简单按字符划分，中文效果尚可）
    tokenized_corpus = [list(text) for text in all_texts]
    bm25 = rank_bm25.BM25Okapi(tokenized_corpus)
    query_tokens = list(query)
    bm25_scores = bm25.get_scores(query_tokens)

    # 3. 融合排序
    max_vector = max(r.metadata.get("_score", 1.0) for r in vector_results) or 1.0
    max_bm25 = max(bm25_scores) or 1.0

    fused = []
    for i, r in enumerate(vector_results):
        vector_score = r.metadata.get("_score", max_vector * 0.5) / max_vector
        bm25_norm = bm25_scores[i] / max_bm25 if max_bm25 > 0 else 0
        # 融合：向量 60% + BM25 40%（学术术语精确匹配占重要地位）
        combined_score = 0.6 * vector_score + 0.4 * bm25_norm
        fused.append({
            "doc": r,
            "combined_score": combined_score,
            "vector_score": vector_score,
            "bm25_score": bm25_norm,
        })

    fused.sort(key=lambda x: x["combined_score"], reverse=True)
    return fused


# ─── 语义检索 ──────────────────────────────────────────
async def search_chunks(
    query: str,
    collection_name: str,
    top_k: int = 8,  # 增大到 8，候选多了答案更完整
    openai_api_key: str = "",
    persist_directory: str = CHROMADB_DIR,
) -> list[dict]:
    """
    将问题向量化 → ChromaDB 检索 → 返回相关 chunks
    使用本地 sentence-transformers embedding + Hybrid Search
    top_k 增大到 8，向量检索候选更丰富
    """
    safe_collection_name = re.sub(r"[^a-zA-Z0-9_]", "_", collection_name)

    embedding_fn = get_chroma_embedding_fn()

    vectorstore = Chroma(
        collection_name=safe_collection_name,
        embedding_function=embedding_fn,
        persist_directory=persist_directory,
    )

    # 检索 2 倍 top_k，再从中选最好的（Hybrid Search 重排）
    hybrid_results = hybrid_search(vectorstore, query, embedding_fn, k=top_k * 2)

    chunks = []
    for item in hybrid_results[:top_k]:
        r = item["doc"]
        chunks.append({
            "content": r.page_content,
            "paper_id": r.metadata.get("paper_id", ""),
            "chunk_index": r.metadata.get("chunk_index", 0),
            "page_number": r.metadata.get("page_number", 0),
            "text": r.metadata.get("text", ""),
            "combined_score": round(item.get("combined_score", item.get("vector_score", 1.0)), 3),
        })

    return chunks
