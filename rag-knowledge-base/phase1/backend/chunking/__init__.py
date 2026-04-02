"""
Phase 1 — 两级 Chunk 设计

Recall Chunks（召回块）：400-800 tokens，按小节切分，用于初次检索
Evidence Chunks（证据块）：150-350 tokens，按段落/结论/方法切分，用于最终引用
"""
import re, json
from dataclasses import dataclass, field
from typing import Literal
from . import config

# ─── tiktoken token 计数（轻量）──────────────────────────

def count_tokens(text: str) -> int:
    """估算中英文混合文本的 token 数（经验公式）"""
    # 中文：1 token ≈ 0.5 字符（经验值，BM25 等场景够用）
    # 英文：1 token ≈ 4 字符
    # 留一定余量
    chinese = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    english = len(text) - chinese
    return int(chinese * 1.5 + english / 4) + 10


@dataclass
class RecallChunk:
    chunk_id: str
    paper_id: str
    section_id: str | None
    chunk_text: str
    token_count: int
    page_range: str
    order: int


@dataclass
class EvidenceChunk:
    chunk_id: str
    paper_id: str
    recall_chunk_id: str
    section_id: str | None
    chunk_text: str
    token_count: int
    chunk_type: Literal["body", "table", "figure", "abstract", "conclusion", "method"]
    page_range: str


# ─── 一级 Chunk：Recall Chunk（按小节切分）────────────────

def split_into_recall_chunks(
    paper_id: str,
    sections: list[dict],  # [{section_id, title, path, order, page_start, page_end, paragraphs}]
    target_tokens: int = 600,
    overlap_tokens: int = 80,
) -> list[RecallChunk]:
    """
    按小节/段落边界切分 recall chunks
    - 目标 400-800 tokens
    - 重叠 80 tokens（保持上下文）
    """
    chunks = []

    for sec in sections:
        sec_text = "\n".join(sec.get("paragraphs", []))
        if not sec_text.strip():
            continue

        # 估算总 token 数
        total_tokens = count_tokens(sec_text)
        page_range = ""
        if sec.get("page_start") and sec.get("page_end"):
            page_range = f"{sec['page_start']}-{sec['page_end']}"

        # 如果 section 本身就小，直接作为一个 chunk
        if total_tokens <= target_tokens:
            chunk_id = f"{paper_id}-rc-{sec['order']:03d}"
            chunks.append(RecallChunk(
                chunk_id=chunk_id,
                paper_id=paper_id,
                section_id=sec.get("section_id"),
                chunk_text=sec_text,
                token_count=total_tokens,
                page_range=page_range,
                order=sec["order"],
            ))
            continue

        # 大 section 需要拆分成多个 chunks
        paragraphs = sec.get("paragraphs", [])
        current_text = ""
        current_tokens = 0
        sub_order = 0

        for para in paragraphs:
            para_tokens = count_tokens(para)
            # 如果单个段落就超过 target，直接截断
            if para_tokens > target_tokens:
                if current_text:
                    chunks.append(_make_recall_chunk(
                        paper_id, sec, current_text, current_tokens,
                        page_range, sec["order"], sub_order
                    ))
                    sub_order += 1
                    current_text = ""
                    current_tokens = 0
                # 截断段落（取前 target_tokens）
                truncated = _truncate_to_tokens(para, target_tokens)
                chunks.append(_make_recall_chunk(
                    paper_id, sec, truncated, target_tokens,
                    page_range, sec["order"], sub_order
                ))
                sub_order += 1
                continue

            if current_tokens + para_tokens <= target_tokens:
                current_text += "\n" + para
                current_tokens += para_tokens
            else:
                # 触发切分，加当前 chunk
                chunks.append(_make_recall_chunk(
                    paper_id, sec, current_text, current_tokens,
                    page_range, sec["order"], sub_order
                ))
                sub_order += 1

                # 重叠部分（取最后 overlap_tokens 个字符）
                overlap_text = _get_overlap_text(current_text, overlap_tokens)
                current_text = overlap_text + "\n" + para
                current_tokens = count_tokens(current_text)

        # 处理剩余
        if current_text.strip():
            chunks.append(_make_recall_chunk(
                paper_id, sec, current_text, current_tokens,
                page_range, sec["order"], sub_order
            ))

    return chunks


