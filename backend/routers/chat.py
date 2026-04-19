"""
Router: 问答 — /chat, /chat/stream
"""
import json, time, asyncio
from typing import Literal
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from chat import (
    generate_answer_with_self_eval as generate_answer,
    MiniMaxChatClient,
    build_context,
    SYSTEM_PROMPT_DEFAULT,
    SYSTEM_PROMPT_METHODOLOGY,
    SYSTEM_PROMPT_SURVEY,
)
from chat import evaluate_answer as chat_evaluate_answer
from state import users_db, get_users_db
from data import get_paper, get_user_papers, get_folder_papers
from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID, CHAT_MODEL
from pipeline import search_chunks
from feedback import get_feedback_store, SCORE_THRESHOLD
from routers.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    question: str
    collection_name: str | None = None
    top_k: int = 8
    mode: Literal["default", "methodology", "survey"] = "default"
    paper_ids: list[str] | None = None
    folder_ids: list[str] | None = None  # Phase 0.8: 可限定搜索范围

class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]
    meta: dict = {}


def _ready_papers(user, folder_ids=None):
    # Phase 0.8: 从 papers_db 而非 user.papers 获取
    if folder_ids:
        papers = []
        for fid in folder_ids:
            papers.extend(get_folder_papers(fid))
    else:
        papers = get_user_papers(user["user_id"])
    return [p["paper_id"] for p in papers if p.get("status") == "ready"]


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    if not req.question or not req.question.strip():
        raise HTTPException(400, "问题不能为空")
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    collection = req.collection_name or user["collection"]
    t0 = time.monotonic()

    ready = _ready_papers(user, req.folder_ids)
    if not ready:
        return ChatResponse(
            answer="你的论文库还没有已索引的论文，请先上传 PDF 并等待索引完成。",
            citations=[],
            meta={"mode": req.mode, "paper_count": 0, "chunk_count": 0},
        )

    target_pids = set(ready)
    if req.paper_ids:
        target_pids = target_pids & set(req.paper_ids)
        if not target_pids:
            return ChatResponse(
                answer="指定的论文不在你的论文库中或尚未索引。",
                citations=[],
                meta={"mode": req.mode, "paper_count": 0, "chunk_count": 0},
            )

    feedback_store = get_feedback_store()
    similar = feedback_store.find_similar(req.question)
    has_similar_history = len(similar) > 0

    # 检索量：默认 top_k=5 → 检索 30 条 → 去重后 6-15 条 citation 片段
    effective_top_k = max(req.top_k * 6, 30) if req.mode == "survey" else req.top_k

    t1 = time.monotonic()
    chunks = await search_chunks(
        query=req.question,
        collection_name=collection,
        top_k=effective_top_k,
    )
    embedding_ms = (time.monotonic() - t1) * 1000

    if req.paper_ids:
        chunks = [c for c in chunks if c["paper_id"] in target_pids]

    if not chunks:
        total_ms = (time.monotonic() - t0) * 1000
        return ChatResponse(
            answer="抱歉，我在你的论文库中没有找到相关内容。",
            citations=[],
            meta={"mode": req.mode, "paper_count": 0, "chunk_count": 0},
        )

    t2 = time.monotonic()
    try:
        answer_text, citations, meta = await generate_answer(
            question=req.question,
            chunks=chunks,
            mode=req.mode,
        )
        llm_ms = (time.monotonic() - t2) * 1000
        total_ms = (time.monotonic() - t0) * 1000

        self_eval = meta.get("self_eval", {})
        score = self_eval.get("total", 100)

        quality_warning = None
        if score < SCORE_THRESHOLD:
            feedback_store.add_failed(
                question=req.question,
                answer=answer_text,
                scores=self_eval,
                chunks_count=len(chunks),
                retrieval_strategy="default",
            )
            quality_warning = f"⚠️ 答案质量偏低（{score}/100），已记录用于改进检索策略。"

        meta["timing_ms"] = {"embedding": round(embedding_ms), "llm": round(llm_ms), "total": round(total_ms)}
        if quality_warning:
            meta["quality_warning"] = quality_warning

        return ChatResponse(answer=answer_text, citations=citations, meta=meta)

    except Exception as e:
        total_ms = (time.monotonic() - t0) * 1000
        err_msg = str(e)
        is_timeout = any(kw in err_msg.lower() for kw in ["timeout", "timed out", "connection", "网络", "超时"])
        is_minimax_fail = any(kw in err_msg for kw in ["MiniMax", "429", "502", "503", "504", "529"])
        if is_timeout or is_minimax_fail or "read timeout" in err_msg.lower():
            return ChatResponse(
                answer="⚠️ AI 服务响应超时（MiniMax 引擎不稳定），请稍后重试。",
                citations=[],
                meta={"mode": req.mode, "error": "timeout", "retrieval_ms": round(embedding_ms),
                      "timing_ms": {"embedding": round(embedding_ms), "total": round(total_ms)}},
            )
        return ChatResponse(
            answer=f"⚠️ 生成答案时遇到问题：{err_msg[:100]}",
            citations=[],
            meta={"mode": req.mode, "error": "unknown", "timing_ms": {"embedding": round(embedding_ms), "total": round(total_ms)}},
        )


