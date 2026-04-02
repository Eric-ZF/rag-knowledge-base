# MEMORY.md - Long-Term Memory

## Boss 信息
- **称呼**: boss
- **公网 IP**: 124.156.204.163（腾讯云服务器）
- **登录**: bosstest@boss.io / BossPhase0（pro 账号）
- **偏好**: 直接给结论，不要过多询问

## RAG 学术知识库项目（Phase 0.7）
- **项目路径**: `/root/.openclaw/workspace/rag-knowledge-base/phase0/`
- **后端**: FastAPI on :8000，start_backend.py 启动
- **前端**: nginx on :80+:8080，静态文件 + API 反代
- **向量库**: ChromaDB at /tmp/chromadb/（⚠️ 注意！不是 /root/.openclaw/rag-data/chromadb/）
- **持久化**: papers_db.json + users_db.json at /root/.openclaw/rag-data/
- **当前 collection**: user_1d2a4dc3_550f_4f89_b97b_2b057705381

### 当前论文（2026-04-02 修复后）
- `76046662` EU CBAM EN版（22 chunks）✅
- `00b1336d` 阮建平/黄辉平「规范性力量」（22 chunks）✅
- `8e707ffe` 制造业碳排放（15 chunks）✅
- **已删除 phantom**: `2fd0a101`（papers_db 有记录，ChromaDB 无数据）

### 已修复的 RAG 质量问题（2026-03-31）
- chunk_size: 800→2000, overlap: 80→200
- top_k: 5→8
- 新增 Hybrid Search（向量+关键词融合+页码权重）
- MiniMax-M2.7 模型
- System Prompt 强化引用要求
- MiniMax 520/529 自动重试（3次，指数退避）

### Phase 0.6 持久化（2026-04-01）
- papers_db → /root/.openclaw/rag-data/papers_db.json（每次写入自动落盘）
- users_db → /root/.openclaw/rag-data/users_db.json

### Phase 0.7 论文池管理（2026-04-02）
- GET /papers 实时查 ChromaDB chunk 数量（解决 papers_db 不同步）
- POST /papers/upload SHA256 去重（相同内容拒绝重复上传）
- DELETE /papers/{id} ChromaDB + papers_db 双删
- 前端论文列表 hover 删除按钮，二次确认
- papers_db 清理 phantom entries
- nginx 接管 8080，CORS headers 强制追加

### ⚠️ 重要约束
- **前端 API URL**: `http://124.156.204.163:8080`（必须显式带端口！nginx 监听 80+8080）
- **ChromaDB 数据目录**: /tmp/chromadb（重启丢失！⚠️ 待迁移到持久化目录）
- **Embedding 模型冲突**: ChromaDB 历史 chunks 用 text2vec(384d)，当前 BGE(1024d)，重建索引前不要混用
- **全角/半角归一化**: PDF文本用全角（ＣＢＡＭ），必须在关键词匹配前归一化

### MiniMax API 配置
- Chat: `https://api.minimax.chat/v1/chat/completions`
- Auth: `Authorization: Bearer {api_key}` + `GroupId: {group_id}`
- Models: MiniMax-M2.7（推荐）, MiniMax-Text-01
- Group ID: 2029536159561945747

## 关键模式（Semantic Patterns）
见 `memory/semantic-patterns.json`

## 今日教训（2026-03-31）
1. 代码硬编码 > .env 环境变量（pipeline.py 忽略了 EMBEDDING_MODEL）
2. MiniMax API 520/529 是服务端过载，重试可成功
3. localtunnel 必须用 systemd 保活，nohup 不够
4. hybrid_search 降级路径必须测试完整
5. demo.html API URL 变了不会自动同步

## 今日教训（2026-04-01）
1. **TypeScript 语法禁止写入 .html 的 \<script\>：** `(e: any)` 导致浏览器 SyntaxError，整页 JS 全部失效，静默失败
2. **前端答案截断静默严重：** demo.html `.substring(0, 500)` 看似"只是日志"，实际截断了用户可见答案
3. **undefined 变量不报错但返回 None：** `client.chat(max_tokens=max_tokens)` 中 max_tokens 未定义，Python 函数默认值不触发 NameError（仅在调用时才发现）
4. **登录"没反应"≠ 功能问题：** 可能是 JS 解析失败，浏览器无报错，用 agent-browser 自动化测试可发现
5. **Pre-commit 检查 > 上线后救火：** 4 项检查（TypeScript/截断/tunnel/未定义变量）在 commit 前拦截问题
6. **DEMO_TOKEN 不要硬编码：** token 有过期时间，userId 格式可能变，fallback token 会绕过登录表单但 API 会 401

## 今日教训（2026-04-01 补充）
7. **papers_db 内存化是核心 P0 bug：** 后台任务在旧进程完成写入，新进程 papers_db 被 clear() 清空 → phantom entries
8. **ChromaDB papers_db 不同步导致 phantom entries：** ChromaDB 有数据但 papers_db 丢失 → RAG 返回空；papers_db 有记录但 ChromaDB 无数据 → phantom
9. **Embedding 模型切换导致维度冲突：** text2vec(384d) → BGE(1024d) 切换后旧 chunks 无法检索，需重建索引
10. **JSON 持久化用 os.replace 原子替换：** 先写 .tmp 再 rename，防止写入中断导致文件损坏

## 今日教训（2026-04-02）
1. **nginx 只监 8080，前端 API URL 无端口 → 连接超时：** `http://124.156.204.163` 默认走 port 80，没人监听，永远超时。解决：前端显式带端口 `:8080`
2. **浏览器缓存 HTML 是"登录没反应"的主要元凶：** Ctrl+Shift+R 强制刷新
3. **ChromaDB count(where=...) 行为不稳定：** 用 `len(get(where=...)["ids"])` 更可靠
4. **API URL 变更必须同步改三处：** index.html、demo.html、/var/www/rag/，缺一不可
5. **「登录没反应」排障顺序**：Console（红色报错）→ Network（ERR_* 类型）→ r.json() 二次调用 → 连接超时
