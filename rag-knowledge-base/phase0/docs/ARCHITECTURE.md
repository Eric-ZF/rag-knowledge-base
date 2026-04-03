# Phase 1 — 学术知识库架构设计

> 基于 Azure AI Search 五层架构，目标是成为"结构化学术知识系统"而非"文本堆"

---

## 一、目标

把当前 Phase 0 系统从"上传 PDF + 语义搜索 + 聊天"重构成：

```
文献导入 → 结构化解析 → 学术语义切块 → 索引入库
→ 混合检索 → 重排 → 证据约束生成 → 引用输出 → 评测反馈
```

---

## 二、五层架构

### Layer 1: 数据接入层 (Data Ingestion)

**职责**：接收多来源学术资源，分配唯一 ID，保留元数据

**支持类型**：
- PDF 论文（预印本、录用稿、正式发表版）
- Word/Excel（项目申报书、结题报告）
- 网页 URL（研究报告、政策文件）
- TXT/Markdown（研究笔记、提纲）
- 政策文件 PDF

**关键设计**：
- 每个文献对象有唯一 `paper_id`（UUID）
- 保留 `source`（来源）、`version`（预印本/录用/正式）、`language`、`created_at`
- 版本管理：同一篇论文多次上传时识别并提示用户

### Layer 2: 文档解析与知识加工层 (Parsing & Profiling)

**职责**：把原始文档转成结构化知识对象

**Docling 解析输出**（统一 JSON）：
```json
{
  "title": "...",
  "authors": ["..."],
  "abstract": "...",
  "keywords": ["..."],
  "year": 2024,
  "journal": "...",
  "doi": "...",
  "sections": [
    {
      "section_id": "s1",
      "title": "1. Introduction",
      "path": "1",
      "order": 1,
      "page_start": 1,
      "page_end": 3,
      "paragraphs": ["..."]
    }
  ],
  "tables": [
    {
      "table_id": "t1",
      "title": "表 1: 描述性统计",
      "markdown": "| 列1 | 列2 |...",
      "page_range": "4"
    }
  ],
  "references": "..."
}
```

**文献画像抽取**（paper_profiles）：
```json
{
  "paper_id": "...",
  "research_question": "数字政策如何影响绿色创新？",
  "research_object": "中国城市层面企业",
  "data_source": "工业企业数据库 +专利数据库",
  "time_span": "2000-2020",
  "method": "DID + 工具变量",
  "mechanism": ["融资约束","技术创新","环境规制"],
  "main_findings": "数字政策显著促进绿色专利增长18%",
  "heterogeneity": "东部>西部，国有企业>民营企业",
  "policy_implication": "应差异化设计数字政策",
  "limitations": "仅考虑发明专利，实用新型待验证"
}
```

### Layer 3: Chunk 切分模块（两级设计）

**召回块（Recall Chunks）**：
- 按小节/连续语义段切分
- 长度：400–800 tokens
- 用途：初次检索，保证召回率

**证据块（Evidence Chunks）**：
- 按单段、结论段、方法段、表格说明切分
- 长度：150–350 tokens
- 用途：最终生成引用的最小单元

### Layer 4: 检索与排序层（Retrieval & Ranking）

**混合检索流程**：
```
Query 预处理
  ↓
BM25 关键词检索 ──┐
                    ├→ RRF 融合 → 元数据过滤 → Reranker 重排
向量语义检索 ─────┘
  ↓
初始召回 40–80 条 → 重排后保留 8–12 条 → 最终生成用 4–6 条
```

**元数据过滤支持**：
- 年份（range）
- 作者（exact）
- 期刊/来源（exact）
- 语言（zh/en）
- 研究方法（DID/RCT/IV/...）
- 地区（country/city）

### Layer 5: 生成与服务层（Generation）

**Evidence-First Pipeline**（Allen AI ScholarQA 思路）：
- 每个关键判断必须附出处页码
- 区分：文献共识 | 文献分歧 | 系统综合判断
- 证据不足时明确声明

**输出格式**：
```
## 问题概述
[用户问题重述]

## 主流结论
[基于证据的总结，引用序号]

## 代表性文献
[1] 作者(年份)，期刊，核心发现
[2] ...

## 分歧与原因
[文献间结论差异及原因分析]

## 研究空白
[现有研究未覆盖的方向]

## 参考文献
[完整引用列表]
```

