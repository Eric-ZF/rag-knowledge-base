"""
Phase 0.6 — FastAPI 入口
papers_db + users_db 全部持久化为 JSON，重启不丢失。
"""

import os, re, uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import create_access_token, verify_token
from config import validate_minimax_chat_config, MINIMAX_API_KEY, MINIMAX_GROUP_ID, CHROMADB_DIR
from data import (
    init_papers, init_users,
    get_paper, upsert_paper, update_paper, delete_paper,
    get_user_papers,
)
from pipeline import process_pdf, search_chunks
from chat import generate_answer

# ─── 启动验证 ─────────────────────────────────────────
try:
    validate_minimax_chat_config()
except RuntimeError as e:
    print(f"⚠️  {e}")

# ─── 数据层初始化（从 JSON 恢复）─────────────────────
init_papers()
users_db, users_by_email = init_users()

# ─── FastAPI ─────────────────────────────────────────
app = FastAPI(
    title="RAG 学术知识库 — Phase 0.6",
    version="0.6.0",
    debug=os.getenv("DEBUG", "true").lower() == "true",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Pydantic 模型 ────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    collection_name: str | None = None
    top_k: int = 5

class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]

class PaperUploadResponse(BaseModel):
    paper_id: str
    title: str
    status: str

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str


# ─── 健康检查 ─────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "phase": "phase0.6",
        "model": "MiniMax-M2 + local embedding",
        "minimax_configured": bool(MINIMAX_API_KEY and MINIMAX_GROUP_ID),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── 认证 ─────────────────────────────────────────────
@app.post("/auth/register")
async def register(req: RegisterRequest):
    email, password = req.email, req.password
    if email in users_by_email:
        raise HTTPException(400, "邮箱已注册")
    user_id = str(uuid.uuid4())
    collection_name = f"user_{user_id.replace('-', '_')}"
    user_record = {
        "email": email,
        "user_id": user_id,
        "password": password,
        "plan": "free",
        "collection": collection_name,
    }
    users_db[user_id] = user_record
    users_by_email[email] = user_record
    _save_users()
    return {"user_id": user_id, "collection": collection_name}


@app.post("/auth/login")
async def login(req: LoginRequest):
    email, password = req.email, req.password
    user = users_by_email.get(email)
    if not user or user["password"] != password:
        raise HTTPException(401, "邮箱或密码错误")
    token = create_access_token({"sub": email, "user_id": user["user_id"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "collection": user["collection"],
        "plan": user["plan"],
    }


def _save_users() -> None:
    from data import _save_users as _su
    _su(users_db)


def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "未提供认证信息")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(401, "无效的认证方式")
        payload = verify_token(token)
        email, user_id = payload["sub"], payload.get("user_id")
        if not user_id or user_id not in users_db:
            raise HTTPException(401, "用户不存在")
        return user_id, users_db[user_id]
    except (ValueError, KeyError):
        raise HTTPException(401, "无效的 Token")


# ─── 后台任务：处理 PDF ───────────────────────────────
def _process_pdf_background(paper_id: str, tmp_path: str, collection: str, title: str):
    try:
        import asyncio
        result = asyncio.run(process_pdf(
            pdf_path=tmp_path,
            paper_id=paper_id,
            collection_name=collection,
            title=title,
        ))
        update_paper(paper_id, status="ready", chunks_count=result["chunks_count"])
        print(f"[{paper_id}] ✅ 索引完成，{result['chunks_count']} chunks")
    except Exception as e:
        update_paper(paper_id, status="error", error=str(e))
        print(f"[{paper_id}] ❌ 索引失败: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─── PDF 上传 ────────────────────────────────────────
@app.post("/papers/upload", response_model=PaperUploadResponse)
async def upload_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_info: tuple = Depends(get_current_user),
):
    user_id, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 文件")

    MAX_FILE_SIZE = 50 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(413, f"文件大小超过限制（最大 50MB），当前: {len(content)//1024//1024}MB")

    if user["plan"] == "free" and len(user["papers"]) >= 20:
        raise HTTPException(429, "免费用户论文上限 20 篇")

    paper_id = str(uuid.uuid4())
    title = file.filename.replace(".pdf", "").strip()

    tmp_path = f"/tmp/{paper_id}.pdf"
    Path(tmp_path).write_bytes(content)

    upsert_paper(paper_id, {
        "paper_id": paper_id,
        "user_id": user_id,
        "title": title,
        "status": "processing",
        "chunks_count": None,
        "collection": user["collection"],
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
    })
    user["papers"].append(paper_id)
    _save_users()

    background_tasks.add_task(_process_pdf_background, paper_id, tmp_path, user["collection"], title)
    return PaperUploadResponse(paper_id=paper_id, title=title, status="processing")


@app.get("/papers/{paper_id}/status")
async def paper_status(paper_id: str, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")
    return {
        "paper_id": paper_id,
        "title": p["title"],
        "status": p["status"],
        "chunks_count": p.get("chunks_count"),
        "error": p.get("error"),
    }


@app.get("/papers")
async def list_papers(user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    return [
        {
            "paper_id": pid,
            "title": p["title"],
            "status": p["status"],
            "chunks_count": p.get("chunks_count"),
        }
        for pid in user["papers"]
        if (p := get_paper(pid))
    ]


@app.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    p = get_paper(paper_id)
    if not p or p["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")
    if p["status"] == "processing":
        raise HTTPException(409, "论文正在处理中，无法删除")

    # 从 ChromaDB 删除 chunks
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMADB_DIR)
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", p["collection"])
        col = client.get_collection(safe_name)
        results = col.get(where={"paper_id": paper_id})
        if results["ids"]:
            col.delete(ids=results["ids"])
            print(f"[{paper_id}] 🗑️ 删除 {len(results['ids'])} chunks")
    except Exception as e:
        print(f"[{paper_id}] ⚠️ ChromaDB 删除失败: {e}")

    user["papers"].remove(paper_id)
    _save_users()
    delete_paper(paper_id)
    return {"ok": True, "paper_id": paper_id, "title": p["title"]}


# ─── RAG 问答 ─────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    collection = req.collection_name or user["collection"]

    # 只查询 status=ready 的论文
    ready = [
        pid for pid in user["papers"]
        if (p := get_paper(pid)) and p["status"] == "ready"
    ]
    if not ready:
        return ChatResponse(
            answer="你的论文库还没有已索引的论文，请先上传 PDF 并等待索引完成。",
            citations=[],
        )

    chunks = await search_chunks(query=req.question, collection_name=collection, top_k=req.top_k)
    if not chunks:
        return ChatResponse(answer="抱歉，我在你的论文库中没有找到相关内容。", citations=[])

    try:
        answer_text, citations = await generate_answer(question=req.question, chunks=chunks)
        return ChatResponse(answer=answer_text, citations=citations)
    except Exception as e:
        raise HTTPException(500, f"生成答案失败: {e}")


@app.get("/me/quota")
async def my_quota(user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    return {
        "plan": user["plan"],
        "papers_used": len(user["papers"]),
        "papers_limit": None if user["plan"] == "pro" else 20,
        "collection": user["collection"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
