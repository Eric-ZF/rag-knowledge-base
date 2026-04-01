# Phase 1 工程架构文档

> **知研（Zhiyan）** — 学术文献研究工作台
> 架构风格：单体 + 演进式，Phase 1 以速度优先

---

## 一、需求摘要

### 核心功能（MVP 三件套）
1. 批量上传 + 云端存储（不限量）
2. 跨论文方法论审计问答
3. 文献综述生成（Markdown）

### 非功能需求

| 指标 | 目标 |
|-----|------|
| 论文处理量 | 单用户 100-500 篇 |
| 冷启动时间（20篇索引） | < 30 秒 |
| 问答响应时间 | < 5 秒 |
| 可用性 | 99.5%（单机部署） |
| 数据持久性 | 论文不丢失 |

---

## 二、技术选型

| 组件 | 选型 | 理由 | 不引入原因 |
|-----|------|------|-----------|
| 后端框架 | FastAPI（已有） | 异步 + SSE 原生支持 | — |
| 向量数据库 | ChromaDB（已有） | Phase 0 已验证 | — |
| Embedding | BGE large zh（已有） | 中英双语支持 | — |
| LLM | MiniMax M2（已有） | 成本低，中文好 | — |
| 前端 | HTML/JS（已有） | 快速迭代 | — |
| 文件存储 | 本地文件系统 | Phase 1 够用 | OSS 过度设计 |
| 用户数据 | JSON 文件（已有） | Phase 0 已验证 | PostgreSQL 过渡设计 |

**约束**：不引入额外基础设施，单机可跑。

---

## 三、整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                         Client (Browser)                      │
│    ┌──────────────────────────────────────────────────────┐  │
│    │  知研 Web App (index.html)                          │  │
│    │  • 批量上传 UI    • 论文列表    • 跨论文问答         │  │
│    │  • SSE 进度条    • 文献综述展示                     │  │
│    └──────────────────────────────────────────────────────┘  │
└───────────────────────────────┬──────────────────────────────┘
                                │ HTTP / SSE
┌───────────────────────────────▼──────────────────────────────┐
│                      API Layer (FastAPI)                     │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │
│  │ Auth API   │  │ Paper API  │  │ Chat API           │    │
│  │ 登录/注册   │  │ 上传/列表/删除│  │ 跨论文问答          │    │
│  │ JWT Token  │  │ SSE 进度    │  │ 综述生成           │    │
│  └────────────┘  └────────────┘  └────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Background Tasks (PDF 异步索引)                       │   │
│  │ parse_pdf → chunk → embed → ChromaDB                 │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────────┬──────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐
│  File System      │  │   ChromaDB     │  │  MiniMax API     │
│  /tmp/papers/    │  │   Vector DB    │  │  (外部服务)       │
│  原始 PDF 存储    │  │  用户论文向量   │  │  LLM 生成回答     │
│  (持久化到磁盘)   │  │  (已有)        │  │                  │
└──────────────────┘  └────────────────┘  └──────────────────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                    ┌──────────────────────┐
                    │  JSON 文件持久化      │
                    │  papers_db.json      │
                    │  users_db.json       │
                    └──────────────────────┘
```

---

## 四、数据流设计

### 4.1 论文上传流程

```
Client                      FastAPI Backend                  ChromaDB
   │                             │                               │
   │  POST /papers/upload        │                               │
   │  (multipart/form-data)      │                               │
   │────────────────────────────>│                               │
   │                             │                               │
   │  1. 保存 PDF → /tmp/papers/│                               │
   │  2. 生成 paper_id (UUID)   │                               │
   │  3. 写入 papers_db.json    │                               │
   │  4. user["papers"].append()│                               │
   │  5. 返回 paper_id          │                               │
   │  202 Accepted              │                               │
   │<────────────────────────────│                               │
   │                             │                               │
   │                             │  Background Task:              │
   │                             │  process_pdf(paper_id)        │
   │                             │──────────────────────────────>│
   │                             │    SSE: parsing (10%)          │
   │                             │    SSE: chunking (30%)        │
   │                             │    SSE: embedding (60%)       │
   │                             │    SSE: indexing (90%)        │
   │                             │    SSE: complete (100%)       │
   │                             │<──────────────────────────────│
   │                             │  update paper status: ready   │
   │                             │                               │
   │  GET /papers/{id}/events   │                               │
   │  (SSE keep-alive)          │                               │
   │────────────────────────────>│                               │
