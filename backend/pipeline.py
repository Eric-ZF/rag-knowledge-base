"""
Phase 0.7+：PDF → Docling 结构化解析 → 两级 Chunk → Jina AI Embedding → ChromaDB

Parsing: Docling 2.x（表格/公式/参考文献/页码全结构化）
Embedding: jina-embeddings-v2-base-zh（1024维，Jina AI 云端 API，无需本地 GPU）

两级 Chunk 设计（学术 RAG 最佳实践）：
  - Recall Chunk（召回块）：400-800 tokens，按语义段落切分，保证召回率
  - Evidence Chunk（证据块）：150-350 tokens，按单段/结论/表格行切分，最小可引用单元
"""

import logging
logger = logging.getLogger(__name__)

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
                    logger.warning(f"Jina API batch {i//BATCH} failed: {e}, retrying...")
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
        logger.warning(f"PDF metadata 提取失败: {e}")
        meta = {'title': '', 'authors': '', 'year': None, 'doi': '', 'journal': '', 'publisher': ''}
    return meta


def _is_spaced_text(text: str) -> bool:
    """
    检测中文 PDF 字符间隔问题（pdfplumber 对扫描 PDF 的常见产物）。
    两种模式:
    1. 字符间隔: "我 的 祖 国" - 大量"单字+空格"模式
    2. 字符压缩: "对对中中国国高高碳碳..." - 连续CJK字符无间隔
    RapidOCR 对两者都有很好的修复效果。
    """
    import re
    if not text:
        return False
    total_cjk = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    if total_cjk < 10:
        return False

    # 模式1: 字符间隔（单字+空格），如"对 的 中 国"
    spaced_pattern = re.compile(r'[\u4e00-\u9fff] ')
    spaced_matches = spaced_pattern.findall(text)
    spaced_count = sum(len(m) for m in spaced_matches)

    # 模式2: 字符压缩（连续CJK无间隔），如"对对中国"
    # 统计连续2+个CJK无间隔的情况
    compressed_pattern = re.compile(r'[\u4e00-\u9fff]{2,}')
    compressed_matches = compressed_pattern.findall(text)
    # 每个匹配中，除了第一个字符外都是"多余"的压缩字符
    compressed_count = sum(max(0, len(m) - 1) for m in compressed_matches)

    # 字符间隔模式为主（压缩文本中可能也有间隔）
    # 但字符压缩更严重：连续2个CJK无间隔 = 必有1个压缩字符
    total_bad = spaced_count + compressed_count
    ratio = total_bad / total_cjk
    # 阈值15%：超过说明有问题
    return ratio > 0.15


class SpacedTextError(Exception):
    """pdfplumber 提取文本存在字符间隔，需要 RapidOCR 兜底"""
    pass


def _is_garbled_text(text: str) -> bool:
    """
    判断文本是否为乱码（Docling/RapidOCR 解析失败产物）。
    对中文 PDF：CJK 字符占比 < 5% 且文本偏短 → 判定为乱码。
    对英文 PDF：isprintable 比例 < 30% → 乱码。
    """
    if not text or len(text.strip()) < 20:
        return True
    cjk_count = sum(1 for c in text if '一' <= c <= '鿿')
    cjk_ratio = cjk_count / max(len(text), 1)
    if cjk_ratio < 0.05 and cjk_count < 10:
        return True
    valid = sum(1 for c in text if c.isprintable())
    if valid / len(text) < 0.30:
        return True
    return False


def _extract_section_title_from_text(text: str) -> str:
    """
    从段落首行提取章节标题（如 '1. 引言'、'二，研究方法'）。
    返回干净标题字符串，找不到返回空字符串。
    """
    first_line = text.strip().split('\n')[0].strip()
    if len(first_line) > 80 or len(first_line) < 2:
        return ""
    if re.match(r'^[\d\u4e00-\u9fff\u3000-\u303f\uff00-\uffef一二三四五六七八九十]+[.、)\s]', first_line):
        return first_line
    if re.match(r'^[A-Z][A-Z\s\-]+$', first_line[:30]):
        return first_line
    return ""


