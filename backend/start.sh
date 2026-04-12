#!/bin/bash
# RAG Backend 启动脚本
# 路径: /root/.openclaw/workspace/rag-knowledge-base/phase0/backend/start.sh
# systemd: ExecStart=/root/.openclaw/workspace/rag-knowledge-base/phase0/backend/start.sh

cd /root/.openclaw/workspace/rag-knowledge-base/phase0/backend

# 加载 .env（如果存在）
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

exec /usr/bin/python3 -m uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
