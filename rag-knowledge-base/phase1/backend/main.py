"""
Phase 1 — FastAPI 入口
学术知识库 · Evidence-First RAG
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config
from .storage.schema import init_db
from .storage import papers as papers_storage
from .routers import papers, chat, upload


# ─── Lifespan ───────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 初始化数据库
    init_db()
    # 预加载 embedding 模型
    Path("/tmp/phase1_starting").write_text("1")
    print("📥 预加载 Embedding 模型...")
    from .pipeline import get_embedding_model
    _ = get_embedding_model()
    Path("/tmp/phase1_starting").write_text("0")
    print("✅ Phase 1 就绪")
    yield


# ─── FastAPI ────────────────────────────────────────────

app = FastAPI(
    title="Academic Knowledge Base — Phase 1",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(papers.router, prefix="/api/v1", tags=["papers"])
app.include_router(chat.router, prefix="/api/v1", tags=["chat"])
app.include_router(upload.router, prefix="/api/v1", tags=["upload"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "phase": "phase1.0",
        "model": f"bge-large-zh-v1.5 + {config.CHAT_MODEL}",
        "chromadb": config.CHROMADB_DIR,
        "sqlite": str(config.SQLITE_PATH),
    }


@app.get("/")
async def root():
    return {
        "name": "Academic Knowledge Base — Phase 1",
        "docs": "/docs",
        "health": "/health",
    }