def parse_pdf_plumber(pdf_path: str) -> tuple[list[Document], str, dict]:
    """
    使用 pdfplumber 解析 PDF（降级方案，保留原始中文文本）。
    优点：完全不依赖 OCR，提取干净的 PDF 原文。
    """
    import pdfplumber

    all_parts = []
    full_text_parts = []
    pdf_meta = {"title": "", "authors": "", "year": None, "doi": "", "journal": "", "publisher": ""}

    with pdfplumber.open(pdf_path) as pdf:
        doc_info = pdf.metadata or {}
        pdf_meta["title"] = doc_info.get("Title", "") or ""
        authors = doc_info.get("Author", "") or ""
        pdf_meta["authors"] = authors if isinstance(authors, str) else "; ".join(str(a) for a in authors)
        pdf_meta["publisher"] = doc_info.get("Producer", "") or ""

        # 从首页文本提取标题和作者（CNKI 格式）
        if not pdf_meta.get("authors") or not pdf_meta.get("title"):
            try:
                import re as _re
                first_page = pdf.pages[0].extract_text() or "" if pdf.pages else ""
                if first_page:
                    nl = chr(10)
                    first_lines = [l.strip() for l in first_page.split(nl) if l.strip()]
                    author_pat = _re.compile(r'^[一-龥]{2,4}(?:\s|·)[一-龥]{2,4}(?:[\s·][一-龥]{2,4})*$')
                    if not pdf_meta.get("authors"):
                        for line in first_lines[:5]:
                            if author_pat.match(line):
                                pdf_meta["authors"] = line
                                break
                    if not pdf_meta.get("title"):
                        skip_indices = set()
                        for i, line in enumerate(first_lines[:4]):
                            if len(line) <= 5 or author_pat.match(line):
                                skip_indices.add(i)
                        title_parts = [l for i, l in enumerate(first_lines[:4]) if i not in skip_indices]
                        if title_parts:
                            pdf_meta["title"] = ''.join(title_parts)
                    doi_match = _re.search(r'(10\.\d{4,}/[^\s' + chr(0x3000) + chr(0x00a0) + r']+)', first_page)
                    if doi_match:
                        pdf_meta["doi"] = doi_match.group(1).rstrip('.,;')
            except Exception:
                pass

        table_count = 0
        current_section_title = ""

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if not text.strip():
                continue

            # 提取表格
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                if table and len(table) > 1:
                    table_count += 1
                    md_lines = []
                    md_lines.append("| " + " | ".join(str(c or "").strip() for c in table[0]) + " |")
                    md_lines.append("|" + "|".join(["---"] * len(table[0])) + "|")
                    for row in table[1:]:
                        md_lines.append("| " + " | ".join(str(c or "").strip() for c in row) + " |")
                    md_text = "\n".join(md_lines)
                    all_parts.append({
                        "text": md_text,
                        "page_number": page_num,
                        "section_type": "table",
                        "source": "plumber",
                        "section_title": current_section_title,
                        "table_index": table_count,
                    })
                    full_text_parts.append(md_text)

            # 按段落拆分
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para in paragraphs:
                section_type = _classify_section(para, page_num)
                section_title = _extract_section_title_from_text(para)
                if section_title:
                    current_section_title = section_title
                all_parts.append({
                    "text": para,
                    "page_number": page_num,
                    "section_type": section_type,
                    "source": "plumber",
                    "section_title": current_section_title,
                })
                full_text_parts.append(para)

    if not full_text_parts:
        raise ValueError(f"pdfplumber 解析失败，PDF 无可提取文本: {pdf_path}")

    documents = []
    for i, part in enumerate(all_parts):
        documents.append(Document(
            page_content=part["text"],
            metadata={
                "page_number": part["page_number"],
                "section_type": part["section_type"],
                "source": part["source"],
                "section_title": part.get("section_title", ""),
                "chunk_index": i,
                **{k: v for k, v in part.items()
                   if k not in ("text", "page_number", "section_type", "source", "section_title")},
            }
        ))

    content_hash = hashlib.sha256(
        ("|||".join(full_text_parts)).encode("utf-8")
    ).hexdigest()
    return documents, content_hash, pdf_meta