---

## 三、数据库表结构

### papers（文献主表）
| 字段 | 类型 | 说明 |
|------|------|------|
| paper_id | UUID | 主键 |
| title | TEXT | 标题 |
| authors | TEXT[] | 作者列表 |
| year | INT | 发表年份 |
| source | TEXT | 来源/期刊 |
| doi | TEXT | DOI |
| language | TEXT | zh/en |
| abstract | TEXT | 摘要 |
| keywords | TEXT[] | 关键词 |
| version | TEXT | preprint/accepted/published |
| file_hash | TEXT | SHA256，用于去重 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### sections（章节表）
| 字段 | 类型 |
|------|------|
| section_id | UUID |
| paper_id | UUID (FK) |
| title | TEXT |
| path | TEXT (1.2.3) |
| order | INT |
| page_start | INT |
| page_end | INT |

### chunks（证据块表）
| 字段 | 类型 |
|------|------|
| chunk_id | UUID |
| paper_id | UUID (FK) |
| section_id | UUID (FK) |
| chunk_type | TEXT (body/table/figure/abstract/conclusion) |
| chunk_text | TEXT |
| token_count | INT |
| page_range | TEXT |
| recall_chunk_id | UUID (上一层级召回块) |
| embedding_vector | BLOB(1024) |

### paper_profiles（文献画像表）
| 字段 | 类型 |
|------|------|
| paper_id | UUID (FK) |
| research_question | TEXT |
| research_object | TEXT |
| data_source | TEXT |
| time_span | TEXT |
| method | TEXT[] |
| mechanism | TEXT[] |
| main_findings | TEXT |
| heterogeneity | TEXT |
| policy_implication | TEXT |
| limitations | TEXT |

### qa_logs（问答日志表）
| 字段 | 类型 |
|------|------|
| query_id | UUID |
| user_query | TEXT |
| rewritten_query | TEXT |
| retrieved_chunk_ids | UUID[] |
| selected_chunk_ids | UUID[] |
| answer_text | TEXT |
| citation_list | JSON |
| feedback_score | INT |
| created_at | TIMESTAMP |

---

## 四、模块依赖关系

```
papers_upload (API)
  ↓
parse_document (Layer 2) ← 需要解析器（PDF.js / Docling）
  ↓
extract_profile (Layer 2) ← LLM 抽取画像
  ↓
chunk_document (Layer 3) ← 两级切分
  ↓
generate_embedding (Layer 3) ← BGE embedding
  ↓
upsert_to_chroma (Layer 4) ← 写入向量库 + 元数据
  ↓
chat (API)
  ↓
hybrid_search (Layer 4) ← BM25 + vector + RRF
  ↓
rerank (Layer 4) ← CrossEncoder 重排
  ↓
evidence_constrained_generate (Layer 5) ← MiniMax M2.7
  ↓
format_citation_output (Layer 5)
  ↓
log_qa (Layer 5)
```

---

## 五、当前系统 → Phase 1 迁移路径

### 现有代码（Phase 0）
```
backend/
  main.py          # FastAPI 入口
  auth.py          # JWT 认证
  papers.py        # 论文 CRUD（弱）
  pipeline.py      # embedding + hybrid_search
  data.py          # papers_db (in-memory dict)
  chat.py          # /chat 端点
  config.py        # MiniMax 配置
frontend/
  index.html       # SPA（上传+问答）
```

