"""
Phase 0 验证 Sprint — FastAPI 入口
使用 MiniMax 模型（Embedding: eambo-01 / Chat: MiniMax-Text-01）
"""

import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import create_access_token, verify_token
from config import validate_minimax_config, MINIMAX_API_KEY, MINIMAX_GROUP_ID
from pipeline import process_pdf, search_chunks
from chat import generate_answer

# ─── 环境变量（Phase 0 MiniMax 配置）──────────────────
load_dotenv()

DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# ─── 启动时验证 MiniMax 配置 ────────────────────────────
# 如果配置不完整打印警告（Phase 0 开发模式不阻塞启动）
try:
    validate_minimax_config()
    print("✅ MiniMax 配置验证通过")
    print(f"   Embedding: eambo-01 | Chat: MiniMax-Text-01")
    print(f"   Group ID: {MINIMAX_GROUP_ID[:8]}...")
except RuntimeError as e:
    print(f"⚠️  {e}")
    print("⚠️  Phase 0 需要配置 MiniMax API Key 和 Group ID 才能完整运行")

# ─── FastAPI 初始化 ────────────────────────────────────
app = FastAPI(
    title="RAG 学术知识库 — Phase 0（MiniMax）",
    version="0.2.0",
    debug=DEBUG,
)

# CORS：Phase 0 允许本地开发
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase 0 开发模式
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 内存存储（Phase 0 简单方案）──────────────────────
# 生产环境换 PostgreSQL
users_db: dict = {}  # {user_id: {email, password, plan, papers: [paper_id], collection}}
papers_db: dict = {}  # {paper_id: {user_id, title, status, chunks_count, collection}}

# ─── Pydantic 模型 ─────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    collection_name: str | None = None  # 可选，不传则自动用用户 collection
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]


class PaperUploadResponse(BaseModel):
    paper_id: str
    title: str
    status: str
    chunks_count: int | None = None


# ─── 健康检查 ──────────────────────────────────────────
@app.get("/health")
async def health():
    minimax_ok = bool(MINIMAX_API_KEY and MINIMAX_GROUP_ID)
    return {
        "status": "ok" if minimax_ok else "degraded",
        "phase": "phase0",
        "model": "MiniMax",
        "minimax_configured": minimax_ok,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ─── 认证 ──────────────────────────────────────────────
@app.post("/auth/register")
async def register(email: str, password: str):
    """Phase 0：简单注册，不做邮箱验证"""
    for u in users_db.values():
        if u["email"] == email:
            raise HTTPException(400, "邮箱已注册")

    user_id = str(uuid.uuid4())
    collection_name = f"user_{user_id.replace('-', '_')}"

    users_db[user_id] = {
        "email": email,
        "password": password,  # Phase 0 明文，生产要 hash
        "plan": "free",
        "papers": [],
        "collection": collection_name,
    }

    return {"user_id": user_id, "collection": collection_name}


@app.post("/auth/login")
async def login(email: str, password: str):
    """Phase 0：简单登录，返回 JWT"""
    user = None
    for uid, u in users_db.items():
        if u["email"] == email and u["password"] == password:
            user = u
            break

    if not user:
        raise HTTPException(401, "邮箱或密码错误")

    # 找到 user_id
    user_id = next(uid for uid, u in users_db.items() if u["email"] == email)

    token = create_access_token({"sub": email, "user_id": user_id})

    return {
        "access_token": token,
        "token_type": "bearer",
        "collection": user["collection"],
        "plan": user["plan"],
    }


def get_current_user(authorization: str = Header(None)):
    """Phase 0：解析 JWT"""
    if not authorization:
        raise HTTPException(401, "未提供认证信息")
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(401, "无效的认证方式")
        payload = verify_token(token)
        email = payload["sub"]
        user_id = payload.get("user_id")

        # 兼容旧 token（无 user_id）
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


# ─── PDF 上传 ──────────────────────────────────────────
@app.post("/papers/upload", response_model=PaperUploadResponse)
async def upload_paper(
    file: UploadFile = File(...),
    user_info: tuple = Depends(get_current_user),
):
    """上传 PDF → 解析 → 向量化 → 存入 ChromaDB"""
    user_id, user = user_info

    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置，请联系管理员")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "只支持 PDF 文件")

    # 免费用户限额检查
    if user["plan"] == "free" and len(user["papers"]) >= 20:
        raise HTTPException(429, "免费用户论文上限 20 篇，请升级到 Pro")

    paper_id = str(uuid.uuid4())
    title = file.filename.replace(".pdf", "")

    # 保存临时文件
    tmp_path = Path(f"/tmp/{paper_id}.pdf")
    with open(tmp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    papers_db[paper_id] = {
        "user_id": user_id,
        "title": title,
        "status": "processing",
        "chunks_count": None,
        "collection": user["collection"],
    }
    user["papers"].append(paper_id)

    # 同步处理（Phase 0 简单起见）
    # 生产环境要换 Celery 异步队列
    try:
        result = await process_pdf(
            pdf_path=str(tmp_path),
            paper_id=paper_id,
            collection_name=user["collection"],
        )
        papers_db[paper_id]["status"] = "ready"
        papers_db[paper_id]["chunks_count"] = result["chunks_count"]
    except Exception as e:
        papers_db[paper_id]["status"] = "error"
        raise HTTPException(500, f"索引失败: {str(e)}")
    finally:
        tmp_path.unlink(missing_ok=True)

    return PaperUploadResponse(
        paper_id=paper_id,
        title=title,
        status="ready",
        chunks_count=result["chunks_count"],
    )


@app.get("/papers")
async def list_papers(user_info: tuple = Depends(get_current_user)):
    """列出当前用户的论文"""
    _, user = user_info
    return [
        papers_db[pid]
        for pid in user["papers"]
        if pid in papers_db
    ]


# ─── RAG 问答 ──────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user_info: tuple = Depends(get_current_user),
):
    """语义检索 → 组装上下文 → MiniMax 生成答案"""
    user_id, user = user_info

    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise HTTPException(503, "MiniMax API 未配置")

    # 免费用户不支持 RAG
    if user["plan"] == "free":
        raise HTTPException(403, "Free 用户不支持 RAG 问答，请升级到 Pro")

    # collection 优先用请求参数，否则用用户的
    collection = req.collection_name or user["collection"]

    # 检索相关 chunks
    chunks = await search_chunks(
        query=req.question,
        collection_name=collection,
        top_k=req.top_k,
    )

    if not chunks:
        return ChatResponse(
            answer="抱歉，我在你的论文库中没有找到相关内容。请尝试上传更多论文或调整问题。",
            citations=[],
        )

    # 生成答案
    answer_text, citations = await generate_answer(
        question=req.question,
        chunks=chunks,
    )

    return ChatResponse(answer=answer_text, citations=citations)


@app.get("/me/quota")
async def my_quota(user_info: tuple = Depends(get_current_user)):
    """当前配额使用情况"""
    _, user = user_info
    return {
        "plan": user["plan"],
        "papers_used": len(user["papers"]),
        "papers_limit": 20 if user["plan"] == "free" else float("inf"),
        "collection": user["collection"],
        "minimax_configured": bool(MINIMAX_API_KEY and MINIMAX_GROUP_ID),
    }


# ─── 启动 ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