def _parse_pdf_rapidocr(pdf_path: str) -> tuple[list[Document], str, dict]:
    """
    使用 RapidOCR 解析 PDF（第三级兜底，专治扫描件/字符间隔 PDF）。
    RapidOCR 使用 PP-OCRv4 OCR 引擎，对扫描 PDF 中文识别效果好。
    """
    from rapidocr import RapidOCR
    import pdfplumber

    ocr_engine = RapidOCR()
    all_parts = []
    full_text_parts = []
    pdf_meta: dict[str, Any] = {"title": "", "authors": "", "year": None, "doi": "", "journal": "", "publisher": ""}

    # 提取 PDF 元数据
    with pdfplumber.open(pdf_path) as pdf:
        doc_info = pdf.metadata or {}
        pdf_meta["title"] = doc_info.get("Title", "") or ""
        authors = doc_info.get("Author", "") or ""
        pdf_meta["authors"] = authors if isinstance(authors, str) else "; ".join(str(a) for a in authors)
        pdf_meta["publisher"] = doc_info.get("Producer", "") or ""

    # 按页处理，用 OCR 提取每页文本
    current_section_title = ""
    table_count = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # 先尝试 pdfplumber 提取文字（处理非扫描页）
            plumber_text = page.extract_text() or ""
            
            # 用 RapidOCR 处理页面图片（处理扫描页/字符间隔页）
            page_image = page.to_image(resolution=300)
            img_array = page_image.original
            ocr_output = ocr_engine(img_array)

            ocr_text_lines = []
            if ocr_output and hasattr(ocr_output, 'txts'):
                for text in ocr_output.txts:
                    if text and isinstance(text, str) and text.strip():
                        ocr_text_lines.append(text.strip())
            ocr_text = "\n".join(ocr_text_lines)

            if not ocr_text.strip():
                logger.debug(f"[RapidOCR] page {page_num} returned empty result, using plumber text")

            # 选择更好的文本源：取较长的一个
            use_text = ocr_text if len(ocr_text) > len(plumber_text) else plumber_text

            # 检测字符间隔（如果 pdfplumber 文本明显比 OCR 长，说明 plumber 更好）
            if plumber_text and _is_spaced_text(plumber_text):
                # plumber 文本有间隔，用 OCR 结果替换
                use_text = ocr_text

            if not use_text.strip():
                continue

            # 表格提取（仍用 pdfplumber，OCR 对表格效果差）
            tables = page.extract_tables()
            for t_idx, table in enumerate(tables):
                if table and len(table) > 1:
                    table_count += 1
                    md_lines = ["| " + " | ".join(str(c or "").strip() for c in table[0]) + " |"]
                    md_lines.append("|" + "|".join(["---"] * len(table[0])) + "|")
                    for row in table[1:]:
                        md_lines.append("| " + " | ".join(str(c or "").strip() for c in row) + " |")
                    all_parts.append({
                        "text": "\n".join(md_lines),
                        "page_number": page_num,
                        "section_type": "table",
                        "source": "rapidocr_table",
                        "section_title": current_section_title,
                        "table_index": table_count,
                    })
                    full_text_parts.append("\n".join(md_lines))

            # 段落拆分
            paragraphs = [p.strip() for p in use_text.split("\n\n") if p.strip()]
            for para in paragraphs:
                if len(para) < 5:
                    continue
                section_type = _classify_section(para, page_num)
                section_title = _extract_section_title_from_text(para)
                if section_title:
                    current_section_title = section_title
                all_parts.append({
                    "text": para,
                    "page_number": page_num,
                    "section_type": section_type,
                    "source": "rapidocr",
                    "section_title": current_section_title,
                })
                full_text_parts.append(para)

    if not full_text_parts:
        raise ValueError(f"RapidOCR 解析失败，PDF 无可提取文本: {pdf_path}")

    documents = []
    for i, part in enumerate(all_parts):
        documents.append(Document(
            page_content=part["text"],
            metadata={
                "page_number": part["page_number"],
                "section_type": part["section_type"],
                "source": part["source"],
                "section_title": part.get("section_title", ""),
                "chunk_index": i,
                **{k: v for k, v in part.items()
                   if k not in ("text", "page_number", "section_type", "source", "section_title")},
            }
        ))

    content_hash = hashlib.sha256(
        ("|||".join(full_text_parts)).encode("utf-8")
    ).hexdigest()
    return documents, content_hash, pdf_meta


