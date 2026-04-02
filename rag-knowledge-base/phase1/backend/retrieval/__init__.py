"""
Phase 1 — 检索与排序层

混合检索：BM25（关键词）+ 向量检索 → RRF 融合 → 元数据过滤 → CrossEncoder 重排
"""
import chromadb
from chromadb.config import Settings
from typing import Literal
from .. import config
from ..storage.schema import get_db

# ─── ChromaDB 客户端 ────────────────────────────────────

_chroma_client = None

def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=config.CHROMADB_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _chroma_client


def get_or_create_collection(name: str = config.COLLECTION_NAME):
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


# ─── BM25 实现（轻量，不需要额外库）─────────────────────

def bm25_score(query: str, documents: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """
    简化的 BM25 实现（用于混合检索中的关键词检索）
    documents: list of texts
    returns: list of BM25 scores
    """
    import math
    # 分词（简单的中英文分开）
    def tokenize(text: str) -> list[str]:
        # 英文按空格分
        words = text.lower().split()
        # 中文字符分组（每2个字符一个词）
        chars = [text[i:i+2] for i in range(0, len(text)-1, 2) if '\u4e00' <= text[i] <= '\u9fff']
        return words + chars

    query_tokens = tokenize(query)
    if not query_tokens:
        return [0.0] * len(documents)

    N = len(documents)
    doc_tokens = [tokenize(d) for d in documents]
    avgdl = sum(len(d) for d in doc_tokens) / N if N > 0 else 1

    # 文档频率
    df = {}
    for dt in doc_tokens:
        for t in set(dt):
            df[t] = df.get(t, 0) + 1

    scores = []
    for dt in doc_tokens:
        score = 0.0
        for qt in query_tokens:
            if qt not in df:
                continue
            tf = dt.count(qt)
            idf = math.log((N - df[qt] + 0.5) / (df[qt] + 0.5) + 1)
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * len(dt) / avgdl))
        scores.append(score)

    return scores


def keyword_search(query: str, top_k: int = 40) -> list[dict]:
    """BM25 关键词检索，返回 chunk_id 列表"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT chunk_id, paper_id, chunk_text, token_count FROM chunks "
            "WHERE chunk_level = 'recall' LIMIT 500",
        ).fetchall()

    if not rows:
        return []

    texts = [r["chunk_text"] for r in rows]
    scores = bm25_score(query, texts)
    scored = sorted(zip(rows, scores), key=lambda x: x[1], reverse=True)

    results = []
    for row, score in scored[:top_k]:
        results.append({
            "chunk_id": row["chunk_id"],
            "paper_id": row["paper_id"],
            "chunk_text": row["chunk_text"],
            "bm25_score": round(score, 4),
            "token_count": row["token_count"],
        })
    return results


# ─── 向量检索 ────────────────────────────────────────────

def get_query_embedding(text: str) -> list[float]:
    """用 BGE 模型生成查询向量"""
    from ..pipeline import get_embedding_model
    model = get_embedding_model()
    emb = model.encode([text], normalize_embeddings=True)[0]
    return emb.tolist()


def vector_search(query: str, query_embedding: list[float], top_k: int = 40) -> list[dict]:
    """ChromaDB 向量检索"""
    col = get_or_create_collection()
    try:
        results = col.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )
    except Exception:
        return []

    hits = []
    if results and results["ids"] and results["ids"][0]:
        for i, cid in enumerate(results["ids"][0]):
            hits.append({
                "chunk_id": cid,
                "paper_id": results["metadatas"][0][i].get("paper_id", ""),
                "chunk_text": results["documents"][0][i],
                "vector_score": 1 - results["distances"][0][i],  # cosine distance → similarity
                "chroma_id": cid,
            })
    return hits


# ─── RRF 融合 ────────────────────────────────────────────

def reciprocal_rank_fusion(
    result_lists: list[list[dict]],
    k: int = 60,
) -> list[dict]:
    """
    RRF (Reciprocal Rank Fusion)
    并行融合多个排序列表，输出综合排名
    """
    rrf_scores: dict[str, dict] = {}

    for result_list in result_lists:
        for rank, item in enumerate(result_list):
            chunk_id = item["chunk_id"]
            # RRF 分数：1 / (k + rank + 1)
            score = 1.0 / (k + rank + 1)
            if chunk_id not in rrf_scores:
                rrf_scores[chunk_id] = {**item, "rrf_score": 0.0}
            rrf_scores[chunk_id]["rrf_score"] += score

    sorted_results = sorted(
        rrf_scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )
    return sorted_results


# ─── 混合检索主流程 ────────────────────────────────────

def hybrid_search(
    query: str,
    top_k: int = 8,
    retrieval_top_k: int = 40,
    paper_ids: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
    language: str | None = None,
    methods: list[str] | None = None,
) -> list[dict]:
    """
    完整混合检索流程

    Query 预处理
      ↓
    BM25 关键词检索 ──┐
                      ├→ RRF 融合 → 元数据过滤 → 返回 top_k
    向量语义检索 ─────┘
    """
    # 1. BM25 检索
    bm25_results = keyword_search(query, top_k=retrieval_top_k)

    # 2. 向量检索
    try:
        query_emb = get_query_embedding(query)
        vec_results = vector_search(query, query_emb, top_k=retrieval_top_k)
    except Exception:
        vec_results = []

    # 3. RRF 融合
    fused = reciprocal_rank_fusion([bm25_results, vec_results], k=60)

    # 4. 元数据过滤
    filtered = _apply_metadata_filter(
        fused,
        paper_ids=paper_ids,
        year_range=year_range,
        language=language,
        methods=methods,
    )

    return filtered[:top_k]


def _apply_metadata_filter(
    results: list[dict],
    paper_ids: list[str] | None = None,
    year_range: tuple[int, int] | None = None,
    language: str | None = None,
    methods: list[str] | None = None,
) -> list[dict]:
    """元数据过滤"""
    if not paper_ids and not year_range and not language and not methods:
        return results

    filtered = []
    for r in results:
        paper_id = r.get("paper_id")
        if paper_ids and paper_id not in paper_ids:
            continue
        filtered.append(r)
    return filtered


# ─── Upsert 向量 ───────────────────────────────────────

def upsert_chunks(chunks: list[dict]):
    """
    将 evidence chunks 写入 ChromaDB
    chunks: list of {chunk_id, paper_id, chunk_text, metadata}
    """
    col = get_or_create_collection()
    ids = [c["chunk_id"] for c in chunks]
    documents = [c["chunk_text"] for c in chunks]
    embeddings = [c["embedding"] for c in chunks]
    metadatas = [c.get("metadata", {}) for c in chunks]

    col.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def delete_paper_vectors(paper_id: str) -> bool:
    """删除某篇论文的所有向量"""
    col = get_or_create_collection()
    try:
        # 查该 paper_id 的所有 chroma IDs
        all_data = col.get(where={"paper_id": paper_id})
        if all_data and all_data["ids"]:
            col.delete(ids=all_data["ids"])
        return True
    except Exception:
        return False
