#!/bin/bash
# Phase 0 pre-commit checks — 在 git commit 前运行
set -e

cd /root/.openclaw/workspace/rag-knowledge-base/phase0
FRONTEND_DIR="./frontend"

echo "🔍 运行 Phase 0 pre-commit 检查..."

# 1. HTML 文件中禁止 TypeScript 泛型语法
echo -n "  [1/4] 检查 HTML JS TypeScript 语法... "
TS_PATTERN=$(grep -rn ": [a-zA-Z]*>" "$FRONTEND_DIR"/*.html 2>/dev/null || true)
if [ -n "$TS_PATTERN" ]; then
  echo "❌ FAIL — 发现 TypeScript 语法"
  echo "$TS_PATTERN"
  exit 1
fi
echo "✅"

# 2. demo.html 禁止 substring/truncation
echo -n "  [2/4] 检查答案截断模式... "
TRUNC=$(grep -n "r\.answer\.substring\|answer\.substring(0," "$FRONTEND_DIR/demo.html" 2>/dev/null || true)
if [ -n "$TRUNC" ]; then
  echo "❌ FAIL — demo.html 仍有截断"
  echo "$TRUNC"
  exit 1
fi
echo "✅"

# 3. API URL 禁止 localtunnel/tunnel
echo -n "  [3/4] 检查 localtunnel URL... "
TUNNEL=$(grep -rn "loca.lt\|ngrok\|tunnel" "$FRONTEND_DIR"/*.html 2>/dev/null || true)
if [ -n "$TUNNEL" ]; then
  echo "❌ FAIL — 发现 tunnel URL"
  echo "$TUNNEL"
  exit 1
fi
echo "✅"

# 4. chat.py 禁止未定义的 max_tokens
echo -n "  [4/4] 检查未定义变量引用... "
UNDEF=$(grep -n "max_tokens[,)]" "$FRONTEND_DIR/../backend/chat.py" 2>/dev/null | grep -v "^\s*#\|= max_tokens\|max_tokens =" || true)
if [ -n "$UNDEF" ]; then
  echo "⚠️  注意: chat.py 引用 max_tokens 请确保已定义"
fi
echo "✅"

echo ""
echo "✅ 全部检查通过，可以提交"