def parse_pdf_with_fallback(pdf_path: str) -> tuple[list[Document], str, dict]:
    """
    解析 PDF，优先使用 Docling（表格/结构化最强）。
    若解析质量过低（乱码比例 > 50%），自动降级到 pdfplumber。
    若 pdfplumber 输出存在字符间隔，进一步降级到 RapidOCR。
    同时检测章节标题，存入 metadata['section_title']。
    """
    # ── 1. 先用 Docling ──────────────────────────────
    from docling.document_converter import DocumentConverter
    converter = DocumentConverter()
    result = converter.convert(source=pdf_path)

    all_parts = []
    full_text_parts = []
    table_count = 0
    current_section_title = ""

    for page_num, page in enumerate(result.pages, start=1):
        page_elements = []
        assembled = getattr(page, "assembled", None)
        if assembled is not None and hasattr(assembled, "elements"):
            page_elements = assembled.elements or []

        body_texts = []
        for elem in page_elements:
            if elem.__class__.__name__ == "TextElement":
                text = getattr(elem, "text", None)
                if text and text.strip():
                    body_texts.append(text.strip())
            elif elem.__class__.__name__ == "Table":
                md = _table_to_markdown(elem)
                if md:
                    table_count += 1
                    all_parts.append({
                        "text": md,
                        "page_number": page_num,
                        "section_type": "table",
                        "source": "docling",
                        "section_title": current_section_title,
                        "table_index": table_count,
                    })
                    full_text_parts.append(md)

        page_combined = "\n\n".join(body_texts)
        if page_combined.strip():
            paragraphs = [p.strip() for p in page_combined.split("\n\n") if p.strip()]
            for para in paragraphs:
                section_type = _classify_section(para, page_num)
                section_title = _extract_section_title_from_text(para)
                if section_title:
                    current_section_title = section_title
                all_parts.append({
                    "text": para,
                    "page_number": page_num,
                    "section_type": section_type,
                    "source": "docling",
                    "section_title": current_section_title,
                })
                full_text_parts.append(para)

    # ── 2. 质量检测 ─────────────────────────────────
    readable_count = sum(1 for t in full_text_parts if not _is_garbled_text(t))
    quality_ratio = readable_count / max(len(full_text_parts), 1)
    logger.info(f"[parse] Docling 质量：{readable_count}/{len(full_text_parts)} 段可读（阈值 50%）")

    if quality_ratio < 0.50:
        logger.warning(f"[parse] Docling 质量低于 50%（{quality_ratio:.1%}），降级到 pdfplumber")
        plumber_docs, plumber_hash, plumber_meta = parse_pdf_plumber(pdf_path)
        # 检查 pdfplumber 输出是否有字符间隔（扫描 PDF 特征）
        plumber_texts = [d.page_content for d in plumber_docs]
        spaced_pages = sum(1 for t in plumber_texts if _is_spaced_text(t))
        logger.info(f"[parse] pdfplumber 字符间隔检测：{spaced_pages}/{len(plumber_texts)} 段存在间隔")
        if spaced_pages > len(plumber_texts) * 0.3:
            # 超过 30% 段落有间隔，切换到 RapidOCR
            logger.warning(f"[parse] pdfplumber {spaced_pages}/{len(plumber_texts)} 段字符间隔 > 30%，降级到 RapidOCR")
            return _parse_pdf_rapidocr(pdf_path)
        return plumber_docs, plumber_hash, plumber_meta

    # ── 3. 生成 Documents ───────────────────────────────
    documents = []
    for i, part in enumerate(all_parts):
        documents.append(Document(
            page_content=part["text"],
            metadata={
                "page_number": part["page_number"],
                "section_type": part["section_type"],
                "source": part["source"],
                "section_title": part.get("section_title", ""),
                "chunk_index": i,
                **{k: v for k, v in part.items()
                   if k not in ("text", "page_number", "section_type", "source", "section_title")},
            }
        ))

    content_hash = hashlib.sha256(
        ("|||".join(full_text_parts)).encode("utf-8")
    ).hexdigest()
    pdf_meta = _extract_pdf_metadata(result)
    return documents, content_hash, pdf_meta


