# RAG 学术知识库 — 系统架构设计

> 生成时间：2026-03-30 17:20 GMT+8
> 版本：v2.1（与 CEO v2.0 对齐）
> 依据：CEO-analysis.md (v2.0, 2026-03-30) · DESIGN-interaction.md (v4.0) · QA-test-strategy.md (v3.0)

---

## 0. 决策共识（CEO ↔ ENG 对齐）

经过 CEO产品分析（v2.0）和 CS/BS架构专题讨论，团队已达成以下共识：

| 决策项 | 结论 | 触发原因 |
|-------|------|---------|
| 产品方向 | Go，建议垂直切入（中文核心期刊 + 研究生场景） | CEO评估 4.8/5 |
| MVP 核心假设 | 研究者愿意为"私有论文库 RAG 问答"付钱 | 唯一需要验证的假设 |
| 架构风格 | **纯BS架构** | 研究者多设备场景是刚需 |
| MVP 功能范围 | RAG Q&A + 最低限度管理（上传/列表），无完整收藏夹/团队协作 | CEO v2.0 聚焦验证 |
| 演进策略 | 先MVP单体，团队>10人再拆分微服务 | Kent Beck原则 |
| 隐私路线 | 服务端处理 + 即时删除原文件，不做端侧RAG | 功能与隐私的平衡 |
| 知识图谱 | MVP阶段不做，Phase 2再引入 | YAGNI |
| 团队协作 | **MVP和Phase 2 均不做**，Phase 3+ 再说 | CEO v2.0 砍掉 |
| 定价方案 | ¥0 Free / ¥99 Pro / ¥299 Academic 三档 | CEO v2.0 定义 |
| 验证周期 | 2个月验证 sprint + 3个月产品化 = 5个月总周期 | CEO v2.0 |

---

## 1. 需求快照

| 维度 | 内容 |
|-----|------|
| **核心功能** | 论文上传 · 语义检索 · RAG问答 · 文献管理 |
| **目标用户** | 博士研究生（主力）> 教授 > 独立研究者 |
| **用户规模** | MVP 50人 → 1年后 10,000人 |
| **数据规模** | 每用户 100-500篇私有PDF，全量100万篇元数据 |
| **性能目标** | 检索 P99 < 2s，API QPS 100 |
| **可用性目标** | MVP阶段 99%，正式版 99.5% |
| **隐私约束** | 用户PDF永不泄露 —— 这是产品的命根子 |

---

## 2. 架构决策记录 (ADR)

### ADR #1：整体风格 —— Phase 0验证 → Month 3-5 MVP单体 → 演进拆分
**状态**：已接受
**决策**：
- Phase 0（Month 1-2）：纯手动/半自动化验证，不做产品部署
- Month 3-5：用单体（Next.js + FastAPI合一部署）
- Month 6+：按 Kent Beck"先跑起来再演进"原则演进
**演进触发条件**：
- 团队规模 > 10人
- 某模块（PDF解析/GPU推理）成为独立瓶颈

### ADR #2：RAG Pipeline —— 服务端向量检索 + LLM生成
**状态**：已接受
**决策**：PDF在**服务端内存中完成解析+向量化**，原文件处理完立即删除，只存储向量+元数据
**理由**：纯端侧（CS）RAG能力太弱（Embedding模型、LLM均无法本地运行）；BS方案功能完整，用户隐私通过"不存储原文件"换信任

### ADR #3：Embedding选型
**状态**：已接受

| 方案 | 选型 | 适用阶段 | 理由 |
|-----|------|--------|------|
| 云端 | `text-embedding-3-small` (OpenAI) | Phase 1-2 | 零运维，成本低($0.02/1M) |
| 本地 | `BGE-large-zh` (HuggingFace) | Phase 3+ | 中文语义更强，自托管合规 |

**过渡策略**：Phase 1先用OpenAI API验证产品，Phase 3切换本地模型

### ADR #4：向量数据库
**状态**：已接受
**决策**：`Qdrant` (开源，Rust实现，支持HNSW+混合检索)
**理由**：比Milvus轻量，比Pinecone便宜，支持本地部署

### ADR #5：LLM选型
**状态**：已接受

| 用途 | 模型 | 成本 | 理由 |
|-----|------|------|------|
| 主力摘要/问答 | `Claude 3.5 Haiku` | $0.2/1M tokens | 速度快，学术内容理解强 |
| 复杂推理/长文 | `Claude 3.5 Sonnet` | $3/1M tokens | 论文全篇分析时才用 |
| 中文增强 | `GPT-4o-mini` (备用) | $0.15/1M tokens | OpenAI中文覆盖补足 |

