# 📐 RAG 学术知识库 — 系统架构文档

> 本文档描述 Phase 0（当前）和 Phase 1（规划）的系统架构。Phase 0 为单体 FastAPI，Phase 1 拆分为五层。

---

## 一、当前系统架构（Phase 0.8）

### 1.1 架构概览

Phase 0 是**单体 FastAPI 应用**，所有模块运行在单一进程内，通过 systemd 托管。

```
用户浏览器
    │  HTTP / SSE
    ▼
Nginx (80+8080)
    │  反向代理 / 静态托管
    ▼
FastAPI (:8000)  ← systemd 托管
    │
    ├── Auth (JWT)
    ├── Papers (CRUD + SSE 索进进度)
    ├── Chat (混合检索 + LLM 生成)
    └── RAG Pipeline (PDF → ChromaDB)
    │
    ├── ChromaDB (向量存储)
    ├── MiniMax API (LLM)
    └── 文件系统 (PDF)
```

### 1.2 后端模块（backend/）

```
backend/
├── main.py              # FastAPI 入口、lifespan 初始化、路由挂载
├── auth.py              # JWT token 签发与验证
├── chat.py              # /chat 端点：检索 → prompt → LLM → 格式化
├── config.py            # 环境变量读取、启动校验
├── data.py              # users_db / papers_db 持久化（JSON 文件）
├── feedback.py          # 用户反馈存储
├── folders_db.py        # 文件夹树 CRUD（用户隔离）
├── logging_config.py    # 结构化日志配置
├── papers_db.py         # papers_db（论文元数据，JSON 持久化）
├── pipeline.py          # PDF → Docling 解析 → 两级 chunk → BGE embedding → ChromaDB
├── rate_limit.py        # 简单速率限制（内存计数器）
├── requirements.txt     # Python 依赖
├── state.py             # 运行时共享状态（users 引用、folders 引用）
├── start.sh             # 开发启动脚本
├── routers/
│   ├── auth.py          # /auth/* 路由
│   ├── chat.py          # /chat/* 路由
│   ├── feedback.py      # /feedback/* 路由
│   └── papers.py        # /papers/* 路由
└── tests/
    └── test_api.py      # pytest API 测试
```

**关键设计决策：**

- **数据存储**：JSON 文件（`papers_db.json`、`users_db.json`），无数据库依赖
- **向量存储**：ChromaDB（PersistentClient，持久化到磁盘）
- **用户隔离**：JWT sub claim → users_db lookup → papers_db filter by user_id
- **文件夹系统**：树形结构，每用户最多 100 个文件夹，支持嵌套
- **SSE 进度流**：上传/索引进度通过 `text/event-stream` 实时推送

### 1.3 前端（frontend/）

```
frontend/
├── index.html   # 主界面（单文件 SPA，~2100 行）
└── demo.html   # 简化演示页
```

**index.html 功能模块：**

| 模块 | 说明 |
|------|------|
| Auth | 登录/注册（手机号 + 密码） |
| FolderTree | 左侧文件夹树导航 |
| PaperList | 论文卡片列表（勾选 + 批量移动） |
| UploadPanel | PDF 上传（支持多文件排队） |
| ChatPanel | 问答界面（流式输出 + 思考折叠 + 引用列表） |
| MarkdownRenderer | marked.js + 自定义 AST 过滤（引用块清理） |

### 1.4 RAG Pipeline（pipeline.py）

```
PDF 文件
    │
    ▼
Docling 解析
    ├── 提取文本段落
    ├── 提取表格（转为 Markdown）
    ├── 提取页码信息
    └── 输出结构化 JSON
    │
    ▼
两级 Chunk 分块
    ├── Recall Chunk：400-800 tokens（按语义段切分，用于召回）
    └── Evidence Chunk：150-350 tokens（单段/结论/方法，用于引用）
    │
    ▼
BGE-large-zh-v1.5 Embedding（CPU 推理，1024 维）
    │
    ▼
ChromaDB（collection: papers_{user_id}）
    └── 写入 (chunk_text, embedding, metadata: {paper_id, page_range, chunk_type})
```

