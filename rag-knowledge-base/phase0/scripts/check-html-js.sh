#!/bin/bash
# 检查 frontend/*.html 中是否有 TypeScript 语法（会破坏纯浏览器 JS）
echo "=== 检查 HTML 文件中的 TypeScript 语法 ==="
found=0
for f in /root/.openclaw/workspace/rag-knowledge-base/phase0/frontend/*.html; do
  if grep -n ": [a-zA-Z]*>" "$f" 2>/dev/null; then
    echo "❌ $f 包含 TypeScript 语法"
    grep -n ": [a-zA-Z]*>" "$f"
    found=1
  fi
done
if [ $found -eq 0 ]; then
  echo "✅ 无 TypeScript 语法"
fi