```

### 4.2 跨论文问答流程

```
Client                      FastAPI Backend              ChromaDB / MiniMax
   │                             │                             │
   │  POST /chat                 │                             │
   │  {question, paper_ids?, top_k?}                            │
   │────────────────────────────>│                             │
   │                             │                             │
   │  1. 可选：限定论文范围       │                             │
   │     (paper_ids 参数)        │                             │
   │                             │                             │
   │  2. Hybrid Search:          │                             │
   │     query_embeddings (BGE)  │                             │
   │     + keyword filter        │                             │
   │                             │────────────────────────────>│
   │                             │  检索 Top-K chunks          │
   │                             │<────────────────────────────│
   │                             │                             │
   │  3. 组装 Prompt:             │                             │
   │     system: 你是一个学术研究助手│                           │
   │     user: {question}         │                             │
   │     + retrieved chunks       │                             │
   │                             │                             │
   │                             │ MiniMax Chat API             │
   │                             │────────────────────────────>│
   │                             │  生成回答 + citations        │
   │                             │<────────────────────────────│
   │                             │                             │
   │  {answer, citations}        │                             │
   │<────────────────────────────│                             │
```

### 4.3 文献综述生成流程

```
Client                      FastAPI Backend
   │
   │  POST /chat
   │  {question: "生成关于 XXX 研究方向的文献综述",
   │    paper_ids: ["id1", "id2", ...],
   │    mode: "survey"}
   │────────────────────────────>│
   │
   │  1. 检索相关 chunks (top_k=20)
   │  2. 按论文分组
   │  3. 组装结构化 prompt:
   │     "你是一个学术研究员，请根据以下论文片段，
   │      生成一篇结构化文献综述，包含：
   │      (1) 研究主题概述
   │      (2) 主要理论框架
   │      (3) 方法论分类
   │      (4) 数据来源分类
   │      (5) 结论与研究空白"
   │  4. MiniMax 生成 Markdown 格式综述
   │
   │  {answer: "## 文献综述\n\n### 1. 研究概述...",
   │    citations: [...],
   │    meta: {paper_count: 12, theme: "碳边境调节"}}
   │<────────────────────────────│
```

---

## 五、接口设计

### 5.1 论文管理 API

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | `/papers/upload` | 上传 PDF（multipart），返回 paper_id |
| GET | `/papers` | 论文列表 |
| DELETE | `/papers/{id}` | 删除论文（同时清理 ChromaDB chunks） |
| GET | `/papers/{id}/status` | 论文状态（processing/ready/error） |
| GET | `/papers/{id}/events` | SSE 实时进度推送 |
| GET | `/papers/{id}/chunks` | 查看论文 chunks（调试用） |

### 5.2 对话 API

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | `/chat` | 跨论文问答（JSON，响应快） |
| POST | `/chat/survey` | 文献综述生成（特殊 prompt） |

### 5.3 请求/响应示例

```python
# POST /chat — 跨论文问答
Request:
{
    "question": "哪些论文用了实证模型？用了哪些数据？",
    "paper_ids": ["id1", "id2"],      # 可选，不填则搜索全库
    "top_k": 8
}

Response:
{
    "answer": "## 回答\n\n根据检索结果，以下论文使用了实证模型：\n\n"
              "### 1. 论文A — OLS 回归模型\n"
              "使用了国家统计局 2010-2020 年省级面板数据...\n\n"
              "### 2. 论文B — 双重差分法（DID）\n"
              "数据来源于企业年报和环保部门公开数据...",
    "citations": [
        {
            "paper_id": "xxx",
            "title": "论文A标题",
            "chunk_index": 3,
            "page_number": 5,
            "content": "本文采用OLS回归模型..."
        }
    ]
}

# POST /chat/survey — 文献综述生成
Request:
{
    "question": "碳边境调节机制相关研究的方法论综述",
    "paper_ids": ["id1", "id2", "id3"],  # 可选
    "top_k": 20
}

