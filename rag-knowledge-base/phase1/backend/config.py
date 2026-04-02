"""
Phase 1 — 学术知识库
配置层
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ─── 路径配置 ─────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# SQLite 关系数据库路径
SQLITE_PATH = DATA_DIR / "academic.db"

# ChromaDB 向量数据库路径
CHROMADB_DIR = os.getenv("CHROMADB_DIR", str(BASE_DIR / "chromadb"))

# 原始文件存储（PDF/Word 等）
FILES_DIR = DATA_DIR / "files"
FILES_DIR.mkdir(exist_ok=True)

# ─── Embedding 配置 ───────────────────────────────────
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
EMBEDDING_DIM = 1024  # BGE-large-zh-v1.5

# ─── MiniMax LLM 配置 ─────────────────────────────────
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")
MINIMAX_BASE_URL = "https://api.minimax.chat/v1/chat/completions"
CHAT_MODEL = os.getenv("CHAT_MODEL", "MiniMax-M2.7")

# ─── JWT 配置 ─────────────────────────────────────────
JWT_SECRET = os.getenv("JWT_SECRET", "phase1-2026-academic-knowledge-base")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 7 天

# ─── ChromaDB 配置 ───────────────────────────────────
COLLECTION_NAME = "academic_kb"