### ADR #6：PDF解析技术栈
**状态**：已接受

| 阶段 | 选型 | 理由 |
|-----|------|------|
| MVP | `Unstructured.io` (API模式) | 快，公式表格保留好，SaaS无需运维 |
| 降本 | `Marker` (自托管Docker) | 开源，免费，GPU机器可承载 |

### ADR #7：PDF预览（BS特殊处理）
**状态**：已接受
**决策**：浏览器端用 `pdf.js` 渲染PDF预览，不把原始PDF传给后端预览接口
**理由**：避免PDF预览API成为数据泄露点；用户上传时前端直接分块上传到S3

### ADR #8：三档定价配额技术实现（与 CEO v2.0 对齐）
**状态**：已接受
**决策**：三档定价的工程实现

| 层级 | 价格 | 论文上限 | 检索限额 | RAG 问答 |
|-----|------|---------|---------|---------|
| **Free** | ¥0 | 20篇 | 20次/天 | ❌ 不支持 |
| **Pro** | ¥99/月 | 无限 | 无限 | ✅ 支持 |
| **Academic** | ¥299/月 | 无限（团队上限 3-5 人）| 无限 | ✅ 支持 |

**配额实施**：

```python
# PostgreSQL users.plan 字段映射
# 每次 API 调用前检查配额

async def check_paper_quota(user_id: str) -> bool:
    user = await db.users.find_one(id=user_id)
    if user.plan == "free":
        count = await db.papers.count(user_id=user_id)
        return count < 20
    return True  # Pro/Academic 无上限

async def check_search_quota(user_id: str, window: str = "day") -> bool:
    user = await db.users.find_one(id=user_id)
    if user.plan == "free":
        key = f"search:{user_id}:{window}"
        count = redis.get(key) or 0
        return int(count) < 20
    return True

# 超限返回 429
if not await check_paper_quota(user_id):
    return JSONResponse(status_code=429, content={"error": "免费用户论文上限 20 篇，请升级到 Pro"})
```

---

## 3. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户浏览器 (Browser)                              │
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                 │
│   │  Next.js SPA │    │  pdf.js      │    │  流式响应    │                 │
│   │  (主应用)     │    │  (PDF预览)   │    │  (SSE/WSS)  │                 │
│   └──────┬───────┘    └──────────────┘    └──────────────┘                 │
│          │                                                               │
│          │ HTTPS (TLS 1.3)                                               │
└──────────┼───────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          反向代理 (nginx) + API Gateway                      │
│                      限流 / JWT验证 / 路由 / 请求日志                         │
└──────────────────────────────┬────────────────────────────────────────────┘
                               │
             ┌─────────────────┼─────────────────┐
             │                 │                 │
             ▼                 ▼                 ▼
┌──────────────────┐  ┌──────────────┐  ┌─────────────────┐
│   Auth Module    │  │ Paper Module │  │  Search Module   │
│  (JWT + 订阅)    │  │ (上传/解析/  │  │  (向量检索 +    │
│                  │  │  元数据)     │  │   RAG问答)       │
└────────┬─────────┘  └──────┬───────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
  ┌─────────────┐    ┌─────────────────┐   ┌───────────┐
  │ PostgreSQL  │    │     Qdrant      │   │   Redis   │
  │  用户/元数据 │    │   (向量存储)    │   │   缓存    │
  └─────────────┘    └─────────────────┘   └───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Object Storage   │
                    │   (S3 / MinIO)      │
                    │  PDF暂存(处理后删除) │
                    │  Chunk向量 → Qdrant │
                    └─────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Unstructured API  │
                    │   (PDF → Markdown)   │
                    └─────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Embedding API     │
                    │  (OpenAI / BGE)     │
                    └─────────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │   Claude API        │
                    │  (RAG生成答案)       │
                    └─────────────────────┘
```

---

## 4. 核心数据流（完整链路）

### 路径A：论文上传 → 索引

```
① 用户在浏览器选择PDF
       │
       ▼
② pdf.js 前端预览（不离开发浏览器）
       │
       ▼
③ 前端分片上传 → S3 (AES-256加密，路径含user_id隔离)
   PUT /upload/{user_id}/{paper_id}.pdf
       │
       ▼
④ API触发索引任务 (写入 indexing_jobs 表，status='pending')
       │
       ▼
