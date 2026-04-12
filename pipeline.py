"""
Phase 0.7+：PDF → Docling 结构化解析 → 两级 Chunk → Jina AI Embedding → ChromaDB

Parsing: Docling 2.x（表格/公式/参考文献/页码全结构化）
Embedding: jina-embeddings-v2-base-zh（1024维，Jina AI 云端 API，无需本地 GPU）

两级 Chunk 设计（学术 RAG 最佳实践）：
  - Recall Chunk（召回块）：400-800 tokens，按语义段落切分，保证召回率
  - Evidence Chunk（证据块）：150-350 tokens，按单段/结论/表格行切分，最小可引用单元
"""

import hashlib
import os
import re
import requests
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from langchain_core.documents import Document
from langchain_chroma import Chroma

from config import EMBEDDING_MODEL, EMBEDDING_DIM, CHROMADB_DIR, JINA_API_KEY


# ─── Jina AI Embedding（云端 API，无本地模型）──────────
JINA_API_URL = "https://api.jina.ai/v1/embeddings"


def _jina_embed_batch(texts: list[str]) -> list[list[float]]:
    """调用 Jina AI API 批量 embedding，返回归一化向量列表"""
    resp = requests.post(
        JINA_API_URL,
        headers={
            "Authorization": f"Bearer {JINA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBEDDING_MODEL, "input": texts},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    # 按 index 排序保证顺序
    data.sort(key=lambda x: x["index"])
    return [item["embedding"] for item in data]


class JinaEmbeddingWrapper:
    """Jina AI 云端 embedding，封装为 LangChain 兼容接口"""

    def __init__(self):
        self.dim = EMBEDDING_DIM

    def embed_query(self, text: str) -> list[float]:
        return _jina_embed_batch([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # Jina API 单次最多 256 条，我们分成小批量
        results = []
        BATCH = 64
        for i in range(0, len(texts), BATCH):
            batch = texts[i:i + BATCH]
            for _ in range(3):  # 重试3次
                try:
                    results.extend(_jina_embed_batch(batch))
                    break
                except Exception as e:
                    print(f"⚠️ Jina API batch {i//BATCH} failed: {e}, retrying...", flush=True)
                    time.sleep(2)
        return results

    def __call__(self, text: str) -> list[float]:
        return self.embed_query(text)


def get_chroma_embedding_fn():
    return JinaEmbeddingWrapper()


# ─── Docling PDF 解析 ──────────────────────────────────
def _table_to_markdown(table_obj) -> str:
    """
    将 Docling 2.84.0 的 Table 对象转换为 Markdown 格式。
    Table.table_cells 是扁平列表，按 row/col offset 索引排列。
    """
    try:
        num_rows = table_obj.num_rows or 0
        num_cols = table_obj.num_cols or 0
        if num_rows == 0 or num_cols == 0 or not table_obj.table_cells:
            return ""

        # 构建 grid[row][col] = text
        grid = [["" for _ in range(num_cols)] for _ in range(num_rows)]
        for cell in table_obj.table_cells:
            row = cell.start_row_offset_idx
            col = cell.start_col_offset_idx
            if 0 <= row < num_rows and 0 <= col < num_cols:
                grid[row][col] = (cell.text or "").strip()

        # 生成 Markdown table
        md_lines = []
        md_lines.append("| " + " | ".join(f"col{j}" for j in range(num_cols)) + " |")
        md_lines.append("|" + "|".join(["---"] * num_cols) + "|")
        for row in grid:
            md_lines.append("| " + " | ".join(str(c).strip() for c in row) + " |")

        return "\n".join(md_lines)
    except Exception:
        return ""


def _extract_pdf_metadata(result) -> dict:
    """
    从 Docling ConversionResult 中提取 PDF 元数据。
    尝试获取：title, authors, year, doi, journal
    """
    meta = {}
    try:
        # Docling result.metadata 的标准字段
        doc_meta = getattr(result, 'metadata', None) or {}
        if hasattr(doc_meta, '__dict__'):
            doc_meta = vars(doc_meta)

        # title：优先用 Docling 解析出的标题，否则用 PDF metadata
        meta['title'] = (
            getattr(result, 'title', None)
            or doc_meta.get('title')
            or doc_meta.get('subject')
            or ''
        )
        # authors
        raw_authors = (
            getattr(result, 'authors', None)
            or doc_meta.get('authors')
            or []
        )
        if isinstance(raw_authors, list):
            meta['authors'] = '; '.join(str(a) for a in raw_authors if a)
        elif raw_authors:
            meta['authors'] = str(raw_authors)
        else:
            meta['authors'] = ''
        # year：尝试从 creation_date 提取
        creation_date = (
            getattr(result, 'creation_date', None)
            or doc_meta.get('creation_date')
        )
        if creation_date:
            year_str = str(creation_date)[:4]
            meta['year'] = int(year_str) if year_str.isdigit() else None
        else:
            meta['year'] = None
        # DOI 和 journal：Docling 通常不直接从 PDF header 提取，放在空字符串
        # 前端可编辑，或从文本自动识别
        meta['doi'] = doc_meta.get('doi', '')
        meta['journal'] = doc_meta.get('journal', '')
        # 备用：creator/producer
        meta['publisher'] = doc_meta.get('creator', '') or doc_meta.get('producer', '')
    except Exception as e:
        print(f"[WARN] PDF metadata 提取失败: {e}")
        meta = {'title': '', 'authors': '', 'year': None, 'doi': '', 'journal': '', 'publisher': ''}
    return meta


def parse_pdf_docling(pdf_path: str) -> tuple[list[Document], str, dict]:
    """
    使用 Docling 2.84.0 解析 PDF，返回结构化 Documents + content hash + PDF 元数据。

    Docling 2.84.0 API：
    - result.pages: list[Page]
    - page.assembled.elements: list[PageElement]
      其中 PageElement = TextElement | Table | FigureElement | ContainerElement
    - TextElement.text: str
    - Table.table_cells: list[TableCell] (含 row/col offset)

    Returns:
        documents: List[Document]，每个段落一个 Document
        content_hash: PDF 全文 SHA256（用于去重检测）
        pdf_metadata: dict {title, authors, year, doi, journal, publisher}
    """
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(source=pdf_path)

    all_parts = []
    full_text_parts = []

    # ── 1. 正文页面文本（docling 2.84.0 API）────────────
    table_count = 0
    for page_num, page in enumerate(result.pages, start=1):
        page_elements = []
        assembled = getattr(page, "assembled", None)

        if assembled is not None and hasattr(assembled, "elements"):
            page_elements = assembled.elements or []

        # 从 TextElement 提取文本
        body_texts = []
        for elem in page_elements:
            if elem.__class__.__name__ == "TextElement":
                text = getattr(elem, "text", None)
                if text and text.strip():
                    body_texts.append(text.strip())
            elif elem.__class__.__name__ == "Table":
                # 表格：转 Markdown
                md = _table_to_markdown(elem)
                if md:
                    table_count += 1
                    all_parts.append({
                        "text": f"[表格 {table_count}]\n{md}",
                        "page_number": page_num,
                        "section_type": "table",
                        "source": "table",
                        "table_index": table_count,
                    })
                    full_text_parts.append(md)

        # 合并同一页的 body 文本，按空行分段
        page_combined = "\n\n".join(body_texts)
        if page_combined.strip():
            paragraphs = [p.strip() for p in page_combined.split("\n\n") if p.strip()]
            for para in paragraphs:
                section_type = _classify_section(para, page_num)
                all_parts.append({
                    "text": para,
                    "page_number": page_num,
                    "section_type": section_type,
                    "source": "body",
                })
                full_text_parts.append(para)

    # ── 2. 生成 Documents ───────────────────────────────
    documents = []
    for i, part in enumerate(all_parts):
        documents.append(Document(
            page_content=part["text"],
            metadata={
                "page_number": part["page_number"],
                "section_type": part["section_type"],
                "source": part["source"],
                "chunk_index": i,
                **{k: v for k, v in part.items()
                   if k not in ("text", "page_number", "section_type", "source")},
            }
        ))

    # ── 3. Content hash ─────────────────────────────────
    content_hash = hashlib.sha256(
        ("|||".join(full_text_parts)).encode("utf-8")
    ).hexdigest()

    # ── 4. PDF 元数据 ────────────────────────────────────
    pdf_meta = _extract_pdf_metadata(result)
    print(f"[DEBUG] PDF metadata: title={pdf_meta.get('title','')[:40]} authors={pdf_meta.get('authors','')[:30]} year={pdf_meta.get('year')}")

    return documents, content_hash, pdf_meta


def _classify_section(text: str, page_num: int) -> str:
    """
    根据文本内容 + 页码判断段落类型（用于 chunk 权重和检索优先级）
    """
    first_line = text.strip().split('\n')[0][:100].lower()

    # 摘要（通常第1页，或有"摘要"关键字）
    if page_num == 1 and any(kw in first_line for kw in ['摘要', 'abstract', '概要', '提要']):
        return "abstract"
    # 引言/背景
    if any(kw in first_line for kw in ['1', '一、', '引言', 'introduction', '背景', '研究现状']):
        return "introduction"
    # 方法
    if any(kw in first_line for kw in ['方法', 'method', '实验', '数据来源', '2', '二、']):
        return "method"
    # 结果
    if any(kw in first_line for kw in ['结果', 'result', '分析', '3', '三、']):
        return "result"
    # 讨论
    if any(kw in first_line for kw in ['讨论', 'discussion', '4', '四、']):
        return "discussion"
    # 结论
    if any(kw in first_line for kw in ['结论', 'conclusion', '总结', '主要发现', '研究发现']):
        return "conclusion"
    # 参考文献
    if any(kw in first_line for kw in ['参考文献', 'reference', '引用', 'bibliography']):
        return "reference"

    # 默认正文
    return "body"


# ─── 两级 Chunk ────────────────────────────────────────
class TwoLevelChunker:
    """
    两级 Chunk 设计（学术 RAG 最佳实践）：

    召回块（Recall Chunk）：
      - 长度：400-800 tokens（中文约 800-1600 字）
      - 切分依据：按语义段落/小节重叠切分
      - 用途：初次检索，保证召回率

    证据块（Evidence Chunk）：
      - 长度：150-350 tokens（中文约 300-700 字）
      - 切分依据：按单段/结论句/表格行切分
      - 用途：最终生成引用的最小单元，精确到句
    """

    def __init__(self):
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        # 召回块分割器：按自然段落切分
        self.recall_splitter = RecursiveCharacterTextSplitter(
            chunk_size=6000,   # 中文字符数（约 600-800 tokens）
            chunk_overlap=400, # 400 字重叠，防止段落割裂
            separators=["\n\n\n", "\n\n", "\n", "。", "！", "？", "；"],
            length_function=lambda x: len(x),
        )

        # 证据块分割器：更细粒度，按单句切分
        self.evidence_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,   # 中文约 2000 字（150-350 tokens）
            chunk_overlap=150,
            separators=["\n", "。", "！", "？"],
            length_function=lambda x: len(x),
        )

    def chunk(self, documents: list[Document]) -> list[Document]:
        """
        对原始文档做两级切分：
        1. 先切召回块
        2. 再从召回块切证据块
        3. 合并，去重，保留位置信息
        """
        recall_chunks = self.recall_splitter.split_documents(documents)
        evidence_chunks = self.evidence_splitter.split_documents(documents)

        all_chunks = []

        # 合并，设置 chunk_type
        for i, chunk in enumerate(recall_chunks):
            meta = dict(chunk.metadata)
            meta["chunk_type"] = "recall"
            meta["recall_index"] = i
            all_chunks.append(Document(
                page_content=chunk.page_content,
                metadata=meta,
            ))

        for i, chunk in enumerate(evidence_chunks):
            meta = dict(chunk.metadata)
            meta["chunk_type"] = "evidence"
            meta["evidence_index"] = i
            all_chunks.append(Document(
                page_content=chunk.page_content,
                metadata=meta,
            ))

        return all_chunks


# ─── 向量化 + 存入 ChromaDB ───────────────────────────
async def process_pdf(
    pdf_path: str,
    paper_id: str,
    collection_name: str,
    title: str = "",
    openai_api_key: str = "",
    persist_directory: str = CHROMADB_DIR,
    progress_callback: callable = None,
) -> dict[str, Any]:
    """
    完整 pipeline：PDF → Docling解析 → 两级Chunk → BGE向量 → ChromaDB

    进度阶段：parsing → chunking → embedding → indexing → complete
    """
    def emit(stage: str, progress: float, **kwargs):
        if progress_callback:
            progress_callback(stage, progress, **kwargs)

    # 1. Docling 解析 PDF
    print(f"[{paper_id}] 开始 Docling 解析 PDF...")
    raw_docs, content_hash, pdf_meta = parse_pdf_docling(pdf_path)
    print(f"[{paper_id}] Docling 解析完成：{len(raw_docs)} 个原始单元（正文+表格+参考文献）")

    if not raw_docs:
        raise ValueError(f"PDF 解析失败，文档为空: {pdf_path}")

    # 2. 两级分块
    chunker = TwoLevelChunker()
    all_chunks = chunker.chunk(raw_docs)
    print(f"[{paper_id}] 两级 Chunk 完成：{len(all_chunks)} 个 chunks（Recall + Evidence）")

    if not all_chunks:
        raise ValueError(f"PDF 分块失败，chunks 为空: {pdf_path}")

    # 3. 初始化 Embedding
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
    texts = [c.page_content for c in all_chunks]
    # 用 PDF 元数据覆盖 title（优先用 Docling 解析出的标题）
    display_title = pdf_meta.get('title') or title
    metadatas = [
        {
            "paper_id": paper_id,
            "title": display_title,
            "authors": pdf_meta.get('authors', ''),
            "year": pdf_meta.get('year'),
            "journal": pdf_meta.get('journal', ''),
            "doi": pdf_meta.get('doi', ''),
            "chunk_type": c.metadata.get("chunk_type", "recall"),
            "section_type": c.metadata.get("section_type", "body"),
            "source": c.metadata.get("source", "body"),
            "page_number": c.metadata.get("page_number", 0),
            "chunk_index": i,
            "text": c.page_content[:200],  # 前200字预览
            # 证据块额外字段
            "is_evidence": c.metadata.get("chunk_type") == "evidence",
            "is_recall": c.metadata.get("chunk_type") == "recall",
        }
        for i, c in enumerate(all_chunks)
    ]

    vectorstore.add_texts(texts=texts, metadatas=metadatas)

    recall_count = sum(1 for m in metadatas if m["chunk_type"] == "recall")
    evidence_count = sum(1 for m in metadatas if m["chunk_type"] == "evidence")

    print(f"[{paper_id}] ✅ 向量写入完成：{recall_count} 召回块 + {evidence_count} 证据块")
    print(f"[{paper_id}]    Collection: '{safe_collection_name}'")
    print(f"[{paper_id}]    Embedding: {EMBEDDING_MODEL}（1024维）")

    emit("complete", 1.0, chunks_count=len(all_chunks))
    return {
        "chunks_count": len(all_chunks),
        "recall_count": recall_count,
        "evidence_count": evidence_count,
        "content_hash": content_hash,
        "pdf_metadata": pdf_meta,
    }


# ─── Hybrid Search（保留原有实现）──────────────────────

# ─── BM25 检索（真正基于倒排索引的关键词检索）────────────
def _tokenize(text: str) -> list[str]:
    """简单中英文混合分词"""
    import re
    chinese = re.findall(r'[\u4e00-\u9fff]+', text)
    english = re.findall(r'[a-zA-Z0-9]+', text)
    tokens = chinese + english
    return [t.lower() for t in tokens if len(t) > 1 and not t.isdigit()]


class BM25Index:
    """
    轻量级 BM25 索引（rank_bm25 后端）。
    在 ChromaDB 返回的候选集上构建，不持久化。
    对于 ~1500 chunks 的学术库，建索引 ~50ms，完全可接受。
    """

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        if not chunks:
            self.bm25 = None
            return
        try:
            from rank_bm25 import BM25Okapi
            tokenized = [self._chunk_tokens(c["content"]) for c in chunks]
            # 过滤空token列表（防止 ZeroDivisionError）
            non_empty = [t for t in tokenized if t]
            if not non_empty:
                self.bm25 = None
                print("[BM25Index] 所有chunks tokenize为空，跳过BM25")
                return
            self.bm25 = BM25Okapi(non_empty)
        except ImportError:
            self.bm25 = None
            print("[BM25Index] rank_bm25 未安装，降级为关键词匹配")
        except ZeroDivisionError:
            self.bm25 = None
            print("[BM25Index] BM25初始化 ZeroDivisionError（tokenize全空），跳过BM25")

    def _chunk_tokens(self, content: str) -> list[str]:
        return _tokenize(content)

    def search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        """BM25 检索，返回 [(chunk_index, score)] 按分数降序"""
        if not self.bm25 or not self.chunks:
            return []
        tokens = _tokenize(query)
        scores = self.bm25.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]

def hybrid_search(vectorstore, query: str, query_embedding_fn, k: int = 10) -> list[dict]:
    """
    真正混合检索：向量检索 ∪ BM25 检索 → RRF 融合 → 质量加权。

    学术场景必须精确匹配专业术语（"DID"、"OLS"、"碳排放权交易"），
    纯向量无法可靠捕捉这些精确词项。

    策略：向量 Top(k*3) ∪ BM25 Top(k*3) → RRF(k=60) 融合 → section/page 加权
    """
    import re

    # ── 1. 向量检索候选 ───────────────────────────────
    query_vec = query_embedding_fn.embed_query(query)
    vector_results = vectorstore._collection.query(
        query_embeddings=[query_vec],
        n_results=k * 3,
        include=["documents", "metadatas", "distances"],
    )

    from langchain_core.documents import Document
    # 统一候选集，用 id → (doc, vector_rank, vector_score)
    candidates: dict[str, dict] = {}
    docs = vector_results.get("documents", [[]])[0]
    metas = vector_results.get("metadatas", [[]])[0]
    dists = vector_results.get("distances", [[]])[0]
    for rank, (doc, meta, dist) in enumerate(zip(docs, metas, dists), 1):
        chunk_id = f"{meta.get('paper_id','')}-{meta.get('chunk_index', rank)}"
        d = Document(page_content=doc, metadata=meta)
        d.metadata["_vector_rank"] = rank
        d.metadata["_vector_score"] = 1.0 - dist
        candidates[chunk_id] = {"doc": d, "vector_rank": rank}

    if not candidates:
        return []

    # ── 2. BM25 检索（在向量候选集上建索引）────────────
    # 将 ChromaDB 返回的 chunks 转为 dict list 供 BM25Index
    chunk_dicts = []
    for cid, c in candidates.items():
        doc = c["doc"]
        chunk_dicts.append({
            "chunk_id": cid,
            "content": doc.page_content,
            "metadata": dict(doc.metadata),
        })

    bm25_index = BM25Index(chunk_dicts)
    bm25_results = bm25_index.search(query, top_k=k * 3)  # [(idx, score)]

    # 归一化 BM25 分数，分配 rank
    if bm25_results:
        max_bm25 = bm25_results[0][1] or 1.0
        for rank, (idx, score) in enumerate(bm25_results, 1):
            chunk_id = chunk_dicts[idx]["chunk_id"]
            if chunk_id in candidates:
                candidates[chunk_id]["bm25_rank"] = rank
                candidates[chunk_id]["bm25_score"] = score / max_bm25
            else:
                # BM25 命中了向量检索未召回的 chunk（扩展候选）
                extra_doc = Document(
                    page_content=chunk_dicts[idx]["content"],
                    metadata=chunk_dicts[idx]["metadata"],
                )
                extra_doc.metadata["_bm25_rank"] = rank
                extra_doc.metadata["_bm25_score"] = score / max_bm25
                candidates[chunk_id] = {
                    "doc": extra_doc,
                    "vector_rank": 999,
                    "bm25_rank": rank,
                    "bm25_score": score / max_bm25,
                }

    # ── 3. 彻底过滤参考文献区（不只是扣分，彻底排除）──────────────
    ref_penalize = []
    for cid, c in candidates.items():
        section = c["doc"].metadata.get("section_type", "body")
        if section == "reference":
            ref_penalize.append(cid)
    for cid in ref_penalize:
        del candidates[cid]

    # ── 4. RRF 融合（Reciprocal Rank Fusion, k=60）────
    RRF_K = 60
    for cid, c in candidates.items():
        vr = c.get("vector_rank", 999)
        br = c.get("bm25_rank", 999)
        vs = c.get("vector_score", 0)
        bs = c.get("bm25_score", 0)

        # RRF score
        rrf = (1 / (RRF_K + vr)) + (1 / (RRF_K + br))

        # 加上归一化分数成分（权重 30%）
        combined = 0.7 * rrf + 0.3 * (0.5 * vs + 0.5 * bs)

        # Section 质量加权
        section = c["doc"].metadata.get('section_type', 'body')
        if section in ('abstract', 'conclusion'):
            combined += 0.15
        elif section == 'method':
            combined += 0.08

        # Evidence chunk 优先
        if c["doc"].metadata.get('is_evidence'):
            combined += 0.10

        # 前3页加权
        page = c["doc"].metadata.get('page_number', 999)
        if page <= 3:
            combined += 0.10
        elif page >= 25:
            combined -= 0.08

        c["combined_score"] = round(combined, 4)
        c["chunk_type"] = c["doc"].metadata.get('chunk_type', 'recall')
        c["section_type"] = section

    # ── 4. 排序输出 ──────────────────────────────────
    fused = sorted(candidates.values(), key=lambda x: x["combined_score"], reverse=True)
    result = []
    for item in fused[:k]:
        r = item["doc"]
        result.append({
            "doc": r,
            "combined_score": item["combined_score"],
            "vector_rank": item.get("vector_rank", 999),
            "bm25_rank": item.get("bm25_rank", 999),
            "keyword_hits": 0,
            "full_hit": 0,
            "chunk_type": item["chunk_type"],
            "section_type": item["section_type"],
        })
    return result


# ─── 语义检索 ──────────────────────────────────────────
async def search_chunks(
    query: str,
    collection_name: str,
    top_k: int = 10,
    openai_api_key: str = "",
    persist_directory: str = CHROMADB_DIR,
) -> list[dict]:
    """
    语义检索：向量化 → ChromaDB → 混合检索 → 返回相关 chunks
    """
    safe_collection_name = re.sub(r"[^a-zA-Z0-9_]", "_", collection_name)
    embedding_fn = get_chroma_embedding_fn()

    vectorstore = Chroma(
        collection_name=safe_collection_name,
        embedding_function=embedding_fn,
        persist_directory=persist_directory,
    )

    hybrid_results = hybrid_search(vectorstore, query, embedding_fn, k=top_k * 3)

    chunks = []
    for item in hybrid_results[:top_k]:
        r = item["doc"]
        chunks.append({
            "content": r.page_content,
            "paper_id": r.metadata.get("paper_id", ""),
            "chunk_type": r.metadata.get("chunk_type", "recall"),
            "section_type": r.metadata.get("section_type", "body"),
            "chunk_index": r.metadata.get("chunk_index", 0),
            "page_number": r.metadata.get("page_number", 0),
            "text": r.metadata.get("text", ""),
            "combined_score": round(item.get("combined_score", item.get("vector_score", 1.0)), 3),
        })

    return chunks