### 1.5 混合检索（chat.py + hybrid_search）

```
用户 Query
    │
    ├─→ BM25 关键词检索 → top-40
    │
    ├─→ BGE 向量检索 → top-40
    │
    ▼
RRF (Reciprocal Rank Fusion) 融合 → top-20
    │
    ▼
CrossEncoder 重排（可选，内存允许时）→ top-12
    │
    ▼
Evidence 过滤（去除引言/参考文献/背景块）→ 保留 4-6 条
    │
    ▼
构建 Prompt（System + Retriever Chunks + User Query）
    │
    ▼
MiniMax M2.7 生成（流式 SSE）
    │
    ▼
marked.js 渲染 + AST 过滤（清理 LLM 生成的参考文献块）
```

### 1.6 数据流（用户隔离）

```
JWT Token (Authorization: Bearer <token>)
    │
    ▼
auth.py 验证 → user_id
    │
    ├─→ /papers → papers_db.filter(user_id=user_id)
    │
    ├─→ /chat → ChromaDB collection = papers_{user_id}
    │
    └─→ /folders → folders_db.filter(user_id=user_id)
```

---

## 二、Phase 1 演进架构（规划）

> ⚠️ 以下为规划内容，代码尚未实现。Phase 1 目标是将单体 FastAPI 拆分为清晰的分层架构。

### 2.1 五层架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Layer 1: 数据接入层                           │
│         Papers Upload API + Parser Factory + Deduplication       │
├─────────────────────────────────────────────────────────────────┤
│                   Layer 2: 文档解析与知识加工层                    │
│        Docling Parser + Paper Profile Extractor (LLM)            │
├─────────────────────────────────────────────────────────────────┤
│                     Layer 3: Chunk 切分层                         │
│         Recall Chunk (召回) + Evidence Chunk (引用)              │
├─────────────────────────────────────────────────────────────────┤
│                    Layer 4: 检索与排序层                          │
│      BM25 + Vector Search + RRF + CrossEncoder Rerank           │
├─────────────────────────────────────────────────────────────────┤
│                    Layer 5: 生成与服务层                          │
│    Evidence-First Prompt + MiniMax M2.7 + Citation Formatter    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Phase 1 目录结构（目标）

```
backend/
├── main.py                         # FastAPI 入口（不变）
├── config.py                       # 环境变量（不变）
├── auth.py                         # JWT（不变）
│
├── ingestion/                      # Layer 1: 数据接入
│   ├── __init__.py
│   ├── parser_factory.py           # 解析器工厂
│   ├── pdf_parser.py               # PDF 解析
│   ├── doc_parser.py               # Word/Excel 解析
│   ├── url_parser.py               # 网页抓取
│   └── deduplicator.py             # SHA256 去重
│
├── parsing/                        # Layer 2: 文档解析
│   ├── __init__.py
│   ├── docling_parser.py           # Docling 结构化输出
│   └── profile_extractor.py        # LLM 抽取文献画像
│
├── chunking/                       # Layer 3: 知识加工
│   ├── __init__.py
│   ├── hierarchical_chunker.py    # 两级 chunk 设计
│   └── token_counter.py            # tiktoken 计数
│
├── retrieval/                      # Layer 4: 检索排序
│   ├── __init__.py
│   ├── bm25_retriever.py           # BM25 关键词检索
│   ├── vector_retriever.py          # ChromaDB 向量检索
│   ├── hybrid_merger.py             # RRF 融合
│   └── reranker.py                  # CrossEncoder 重排
│
├── generation/                     # Layer 5: 生成
│   ├── __init__.py
│   ├── prompt_builder.py            # System prompt 构造
│   └── answer_formatter.py          # 输出格式控制
│
├── storage/                        # 数据持久化（当前 JSON → 未来 PostgreSQL）
│   ├── __init__.py
│   ├── papers.py                   # papers 主表
│   ├── sections.py                 # sections 表
│   ├── chunks.py                   # chunks 表
│   ├── profiles.py                 # paper_profiles 表
│   └── qa_logs.py                  # qa_logs 表
│
└── routers/                        # API 路由（重构）
    ├── papers.py
    ├── chat.py
    └── upload.py

frontend/                           # Vanilla JS → React SPA
├── index.html
└── components/
    ├── UploadPanel.jsx
    ├── ChatPanel.jsx
    ├── PaperList.jsx
    ├── ProfileDrawer.jsx
    └── CitationCard.jsx
```