### Phase 1 目标结构
```
backend/
  main.py                    # FastAPI 入口（不变）
  auth.py                    # JWT（不变）
  # --- Layer 1: 数据接入 ---
  ingestion/
    __init__.py
    parser_factory.py        # 解析器工厂
    pdf_parser.py            # PDF 解析（pymupdf）
    doc_parser.py            # Word/Excel 解析
    url_parser.py            # 网页抓取
    text_parser.py           # TXT/MD 解析
    deduplicator.py          # SHA256 去重 + 版本检测
  # --- Layer 2: 文档解析 ---
  parsing/
    __init__.py
    docling_parser.py        # Docling 结构化输出
    profile_extractor.py     # LLM 抽取文献画像
  # --- Layer 3: 知识加工 ---
  chunking/
    __init__.py
    hierarchical_chunker.py  # 两级 chunk 设计
    token_counter.py        # tiktoken 计数
  # --- Layer 4: 检索排序 ---
  retrieval/
    __init__.py
    bm25_retriever.py       # BM25 关键词检索
    vector_retriever.py      # ChromaDB 向量检索
    hybrid_merger.py         # RRF 融合
    reranker.py              # CrossEncoder 重排
  # --- Layer 5: 生成 ---
  generation/
    __init__.py
    prompt_builder.py        # System prompt 构造
    answer_formatter.py      # 输出格式控制
  # --- 数据层 ---
  storage/
    __init__.py
    papers.py                # papers 表操作
    sections.py              # sections 表操作
    chunks.py                # chunks 表操作
    profiles.py               # paper_profiles 表操作
    qa_logs.py               # qa_logs 表操作
  # --- API ---
  routers/
    papers.py               # 论文管理 API
    chat.py                 # 问答 API（重构）
    upload.py               # 上传 API（重构）
  # 原有
  config.py
  pipeline.py               # 向量检索（融入 retrieval/）
  chat.py                   # 聊天（融入 generation/）
  data.py                   # papers_db（替换为 storage/）

frontend/
  index.html               # 重构为分离式 SPA
  components/
    UploadPanel.jsx         # 上传面板
    ChatPanel.jsx           # 问答面板
    PaperList.jsx           # 论文管理列表
    ProfileDrawer.jsx       # 文献画像侧边栏
    CitationCard.jsx       # 引用卡片
```

---

## 六、关键实现说明

### 6.1 解析器选型
- **PDF**: `pymupdf`（已安装）+ 后续可选 `docling`
- **Word/Excel**: `python-docx` + `openpyxl`
- **网页**: `trafilatura`（学术类文章）
- **文本**: 直接读取

### 6.2 两级 Chunk 设计实现
```python
# 第一级：召回块（Recall Chunks）
recall_chunks = hierarchical_chunk(
    text, 
    target_tokens=600,   # 400-800
    overlap_tokens=80,
    split_by="section"   # 按章节切
)

# 第二级：证据块（Evidence Chunks）
evidence_chunks = semantic_chunk(
    recall_chunk,
    target_tokens=250,   # 150-350
    split_by=["\n\n", "。", "；"]  # 段落边界
)
```

### 6.3 混合检索实现
```python
# 1. BM25 检索
bm25_results = bm25_retriever.search(query, top_k=40)

# 2. 向量检索
vec_results = vector_retriever.search(query_embedding, top_k=40)

# 3. RRF 融合
merged = reciprocal_rank_fusion([bm25_results, vec_results], k=60)

# 4. 元数据过滤
filtered = apply_filters(merged, year=(2020,2024), method=["DID"])

# 5. Reranker 重排
reranked = cross_encoder.rerank(query, filtered, top=12)
```

### 6.4 证据约束生成 System Prompt
```
你是一个学术研究助手，专门基于检索到的论文证据回答问题。

规则：
1. 只能使用提供的证据块中的信息回答
2. 每个重要判断必须用 [论文序号-页码] 格式引用
3. 区分：证据支持的结论 vs 系统推测
4. 如果证据不足，明确说明"现有文献未提供相关信息"

回答格式：
## 问题
[重述问题]

## 核心回答
[基于证据的完整回答]

## 参考文献
[按引用顺序列出完整文献信息]
```

### 6.5 文献画像 LLM 抽取 Prompt
```
从以下论文摘要和全文中抽取结构化信息：

标题：{title}
摘要：{abstract}
关键词：{keywords}

请输出以下字段（如果某字段无法从文中确定，填"未说明"）：
- 研究问题：
- 研究对象：
- 数据来源：
- 时间范围：
- 研究方法：
- 核心机制：
- 主要结论：
- 异质性发现：
- 政策启示：
- 研究局限：
```

---

## 七、上线计划

### Phase 1.0（数据层重构）
- [ ] 新数据库表结构（papers/sections/chunks/profiles/qa_logs）
- [ ] 保留现有 auth.py 和 login 流程
- [ ] 迁移现有 3 篇论文数据到新结构

### Phase 1.1（解析层）
- [ ] parser_factory + PDF 解析
- [ ] 两级 chunk 实现
- [ ] SHA256 去重

### Phase 1.2（检索层）
- [ ] BM25 + 向量混合检索
- [ ] RRF 融合
- [ ] CrossEncoder 重排

