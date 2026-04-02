#!/bin/bash
# RAG Phase 0 自动化测试脚本
# 用法: bash api_tests.sh

BASE="${1:-http://127.0.0.1:8000}"
PASS=0 FAIL=0 SKIP=0

pass() { echo "  ✅ $1"; ((PASS++)); }
fail() { echo "  ❌ $1 — $2"; ((FAIL++)); }
skip() { echo "  ⏭️  $1 (需手动)"; ((SKIP++)); }

echo "=== RAG Phase 0 API 测试 ==="
echo ""

# ── 1. 健康检查 ──────────────────────────────────────
echo "[1] 健康检查"
health=$(curl -sf --max-time 5 "$BASE/health")
if [ $? -eq 0 ]; then
  status=$(echo $health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  [ "$status" = "ok" ] && pass "GET /health → 200" || fail "GET /health → $status"
else
  fail "GET /health → 无响应"
fi

# ── 2. 认证流程 ──────────────────────────────────────
echo "[2] 认证"
TOKEN=$(curl -sf -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"bosstest@boss.io","password":"BossPhase0"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)
[ -n "$TOKEN" ] && pass "POST /auth/login → 200" || fail "POST /auth/login" "Token为空"

wrong=$(curl -sf -X POST "$BASE/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"bosstest@boss.io","password":"wrong"}')
[ $? -ne 0 ] && [ -z "$wrong" ] && pass "错误密码 → 拒绝" || fail "错误密码" "应返回401"

no_body=$(curl -sf -X POST "$BASE/auth/login" -H "Content-Type: application/json" -d '{}')
no_body_detail=$(echo $no_body | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('detail','')[:30])" 2>/dev/null)
[ -n "$no_body_detail" ] && pass "空body → Pydantic错误" || fail "空body" "无验证"

# ── 3. Token 验证 ────────────────────────────────────
echo "[3] Token验证"
no_auth=$(curl -sf "$BASE/papers")
auth_detail=$(echo $no_auth | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('detail','')[:20])" 2>/dev/null)
[ -n "$auth_detail" ] && pass "无Token → 403拒绝" || fail "无Token" "无错误"

bad_token=$(curl -sf "$BASE/papers" -H "Authorization: Bearer invalid")
bad_detail=$(echo $bad_token | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('detail','')[:20])" 2>/dev/null)
[ -n "$bad_detail" ] && pass "无效Token → 拒绝" || fail "无效Token" "无错误"

# ── 4. 论文管理 ──────────────────────────────────────
echo "[4] 论文管理"
papers=$(curl -sf "$BASE/papers" -H "Authorization: Bearer $TOKEN")
paper_count=$(echo $papers | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
[ "$paper_count" = "3" ] && pass "GET /papers → 3篇论文" || fail "GET /papers" "返回$paper_count篇"

# 检查每篇状态
for status in ready processing error; do
  count=$(echo $papers | python3 -c "import sys,json; papers=json.load(sys.stdin); print(sum(1 for p in papers if p['status']=='$status'))" 2>/dev/null)
  [ "$count" -gt 0 ] && pass "论文状态[$status] → ${count}篇" || fail "论文状态[$status]" "无此状态"
done

# ── 5. 配额 ──────────────────────────────────────────
echo "[5] 配额"
quota=$(curl -sf "$BASE/me/quota" -H "Authorization: Bearer $TOKEN")
plan=$(echo $quota | python3 -c "import sys,json; print(json.load(sys.stdin)['plan'])" 2>/dev/null)
[ "$plan" = "pro" ] && pass "GET /me/quota → plan=pro" || fail "GET /me/quota" "plan=$plan"

# ── 6. Chat问答 ───────────────────────────────────────
echo "[6] Chat问答（简单问题）"
chat=$(curl -sf --max-time 30 -X POST "$BASE/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"CBAM实施时间","collection_name":"user_1d2a4dc3_550f_4f89_b97b_2b057705381c","top_k":3,"mode":"default"}')
chat_status=$?
if [ $chat_status -eq 0 ]; then
  answer=$(echo $chat | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('answer','')[:50])" 2>/dev/null)
  [ -n "$answer" ] && pass "POST /chat → 返回答案" || fail "POST /chat" "答案为空"
  cites=$(echo $chat | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('citations',[])))" 2>/dev/null)
  [ "$cites" -gt 0 ] && pass "引用来源 → ${cites}条" || fail "引用来源" "无引用"
else
  fail "POST /chat" "HTTP $chat_status"
fi

# ── 7. CORS ───────────────────────────────────────────
echo "[7] CORS预检"
cors=$(curl -sf -X OPTIONS "$BASE/chat" \
  -H "Origin: http://124.156.204.163:8080" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Authorization, Content-Type" \
  -i 2>/dev/null | grep "access-control-allow-origin")
[ -n "$cors" ] && pass "OPTIONS预检 → CORS头存在" || fail "OPTIONS预检" "无CORS头"

# ── 8. ChromaDB状态 ──────────────────────────────────
echo "[8] ChromaDB"
chroma_total=$(python3 -c "
import chromadb
client = chromadb.PersistentClient(path='/root/.openclaw/rag-data/chromadb')
total=sum(c.count() for c in [client.get_collection(n) for n in [col.name for col in client.list_collections()]])
print(total)
" 2>/dev/null)
[ "$chroma_total" -gt 100 ] && pass "ChromaDB → ${chroma_total} chunks" || fail "ChromaDB" "chunks=$chroma_total"

# ── 9. 上传/删除（需手动PDF） ───────────────────────
echo "[9] 上传/删除"
skip "POST /papers/upload" "需真实PDF文件"
skip "DELETE /papers/{id}" "需已有paper_id"

# ── 10. Nginx连通性 ─────────────────────────────────
echo "[10] Nginx"
nginx_ok=$(curl -sf --max-time 3 http://127.0.0.1:8080/ | head -1)
[ -n "$nginx_ok" ] && pass "nginx :8080 → 静态文件" || fail "nginx :8080" "无响应"

nginx_proxy=$(curl -sf --max-time 3 http://127.0.0.1:8080/health)
[ -n "$nginx_proxy" ] && pass "nginx :8080 → API反代" || fail "nginx :8080 → API反代" "无响应"

# ── 11. 重复上传检测 ────────────────────────────────
echo "[11] 安全/边界"
skip "重复上传SHA256去重" "需相同PDF"
skip "论文删除后不可恢复" "需实际删除"

echo ""
echo "=== 结果汇总 ==="
echo "  通过: $PASS"
echo "  失败: $FAIL"
echo "  跳过: $SKIP"
[ "$FAIL" -eq 0 ] && echo "  🎉 全部通过！" || echo "  ⚠️  $FAIL 项需修复"
