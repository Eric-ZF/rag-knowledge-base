#!/bin/bash
# pre-commit hook: Phase 0 部署前检查
# 安装: cp hooks/pre-commit-checks.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -e

FRONTEND_DIR="/root/.openclaw/workspace/rag-knowledge-base/phase0/frontend"
WWW_DIR="/var/www/rag"
API_URL="http://124.156.204.163:8080"
ERRORS=0

echo "=== Phase 0 Pre-commit Checks ==="

# 1. API URL 一致性
echo "[1/4] API URL 一致性..."
for f in "$FRONTEND_DIR/index.html" "$FRONTEND_DIR/demo.html" "$WWW_DIR/index.html" "$WWW_DIR/demo.html"; do
  if [ -f "$f" ]; then
    url=$(grep -m1 "const API" "$f" | grep -o "'[^']*'" | tail -1 | tr -d "'")
    if [ "$url" != "$API_URL" ]; then
      echo "  ❌ $f: API='$url' (应为 '$API_URL')"
      ERRORS=$((ERRORS+1))
    else
      echo "  ✅ $(basename $f)"
    fi
  fi
done

# 2. nginx 端口
echo "[2/4] nginx 端口..."
if ! ss -tlnp | grep -q ":80 " || ! ss -tlnp | grep -q ":8080 "; then
  echo "  ❌ port 80 未监听"
  ERRORS=$((ERRORS+1))
else
  echo "  ✅ port 80"
fi

# 3. backend 健康
echo "[3/4] backend 健康..."
if ! curl -sf --max-time 3 http://127.0.0.1:8000/health > /dev/null 2>&1; then
  echo "  ❌ backend :8000 无响应"
  ERRORS=$((ERRORS+1))
else
  echo "  ✅ backend :8000"
fi

# 4. ChromaDB 数据
echo "[4/4] ChromaDB 数据..."
CHROMA_DIR=$(grep "CHROMADB_DIR" /root/.openclaw/workspace/rag-knowledge-base/phase0/backend/.env | cut -d= -f2)
TOTAL=$(python3 -c "
import chromadb
client = chromadb.PersistentClient(path='$CHROMA_DIR')
total = sum(c.count() for c in [client.get_collection(n) for n in [col.name for col in client.list_collections()]])
print(total)
" 2>/dev/null || echo "0")
if [ "$TOTAL" -lt 10 ]; then
  echo "  ❌ ChromaDB chunk 总数异常: $TOTAL"
  ERRORS=$((ERRORS+1))
else
  echo "  ✅ ChromaDB: $TOTAL chunks"
fi

echo ""
if [ $ERRORS -eq 0 ]; then
  echo "✅ All checks passed"
  exit 0
else
  echo "❌ $ERRORS check(s) failed"
  exit 1
fi