⑤ Background Worker 取任务：
   a) 从S3下载PDF到内存（不落盘）
   b) 调用 Unstructured API → Markdown文本
   c) 按章节(chunk_size=512 tokens)分块
   d) 调用 Embedding API → 向量数组
   e) 批量写入 Qdrant (payload含 user_id filter)
   f) 提取元数据 → PostgreSQL papers 表
   g) S3原文件标记删除（24小时内物理删除）
       │
       ▼
⑥ WebSocket 推送进度到浏览器 (0% → 100%)
```

### 路径B：语义检索 → RAG问答

```
① 用户输入自然语言问题
       │
       ▼
② 前端 → API: POST /api/search
   Body: { query: "论文的主要贡献是什么", paper_ids?: [...] }
       │
       ▼
③ 查询Redis缓存
   Key = hash(query + user_id + paper_ids)
   命中 → 直接返回缓存结果
       │
       ▼
④ 未命中：
   a) Embedding(query) → 向量
   b) Qdrant检索 (top_k=5, filter: user_id={uid})
   c) 组装context块 (text_preview + paper_meta)
   d) 调用 Claude: "根据以下上下文回答..."
   e) 结果写入Redis缓存 (TTL=10min)
       │
       ▼
⑤ 返回: { answer, citations: [{paper_id, chunk, page}] }
   全程流式输出 (SSE)