### 2.3 Phase 1 数据库表设计（PostgreSQL + pgvector）

```sql
-- papers 主表
CREATE TABLE papers (
    paper_id      UUID PRIMARY KEY,
    user_id       UUID NOT NULL,
    title         TEXT NOT NULL,
    authors       TEXT[],
    year          INT,
    source        TEXT,
    doi           TEXT,
    language      TEXT DEFAULT 'zh',
    abstract      TEXT,
    keywords      TEXT[],
    file_hash     TEXT UNIQUE,        -- SHA256 去重
    version       TEXT,               -- preprint/accepted/published
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

-- sections 章节表
CREATE TABLE sections (
    section_id    UUID PRIMARY KEY,
    paper_id      UUID REFERENCES papers(paper_id),
    title         TEXT,
    path          TEXT,               -- "1.2.3" 层级路径
    order_idx     INT,
    page_start    INT,
    page_end      INT
);

-- chunks 证据块表
CREATE TABLE chunks (
    chunk_id      UUID PRIMARY KEY,
    paper_id      UUID REFERENCES papers(paper_id),
    section_id    UUID REFERENCES sections(section_id),
    chunk_type    TEXT,               -- body/table/figure/abstract/conclusion
    chunk_text    TEXT,
    token_count   INT,
    page_range    TEXT,
    recall_chunk_id UUID,              -- 上一层级召回块
    embedding     vector(1024)          -- pgvector 列
);

-- paper_profiles 文献画像表（LLM 抽取）
CREATE TABLE paper_profiles (
    paper_id      UUID PRIMARY KEY REFERENCES papers(paper_id),
    research_question TEXT,
    research_object  TEXT,
    data_source     TEXT,
    time_span       TEXT,
    methods         TEXT[],
    mechanisms      TEXT[],
    main_findings   TEXT,
    heterogeneity  TEXT,
    policy_implication TEXT,
    limitations     TEXT
);

-- qa_logs 问答日志表
CREATE TABLE qa_logs (
    query_id          UUID PRIMARY KEY,
    user_id           UUID NOT NULL,
    user_query        TEXT,
    rewritten_query   TEXT,
    retrieved_chunks   UUID[],
    selected_chunks   UUID[],
    answer_text       TEXT,
    citation_list     JSONB,
    feedback_score   INT,             -- 1-5
    created_at        TIMESTAMP DEFAULT NOW()
);

-- 向量索引
CREATE INDEX ON chunks USING ivfflat (embedding vector_cosine_ops);
```

### 2.4 Phase 1 检索流程

```
用户 Query
    │
    ▼
Query 预处理（拼写检查 / 同义词扩展）
    │
    ├─→ BM25 检索 → top-40
    │
    ├─→ 向量检索 → top-40
    │
    ▼
RRF 融合（k=60）→ top-80
    │
    ▼
元数据过滤（year / authors / methods / language）
    │
    ▼
语义重排（CrossEncoder）→ top-12
    │
    ▼
Evidence 过滤（去除引言/参考文献/背景）
    │
    ▼
选取 top-6 条证据 → 构建 Prompt
    │
    ▼
MiniMax M2.7 生成
    │
    ▼
引用格式化 → 输出
```

### 2.5 Phase 1 典型业务流程

**场景 1：单问题智能问答（最高频）**
```
用户输入问题
  → Query 改写（扩展同义词）
  → 混合检索（BM25 + 向量 + 元数据过滤）
  → RRF 融合 → 语义重排
  → 证据块选取
  → 证据约束生成（MiniMax M2.7）
  → 引用格式化
  → 前端渲染（引用可点击）
  → QA 日志写入
```

**场景 2：文献综述辅助（中频）**
```
用户输入综述主题（如："数字税对绿色创新的影响"）
  → 按主题 + 年份混合检索 → 召回 30-50 篇
  → 抽取所有文献画像
  → 聚类分析（按研究问题/方法/结论分组）
  → 生成综述框架（共识区 / 分歧区 / 空白区）
  → 输出结构化综述文本 + 参考文献列表
```