### Phase 1.3（生成层）
- [ ] Evidence-first system prompt
- [ ] 结构化输出格式
- [ ] QA 日志记录

### Phase 1.4（前端）
- [ ] 论文管理面板（状态显示/删除/版本）
- [ ] 文献画像侧边栏
- [ ] 引用卡片（显示论文标题+年份）

---

## 八、数据库选型

**当前**：ChromaDB（向量）+ JSON 文件（关系）

**Phase 1 推荐**：PostgreSQL + pgvector

| 数据类型 | 存储 | 理由 |
|---------|------|------|
| 向量 | pgvector | 统一数据库，减少维护复杂度 |
| 关系 | PostgreSQL | 结构化查询（年份/作者/期刊过滤）|
| 文件 | 本地文件系统 + 对象存储 | PDF 原始文件 |

**注意**：Phase 1 继续用 ChromaDB + JSON，Phase 2 再迁移 PostgreSQL

---

## 六、前端功能设计（四页面）

### 页面 1: 文献检索页 (`/search`)
- 左侧：筛选器面板（关键词/作者/年份/主题/研究方法/期刊/地区）
- 右侧：论文卡片列表（标题/作者/年份/期刊 + 方法标签 + 引用数）
- 支持排序：相关性 / 发表时间 / 引用量
- 点击论文卡片 → 展开文献画像 + 章节预览

### 页面 2: 智能问答页 (`/chat`) ← 现有主页改造
- 顶部：当前检索范围提示（"基于 X 篇论文"）
- 中部：对话历史（用户问题 + AI 回答 + 引用标记）
- 底部：输入框 + 模式切换（综述模式 / 精准问答 / 比较模式）
- 输出结构：
  ```
  ## 问题概述
  
  ## 主流结论 [1][2]
  
  ## 代表性文献
  [1] 阮建平(2025)《德国研究》...
  [2] Dong et al.(2025)Regional Studies...
  
  ## 分歧与原因
  
  ## 研究空白
  ```

### 页面 3: 证据溯源页 (`/evidence/:chunk_id`)
- 核心：chunk 原文 + 所属论文信息
- 显示：论文标题 / 作者 / 年份 / 期刊 / 章节路径 / 页码范围
- 支持：定位到原文（高亮 chunk 段落）
- 操作：加入引用 / 举报错误 / 展开上下文（相邻 chunks）

### 页面 4: 文献比较页 (`/compare`)
- 输入：选择 2-N 篇论文（搜索选择或从问答页跳转）
- 输出：多栏比较表
  | 字段 | 论文 A | 论文 B | 论文 C |
  |------|--------|--------|--------|
  | 研究问题 | | | |
  | 研究对象 | | | |
  | 样本/时间 | | | |
  | 研究方法 | | | |
  | 核心结论 | | | |
  | 理论机制 | | | |
  | 异质性发现 | | | |
  | 政策启示 | | | |
  | 局限性 | | | |
- 支持导出：Markdown / CSV / PDF

---

## 七、典型业务流程

### 场景 1: 单问题智能问答（最高频）
```
用户输入问题
  ↓
Query 改写（扩展同义词/补充隐含背景）
  ↓
混合检索（BM25 + 向量 + 元数据过滤）
  ↓
RRF 融合（取 top-80）
  ↓
语义重排（CrossEncoder，取 top-12）
  ↓
证据块选取（过滤：背景/引言/参考文献 → 保留方法/结论/结果）
  ↓
证据约束生成（MiniMax M2.7，4-6 条证据）
  ↓
引用格式化（paper_id → 论文标题/年份/期刊）
  ↓
前端渲染（问答页 + 引用标记可点击）
  ↓
QA 日志写入（query_id + retrieved + selected + answer + score）
```

### 场景 2: 文献综述辅助（中频）
```
用户输入综述主题（如："数字税对绿色创新的影响"）
  ↓
按主题 + 年份（近 5 年）混合检索 → 召回 30-50 篇
  ↓
抽取所有文献画像（research_question / method / findings）
  ↓
聚类分析（按研究问题/方法/结论分组）
  ↓
生成综述框架：
  - 共识区：多数文献支持的结论
  - 分歧区：结论不一致的议题 + 原因分析
  - 空白区：未被研究覆盖的方向
  ↓
输出：结构化综述文本 + 参考文献列表
```

