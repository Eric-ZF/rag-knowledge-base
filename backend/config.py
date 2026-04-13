"""
Phase 0.7 配置：Jina AI Embedding + MiniMax Chat

─────────────────────────────────────────────────────────
模型方案（2026-04-08 确定）：

Embedding（云端）:
  模型: jina-embeddings-v5-text-small
  维度: 1024
  特点: 多语言支持好，零本地内存占用（~0MB）
  API Key: 通过 JINA_API_KEY 环境变量配置

Chat:
  模型: MiniMax-M2.7（OpenAI-compatible API）
  Base URL: https://api.minimax.chat/v1
  Context: 200K tokens
  API Key: sk-cp-... + Group ID

─────────────────────────────────────────────────────────
注意事项：
  - 切换 embedding 后必须重建 ChromaDB 索引（旧 768d → 新 1024d 不兼容）
  - JINA_API_KEY 和 JWT_SECRET 必须通过环境变量设置
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import logging
logger = logging.getLogger(__name__)

# ─── MiniMax Chat 配置 ────────────────────────────────
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")
if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
    raise RuntimeError(
        "❌ MINIMAX_API_KEY 或 MINIMAX_GROUP_ID 未设置。"
        "请在 backend/.env 中配置这两个环境变量。"
    )
MINIMAX_CHAT_ENDPOINT = "https://api.minimax.chat/v1/chat/completions"
CHAT_MODEL = "MiniMax-M2.7"

# ─── Jina AI Embedding 配置 ─────────────────────────
# 使用 jina-embeddings-v5-text-small（1024维，多语言支持好）
# API Key 必须通过环境变量设置，不允许硬编码
EMBEDDING_MODEL = "jina-embeddings-v4"
EMBEDDING_DIM = 2048
JINA_API_KEY = os.getenv("JINA_API_KEY", "")
if not JINA_API_KEY:
    raise RuntimeError("❌ JINA_API_KEY 环境变量未设置。请在 backend/.env 中添加 JINA_API_KEY=<你的Key>")

# ─── ChromaDB ─────────────────────────────────────────
# 放在 /root/.openclaw/rag-data/chromadb，持久化不丢数据
CHROMADB_DIR = os.getenv("CHROMADB_DIR", "/root/.openclaw/rag-data/chromadb/chromadb")

# ─── papers_db 持久化路径 ─────────────────────────────
PAPERS_DB_PATH = os.getenv("PAPERS_DB_PATH", "/root/.openclaw/rag-data/papers_db.json")

# ─── PDF 文件持久化路径 ───────────────────────────────
PAPERS_DIR = os.getenv("PAPERS_DIR", "/root/.openclaw/rag-data/papers")

# ─── 多 Worker 警告 ────────────────────────────────────
import multiprocessing
_cpu_count = multiprocessing.cpu_count()
_workers = int(os.getenv("UVICORN_WORKERS", "1"))
if _cpu_count > 1 and _workers == 1:
    logger.warning("单 worker 模式运行。papers_db/feedback 是内存缓存，"
          f"多 worker 需换 Redis 或外置存储。当前: {_cpu_count} CPU, {_workers} worker")

# ─── 验证 ──────────────────────────────────────────────
def validate_minimax_chat_config():
    """验证 MiniMax Chat 配置"""
    missing = []
    if not MINIMAX_API_KEY:
        missing.append("MINIMAX_API_KEY")
    if not MINIMAX_GROUP_ID:
        missing.append("MINIMAX_GROUP_ID")
    if missing:
        raise RuntimeError(f"⚠️ 缺少 MiniMax Chat 配置: {', '.join(missing)}")
    if not MINIMAX_API_KEY.startswith("sk-cp"):
        raise RuntimeError(f"⚠️ MINIMAX_API_KEY 应以 sk-cp 开头")
    logger.info(f"✅ MiniMax Chat 配置验证通过 (Group ID: {MINIMAX_GROUP_ID[:8]}...)")