**场景 3：研究设计比较（低频）**
```
用户输入："有哪些文献用 DID 研究数字政策"
  → 元数据过滤（method 包含 "DID"）
  → 返回文献列表 + 画像摘要
  → 生成比较表
  → 导出 Markdown / CSV
```

### 2.6 Phase 1 评测框架

| 层次 | 指标 | 目标 |
|------|------|------|
| **检索层** | Recall@K | ≥ 0.85 |
| | MRR | ≥ 0.6 |
| | nDCG@K | ≥ 0.65 |
| | 命中论文率 | ≥ 80% |
| | 命中证据率 | ≥ 70% |
| **回答层** | Groundedness（声明归因率）| ≥ 0.9 |
| | Answer Relevance | ≥ 0.8 |
| | Citation Accuracy | ≥ 0.85 |
| | 矛盾率 | ≤ 5% |
| | 证据覆盖率 | ≥ 0.75 |
| **系统层** | P50 响应时延 | ≤ 8s |
| | P95 响应时延 | ≤ 20s |
| | 解析成功率 | ≥ 95% |
| | 索引更新延迟 | ≤ 60s |

### 2.7 Phase 1 上线计划

| 阶段 | 内容 | 交付物 |
|------|------|--------|
| **Phase 1.0** | 数据层重构（papers/sections/chunks/profiles/qa_logs）| 数据库表 + 迁移脚本 |
| **Phase 1.1** | 解析层（PDF解析 + 两级chunk + 去重）| `parse_document()` |
| **Phase 1.2** | 检索层（BM25 + 向量混合 + RRF + Rerank）| `hybrid_search()` |
| **Phase 1.3** | 生成层（证据约束 + 结构化输出 + QA日志）| `/chat` 重构 |
| **Phase 1.4** | 前端（React SPA：检索/问答/溯源/比较）| React App |
| **Phase 1.5** | 评测层（指标采集 + 反馈面板 + 优化闭环）| `/admin/analytics` |

---

## 三、Phase 0 → Phase 1 迁移路径

### 3.1 现有代码处置

| 现有文件 | Phase 1 处置 |
|---------|------------|
| `pipeline.py` | 拆分到 `ingestion/` + `chunking/` |
| `chat.py` | 拆分到 `retrieval/` + `generation/` |
| `data.py` | 替换为 `storage/`（PostgreSQL）|
| `papers_db.py` | 替换为 `storage/papers.py` |
| `folders_db.py` | 迁移到 `storage/folders.py` |
| `auth.py` | 保持不变 |
| `main.py` | 路由重构，核心逻辑下放到各层 |

### 3.2 迁移原则

1. **保持 API 兼容**：Phase 1 API 端点与 Phase 0 兼容，前端无需同步修改
2. **数据迁移脚本**：提供一次性的 JSON → PostgreSQL 迁移脚本
3. **ChromaDB → pgvector**：embedding 列迁移，collection 名复用
4. **功能开关**：通过环境变量切换新旧实现，灰度验证

---

## 四、技术选型

| 模块 | Phase 0 | Phase 1（规划）| 理由 |
|------|---------|---------------|------|
| **Web 框架** | FastAPI | FastAPI | 异步优势 |
| **向量数据库** | ChromaDB | pgvector | 统一数据库，减少运维 |
| **关系数据库** | JSON 文件 | PostgreSQL | 结构化查询能力 |
| **PDF 解析** | Docling 2.x | Docling 2.x | 表格/版面感知 |
| **Embedding** | BGE-large-zh-v1.5 | BGE-large-zh-v1.5 | 中文最优 1024d |
| **Reranker** | CrossEncoder | CrossEncoder | CPU 可跑 |
| **LLM** | MiniMax M2.7 | MiniMax M2.7 | 成本优先 |
| **前端** | Vanilla JS SPA | React SPA | 组件化开发效率 |
| **BM25** | rank_bm25 | rank_bm25 | 成熟稳定 |