def _classify_section(text: str, page_num: int) -> str:
    """
    根据文本首行 + 页码判断段落类型（用于 chunk 权重和检索优先级）。
    
    设计原则：
    - 必须匹配行首的中文/阿拉伯数字 section 标记
    - 避免 "1" "2" "3" 等单独数字误触发（会匹配页码/图号/表号）
    - 中文 numeral section 标记必须出现在行首（或整行就是一个数字+标题）
    - 政策报告格式 "准见·策言3" 视为 result（因为是策言/建议类）
    """
    import re
    first_line = text.strip().split('\n')[0]
    first_lower = first_line.lower()

    # ── 摘要 ──────────────────────────────────────────
    if page_num == 1 and any(kw in first_lower for kw in ['摘要', 'abstract', '概要', '提要']):
        return "abstract"

    # ── 结论（最具体，优先判断）─────────────────────
    conclusion_patterns = ['结论', 'conclusion', '总结', '主要发现', '研究发现', '政策启示', '研究结论']
    if any(kw in first_lower for kw in conclusion_patterns):
        return "conclusion"

    # ── 方法（关键词优先，避免被数字误触发）─────────
    method_patterns = ['研究设计', '数据来源', '实证方法', '模型设定', '模型构建', '变量选择',
                       '研究框架', 'method', '实验', '样本选择', '数据说明']
    if any(kw in first_lower for kw in method_patterns):
        return "method"

    # ── 结果（关键词优先）───────────────────────────
    result_patterns = ['实证结果', '回归结果', '估计结果', '分析结果', '研究结果',
                       '稳健性', '内生性', '异质性分析', '影响效应']
    if any(kw in first_lower for kw in result_patterns):
        return "result"

    # ── 引言/背景 ───────────────────────────────────
    intro_patterns = ['引言', '前言', '背景', '研究现状', '文献综述', '理论框架',
                      '问题的提出', '研究动机', 'introduction']
    if any(kw in first_lower for kw in intro_patterns):
        return "introduction"

    # ── 讨论 ────────────────────────────────────────
    discussion_patterns = ['讨论', 'discussion', '政策建议', '启示与建议']
    if any(kw in first_lower for kw in discussion_patterns):
        return "discussion"

    # ── 中文数字 section 标记（行首匹配，防止误触发）──
    # 匹配 "一、", "二、", "三、" 等在行首（或整行开头）
    # 但排除 "表1", "图2", "第3页" 等非标题数字
    cn_match = re.match(r'^[一二三四五六七八九十]+[、、]', first_line)
    if cn_match:
        marker = cn_match.group()[:2]  # e.g. "三、"
        # 常见章节 → section 映射（基于中文论文惯例）
        section_map = {
            '一、': 'introduction',  # 一、问题提出 / 文献综述
            '二、': 'introduction',  # 二、理论背景
            '三、': 'method',        # 三、研究设计 / 实证方法
            '四、': 'result',        # 四、实证结果
            '五、': 'discussion',    # 五、结论与讨论
            '六、': 'conclusion',    # 六、研究结论
            '七、': 'conclusion',
            '八、': 'conclusion',
        }
        return section_map.get(marker, 'body')

    # ── 阿拉伯数字 section 标记（行首，\d+. 或 \d+、）──
    # e.g. "1. 引言", "2. 研究设计"
    arabic_match = re.match(r'^[0-9]+[.、\s]', first_line)
    if arabic_match:
        num_str = re.match(r'^[0-9]+', first_line).group()
        num = int(num_str)
        # 阿拉伯数字 section（通常：1=引言, 2=方法, 3=结果, 4=讨论, 5=结论）
        section_map = {1: 'introduction', 2: 'method', 3: 'result', 4: 'discussion', 5: 'conclusion'}
        return section_map.get(num, 'body')

    # ── 参考文献 ────────────────────────────────────
    ref_patterns = ['参考文献', 'reference', '引用', 'bibliography', '资料来源']
    if any(kw in first_lower for kw in ref_patterns):
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
        对原始文档做两级级联切分：
        1. 先切召回块（按语义段落，较大粒度）
        2. 从召回块切证据块（更细粒度，确保 evidence ⊂ recall）
        3. 合并，保留来源关系

        Fix: 证据块从 recall chunks 切分（非独立切分原文档），
             消除重复 content，ChromaDB 写入量减半。
        """
        recall_chunks = self.recall_splitter.split_documents(documents)
        # 级联切分：evidence 从 recall 块切出，确保子集关系无重复
        evidence_chunks = self.evidence_splitter.split_documents(recall_chunks)

        all_chunks = []

        # 合并，设置 chunk_type；evidence 记录来自哪个 recall chunk
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
            # 记录父 recall chunk 的索引（用于溯源）
            # evidence_splitter 返回的 Document.metadata 仍保留 source chunk 信息
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
    logger.info(f"[{paper_id}] 开始 Docling 解析 PDF...")
    raw_docs, content_hash, pdf_meta = parse_pdf_with_fallback(pdf_path)
    logger.info(f"[{paper_id}] Docling 解析完成：{len(raw_docs)} 个原始单元（正文+表格+参考文献）")

    if not raw_docs:
        raise ValueError(f"PDF 解析失败，文档为空: {pdf_path}")

    # 2. 过滤噪音：参考文献 / 元数据 / 页眉页脚 / DOI 行
    import re
    def _is_noise(doc: Document) -> bool:
        text = doc.page_content
        meta = doc.metadata or {}
        stype = meta.get("section_type", "")

        # 丢弃参考文献章节
        if stype == "reference":
            return True

        # 丢弃过短的元数据行（DOI / 文章编号 / 收稿日期 / 作者简介等）
        if len(text.strip()) < 20:
            # DOI 行
            if re.search(r'10\.\d{4,}/\S+', text):
                return True
            # 文献标志码 / 文章编号
            if re.search(r'[文献标志码文章编号中图分类号]+', text):
                return True
            # 收稿日期 / 作者简介单行
            if re.search(r'^[收稿日期作者简介]+', text):
                return True
            # 页码/期号行（纯数字+符号）
            if re.match(r'^\s*\d+\s*[年期号页]+\s*\d*\s*$', text):
                return True

        # 丢弃全篇为期刊页眉页脚的块（大量含年份+期号+期刊名）
        # 检查是否大量包含 "年第X期" 或 "Vol." 模式
        if len(text) < 200:
            density = len(re.findall(r'(?:\d{4}年|第\d+期|Vol\.|ISSN|LuJie)', text))
            if density >= 2:
                return True

        return False

    raw_docs = [d for d in raw_docs if not _is_noise(d)]
    logger.info(f"[{paper_id}] 噪音过滤完成，剩余 {len(raw_docs)} 个原始单元")

    # 3. 两级分块
    chunker = TwoLevelChunker()
    all_chunks = chunker.chunk(raw_docs)
    logger.info(f"[{paper_id}] 两级 Chunk 完成：{len(all_chunks)} 个 chunks（Recall + Evidence）")

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

    # 写入前先删除该论文的旧 chunks（避免重复累积）
    try:
        vectorstore._collection.delete(where={"paper_id": paper_id})
        logger.info(f"[{paper_id}] 删除旧 chunks")
    except Exception as e:
        logger.warning(f"[{paper_id}] 删除旧 chunks 失败: {e}")

    vectorstore.add_texts(texts=texts, metadatas=metadatas)

    recall_count = sum(1 for m in metadatas if m["chunk_type"] == "recall")
    evidence_count = sum(1 for m in metadatas if m["chunk_type"] == "evidence")

    logger.info(f"[{paper_id}] ✅ 向量写入完成：{recall_count} 召回块 + {evidence_count} 证据块")
    logger.debug(f"[{paper_id}] Collection: {safe_collection_name}")
    logger.debug(f"[{paper_id}] Embedding: {EMBEDDING_MODEL}（1024维）")

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
                logger.debug("[BM25Index] 所有chunks tokenize为空，跳过BM25")
                return
            self.bm25 = BM25Okapi(non_empty)
        except ImportError:
            self.bm25 = None
            logger.info("[BM25Index] rank_bm25 未安装，降级为关键词匹配")
        except ZeroDivisionError:
            self.bm25 = None
            logger.warning("[BM25Index] BM25初始化 ZeroDivisionError（tokenize全空），跳过BM25")

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
    真正混合检索：向量检索 ∪ BM25（全量） → RRF 融合 → 质量加权。

    学术场景必须精确匹配专业术语（"DID"、"OLS"、"碳排放权交易"），
    纯向量无法可靠捕捉这些精确词项。

    策略：向量 Top(k*3) ∪ BM25 Top(k*3) → RRF(k=60) 融合 → section/page 加权

    Fix: BM25 改为在全量 chunks 上构建（而非仅在向量候选集上），
         消除偏差累积，实现向量 + BM25 真正独立融合。
    """
    import re

    # ── 1. 获取全量 chunks（用于 BM25 全量索引）────────
    # 分批获取避免大集合内存压力，同时确保拿到所有 chunks
    all_chunk_dicts: list[dict] = []
    batch_size = 5000
    offset = 0
    while True:
        batch = vectorstore._collection.get(
            limit=batch_size, offset=offset,
            include=["documents", "metadatas"]
        )
        if not batch or not batch.get("ids"):
            break
        for cid, doc, meta in zip(
            batch["ids"], batch["documents"], batch["metadatas"]
        ):
            if doc and meta:
                all_chunk_dicts.append({
                    "chunk_id": cid,
                    "content": doc,
                    "metadata": dict(meta),
                })
        offset += batch_size
        if len(batch["ids"]) < batch_size:
            break

    if not all_chunk_dicts:
        return []

    # ── 2. BM25 全量索引（独立于向量检索）──────────────
    bm25_index = BM25Index(all_chunk_dicts)
    bm25_all_results = bm25_index.search(query, top_k=min(len(all_chunk_dicts), k * 5))
    # 建立 chunk_id → bm25_rank/bm25_score 映射
    bm25_map: dict[str, dict] = {}
    if bm25_all_results:
        max_bm = bm25_all_results[0][1] or 1.0
        for rank, (idx, score) in enumerate(bm25_all_results, 1):
            cid = all_chunk_dicts[idx]["chunk_id"]
            bm25_map[cid] = {"bm25_rank": rank, "bm25_score": score / max_bm}

    # ── 3. 向量检索候选 ───────────────────────────────
    query_vec = query_embedding_fn.embed_query(query)
    vector_results = vectorstore._collection.query(
        query_embeddings=[query_vec],
        n_results=k * 3,
        include=["documents", "metadatas", "distances"],
    )

    from langchain_core.documents import Document
    candidates: dict[str, dict] = {}
    docs = vector_results.get("documents", [[]])[0]
    metas = vector_results.get("metadatas", [[]])[0]
    dists = vector_results.get("distances", [[]])[0]
    for rank, (doc, meta, dist) in enumerate(zip(docs, metas, dists), 1):
        if meta is None:
            continue  # skip chunks without metadata
        chunk_id = f"{meta.get('paper_id','')}-{meta.get('chunk_index', rank)}"
        d = Document(page_content=doc, metadata=meta)
        d.metadata["_vector_rank"] = rank
        d.metadata["_vector_score"] = 1.0 - dist
        candidates[chunk_id] = {"doc": d, "vector_rank": rank}

    if not candidates:
        # 兜底：直接用 BM25 结果
        for cid, bm_info in sorted(bm25_map.items(), key=lambda x: x[1]["bm25_rank"]):
            candidates[cid] = {
                "doc": Document(page_content=all_chunk_dicts[bm25_all_results[bm_info["bm25_rank"] - 1][0]]["content"],
                                 metadata=all_chunk_dicts[bm25_all_results[bm_info["bm25_rank"] - 1][0]]["metadata"]),
                "vector_rank": 999,
                "bm25_rank": bm_info["bm25_rank"],
                "bm25_score": bm_info["bm25_score"],
            }
        if not candidates:
            return []

    # ── 4. 向量检索结果注入 BM25 分数 ──────────────────
    # 未命中向量的 BM25 命中 Chunk 也加入候选（独立发现）
    for cid, bm_info in bm25_map.items():
        if cid not in candidates:
            for cd in all_chunk_dicts:
                if cd["chunk_id"] == cid:
                    candidates[cid] = {
                        "doc": Document(page_content=cd["content"], metadata=cd["metadata"]),
                        "vector_rank": 999,
                        "bm25_rank": bm_info["bm25_rank"],
                        "bm25_score": bm_info["bm25_score"],
                    }
                    break

    # 给向量候选注入 BM25 分数
    for cid, c in candidates.items():
        if cid in bm25_map:
            c["bm25_rank"] = bm25_map[cid]["bm25_rank"]
            c["bm25_score"] = bm25_map[cid]["bm25_score"]

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
    section_filter: str | None = None,
) -> list[dict]:
    """
    语义检索：向量化 → ChromaDB → 混合检索 → 返回相关 chunks

    Args:
        section_filter: 可选，如 "introduction"/"methodology"/"conclusion"，
                       只召回匹配 section_type 的 chunks
    """
    # ── Query 扩展：针对学术 RAG 的词项补充 ──────────────────────
    # 当用户问及"方法/数据/模型"时，自动补充领域术语，提升召回率
    QUERY_EXPANSION = {
        "method": ["研究设计", "模型设定", "CGE", "GTAP", "计量模型", "回归分析", "数据来源", "样本", "变量"],
        "data": ["数据库", "数据来源", "样本", "统计年鉴", "年鉴数据", "调查数据"],
        "result": ["回归结果", "实证结果", "估计结果", "回归系数", "显著性", "稳健性检验", "内生性检验"],
        "conclusion": ["研究结论", "政策启示", "研究结论与建议", "主要发现"],
    }
    expanded_query = query
    query_lower = query.lower()
    for intent, terms in QUERY_EXPANSION.items():
        if any(kw in query_lower for kw in [intent, "方法", "数据", "模型", "变量", "结果", "结论"]):
            for term in terms:
                if term.lower() not in query_lower:
                    expanded_query += f" {term}"

    safe_collection_name = re.sub(r"[^a-zA-Z0-9_]", "_", collection_name)
    embedding_fn = get_chroma_embedding_fn()

    vectorstore = Chroma(
        collection_name=safe_collection_name,
        embedding_function=embedding_fn,
        persist_directory=persist_directory,
    )

    # 扩大召回倍数（确保 citation 去重后仍有足够片段）：
    # k=5 → retrieve_k=30 → RRF 输出30条 → citation 去重(每篇3条)后 ≈ 6-9条
    retrieve_k = top_k * 6 if section_filter else top_k * 6
    # 用扩展 query 做检索（BM25 + 向量都用扩展版本）
    try:
        hybrid_results = hybrid_search(vectorstore, expanded_query, embedding_fn, k=retrieve_k)
    except Exception as e:
        logger.warning(f"[{safe_collection_name}] 检索失败 ({e})，fallback 到 user_old_bosstest")
        hybrid_results = []

    # Fallback：如果当前用户 collection 为空或出错，尝试旧 collection（user_old_bosstest）
    if not hybrid_results and safe_collection_name.startswith("papers_"):
        logger.debug(f"[{safe_collection_name}] 无检索结果，fallback 到 user_old_bosstest")
        vectorstore_old = Chroma(
            collection_name="user_old_bosstest",
            embedding_function=embedding_fn,
            persist_directory=persist_directory,
        )
        try:
            hybrid_results = hybrid_search(vectorstore_old, expanded_query, embedding_fn, k=retrieve_k)
        except Exception as e2:
            logger.warning(f"[user_old_bosstest] fallback 也失败: {e2}")
            hybrid_results = []

    chunks = []
    for item in hybrid_results:
        r = item["doc"]
        chunk_section = r.metadata.get("section_type", "body")
        if section_filter and chunk_section != section_filter:
            continue
        chunks.append({
            "content": r.page_content,
            "paper_id": r.metadata.get("paper_id", ""),
            "title": r.metadata.get("title", ""),
            "authors": r.metadata.get("authors", ""),
            "year": r.metadata.get("year"),
            "journal": r.metadata.get("journal", ""),
            "doi": r.metadata.get("doi", ""),
            "chunk_type": r.metadata.get("chunk_type", "recall"),
            "section_type": chunk_section,
            "section_title": r.metadata.get("section_title", ""),
            "chunk_index": r.metadata.get("chunk_index", 0),
            "page_number": r.metadata.get("page_number", 0),
            "text": r.metadata.get("text", ""),
            "combined_score": round(item.get("combined_score", item.get("vector_score", 1.0)), 3),
        })
        if len(chunks) >= top_k:
            break

    return chunks