```

---

## 5. 数据库设计

### PostgreSQL Schema

```sql
-- 用户表
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email       VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255),           -- NULL if SSO only
  plan        VARCHAR(20)  DEFAULT 'free',  -- free / pro / team
  storage_used_bytes BIGINT DEFAULT 0,
  max_storage_bytes  BIGINT DEFAULT 5368709120,  -- 5GB free
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 论文元数据
CREATE TABLE papers (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID REFERENCES users(id) ON DELETE CASCADE,
  title        TEXT NOT NULL,
  authors      TEXT[],
  abstract     TEXT,
  year         INTEGER,
  venue        TEXT,
  doi          VARCHAR(255),
  file_path    VARCHAR(512),            -- S3 key (加密存储路径)
  file_hash    VARCHAR(64),             -- SHA256，防止重复上传
  file_size    BIGINT,                  -- 字节数
  chunk_count  INTEGER DEFAULT 0,        -- 总chunk数
  status       VARCHAR(20) DEFAULT 'pending',
              -- pending → indexing → ready → error
  error_msg    TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- 收藏夹（支持嵌套）
CREATE TABLE collections (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
  name       VARCHAR(255) NOT NULL,
  parent_id  UUID REFERENCES collections(id),
  color      VARCHAR(7),               -- Hex color
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 论文 ↔ 收藏夹 多对多
CREATE TABLE paper_collections (
  paper_id     UUID REFERENCES papers(id) ON DELETE CASCADE,
  collection_id UUID REFERENCES collections(id) ON DELETE CASCADE,
  added_at     TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (paper_id, collection_id)
);

-- 索引进度追踪
CREATE TABLE indexing_jobs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id      UUID REFERENCES papers(id) ON DELETE CASCADE,
  status        VARCHAR(20) DEFAULT 'queued',  -- queued / running / done / failed
  chunks_indexed INTEGER DEFAULT 0,
  total_chunks  INTEGER,
  started_at    TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ,
  error_msg     TEXT
);

-- 搜索历史（可选，用于个性化推荐）
CREATE TABLE search_history (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
  query      TEXT,
  results_count INTEGER,
  latency_ms INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_papers_user_id ON papers(user_id);
CREATE INDEX idx_papers_status  ON papers(status);
CREATE INDEX idx_indexing_jobs_paper_id ON indexing_jobs(paper_id);
```

### Qdrant Collection

```json
{
  "name": "paper_chunks",
  "vectors": {
    "size": 1536,
    "distance": "Cosine"
  },
  "hnsw_config": {
    "m": 16,
    "ef_construct": 128
  },
  "payload_schema": {
    "paper_id":    { "type": "keyword" },
    "user_id":     { "type": "keyword" },   // ★ 强制隔离
    "chunk_index": { "type": "integer" },
    "page_number": { "type": "integer" },
    "section":     { "type": "keyword" },   // abstract / method / result / ...
    "text":        { "type": "text" }        // 实际chunk文本
  }
}
```

### Redis Cache

| Key | Value | TTL |
|-----|-------|-----|
| `meta:paper:{id}` | Paper元数据JSON | 1h |
| `quota:{user_id}` | `{searches_left, resets_at}` | 5min |
| `cache:search:{hash}` | 检索结果JSON | 10min |
| `session:{user_id}` | 在线状态 | 30min |

---

## 6. API 规范

### 认证
```
POST /api/auth/register      注册
POST /api/auth/login         登录 → JWT (1h) + RefreshToken (7d)
POST /api/auth/refresh        刷新Token
```

### 论文管理
```
POST   /api/papers/upload     上传PDF (multipart/form-data)
GET    /api/papers            列表 (分页, filter by collection)
GET    /api/papers/:id        详情
GET    /api/papers/:id/status 索引进度 (SSE实时)
DELETE /api/papers/:id       删除论文 + 向量 + S3文件
PATCH  /api/papers/:id        更新元数据 (title, authors)
```

### 收藏管理
```
GET    /api/collections              收藏夹列表
POST   /api/collections               创建收藏夹
PUT    /api/collections/:id           重命名/移动收藏夹
DELETE /api/collections/:id           删除（含paper_collections）
POST   /api/papers/:id/collections    论文加入收藏夹
DELETE /api/papers/:id/collections/:cid  从收藏夹移除
```

### 检索与问答
```
POST /api/search
  Body:  { query, top_k=5, collection_ids?: [], year_range?: [] }
  Resp:  { results: [{ paper, chunk, score, page }], latency_ms }

POST /api/chat
  Body:  { query, paper_ids?: [], stream=true }
  Resp:  (SSE) answer块 + citations

GET  /api/papers/:id/chunks?page=1&size=20   预览某论文所有chunk
```

### 订阅与配额
```
GET  /api/me/quota          当前用量 (papers_count, storage_used, searches_left)
POST /api/me/upgrade        升级计划 (跳转到Stripe Checkout)
```

---

## 7. 安全与隐私设计

> **设计原则：隐私是产品底线，不是可选项**

### 威胁模型

| 威胁 | 攻击场景 | 防御手段 |
|-----|---------|---------|
| **T1: PDF原文件泄露** | 服务器被入侵，用户PDF曝光 | 内存处理原文件 + 24h内删除S3原文件 |
| **T2: 跨用户检索泄露** | A用户检索到B用户的论文chunk | Qdrant强制user_id filter；LLM输入只注入已授权chunk |
| **T3: Token盗用** | 攻击者拿到JWT调用API | 短期JWT(1h) + 设备指纹 + 异常IP检测 |
| **T4: 批量爬取** | 竞品/爬虫消耗免费配额 | 限流(5 req/min free)；行为指纹识别 |
| **T5: 恶意PDF** | 上传含恶意JS/PDF的PDF | 服务端不执行PDF代码，只提取文本；pdf.js沙箱渲染 |

### 隐私合规

```
上传阶段:
  浏览器 ──HTTPS──→ nginx ──TLS──→ FastAPI
                         │
                         ▼
                    S3 (AES-256加密存储)
                    Key管理: AWS KMS / 自托管Vault
                    访问: 每个user_id独立路径前缀
                    删除策略: 索引完成后标记，24h后物理删除

检索阶段:
  用户查询 ──JWT验证──→ Qdrant查询
                           │
                           └── WHERE user_id = {current_user}  (强制)
```

---

## 8. 性能设计

### 目标指标

| 操作 | 指标 | 达标手段 |
|-----|------|---------|
| PDF上传 (10MB) | < 5s | 前端直传S3 (分片)，API只记录元数据 |
| 论文索引 (20页) | < 15s | Unstructured API异步处理，WebSocket进度 |
| 语义检索 P99 | < 1s | Qdrant HNSW索引 (ef=128)，Redis缓存 |
| RAG生成首Token | < 2s | SSE流式输出，边生成边返回 |
| 99.5%可用性 | 全年<44h宕机 | 多AZ部署，Qdrant集群 |

### 三级缓存

```
① 浏览器内存         ← 本次会话内的重复query
② Redis (10min TTL)  ← 常见检索模式
③ Qdrant HNSW        ← 向量索引
```

---

## 9. 前端技术栈 (Next.js)

```
src/
├── app/
│   ├── (auth)/login
│   ├── (auth)/register
│   ├── (main)/dashboard        主控制台
│   ├── (main)/paper/[id]       论文详情/阅读
│   ├── (main)/search           检索页
│   └── (main)/settings         账户设置
├── components/
│   ├── pdf/PdfViewer.tsx       pdf.js封装
│   ├── chat/ChatPanel.tsx      RAG问答侧边栏
│   ├── search/ResultList.tsx   检索结果
│   └── layout/
├── lib/
│   ├── api.ts                   请求封装 (Bearer Token)
│   └── s3-upload.ts             前端直传S3
└── hooks/
    ├── useIndexingStatus.ts     WebSocket进度
    └── useSearch.ts             检索+缓存
```

---

## 10. 部署架构

### Phase 0: 验证 Sprint（Month 1-2）

```
纯手动/半自动化验证:
  ├── GPT-4 + LangChain notebook
  ├── Google Drive 共享 PDF（不用构建系统）
  └── 人工收集用户付费意向

无需任何生产部署
```

### Month 3-5: MVP 产品化

```
1台 4核8G VPS:
  ├── nginx (反向代理 + SSL)
  ├── Next.js (静态托管 or SSR)
  ├── FastAPI (ASGI, uvicorn)
  ├── Qdrant (Docker, 内存模式)
  ├── PostgreSQL (Docker volume)
  └── Redis (Docker)

估算成本: ¥300-500/月
```

### Month 6+: 增长期

```
Web层:    2台 2核4G (nginx upstream, 自动故障转移)
API层:    3台 4核8G (FastAPI, 水平扩展)
GPU机:    1台 GPU实例 (Embedding计算任务队列)
数据库:   RDS PostgreSQL (主从) + ElastiCache Redis
向量库:   Qdrant集群 (3节点)
对象存储: S3兼容 (MinIO集群 or 腾讯COS)
估算成本: ¥2000-4000/月
```

### Month 6-12: 增长期

```
全量K8s化:
  - API HorizontalPodAutoscaler (CPU>70%扩容)
  - Qdrant StatefulSet (3+节点)
  - 按需GPU算力 (Celery队列 + Spot实例)
  - CDN (腾讯云COS + CDN加速PDF/静态资源)
```

---

## 11. 迭代路线图（与 CEO v2.0 对齐）

```
Phase 0  验证 Sprint（第1-2个月）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 这是验证阶段，不是产品化
✅ 用 GPT-4 + LangChain 手动跑通 pipeline（不做产品化）
✅ 邀请 20 个真实用户内测
✅ 开放公测，收集付费意向
🎯 通过标准: >50% 用户主动问"什么时候可以付费"
❌ 未通过 → 立即 Pivot 或放弃

Month 3-5  MVP 产品化
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Next.js + FastAPI + Qdrant 产品化上线
✅ PDF上传 + 语义检索 + RAG问答
✅ 用户注册/登录/订阅（¥0 Free / ¥99 Pro / ¥299 Academic）
✅ 免费配额: 20篇论文 + 20次/天检索
✅ Pro/Academic 配额: 无限论文 + 无限检索
🎯 验证指标: 50用户, DAU>30%, 留存>40%

Month 6-12  增长 + Phase 2 探索
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Phase 2 功能探索（见下方，不做团队协作）
✅ 中文Embedding切换 (BGE-large-zh)
✅ 知识图谱 (实体识别 + 关系抽取)
✅ API开放文档 (可供学术平台集成)
✅ 移动端H5 (响应式)
🎯 验证指标: 2000用户, MRR>¥100k
```

**Phase 2 功能探索（暂定，不承诺）：**
- 收藏夹 + 标签管理体系（基于 MVP 验证结果决定优先级）
- 中文核心期刊元数据深度覆盖
- 论文推荐（基于用户已有论文的相似论文发现）

**不做（CEO v2.0 明确砍掉）：**
- ❌ 团队协作/共享收藏夹（MVP 和 Phase 2 均不做）
- ❌ 写作插件集成（MVP 不做）
- ❌ 知识图谱可视化（MVP 不做）

---

## 12. 关键决策总结

| # | 问题 | 决策 | 风险/备选 |
|---|-----|------|---------|
| 1 | 架构风格 | **BS + 服务端RAG** | 隐私用"即删原文件"换 |
| 2 | 向量库 | **Qdrant** | 开源可私有，Milvus太重 |
| 3 | PDF预览 | **pdf.js浏览器端** | 不做服务端预览API |
| 4 | Embedding | **OpenAI API先, BGE自托管后** | 中文能力Phase3补 |
| 5 | LLM | **Claude 3.5 Haiku主力** | GPT-4o-mini备用 |
| 6 | PDF解析 | **Unstructured.io (SaaS先)** | Phase2换Marker自托管降本 |
| 7 | 演进策略 | **MVP单体 → Phase3微服务** | Kent Beck原则 |
| 8 | 隐私隔离 | **user_id强制filter in Qdrant** | 一票否决项 |

---

> 文件版本记录
> - v1.0 (16:48): 初始架构设计
> - v2.0 (17:20): 整合CS/BS决策，补充PDF预览分离、即删原文件、全链路数据流、Phase1-3分离部署方案
