# 🔬 RAG 学术知识库

> 基于私有论文库的智能问答系统 — 让 AI 回答可溯源、可验证

[![GitHub Repo](https://img.shields.io/badge/GitHub-Repository-blue?logo=github)](https://github.com/Eric-ZF/rag-knowledge-base)
[![Python](https://img.shields.io/badge/Python-3.12+-green?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-orange?logo=fastapi)](https://fastapi.tiangolo.com/)

---

## 🎯 项目简介

一个面向研究者/学术人员的私有论文 RAG 问答系统。不同于通用 RAG，本系统专注于**溯源验证**：

- 每句回答均可点击跳转到原始 PDF 页面
- 支持中文学术论文的混合检索（向量 + 关键词）
- 表格、段落结构化解析，不丢失论文原始结构

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                        用户浏览器                             │
│              http://124.156.204.163:8080                     │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼───────────────────────────────────┐
│                      Nginx (port 80+8080)                     │
│              静态文件托管 + API 反向代理 (:8000)               │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                   FastAPI Backend (:8000)                     │
│                   systemd 托管 · 自动重启                       │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Auth API  │  │ Papers API   │  │    Chat API        │  │
│  │  JWT 登录   │  │ 上传/索引/删除 │  │  混合检索 + 生成    │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │               RAG Pipeline                             │   │
│  │  PDF ──▶ Docling ──▶ 两级Chunk ──▶ BGE Embedding   │   │
│  │         (解析)    (召回+证据)     (1024d向量)          │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────┬───────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌────────────┐  ┌─────────────┐  ┌──────────────┐
   │  ChromaDB  │  │ MiniMax API  │  │  文件系统     │
   │  (向量库)   │  │  (LLM 生成)  │  │  (PDF 存储)   │
   └────────────┘  └─────────────┘  └──────────────┘
```

---

## ⚡ 核心技术特性

| 特性 | 实现方案 |
|------|---------|
| **PDF 解析** | Docling 2.x — 表格/段落/参考文献结构化 |
| **两级 Chunk** | Recall Chunk（召回）+ Evidence Chunk（精确引用） |
| **混合检索** | BGE 向量检索 + BM25 关键词融合 |
| **重排序** | CrossEncoder（内存允许时启用） |
| **引用定位** | 点击引用直接跳转 PDF 对应页码 |
| **LLM** | MiniMax-M2.7（支持中文学术写作） |
| **Embedding** | BGE-large-zh-v1.5（本地 CPU 推理，1024d） |

---

## 📁 目录结构

```
phase0/
├── backend/
│   ├── main.py              # FastAPI 入口 + 路由定义
│   ├── pipeline.py          # PDF → Docling解析 → 两级Chunk → ChromaDB
│   ├── chat.py              # 混合检索 → MiniMax LLM 生成
│   ├── hybrid_search.py     # 向量 + BM25 混合检索
│   ├── auth.py              # JWT 认证
│   ├── data.py              # papers_db / users_db 持久化
│   └── config.py            # 环境变量配置
├── frontend/
│   ├── index.html           # 主界面（论文列表 + 聊天）
│   └── demo.html            # 简化演示页
├── tests/
│   ├── api_tests.sh         # API 自动化测试
│   └── e2e/rag_e2e.py      # Playwright E2E 测试
├── docs/                    # 架构文档
├── scripts/                 # 部署/运维脚本
└── hooks/                  # pre-commit hooks
```

---

## 🚀 快速开始

### 环境要求

- **Python** 3.12+
- **Linux** (Ubuntu 20.04+)
- **2GB+ 内存**（推荐 4GB，用于加载 BGE 模型）

### 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

requirements.txt 核心依赖：
- `fastapi` + `uvicorn`
- `chromadb` (持久化向量库)
- `docling>=2.0.0` (PDF 解析)
- `semchunk` (两级分块)
- `sentence-transformers` (BGE Embedding)
- `python-jose` (JWT 认证)

### 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 .env，填入：
#   MINIMAX_API_KEY=sk-cp-xxxxx
#   MINIMAX_GROUP_ID=xxxxx
```

### 启动服务

```bash
# 方式一：直接启动（开发用）
cd backend
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000

# 方式二：systemd 生产部署
sudo cp scripts/rag-backend.service /etc/systemd/system/
sudo systemctl enable rag-backend
sudo systemctl start rag-backend
```

### 访问前端

```
http://<服务器IP>:8080
```

默认测试账号：`bosstest@boss.io` / `BossPhase0`

---

## 🔌 API 文档

启动后访问：`http://localhost:8000/docs`（Swagger UI）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/auth/login` | POST | 登录 |
| `/papers` | GET | 论文列表 |
| `/papers/upload` | POST | 上传 PDF（返回 SSE 索进进度） |
| `/papers/{id}` | DELETE | 删除论文 |
| `/papers/{id}/pdf` | GET | 下载原始 PDF |
| `/papers/{id}/events` | GET | SSE 索进进度流 |
| `/chat` | POST | RAG 问答 |

---

## 🧪 测试

```bash
# API 测试（~5 秒）
bash tests/api_tests.sh

# E2E 测试（~2 分钟，需要 Playwright）
python3 tests/e2e/rag_e2e.py
```

---

## 📊 当前状态

| 组件 | 状态 | 说明 |
|------|------|------|
| Backend | ✅ 运行中 | systemd 托管 |
| ChromaDB | ✅ 持久化 | `/root/.openclaw/rag-data/chromadb` |
| papers_db | ✅ 持久化 | JSON 文件 |
| PDF 存储 | ✅ 持久化 | `/root/.openclaw/rag-data/papers/` |
| systemd 守护 | ✅ 已配置 | 崩溃 5s 自动重启 |
| MiniMax API | ✅ 正常 | M2.7 模型 |

---

## 🔮 技术演进路线

```
Phase 0.8 (当前) ───▶ Phase 1 ───▶ Phase 2 ───▶ Phase 3
  单体FastAPI            分层架构       PostgreSQL       域名+HTTPS
  单用户/文件夹         多论文索引      OSS对象存储      团队协作
  marked.js渲染         元数据过滤      多机部署
                       置信度标注
```

详细架构演进规划见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## ⚠️ 已知限制

- **内存敏感**：BGE 模型约 1.3GB，4GB 以上服务器推荐
- **公司网络**：腾讯云 8080 端口可能被拦截，可通过域名/HTTPS 解决
- **单用户优先**：Phase 0-1 以单用户为主，多用户协作待 Phase 3

---

## 📄 License

MIT License
