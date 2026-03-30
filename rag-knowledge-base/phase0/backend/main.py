"""
Phase 0 验证 Sprint — FastAPI 入口
目标：用最快的方式跑通 PDF上传 → RAG问答 全流程
"""

import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import create_access_token, verify_token
from pipeline import process_pdf, search_chunks
from chat import generate_answer

# ─── 环境变量 ────────────────────────────────────────────
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# ─── FastAPI 初始化 ────────────────────────────────────
app = FastAPI(
    title="RAG 学术知识库 — Phase 0 验证",
    version="0.1.0",
    debug=DEBUG,
)

# CORS：Phase 0 允许本地开发
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase 0 开发模式，生产环境要改
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 内存存储（Phase 0 简单方案）───────────────────────
# 生产环境换 PostgreSQL
users_db: dict = {}  # {user_id: {email, password_hash, plan, papers: [paper_id]}}
papers_db: dict = {}  # {paper_id: {user_id, title, status, chunks_count, qdrant_collection}}

# ─── Pydantic 模型 ─────────────────────────────────────
class ChatRequest(BaseModel):
    question: str
    collection_name: str
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict]  # [{paper_id, title, chunk_text, page}]


class PaperUploadResponse(BaseModel):
    paper_id: str
    title: str
    status: str
    chunks_count: int | None = None


# ─── 健康检查 ──────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "phase": "phase0",
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
    collection_name = f"user_{user_id}"
    users_db[user_id] = {
        "email": email,
        "password": password,  # Phase 0 明文存，生产要 hash
        "plan": "free",
        "papers": [],
        "collection": collection_name,
    }
    return {"user_id": user_id, "collection": collection_name}


@app.post("/auth/login")
async def login(email: str, password: str):
    """Phase 0：简单登录，返回 JWT"""
    user = None
    for u in users_db.values():
        if u["email"] == email and u["password"] == password:
            user = u
            break
    if not user:
        raise HTTPException(401, "邮箱或密码错误")
    token = create_access_token({"sub": user["email"], "user_id": list(users_db.keys())[list(users_db.values()).index(user)]})
    return {"access_token": token, "token_type": "bearer"}


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
        for uid, u in users_db.items():
            if u["email"] == email:
                return uid, u
        raise HTTPException(401, "用户不存在")
    except Exception:
        raise HTTPException(401, "无效的 Token")


# ─── PDF 上传 ──────────────────────────────────────────
@app.post("/papers/upload", response_model=PaperUploadResponse)
async def upload_paper(
    file: UploadFile = File(...),
    user_info: tuple = Depends(get_current_user),
):
    """上传 PDF → 解析 → 向量化 → 存入 Qdrant"""
    user_id, user = user_info

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

    # 后台处理（Phase 0 简单起见，这里同步处理）
    # 生产环境要换 Celery 异步队列
    try:
        result = await process_pdf(
            pdf_path=str(tmp_path),
            paper_id=paper_id,
            collection_name=user["collection"],
            openai_api_key=OPENAI_API_KEY,
        )
        papers_db[paper_id]["status"] = "ready"
        papers_db[paper_id]["chunks_count"] = result["chunks_count"]
    except Exception as e:
        papers_db[paper_id]["status"] = "error"
        raise HTTPException(500, f"索引失败: {str(e)}")
    finally:
        # 清理临时文件
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
    result = []
    for paper_id in user["papers"]:
        if paper_id in papers_db:
            result.append(papers_db[paper_id])
    return result


# ─── RAG 问答 ──────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user_info: tuple = Depends(get_current_user),
):
    """语义检索 → 组装上下文 → LLM 生成答案"""
    user_id, user = user_info

    # 检查配额
    if user["plan"] == "free":
        # Phase 0 简化：不做次数统计，直接拒绝 RAG
        raise HTTPException(403, "Free 用户不支持 RAG 问答，请升级到 Pro")

    # 检索相关 chunks
    chunks = await search_chunks(
        query=req.question,
        collection_name=req.collection_name,
        top_k=req.top_k,
        openai_api_key=OPENAI_API_KEY,
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
        anthropic_api_key=ANTHROPIC_API_KEY,
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
    }


# ─── 启动 ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
