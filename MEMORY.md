# MEMORY.md - Long-Term Memory

## Boss 信息
- **称呼**: boss
- **公网 IP**: 124.156.204.163（腾讯云服务器）
- **登录**: bosstest@boss.io / BossPhase0（pro 账号）
- **偏好**: 直接给结论，不要过多询问

## RAG 学术知识库项目（Phase 0）
- **项目路径**: `/root/.openclaw/workspace/rag-knowledge-base/phase0/`
- **后端**: FastAPI on :8000
- **前端**: http.server on :8080
- **向量库**: ChromaDB at /tmp/chromadb/
- **当前 collection**: user_1d2a4dc3_550f_4f89_b97b_2b057705381c（bosstest 用户）
- **当前论文**: d03a2761... (542chunks, 阮建平, CBAM论文), 23a1b6b8... (37chunks, 李涛, CBAM钢铁行业)

### 已修复的 RAG 质量问题（2026-03-31）
- chunk_size: 800→2000, overlap: 80→200
- top_k: 5→8
- 新增 Hybrid Search（向量+BM25融合）
- MiniMax-M2.7 模型
- System Prompt 强化引用要求

### ⚠️ 重要约束
- **不要切换 Embedding 模型**：text2vec(768维)和 eambo-01(1024维)维度不同，切换需重建所有索引
- **backend 重启后需用 /tmp/start_backend.py 恢复用户数据**
- **不要再用 localtunnel**：改用公网IP直连（安全组已开放8000/8080）
- **全角/半角归一化必须在关键词匹配前执行**：PDF文本用全角（ＣＢＡＭ），必须归一化后匹配
- **demo.html API URL 永久指向：http://124.156.204.163:8000**

### MiniMax API 配置（已验证）
- Chat: `https://api.minimax.chat/v1/chat/completions`
- Auth: `Authorization: Bearer {api_key}` + `GroupId: {group_id}`
- Models: MiniMax-M2.7（推荐）, MiniMax-M2, MiniMax-Text-01
- Group ID: 2029536159561945747

## 关键模式（Semantic Patterns）
见 `memory/semantic-patterns.json`

## 今日教训（2026-03-31）
1. 代码硬编码 > .env 环境变量（pipeline.py 忽略了 EMBEDDING_MODEL）
2. MiniMax API 520/529 是服务端过载，重试可成功
3. localtunnel 必须用 systemd 保活，nohup 不够
4. hybrid_search 降级路径必须测试完整
5. demo.html API URL 变了不会自动同步
