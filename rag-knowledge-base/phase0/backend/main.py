"""
Phase 0 验证 Sprint — FastAPI 入口
使用 MiniMax M2（Chat）+ 本地 sentence-transformers（Embedding）
"""

import os
import uuid
import asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import create_access_token, verify_token
from config import validate_minimax_chat_config, MINIMAX_API_KEY, MINIMAX_GROUP_ID
from pipeline import process_pdf, search_chunks
from chat import generate_answer

# ─── 环境变量 ─────────────────────────────────────────
load_dotenv()
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# ─── 启动验证 ─────────────────────────────────────────
try:
    validate_minimax_chat_config()
except RuntimeError as e:
    print(f"⚠️  {e}")

# ─── FastAPI ─────────────────────────────────────────
app = FastAPI(
    title="RAG 学术知识库 — Phase 0（MiniMax + 本地 Embedding）",
    version="0.3.0",
    debug=DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 内存存储 ─────────────────────────────────────────
users_db: dict = {}
papers_db: dict = {}  # {paper_id: {user_id, title, status, chunks_count, collection, error}}

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
        "phase": "phase0",
        "model": "MiniMax-M2 + local embedding",
        "minimax_configured": bool(MINIMAX_API_KEY and MINIMAX_GROUP_ID),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── 认证 ─────────────────────────────────────────────
@app.post("/auth/register")
async def register(req: RegisterRequest):
    email = req.email
    password = req.password
    for u in users_db.values():
        if u["email"] == email:
            raise HTTPException(400, "邮箱已注册")
    user_id = str(uuid.uuid4())
    collection_name = f"user_{user_id.replace('-', '_')}"
    users_db[user_id] = {
        "email": email,
        "password": password,
        "plan": "free",
        "papers": [],
        "collection": collection_name,
    }
    return {"user_id": user_id, "collection": collection_name}


@app.post("/auth/login")
async def login(req: LoginRequest):
    email = req.email
    password = req.password
    user = None
    for uid, u in users_db.items():
        if u["email"] == email and u["password"] == password:
            user = u
            break
    if not user:
        raise HTTPException(401, "邮箱或密码错误")
    user_id = next(uid for uid, u in users_db.items() if u["email"] == email)
    token = create_access_token({"sub": email, "user_id": user_id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "collection": user["collection"],
        "plan": user["plan"],
    }


def get_current_user(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(401, "未提供认证信息")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(401, "无效的认证方式")
        payload = verify_token(token)
        email = payload["sub"]
        user_id = payload.get("user_id")
        if not user_id:
            for uid, u in users_db.items():
                if u["email"] == email:
                    user_id = uid
                    break
        if user_id not in users_db:
            raise HTTPException(401, "用户不存在")
        return user_id, users_db[user_id]
    except (ValueError, KeyError):
        raise HTTPException(401, "无效的 Token")


# ─── 后台任务：处理 PDF ───────────────────────────────
def _process_pdf_background(paper_id: str, tmp_path: str, collection: str):
    """
    后台运行的 PDF 处理任务（在线程池中执行，不阻塞事件循环）
    """
    try:
        result = asyncio.run(process_pdf(
            pdf_path=tmp_path,
            paper_id=paper_id,
            collection_name=collection,
        ))
        papers_db[paper_id]["status"] = "ready"
        papers_db[paper_id]["chunks_count"] = result["chunks_count"]
        print(f"[{paper_id}] ✅ 索引完成，{result['chunks_count']} chunks")
    except Exception as e:
        papers_db[paper_id]["status"] = "error"
        papers_db[paper_id]["error"] = str(e)
        print(f"[{paper_id}] ❌ 索引失败: {e}")
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ─── PDF 上传（立即返回，后台处理）──────────────────
@app.post("/papers/upload", response_model=PaperUploadResponse)
async def upload_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_info: tuple = Depends(get_current_user),
):
    """
    上传 PDF 后立即返回，后台异步处理索引
    用 GET /papers/:id/status 轮询进度
    """
    user_id, user = user_info

    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 文件")

    if user["plan"] == "free" and len(user["papers"]) >= 20:
        raise HTTPException(429, "免费用户论文上限 20 篇，请升级到 Pro")

    paper_id = str(uuid.uuid4())
    title = file.filename.replace(".pdf", "")

    tmp_path = f"/tmp/{paper_id}.pdf"
    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    papers_db[paper_id] = {
        "user_id": user_id,
        "title": title,
        "status": "processing",
        "chunks_count": None,
        "collection": user["collection"],
        "error": None,
    }
    user["papers"].append(paper_id)

    # 后台处理，不阻塞请求
    background_tasks.add_task(_process_pdf_background, paper_id, tmp_path, user["collection"])

    return PaperUploadResponse(paper_id=paper_id, title=title, status="processing")


@app.get("/papers/{paper_id}/status")
async def paper_status(paper_id: str, user_info: tuple = Depends(get_current_user)):
    """轮询论文索进状态"""
    _, user = user_info
    if paper_id not in papers_db or papers_db[paper_id]["user_id"] != user_info[0]:
        raise HTTPException(404, "论文不存在")
    p = papers_db[paper_id]
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
            "title": papers_db[pid]["title"],
            "status": papers_db[pid]["status"],
            "chunks_count": papers_db[pid].get("chunks_count"),
        }
        for pid in user["papers"]
        if pid in papers_db
    ]


# ─── RAG 问答 ─────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user_info: tuple = Depends(get_current_user)):
    user_id, user = user_info

    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    # Phase 0 演示模式：允许所有用户使用 RAG
    # if user["plan"] == "free":
    #     raise HTTPException(403, "Free 用户不支持 RAG 问答，请升级到 Pro")

    collection = req.collection_name or user["collection"]

    # 检查是否有已索引的论文
    user_papers = [pid for pid in user["papers"] if pid in papers_db and papers_db[pid]["status"] == "ready"]
    if not user_papers:
        return ChatResponse(
            answer="你的论文库还没有已索引的论文，请先上传 PDF 并等待索引完成。",
            citations=[],
        )

    chunks = await search_chunks(
        query=req.question,
        collection_name=collection,
        top_k=req.top_k,
    )

    if not chunks:
        return ChatResponse(
            answer="抱歉，我在你的论文库中没有找到相关内容。",
            citations=[],
        )

    answer_text, citations = await generate_answer(question=req.question, chunks=chunks)
    return ChatResponse(answer=answer_text, citations=citations)


@app.get("/me/quota")
async def my_quota(user_info: tuple = Depends(get_current_user)):
    _, user = user_info
    return {
        "plan": user["plan"],
        "papers_used": len(user["papers"]),
        "papers_limit": 20 if user["plan"] == "free" else None,  # None = 无上限
        "collection": user["collection"],
    }


# ─── 启动 ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
