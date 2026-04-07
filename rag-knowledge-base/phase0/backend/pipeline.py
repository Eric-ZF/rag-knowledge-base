"""
Phase 0.7+：PDF → Docling 结构化解析 → 两级 Chunk → BGE Embedding → ChromaDB

Parsing: Docling 2.x（表格/公式/参考文献/页码全结构化）
Embedding: BGE-large-zh-v1.5（1024维，本地运行）

两级 Chunk 设计（学术 RAG 最佳实践）：
  - Recall Chunk（召回块）：400-800 tokens，按语义段落切分，保证召回率
  - Evidence Chunk（证据块）：150-350 tokens，按单段/结论/表格行切分，最小可引用单元
"""

import hashlib
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
    """获取本地 Embedding 模型（单例，BGE-large-zh-v1.5, 1024维）"""
    global _embedding_model
    if _embedding_model is None:
        print(f"📥 首次加载 Embedding 模型: {EMBEDDING_MODEL}（1024维，首次下载后缓存）")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"✅ 模型加载完成，向量维度: {EMBEDDING_DIM}")
    return _embedding_model


# ─── LangChain Embedding Wrapper ──────────────────────
class LocalEmbeddingWrapper:
    """将 sentence-transformers 封装为 LangChain 兼容的 Embedding 接口"""

    def __init__(self):
        self.model = get_embedding_model()
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed_query(self, text: str) -> list[float]:
        vec = self.model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()

    def __call__(self, text: str) -> list[float]:
        return self.embed_query(text)


def get_chroma_embedding_fn():
    return LocalEmbeddingWrapper()


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


def parse_pdf_docling(pdf_path: str) -> tuple[list[Document], str]:
    """
    使用 Docling 2.84.0 解析 PDF，返回结构化 Documents + content hash。

    Docling 2.84.0 API：
    - result.pages: list[Page]
    - page.assembled.elements: list[PageElement]
      其中 PageElement = TextElement | Table | FigureElement | ContainerElement
    - TextElement.text: str
    - Table.table_cells: list[TableCell] (含 row/col offset)

    Returns:
        documents: List[Document]，每个段落一个 Document
        content_hash: PDF 全文 SHA256（用于去重检测）
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

    return documents, content_hash


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
    emit("parsing", 0.1)
    raw_docs, content_hash = parse_pdf_docling(pdf_path)
    print(f"[{paper_id}] Docling 解析完成：{len(raw_docs)} 个原始单元（正文+表格+参考文献）")

    if not raw_docs:
        raise ValueError(f"PDF 解析失败，文档为空: {pdf_path}")

    # 2. 两级分块
    emit("chunking", 0.3)
    chunker = TwoLevelChunker()
    all_chunks = chunker.chunk(raw_docs)
    print(f"[{paper_id}] 两级 Chunk 完成：{len(all_chunks)} 个 chunks（Recall + Evidence）")

    if not all_chunks:
        raise ValueError(f"PDF 分块失败，chunks 为空: {pdf_path}")

    # 3. 初始化 Embedding
    emit("embedding", 0.5)
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
    emit("indexing", 0.7)
    texts = [c.page_content for c in all_chunks]
    metadatas = [
        {
            "paper_id": paper_id,
            "title": title,
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
    }


# ─── Hybrid Search（保留原有实现）──────────────────────
def hybrid_search(vectorstore, query: str, query_embedding_fn, k: int = 10) -> list[dict]:
    """
    混合检索策略（关键词预筛 + 向量重排 + 页码权重）
    学术问答中专业术语必须精确匹配，纯向量语义不足以捕捉术语相关性

    策略：向量 50% + 关键词 30% + 页码位置 20%
    """
    import re

    # 提取关键词（中文词 + 英文缩写）
    chinese_words = re.findall(r'[\u4e00-\u9fff]{2,}', query)
    english_words = re.findall(r'[a-zA-Z]{2,}', query)
    keywords = chinese_words + english_words
    seen = set()
    keywords = [w for w in keywords if not (w in seen or seen.add(w))]
    query_lower = query.lower()

    # 向量检索候选
    query_vec = query_embedding_fn.embed_query(query)
    native_results = vectorstore._collection.query(
        query_embeddings=[query_vec],
        n_results=k * 4,
        include=["documents", "metadatas", "distances"],
    )

    from langchain_core.documents import Document
    vector_candidates = []
    docs = native_results.get("documents", [[]])[0]
    metas = native_results.get("metadatas", [[]])[0]
    dists = native_results.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        d = Document(page_content=doc, metadata=meta)
        d.metadata["_score"] = 1.0 - dist
        vector_candidates.append(d)

    if not vector_candidates:
        return []

    # 全角→半角归一化
    def to_halfwidth(text: str) -> str:
        result = []
        for ch in text:
            code = ord(ch)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            elif code == 0x3000:
                result.append(' ')
            else:
                result.append(ch)
        return ''.join(result)

    for r in vector_candidates:
        content = r.page_content
        content_lower = to_halfwidth(content).lower()
        keyword_hits = sum(
            1 for kw in keywords
            if to_halfwidth(kw).lower() in content_lower
        )
        r.metadata['_keyword_hits'] = keyword_hits
        r.metadata['_full_hit'] = 1 if to_halfwidth(query_lower) in content_lower else 0

    max_score = max(r.metadata.get('_score', 1.0) for r in vector_candidates) or 1.0
    max_kw = max(r.metadata.get('_keyword_hits', 0) for r in vector_candidates) or 1

    fused = []
    for r in vector_candidates:
        vector_score = r.metadata.get('_score', max_score * 0.5) / max_score
        kw_hits = r.metadata.get('_keyword_hits', 0)
        kw_score = kw_hits / max_kw
        full_hit = r.metadata.get('_full_hit', 0)

        combined = 0.5 * vector_score + 0.3 * kw_score

        # Evidence chunk 优先（引用精确度更高）
        if r.metadata.get('is_evidence'):
            combined += 0.15

        # 摘要/结论/方法章节加分
        section = r.metadata.get('section_type', 'body')
        if section in ('abstract', 'conclusion'):
            combined += 0.2
        elif section == 'method':
            combined += 0.1
        elif section == 'reference':
            combined -= 0.2

        # 页码位置权重
        page = r.metadata.get('page_number', 999)
        if page <= 3:
            combined += 0.15
        elif page >= 25:
            combined -= 0.1

        if full_hit:
            combined = combined * 1.3 + 0.15

        fused.append({
            "doc": r,
            "combined_score": round(combined, 4),
            "vector_score": round(vector_score, 4),
            "keyword_hits": kw_hits,
            "full_hit": full_hit,
            "chunk_type": r.metadata.get('chunk_type', 'recall'),
            "section_type": section,
        })

    # CrossEncoder 重排已禁用（1.9GB 服务器内存不足，无法加载 ~1.1GB 的 bge-reranker-base）
    # hybrid_search 纯向量+关键词融合已足够好

    fused.sort(key=lambda x: x["combined_score"], reverse=True)
    return fused[:k]


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