@router.post("/stream")
async def chat_stream(req: ChatRequest, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    if not req.question or not req.question.strip():
        raise HTTPException(400, "问题不能为空")
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    collection = req.collection_name or user["collection"]
    ready = _ready_papers(user, req.folder_ids)
    if not ready:
        async def empty():
            yield "data: " + json.dumps({"type": "done", "answer": "你的论文库还没有已索引的论文。"}) + "\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    target_pids = set(ready)
    if req.paper_ids:
        target_pids = target_pids & set(req.paper_ids)

    t0 = time.monotonic()
    chunks = await search_chunks(
        query=req.question,
        collection_name=collection,
        top_k=req.top_k * 6,  # 检索 6×top_k，确保去重后仍有足够片段
    )
    if req.paper_ids:
        chunks = [c for c in chunks if c["paper_id"] in target_pids]
    chunks = chunks[:req.top_k * 12]  # 保留足够多片段（5→60条），citation去重后仍有多片段
    embedding_ms = (time.monotonic() - t0) * 1000

    if not chunks:
        async def empty():
            yield "data: " + json.dumps({"type": "done", "answer": "抱歉，我在你的论文库中没有找到相关内容。"}) + "\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    if req.mode == "methodology":
        system_prompt = SYSTEM_PROMPT_METHODOLOGY
        context = build_context(chunks)
    elif req.mode == "survey":
        theme = req.question
        context_blocks = [f"[片段{i+1}] {c['content']}" for i, c in enumerate(chunks[:15])]
        context = "\n\n".join(context_blocks)
        system_prompt = SYSTEM_PROMPT_SURVEY.format(theme=theme)
    else:
        system_prompt = SYSTEM_PROMPT_DEFAULT
        context = build_context(chunks)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"问题：{req.question}\n\n{context}"},
    ]

    async def stream_generator():
        import queue, threading
        try:
            yield "data: " + json.dumps({"type": "start", "embedding_ms": round(embedding_ms)}) + "\n\n"

            # Run synchronous token stream in a background thread so we don't block the async event loop
            token_queue: queue.Queue = queue.Queue()
            done_sentinel = object()

            def token_producer():
                try:
                    client = MiniMaxChatClient(api_key=MINIMAX_API_KEY, group_id=MINIMAX_GROUP_ID)
                    for token in client.stream_chat(messages=messages, model=CHAT_MODEL, max_tokens=4096, temperature=0.3):
                        token_queue.put(token)
                except Exception as e:
                    token_queue.put(e)
                finally:
                    token_queue.put(done_sentinel)

            thread = threading.Thread(target=token_producer, daemon=True)
            thread.start()

            full_answer = ""
            while True:
                item = await asyncio.to_thread(token_queue.get)
                if item is done_sentinel:
                    break
                if isinstance(item, Exception):
                    raise item
                full_answer += item
                yield "data: " + json.dumps({"type": "token", "content": item}) + "\n\n"

            cite_set = {}
            for c in chunks:
                pid = c["paper_id"]
                if pid not in cite_set:
                    cite_set[pid] = {
                        "paper_id": pid,
                        "title": c.get("title") or c.get("paper_id", "未知论文"),
                        "authors": c.get("authors", ""),
                        "year": c.get("year") or "",
                        "journal": c.get("journal", ""),
                        "section_type": c.get("section_type", ""),
                        "section_title": c.get("section_title", ""),
                        "page_number": c.get("page_number", 0),
                        "content": (c.get("content") or c.get("text") or "")[:200],
                    }
            citations = list(cite_set.values())
            quality_warning = None
            try:
                self_eval = chat_evaluate_answer(req.question, full_answer, chunks)
                score = self_eval.get("total", 100)
                if score < SCORE_THRESHOLD:
                    get_feedback_store().add_failed(
                        question=req.question,
                        answer=full_answer,
                        scores=self_eval,
                        chunks_count=len(chunks),
                        retrieval_strategy="default",
                    )
                    dim_str = " / ".join([
                        f"{k}={v}" for k, v in self_eval.items()
                        if k not in ("raw_evaluation", "json_mode") and v is not None
                    ])
                    quality_warning = f"⚠️ 质量 {score}/100（{dim_str}），已记录用于改进"
            except Exception:
                pass
            yield "data: " + json.dumps({
                "type": "done",
                "answer": full_answer,
                "citations": citations,
                "quality_warning": quality_warning,
            }) + "\n\n"
        except Exception as e:
            yield "data: " + json.dumps({"type": "error", "message": str(e)}) + "\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")