Response:
{
    "answer": "## 文献综述：碳边境调节机制研究的方法论分析\n\n"
              "### 一、研究概述\n\n"
              "### 二、理论框架分类\n\n"
              "### 三、方法论分布\n\n"
              "### 四、数据来源\n\n"
              "### 五、结论与研究空白",
    "citations": [...],
    "meta": {
        "paper_count": 12,
        "themes": ["碳边境调节", "气候政策"],
        "models": ["OLS", "DID", "CGE"],
        "data_sources": ["国家统计局", "企业年报"]
    }
}
```

---

## 六、数据模型

### 6.1 papers_db.json（已有，Phase 0.6）

```json
{
  "paper_id": {
    "paper_id": "uuid",
    "user_id": "user_id",
    "title": "论文标题",
    "status": "processing|ready|error",
    "chunks_count": 22,
    "collection": "user_xxx",
    "file_path": "/tmp/papers/uuid.pdf",
    "created_at": "2026-04-01T10:00:00Z",
    "updated_at": "2026-04-01T10:05:00Z",
    "methodology_tags": ["OLS", "DID"],
    "error_msg": null
  }
}
```

### 6.2 ChromaDB Collection Schema

```
Collection: user_{user_id}
├── metadata: {embedding_dimension: 1024, model: "BAAI/bge-large-zh-v1.5"}
│
├── Documents (page_content):
│   └── 论文文本块（chunk_size=2000, overlap=200）
│
└── Embeddings:
    └── 1024d BGE 向量

Metadata fields per chunk:
├── paper_id: str        # 论文 UUID
├── title: str           # 论文标题
├── chunk_index: int     # chunk 序号
├── page_number: int     # 来源页码
└── text: str            # 前 200 字预览
```

### 6.3 users_db.json（已有，Phase 0.6）

```json
{
  "user_id": {
    "user_id": "uuid",
    "email": "xxx@xxx.com",
    "password_hash": "$2b$12$...",
    "plan": "free|pro|team",
    "collection": "user_uuid",
    "papers": ["paper_id_1", "paper_id_2"],
    "created_at": "2026-04-01T10:00:00Z"
  }
}
```

---

## 七、演进计划

### Phase 1（4月）— 单体架构，快速验证

```
┌─────────────────────────────────────┐
│         FastAPI 单体服务             │
│  Papers API + Chat API + Auth       │
│  + ChromaDB（本地文件）              │
│  + MiniMax API                      │
│  + JSON 文件持久化                   │
└─────────────────────────────────────┘

目标：
- 验证讲师需求真实
- 核心流程跑通
- 不考虑多机部署
```

### Phase 2（5月）— 引入数据库 + 文件存储

```
新增：
- PostgreSQL：用户管理 + 论文元数据（替代 JSON）
- OSS/S3：PDF 文件存储（支持多机部署）
- Redis：Query 缓存（减少重复 LLM 调用）

改动：
- 无结构变化
- 只是持久层升级
- API 兼容 Phase 1
```

### Phase 3（6月）— 性能优化 + 团队功能

```
新增：
- 读写分离：索引服务 vs 查询服务分离
- 团队知识库：多用户共享 collection
- 流式输出：SSE streaming chat

改动：
- 仅在 Phase 2 验证后才考虑
- API 层可能需要拆分
```

---

## 八、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|-----|------|------|------|
| MiniMax API 限流/涨价 | 中 | 高 | Phase 2 预留切换到其他 LLM 的抽象层 |
| ChromaDB 规模上限 | 低 | 中 | Phase 2 迁移到 Milvus/PgVector |
| 讲师需求验证失败 | 中 | 高 | Phase 1 先约演示再开发 |
| PDF 解析失败（扫描件/加密） | 中 | 低 | 降级：提示用户上传文本版 |
| JSON 文件并发写入冲突 | 中 | 中 | Phase 2 迁移到 PostgreSQL |

---

## 九、测试策略

| 测试类型 | 目标 | 工具 |
|---------|------|------|
| 单元测试（PDF 解析/分块） | 覆盖率 > 80% | pytest |
| API 集成测试 | 关键路径 100% | FastAPI TestClient |
| 端到端（上传→问答） | 手动演示 | — |
| 性能测试（批量索引 100 篇） | 延迟基准 | time/curl |

**Phase 1 不做**：自动化性能测试、混沌测试（过早）

---

## 十、技术债务（Phase 1 已知问题）

| 问题 | 原因 | 解决方案 Phase |
|-----|------|--------------|
| ChromaDB 内置 embedder 维度冲突 | 存 1024d，BGE 编码被绕 | 已用 query_embeddings 绕过 |
| JSON 文件并发写入 | 无锁机制 | Phase 2 迁移 PostgreSQL |
| 旧 22 chunks 维度不一致 | 历史遗留 | 忽略，新上传统一 BGE |
| PDF 存储在 /tmp | 重启丢失 | Phase 2 迁移 OSS |

---

**下一步**：约讲师演示 Phase 0.6 → 收集反馈 → 确定 Phase 1 优先级

---

*Make the change easy, then make the easy change.*
*— Kent Beck*
