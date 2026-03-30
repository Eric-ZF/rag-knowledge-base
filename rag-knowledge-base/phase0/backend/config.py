"""
Phase 0 配置：MiniMax 模型

安装依赖：
  pip install langchain-community anthropic

环境变量：
  MINIMAX_API_KEY=sk-cp...     # MiniMax API Key（sk-cp 开头）
  MINIMAX_GROUP_ID=...          # MiniMax Group ID（账户级别参数，必需）

Embedding:
  模型: eambo-01 (LangChain MiniMaxEmbeddings 内置支持)
  维度: 1536
  Endpoint: https://api.minimax.chat/v1/embeddings

Chat/LLM:
  模型: MiniMax-Text-01 (通过 OpenAI-compatible API)
  Base URL: https://api.minimax.chat/v1
  Context: 200K tokens
  价格: 约 $0.015/1M tokens（比 GPT-4 便宜很多）

⚠️ 注意：MiniMax API 需要 Group ID 参数
   Group ID 在 MiniMax 开放平台控制台获取：
   https://platform.minimax.chat/user/login
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── MiniMax 配置 ──────────────────────────────────────
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.getenv("MINIMAX_GROUP_ID", "")
MINIMAX_EMBED_ENDPOINT = "https://api.minimax.chat/v1/embeddings"
MINIMAX_CHAT_ENDPOINT = "https://api.minimax.chat/v1/chat/completions"
EMBEDDING_MODEL = "embo-01"
CHAT_MODEL = "MiniMax-Text-01"

# ─── 验证配置 ──────────────────────────────────────────
def validate_minimax_config():
    """启动时检查 MiniMax 必需配置"""
    missing = []
    if not MINIMAX_API_KEY:
        missing.append("MINIMAX_API_KEY")
    if not MINIMAX_GROUP_ID:
        missing.append("MINIMAX_GROUP_ID")
    if missing:
        raise RuntimeError(
            f"⚠️ Phase 0 缺少必需配置: {', '.join(missing)}\n"
            f"请在 phase0/backend/.env 中配置\n"
            f"Group ID 获取: https://platform.minimax.chat/user/login"
        )
    # 验证 key 格式
    if not MINIMAX_API_KEY.startswith("sk-cp"):
        raise RuntimeError(
            f"⚠️ MINIMAX_API_KEY 格式错误，应以 sk-cp 开头\n"
            f"当前值: {MINIMAX_API_KEY[:10]}..."
        )
