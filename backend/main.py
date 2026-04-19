"""
Phase 0.8 — FastAPI 入口
多用户 + 文件夹系统初始化
"""
import os, re
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from config import CHROMADB_DIR, PAPERS_DIR

# ─── 统一日志 ────────────────────────────────────────
from logging_config import setup_logging
setup_logging()
logger = __import__("logging").getLogger("rag")

# ─── 启动验证 ────────────────────────────────────────
from config import validate_minimax_chat_config
try:
    validate_minimax_chat_config()
except RuntimeError as e:
    print(f"⚠️  {e}")

# ─── 数据层初始化 ─────────────────────────────────────
from data import init_papers, init_users
init_papers()
users_db, users_by_email, users_by_phone = init_users()

# ─── folders_db 初始化 ──────────────────────────────
from folders_db import init as init_folders
init_folders()

# ─── 共享状态同步到 state.py ───────────────────────────
from state import set_users
set_users(users_db, users_by_email, users_by_phone)

# ─── 迁移检查：确保每个用户都有默认文件夹 ─────────────────
from folders_db import get_all as get_folders_all, create as create_folder
from datetime import datetime
folders = get_folders_all()
migrated = 0
for user_id, user in users_db.items():
    if not user.get("default_folder_id") or user["default_folder_id"] not in folders:
        fid = str(__import__("uuid").uuid4())
        create_folder(fid, user_id, "我的文献", parent_id=None)
        user["default_folder_id"] = fid
        from data import save_users
        save_users()
        migrated += 1
        logger.info(f"[migration] 为用户 {user_id[:8]} 创建默认文件夹")

# ─── Lifespan ───────────────────────────────────────
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("RAG backend Phase 0.8 启动中...")
    Path("/tmp/backend_starting").write_text("1")

    # ── phantom 检测 ──────────────────────────────
    logger.info("启动 phantom 检测...")
    import chromadb
    from data import get_papers_db, update_paper
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
                    update_paper(paper_id, status="error", error="索引丢失，请重新上传")
                    logger.warning(f"[phantom] {paper_id[:8]} ChromaDB 无 chunks，标记为 error")
                    phantom_count += 1
            except Exception as e:
                logger.warning(f"[phantom] {paper_id[:8]} 检测失败: {e}")
    logger.info(f"phantom 检测完成：{phantom_count} 篇标记为 error，{migrated} 个用户文件夹已迁移")

    # ── 超时 stale processing 清理 ──────────────────────
    from papers_db import cleanup_stale_processing
    stale = cleanup_stale_processing(max_age_minutes=30)
    if stale:
        logger.info(f"[cleanup] {len(stale)} 篇 stale processing 已清理: {[p[:8] for p in stale]}")

    # ── 孤立 PDF 清理 ──────────────────────────────
    logger.info("启动孤立 PDF 清理...")
    orphan_deleted = 0
    papers_dir = Path(PAPERS_DIR)
    for pdf_file in papers_dir.glob("*.pdf"):
        pid = pdf_file.stem
        if pid not in papers_db:
            try:
                pdf_file.unlink()
                logger.info(f"[orphan] 孤立 PDF 已删除: {pdf_file.name}")
                orphan_deleted += 1
            except Exception as e:
                logger.warning(f"[orphan] 删除失败 {pdf_file.name}: {e}")
    logger.info(f"孤立 PDF 清理完成：删除 {orphan_deleted} 个残留文件")

    Path("/tmp/backend_starting").write_text("0")
    logger.info("✅ RAG backend Phase 0.8 启动完成")
    yield
    Path("/tmp/backend_starting").write_text("0")

# ─── FastAPI App ─────────────────────────────────────
app = FastAPI(
    title="RAG 学术知识库 — Phase 0.8",
    version="0.8.0",
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
from datetime import datetime

@app.get("/api/version")
def get_version():
    """返回当前部署版本，前端据此检测是否需要强制刷新"""
    return {"version": "20260419", "deployed": True}

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "phase": "phase0.8",
        "version": "0.8.0",
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
