# Phase 0 验证 Sprint — 快速启动

## 目标

用手动的、半自动化的方式，快速验证核心假设：**研究者是否愿意为"私有论文库 RAG 问答"付钱。**

---

## 环境准备

### 1. 安装依赖

```bash
cd phase0/backend
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入真实 API Key
```

必需的环境变量：
- `OPENAI_API_KEY` — Embedding 模型
- `ANTHROPIC_API_KEY` — Claude Haiku（问答）
- `QDRANT_URL` — Qdrant 地址（本地开发用 Docker）

### 3. 启动 Qdrant（Docker）

```bash
docker pull qdrant/qdrant
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  qdrant/qdrant
```

### 4. 启动后端

```bash
cd phase0/backend
uvicorn main:app --reload --port 8000
```

### 5. 打开前端

直接用浏览器打开 `phase0/frontend/index.html`（或者用 VS Code Live Server）。

---

## Phase 0 验证流程

### 第 1-2 周：手动 Pipeline 验证

不要求完整产品，只验证：
1. **上传一篇 PDF** → LangChain 能否正确解析（公式/表格/段落）
2. **向量检索** → 能否找到相关内容（手动检查 top-5 结果）
3. **RAG 问答** → Claude 的回答是否准确，引用是否正确

### 第 3-4 周：真实用户内测

邀请 5-10 个真实用户（研究生/教授）：
1. 让他们上传自己的论文
2. 让他们提问
3. 记录：使用频率、反馈、是否主动询问付费

### 第 5-8 周：公测 + 付费意向收集

开放公测（无需完整产品，可以用简陋的界面）：
- 收集"如果现在收费，你愿意付多少"的反馈
- **通过标准**：>50% 用户主动问"什么时候可以付费"

---

## 技术栈（Phase 0）

| 组件 | 选型 | 说明 |
|-----|------|------|
| 后端 | FastAPI | 最小接口，快速迭代 |
| PDF 解析 | Unstructured | 保留公式/表格/段落 |
| Embedding | `text-embedding-3-small` | OpenAI，1536 维 |
| 向量库 | Qdrant（Docker 本地）| HNSW 索引 |
| LLM | Claude Haiku | 快速，低成本 |
| 前端 | 极简单页 HTML | Phase 0 不追求 UI |

---

## ⚠️ Phase 0 安全说明

Phase 0 是**开发/验证模式**，以下安全措施**未启用**：
- JWT 使用 HS256（⚠️ 生产必须 RS256）
- 用户密码明文存储（⚠️ 生产必须 bcrypt）
- CORS 允许所有来源（⚠️ 生产必须白名单）
- 内存存储 users/papers（⚠️ 生产必须 PostgreSQL）

**不要在 Phase 0 阶段上传真实敏感的论文数据。**

---

## 目录结构

```
phase0/
├── backend/
│   ├── main.py          # FastAPI 入口
│   ├── pipeline.py      # PDF → Markdown → Embedding → Qdrant
│   ├── chat.py          # Claude RAG 问答
│   ├── auth.py          # JWT 认证（Phase 0 HS256）
│   ├── requirements.txt  # 依赖
│   └── .env.example     # 环境变量模板
├── frontend/
│   └── index.html       # 极简单页（登录/上传/聊天）
└── README.md
```

---

## 成功标准（Phase 0 通过门槛）

| 指标 | 目标 |
|-----|------|
| PDF 解析成功率 | > 90% |
| 向量检索 recall | > 60%（人工抽检 top-5）|
| RAG 回答准确率 | > 70%（用户主观评价）|
| 内测用户使用频率 | 平均每人每周 ≥ 5 次问答 |
| 隐私拒绝率 | < 10% 用户拒绝上传 |
| 付费意向 | > 50% 用户主动询问付费 |
