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
    使用 pdfplumber 按页提取文本，保留段落自然结构
    解决 UnstructuredLoader fast策略将每字符/每行当作独立element的问题
    """
    import pdfplumber
    from langchain_core.documents import Document

    all_docs = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if text and text.strip():
                all_docs.append(Document(
                    page_content=text.strip(),
                    metadata={"page_number": page_num}
                ))
    return all_docs


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
    title: str = "",
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
            "title": title,
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


# ─── Hybrid Search（关键词预筛 + 向量重排）─────────────
def hybrid_search(vectorstore, query: str, query_embedding_fn, k: int = 10) -> list[dict]:
    """
    混合检索策略（不依赖 rank_bm25）：

    Step 1: 提取查询关键词（保留完整词，因为中文专业术语不能随意分割）
    Step 2: 批量获取 ChromaDB 中的 chunks，过滤包含关键词的候选
    Step 3: 对候选做向量相似度排序
    Step 4: 融合关键词命中分（命中权重 40%）和向量分（60%）

    学术问答中，专业术语（CBAM、碳边境调节机制）必须精确匹配，
    纯向量语义相似度不足以捕捉术语相关性
    """
    # Step 1: 提取关键词（中文 + 英文缩写，对学术术语尤其重要）
    import re
    # 中文词（至少2个汉字）
    chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', query)
    # 英文词（至少2个字母，用于 CBAM 等英文术语）
    english_words = re.findall(r'[a-zA-Z]{2,}', query)
    # 合并，中文优先，英文作为独立关键词
    keywords = chinese_words + english_words
    # 去重
    seen = set()
    keywords = [w for w in keywords if not (w in seen or seen.add(w))]
    # 保留原始查询（不区分大小写，用于精确匹配）
    query_lower = query.lower()

    # Step 2: 获取足够多的 chunks 进行关键词过滤
    # 先获取 k*4 个候选（保证关键词过滤后仍有足够候选）
    query_vec = query_embedding_fn.embed_query(query)
    vector_candidates = vectorstore.similarity_search_by_vector(query_vec, k=k * 4)

    if not vector_candidates:
        return []

    # Step 3: 关键词命中检测（支持全角/半角归一化）
    def to_halfwidth(text: str) -> str:
        """全角→半角归一化（用于关键词匹配）"""
        result = []
        for ch in text:
            code = ord(ch)
            # 全角英文区：0xFF01-0xFF5E → 转为 0x21-0x7E
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            elif code == 0x3000:  # 全角空格
                result.append(' ')
            else:
                result.append(ch)
        return ''.join(result)

    for r in vector_candidates:
        content = r.page_content
        content_lower = to_halfwidth(content).lower()
        # 统计命中了多少个关键词（全角/半角不敏感）
        keyword_hits = sum(1 for kw in keywords if to_halfwidth(kw).lower() in content_lower)
        r.metadata['_keyword_hits'] = keyword_hits
        # 额外：检查是否包含完整查询词（全角/半角不敏感）
        full_hit = 1 if to_halfwidth(query_lower) in content_lower else 0
        r.metadata['_full_hit'] = full_hit

    # Step 4: 向量分数归一化
    max_score = max(r.metadata.get('_score', 1.0) for r in vector_candidates) or 1.0
    max_kw = max(r.metadata.get('_keyword_hits', 0) for r in vector_candidates) or 1

    fused = []
    for r in vector_candidates:
        vector_score = r.metadata.get('_score', max_score * 0.5) / max_score
        kw_hits = r.metadata.get('_keyword_hits', 0)
        kw_score = kw_hits / max_kw  # 归一化关键词分
        full_hit = r.metadata.get('_full_hit', 0)

        # 融合：向量 50% + 关键词 30% + 页码位置 20%（学术论文前几页是摘要/引言，权重高）
        combined = 0.5 * vector_score + 0.3 * kw_score

        # 页码位置权重：前几页（摘要/引言/结论）加分，参考文献降权
        page = r.metadata.get('page_number', 999)
        if page <= 3:
            page_bonus = 0.2  # 封面/摘要
        elif page <= 10:
            page_bonus = 0.1  # 引言/背景
        elif page <= 25:
            page_bonus = 0.0  # 正文
        else:
            page_bonus = -0.15  # 参考文献/附录降权
        combined += page_bonus

        # 如果完整查询命中，直接加分
        if full_hit:
            combined = combined * 1.3 + 0.2

        fused.append({
            "doc": r,
            "combined_score": round(combined, 4),
            "vector_score": round(vector_score, 4),
            "keyword_hits": kw_hits,
            "full_hit": full_hit,
            "page_bonus": round(page_bonus, 3),
        })

    # 按综合分数排序
    fused.sort(key=lambda x: x["combined_score"], reverse=True)
    return fused[:k]


# ─── 语义检索 ──────────────────────────────────────────
async def search_chunks(
    query: str,
    collection_name: str,
    top_k: int = 10,  # 增大到 10，候选多了答案更完整
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
    hybrid_results = hybrid_search(vectorstore, query, embedding_fn, k=top_k * 3)

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