def _make_recall_chunk(
    paper_id: str, sec: dict, text: str, token_count: int,
    page_range: str, order: int, sub_order: int
) -> RecallChunk:
    chunk_id = f"{paper_id}-rc-{order:03d}-{sub_order:02d}"
    return RecallChunk(
        chunk_id=chunk_id,
        paper_id=paper_id,
        section_id=sec.get("section_id"),
        chunk_text=text.strip(),
        token_count=token_count,
        page_range=page_range,
        order=order * 100 + sub_order,
    )


def _get_overlap_text(text: str, overlap_tokens: int) -> str:
    """获取文本末尾用于重叠的部分"""
    chars_for_tokens = overlap_tokens * 3  # 粗略估算
    if len(text) <= chars_for_tokens:
        return text
    return text[-chars_for_tokens:]


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """截断文本到指定 token 数"""
    target_chars = max_tokens * 3
    if len(text) <= target_chars:
        return text
    return text[:target_chars]


# ─── 二级 Chunk：Evidence Chunk（从 Recall Chunk 切）────────

EVIDENCE_TYPES = {
    "method": ["方法", "methodology", "method", "研究设计", "data", "样本", "变量"],
    "conclusion": ["结论", "结论与讨论", "主要发现", "findings", "results", "结论与政策启示"],
    "abstract": ["摘要", "abstract"],
    "table": ["表", "table", "tab.", "图", "figure", "fig."],
}


def split_into_evidence_chunks(
    paper_id: str,
    recall_chunks: list[RecallChunk],
    target_tokens: int = 250,
) -> list[EvidenceChunk]:
    """
    从 recall chunks 切分出 evidence chunks
    - 目标 150-350 tokens
    - 自动识别 chunk_type（method / conclusion / table / body）
    """
    evidence_chunks = []

    for rc in recall_chunks:
        paragraphs = rc.chunk_text.split("\n")
        current_text = ""
        current_tokens = 0
        chunk_type = _classify_chunk_type(rc.chunk_text)

        for para in paragraphs:
            para_tokens = count_tokens(para)
            new_type = _classify_chunk_type(para)
            # 类型变化时强制切分
            force_split = (new_type != chunk_type and new_type in ("method", "conclusion"))

            if current_tokens + para_tokens <= target_tokens and not force_split:
                current_text += "\n" + para
                current_tokens += para_tokens
            else:
                if current_text.strip():
                    evidence_chunks.append(_make_evidence_chunk(
                        paper_id, rc, current_text, current_tokens,
                        chunk_type, rc.order
                    ))
                current_text = para
                current_tokens = para_tokens
                chunk_type = new_type

        if current_text.strip():
            evidence_chunks.append(_make_evidence_chunk(
                paper_id, rc, current_text, current_tokens,
                chunk_type, rc.order
            ))

    return evidence_chunks


def _classify_chunk_type(text: str) -> Literal["body", "method", "conclusion", "abstract", "table", "figure"]:
    """根据关键词判断 chunk 类型"""
    text_lower = text.lower()
    for etype, keywords in EVIDENCE_TYPES.items():
        if any(k.lower() in text_lower for k in keywords):
            return etype  # type: ignore
    return "body"


def _make_evidence_chunk(
    paper_id: str,
    rc: RecallChunk,
    text: str,
    token_count: int,
    chunk_type: str,
    order: int,
) -> EvidenceChunk:
    import uuid
    chunk_id = f"{paper_id}-ec-{uuid.uuid4().hex[:8]}"
    return EvidenceChunk(
        chunk_id=chunk_id,
        paper_id=paper_id,
        recall_chunk_id=rc.chunk_id,
        section_id=rc.section_id,
        chunk_text=text.strip(),
        token_count=token_count,
        chunk_type=chunk_type,  # type: ignore
        page_range=rc.page_range,
    )


# ─── 主入口 ─────────────────────────────────────────────

def chunk_document(
    paper_id: str,
    sections: list[dict],
) -> tuple[list[RecallChunk], list[EvidenceChunk]]:
    """
    两级 chunk 流水线
    返回 (recall_chunks, evidence_chunks)
    """
    recall_chunks = split_into_recall_chunks(paper_id, sections)
    evidence_chunks = split_into_evidence_chunks(paper_id, recall_chunks)
    return recall_chunks, evidence_chunks