### 场景 3: 研究设计比较（低频）
```
用户输入："有哪些文献用 DID 研究数字政策"
  ↓
元数据过滤（method 包含 "DID" / "倍差法"）
  ↓
返回文献列表 + 画像摘要
  ↓
生成比较表（研究问题/样本/时间/方法/结论/机制对比）
  ↓
支持用户增删论文、手动修改比较维度
  ↓
导出 Markdown / CSV
```

---

## 八、评测与优化机制（三层评测框架）

> 基于 Google Cloud RAG 优化 + Allen AI ScholarQABench

### 检索层指标
| 指标 | 公式/说明 | 目标 |
|------|----------|------|
| Recall@K | 相关文档出现在 top-K 的比例 | ≥ 0.85 |
| MRR | 首个相关文档排名的倒数均值 | ≥ 0.6 |
| nDCG@K | 归一化折损累积增益 | ≥ 0.65 |
| 命中论文率 | 召回的 chunks 所属论文 = 问题相关论文 | ≥ 80% |
| 命中证据率 | 召回的 chunks 真正含答案证据 | ≥ 70% |

### 回答层指标
| 指标 | 说明 | 目标 |
|------|------|------|
| Groundedness | 回答中每个声明是否均可归因于证据 | ≥ 0.9 |
| Answer Relevance | 回答是否切题（LLM 评分 or 嵌入相似度）| ≥ 0.8 |
| Citation Accuracy | 引用的 chunk 是否真正支持对应声明 | ≥ 0.85 |
| Contradiction Rate | 回答与证据矛盾的比例 | ≤ 5% |
| Evidence Coverage | 回答引用证据的覆盖率 | ≥ 0.75 |

### 系统层指标
| 指标 | 说明 | 目标 |
|------|------|------|
| P50 响应时延 | 第 50 百分位回答时间 | ≤ 8s |
| P95 响应时延 | 第 95 百分位回答时间 | ≤ 20s |
| 解析成功率 | PDF 成功解析并入库的比例 | ≥ 95% |
| 索引更新延迟 | 上传 PDF → 可检索的时长 | ≤ 60s |
| 用户反馈得分 | 1-5 星反馈均值 | ≥ 4.0 |

### 反馈收集机制
```
用户对每条回答可操作：
  👍 有用（+1 评分）
  👎 没用（-1 评分 + 可选理由）
  ❌ 引用错误（举报 → 记录到 qa_logs）

定期（每周）：
  分析低评分回答 → 定位 retrieval 问题 / generation 问题
  检索层 Recall < 0.7 的 query → 加入检索评测集
  Groundedness < 0.8 的回答 → 加入 generation 优化集
```

---

## 九、Phase 1 完整路线图

| 阶段 | 内容 | 交付物 |
|------|------|--------|
| **Phase 1.0** | 数据层重构（papers/sections/chunks/profiles/qa_logs）| 数据库表 + 迁移脚本 |
| **Phase 1.1** | 解析层（PDF解析 + 两级chunk + 去重）| `parse_document()` |
| **Phase 1.2** | 检索层（BM25 + 向量混合 + RRF + Rerank）| `hybrid_search()` |
| **Phase 1.3** | 生成层（证据约束 + 结构化输出 + QA日志）| `/chat` 重构 |
| **Phase 1.4** | 前端（4页面：检索/问答/溯源/比较）| React SPA |
| **Phase 1.5** | 评测层（指标采集 + 反馈面板 + 优化闭环）| `/admin/analytics` |

---

## 十、依赖技术栈

| 模块 | 技术选型 | 理由 |
|------|---------|------|
| PDF 解析 | `pymupdf`（现网）+ `docling`（未来）| 表格/版面感知 |
| 向量数据库 | ChromaDB（当前）/ pgvector（未来）| 轻量，暂无运维负担 |
| 关系数据库 | PostgreSQL（未来）| 结构化过滤 + pgvector 同库 |
| Embedding | BGE-large-zh-v1.5（当前）| 中文最优 1024d |
| Reranker | `cross-encoder/ms-marco-MiniLML-12-v2` | 轻量，CPU 可跑 |
| LLM | MiniMax M2.7（当前）| 成本优先 |
| 前端框架 | Vanilla JS → React（Phase 1.4）| 降低重构成本 |
| BM25 | `rank_bm25` | 成熟轻量 |
| 评测框架 | 内部实现（无商业依赖）| 自控 |
