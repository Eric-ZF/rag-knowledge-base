"""
Phase 0.7 — FastAPI 入口（Router 拆分后）
职责：app 创建 + CORS + lifespan（启动检测）+ 健康检查
所有业务路由 → routers/
"""
import os, re, chromadb
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from config import CHROMADB_DIR, PAPERS_DIR, CHAT_MODEL, MINIMAX_API_KEY, MINIMAX_GROUP_ID

# ─── 统一日志 ────────────────────────────────────────
from logging_config import setup_logging
setup_logging()
logger = get_logger = lambda n: __import__("logging").getLogger(n)

# ─── 启动验证 ────────────────────────────────────────
from config import validate_minimax_chat_config
try:
    validate_minimax_chat_config()
except RuntimeError as e:
    print(f"⚠️  {e}")  # 日志系统尚未初始化，用 print

# ─── 数据层初始化 ─────────────────────────────────────
from data import init_papers, init_users
init_papers()
users_db, users_by_email = init_users()

# ─── 共享状态同步到 state.py ───────────────────────────
from state import set_users
set_users(users_db, users_by_email)

# ─── Lifespan ───────────────────────────────────────
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(_app: FastAPI):
    Path("/tmp/backend_starting").write_text("1")
    _logger = __import__("logging").getLogger("rag")

    # ── phantom 检测 ──────────────────────────────
    _logger.info("启动 phantom 检测...")
    from data import get_papers_db
    from state import processing_events
    papers_db = get_papers_db()
    phantom_count = 0
    for paper_id, p in papers_db.items():
        if p.get("status") == "ready":
            try:
                _client = chromadb.PersistentClient(path=CHROMADB_DIR)
                safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", f"user_{p['user_id'].replace('-', '_')}")
                col = _client.get_collection(safe_name)
                results = col.get(where={"paper_id": paper_id})
                if not results["ids"]:
                    from data import update_paper
                    update_paper(paper_id, status="error", error="索引丢失，请重新上传")
                    _logger.warning(f"[phantom] {paper_id[:8]} ChromaDB 无 chunks，标记为 error")
                    phantom_count += 1
            except Exception as e:
                _logger.warning(f"[phantom] {paper_id[:8]} 检测失败: {e}")
    _logger.info(f"phantom 检测完成：{phantom_count} 篇标记为 error")

    # ── 孤立 PDF 清理 ──────────────────────────────
    _logger.info("启动孤立 PDF 清理...")
    orphan_deleted = 0
    papers_dir = Path(PAPERS_DIR)
    for pdf_file in papers_dir.glob("*.pdf"):
        pid = pdf_file.stem
        if pid not in papers_db:
            try:
                pdf_file.unlink()
                _logger.info(f"[orphan] 孤立 PDF 已删除: {pdf_file.name}")
                orphan_deleted += 1
            except Exception as e:
                _logger.warning(f"[orphan] 删除失败 {pdf_file.name}: {e}")
    _logger.info(f"孤立 PDF 清理完成：删除 {orphan_deleted} 个残留文件")

    Path("/tmp/backend_starting").write_text("0")
    _logger.info("✅ RAG backend 启动完成，uvicorn 开始接受请求")
    yield
    Path("/tmp/backend_starting").write_text("0")

# ─── FastAPI App ─────────────────────────────────────
app = FastAPI(
    title="RAG 学术知识库 — Phase 0.7",
    version="0.7.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 健康检查 ───────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "phase": "phase0.7",
        "model": f"{CHAT_MODEL} + Jina AI embedding",
        "minimax_configured": bool(MINIMAX_API_KEY and MINIMAX_GROUP_ID),
        "timestamp": datetime.utcnow().isoformat(),
    }

# ─── 注册 routers ─────────────────────────────────────
from routers.auth import router as auth_router
from routers.papers import router as papers_router
from routers.chat import router as chat_router
from routers.feedback import router as feedback_router

app.include_router(auth_router)
app.include_router(papers_router)
app.include_router(chat_router)
app.include_router(feedback_router)
