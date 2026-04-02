#!/bin/bash
# Phase 0 部署前检查清单
# 每次推送/重启前必须运行

set -e

FRONTEND_DIR="/root/.openclaw/workspace/rag-knowledge-base/phase0/frontend"
WWW_DIR="/var/www/rag"
API_URL="http://124.156.204.163:8080"

echo "=== Phase 0 部署前检查 ==="

# 1. API URL 一致性检查
echo "[1/5] 检查 API URL 一致性..."
for f in "$FRONTEND_DIR/index.html" "$FRONTEND_DIR/demo.html" "$WWW_DIR/index.html" "$WWW_DIR/demo.html"; do
  if [ -f "$f" ]; then
    url=$(grep -m1 "const API" "$f" | grep -o "'[^']*'" | tail -1 | tr -d "'")
    if [ "$url" != "$API_URL" ]; then
      echo "  ❌ $f: API URL = '$url' (应为 '$API_URL')"
    else
      echo "  ✅ $f: OK"
    fi
  fi
done

# 2. nginx 端口检查
echo "[2/5] 检查 nginx 端口..."
if ss -tlnp | grep -q ":80 "; then
  echo "  ✅ port 80: 已监听"
else
  echo "  ❌ port 80: 未监听!"
fi
if ss -tlnp | grep -q ":8080 "; then
  echo "  ✅ port 8080: 已监听"
else
  echo "  ❌ port 8080: 未监听!"
fi

# 3. backend 健康检查
echo "[3/5] 检查后端..."
if curl -sf --max-time 3 http://127.0.0.1:8000/health > /dev/null 2>&1; then
  echo "  ✅ backend :8000: OK"
else
  echo "  ❌ backend :8000: 无响应!"
fi

# 4. nginx 反代检查
echo "[4/5] 检查 nginx 反代..."
if curl -sf --max-time 3 "$API_URL/health" > /dev/null 2>&1; then
  echo "  ✅ nginx → backend: OK"
else
  echo "  ❌ nginx → backend: 连接失败!"
fi

# 5. ChromaDB 数据完整性
echo "[5/5] 检查 ChromaDB..."
TOTAL=$(python3 -c "
import chromadb
client = chromadb.PersistentClient(path='/tmp/chromadb')
for col in client.list_collections():
    c = client.get_collection(col.name)
    print(f'{col.name}: {c.count()} chunks')
" 2>/dev/null || echo "ERROR")
echo "  $TOTAL"

echo ""
echo "=== 检查完成 ==="
