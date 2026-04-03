"""
Phase 0 配置：本地 Embedding + MiniMax Chat

安装依赖：
  pip install sentence-transformers anthropic

─────────────────────────────────────────────────────────
Phase 0 模型方案（2026-03-30 确定）：

Embedding（本地）:
  模型: shibing624/text2vec-base-chinese
  维度: 768
  特点: 中文语义效果好的开源模型，CPU 可跑，零 API 成本
  首次运行自动下载（约 400MB）

Chat:
  模型: MiniMax-M2（OpenAI-compatible API）
  Base URL: https://api.minimax.chat/v1
  Context: 200K tokens
  API Key: sk-cp-... + Group ID

─────────────────────────────────────────────────────────
生产环境升级路径（Phase 1+）：

Embedding:
  → MiniMax eambo-01（付费 API）
  → 或 BGE-large-zh（自托管 GPU）

Chat:
  → MiniMax-M2（已验证可用，继续用）
  → 或 Claude 3.5 Haiku（备选）
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── MiniMax Chat 配置 ────────────────────────────────
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")
MINIMAX_CHAT_ENDPOINT = "https://api.minimax.chat/v1/chat/completions"
CHAT_MODEL = "MiniMax-M2.7"

# ─── 本地 Embedding 配置 ──────────────────────────────
# BGE-large-zh-v1.5: 1024维，中文语义和学术术语效果大幅优于 text2vec
# 切换后必须重新上传 PDF 索引（维度不兼容）
EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
EMBEDDING_DIM = 1024

# ─── ChromaDB ─────────────────────────────────────────
# 放在 /root/.openclaw/rag-data/chromadb，持久化不丢数据
CHROMADB_DIR = os.getenv("CHROMADB_DIR", "/root/.openclaw/rag-data/chromadb")

# ─── papers_db 持久化路径 ─────────────────────────────
PAPERS_DB_PATH = os.getenv("PAPERS_DB_PATH", "/root/.openclaw/rag-data/papers_db.json")

# ─── PDF 文件持久化路径 ───────────────────────────────
PAPERS_DIR = os.getenv("PAPERS_DIR", "/root/.openclaw/rag-data/papers")

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
    print(f"✅ MiniMax Chat 配置验证通过 (Group ID: {MINIMAX_GROUP_ID[:8]}...)")
