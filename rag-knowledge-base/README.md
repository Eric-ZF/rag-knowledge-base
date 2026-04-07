# 🔬 RAG 学术知识库

> 基于私有论文库的智能问答系统 — 让 AI 回答可溯源、可验证

[![Python](https://img.shields.io/badge/Python-3.12+-green?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-orange?logo=fastapi)](https://fastapi.tiangolo.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4-purple?logo=vector)](https://www.trychroma.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow?logo=opensourceinitiative)](LICENSE)

---

## 🎯 项目简介

一个面向研究者 / 学术人员的私有论文 RAG 问答系统。不同于通用 RAG，本系统专注于**溯源验证**：

- ✅ 每句回答均可点击跳转到原始 PDF 对应页面
- ✅ 支持中文学术论文的混合检索（向量 + 关键词融合）
- ✅ Docling 结构化解析，表格 / 段落 / 参考文献保留原始结构
- ✅ 两级 Chunk 设计（Recall Chunk 高召回 / Evidence Chunk 精确引用）

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      用户浏览器                              │
│              http://your-domain.com (:8080)                 │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼───────────────────────────────────┐
│                      Nginx (port 80 + 8080)                   │
│              静态文件托管 + API 反向代理 → FastAPI :8000       │
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
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌────────────────┐ ┌──────────────┐ ┌────────────────────┐
│  File System   │ │   ChromaDB   │ │   MiniMax API      │
│  PDF 持久化存储 │ │  1024d 向量   │ │   MiniMax-M2.7    │
│  /rag-data/    │ │  混合检索      │ │   LLM 生成        │
└────────────────┘ └──────────────┘ └────────────────────┘
```

---

## 📁 项目结构

```
rag-knowledge-base/
├── README.md              # 本文件
├── phase0/                # Phase 0 — 核心验证阶段
│   ├── backend/           # FastAPI 后端
│   │   ├── main.py        # API 入口
│   │   ├── chat.py        # RAG Chat 核心逻辑
│   │   ├── pipeline.py    # PDF 解析 → Chunk → Embedding
│   │   ├── data.py        # papers_db 持久化
│   │   └── config.py      # 配置（API Key / 路径）
│   ├── frontend/          # 前端静态文件
│   │   └── index.html     # 主页面（单文件 HTML）
│   ├── docs/              # 架构文档
│   ├── hooks/             # Git pre-commit hooks
│   ├── scripts/           # 部署 / 维护脚本
│   └── tests/             # 单元测试
├── phase1/                # Phase 1 — 规模化（规划中）
│   ├── backend/
│   ├── frontend/
│   └── tests/
├── CEO-analysis.md        # CEO 产品分析
├── ENG-architecture.md    # 工程架构文档
├── DESIGN-interaction.md   # 交互设计文档
├── PRODUCT-DESIGN.md       # 产品设计文档
└── QA-test-strategy.md   # QA 测试策略
```

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.12 | 主要运行时 |
| nginx | ≥ 1.18 | 反向代理 + 静态托管 |
| 系统内存 | ≥ 4GB | 推荐 4GB+，BGE 模型约 1.3GB |

### 安装

```bash
# 1. 克隆代码
git clone https://github.com/Eric-ZF/rag-knowledge-base.git
cd rag-knowledge-base/phase0

# 2. 安装依赖
pip install -r backend/requirements.txt

# 3. 配置（复制并填写）
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 MINIMAX_API_KEY 和 MINIMAX_GROUP_ID

# 4. 启动后端（systemd 托管）
sudo cp scripts/rag-backend.service /etc/systemd/system/
sudo systemctl enable rag-backend
sudo systemctl start rag-backend

# 5. 配置 nginx
sudo cp scripts/nginx.conf /etc/nginx/sites-available/rag
sudo ln -s /etc/nginx/sites-enabled/rag /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 配置变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `MINIMAX_API_KEY` | ✅ | MiniMax API Key |
| `MINIMAX_GROUP_ID` | ✅ | MiniMax Group ID |
| `CHROMADB_DIR` | ✅ | ChromaDB 持久化路径 |
| `PAPERS_DIR` | ✅ | PDF 文件存储路径 |
| `JWT_SECRET_KEY` | ✅ | JWT 签名密钥 |

---

## 📖 使用流程

### 1. 注册 / 登录
访问部署地址，创建账号并登录。

### 2. 上传论文
拖拽或点击上传 PDF 文件，系统自动：
1. **解析** — Docling 提取文本 / 表格 / 结构
2. **切分** — 两级 Chunk（Recall 6k 字 / Evidence 2k 字）
3. **向量化** — BGE-large-zh-v1.5 生成 1024d 向量
4. **入库** — ChromaDB 持久化

### 3. 提问
在问答区输入问题，系统返回：
- 📝 结构化回答（Markdown 格式）
- 📌 可点击引用 → 跳转 PDF 原文献

### 4. 管理论文
- 查看已上传论文列表及状态
- 删除论文（同步清除 ChromaDB 向量）

---

## 🔧 核心模块说明

### RAG Pipeline（`pipeline.py`）

```
PDF 文件
  │
  ▼
Docling 解析 ─── 提取文本、表格、页码、章节结构
  │
  ▼
两级 Chunk ─── Recall Chunk（高召回） + Evidence Chunk（精确引用）
  │
  ▼
BGE Embedding ─── 1024d 向量，normalize
  │
  ▼
Hybrid Search ─── 向量相似度 × 0.85 + BM25 关键词 × 0.15
  │
  ▼
MiniMax LLM ─── 生成回答，句句标注引用来源
```

### 三种问答模式

| 模式 | 说明 | 检索范围 |
|------|------|---------|
| **默认问答** | 直接回答，结论后标注引用 | top_k=8 |
| **🔬 方法论审计** | 结构化对比各论文的研究方法 | top_k=8 |
| **📝 文献综述** | 生成主题式文献综述 | top_k=40（5×）|

---

## 🛠️ 维护

### 健康检查

```bash
# 手动检查
bash scripts/deploy-checklist.sh

# systemd 服务状态
systemctl status rag-backend
```

### 日志

```bash
# Backend 日志
journalctl -u rag-backend -f

# Nginx 访问 / 错误日志
tail -f /var/log/nginx/access.log
tail -f /var/log/nginx/error.log
```

### 数据备份

ChromaDB 和 papers_db 均持久化在 `/root/.openclaw/rag-data/`，定期备份该目录：

```bash
rsync -av /root/.openclaw/rag-data/ /backup/rag-data/
```

---

## 📈 演进路线

```
Phase 0  ✅ 核心验证（当前）
  ├── PDF 上传 + ChromaDB 索引
  ├── Chat 问答 + 引用跳转
  ├── systemd 托底 + 进程守护
  └── 两级 Chunk + Docling 解析

Phase 1  🔲 规模化
  ├── PostgreSQL 替换 JSON（统一存储）
  ├── Playwright E2E 测试
  ├── 蓝绿部署脚本
  └── 域名 + HTTPS

Phase 2  🔲 精准化学术
  ├── CrossEncoder 重排（升配后启用）
  ├── 知识图谱增强（Graph RAG）
  └── 多论文联合推理

Phase 3  🔲 商业化
  ├── 多租户 + 权限控制
  ├── API Key 管理（开放 API）
  └── 团队协作 / 共享论文库
```

---

## 🧪 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | 0.109+ |
| PDF 解析 | Docling | 2.84+ |
| 向量数据库 | ChromaDB | 0.4+ |
| Embedding | BGE-large-zh-v1.5 | — |
| LLM | MiniMax-M2.7 | — |
| 前端 | 原生 HTML/JS（无框架）| — |
| 部署 | systemd + nginx | — |

---

## 📄 License

MIT License — 详见 [LICENSE](LICENSE) 文件。
