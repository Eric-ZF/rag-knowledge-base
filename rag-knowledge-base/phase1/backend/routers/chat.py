"""Phase 1 — 智能问答 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal
from ..generation import (
    generate_answer,
    rewrite_query,
    filter_chunks_by_type,
)
from ..retrieval import hybrid_search
from ..storage import papers as p

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    mode: Literal["default", "survey", "compare"] = "default"
    top_k: int = 8
    year_range: tuple[int, int] | None = None
    language: str | None = None
    methods: list[str] | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]
    mode: str
    latency_ms: int
    chunks_used: int


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # 1. Query 改写
    rewritten = rewrite_query(req.question)

    # 2. 混合检索
    retrieved = hybrid_search(
        query=rewritten,
        top_k=req.top_k * 2,  # 多召回一些，后面过滤
        year_range=req.year_range,
        language=req.language,
        methods=req.methods,
    )

    if not retrieved:
        return ChatResponse(
            answer="抱歉，没有找到与您问题相关的论文证据。请尝试调整检索词或上传更多相关文献。",
            citations=[],
            mode=req.mode,
            latency_ms=0,
            chunks_used=0,
        )

    # 3. 过滤：优先方法/结论 chunks
    filtered = filter_chunks_by_type(retrieved[: req.top_k * 2])

    # 4. 证据约束生成
    result = await generate_answer(
        query=req.question,
        retrieved_chunks=filtered,
        mode=req.mode,
    )

    # 5. 记录 QA 日志
    try:
        p.create_qa_log(
            user_query=req.question,
            rewritten_query=rewritten,
            mode=req.mode,
            retrieved_chunk_ids=[c["chunk_id"] for c in retrieved],
            selected_chunk_ids=[c["chunk_id"] for c in filtered],
            answer_text=result["answer"],
            citation_list=result["citations"],
            latency_ms=result["latency_ms"],
        )
    except Exception:
        pass  # 日志失败不影响主流程

    return ChatResponse(**result)


@router.post("/chat/feedback")
async def chat_feedback(query_id: str, score: int, reason: str = ""):
    """用户反馈"""
    if score < 1 or score > 5:
        raise HTTPException(400, "score must be 1-5")
    p.update_qa_feedback(query_id, score, reason)
    return {"ok": True}
