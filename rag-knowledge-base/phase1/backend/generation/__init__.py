"""
Phase 1 — 生成与服务层

证据约束生成 + 结构化输出
"""
import json, time, httpx
from typing import Literal
from .. import config
from ..storage.papers import get_chunks_by_ids, get_profile, get_paper

# ─── System Prompt ──────────────────────────────────────

SYSTEM_PROMPT = """你是一个专业的学术研究助手，专注于基于论文证据回答问题。

【核心原则】
1. 只使用提供的证据块（Evidence）中的信息回答问题
2. 每个重要声明必须用 [序号] 格式标注出处，格式：[1-3] 表示第1篇文献的第3页/段落
3. 严格区分：证据支持的结论 vs 你的推测
4. 当证据不足时，明确说明"现有文献未提供该信息"
5. 禁止虚构参考文献或数据

【回答格式】
## 问题概述
[用一句话重述用户的问题]

## 核心回答
[基于证据的完整回答，段落式，引用标注]

## 主要参考文献
[列出所有引用的文献，格式：序号. 作者(年份). 标题. 期刊/会议.]

## 证据不足之处
[列出证据未能覆盖的问题]
"""


SURVEY_SYSTEM_PROMPT = """你是一个专业的学术研究综述助手。

【核心原则】
1. 只使用提供的证据回答
2. 按"共识—分歧—空白"框架组织综述
3. 每项声明必须标注出处 [序号]
4. 当证据不足时明确说明

【回答格式】
## 综述主题
[主题]

## 研究共识
[多数文献支持的结论，引用标注]

## 研究分歧
[文献间结论差异及可能原因，引用标注]

## 研究空白
[现有研究未覆盖的方向]

## 主要文献
[完整参考文献列表]
"""


COMPARE_SYSTEM_PROMPT = """你是一个专业的学术论文比较助手。

【核心原则】
1. 只使用提供的论文画像信息进行比较
2. 每个比较维度必须引用具体文献
3. 客观呈现差异，不添加推测

【回答格式】
## 比较主题
[涉及哪些论文/研究问题]

## 比较表
| 维度 | [论文A] | [论文B] | ... |
[详细比较]

## 关键差异
[最显著的差异分析]

## 互补性
[哪些方面可以相互补充]
"""


# ─── LLM 调用 ───────────────────────────────────────────

async def call_minimax(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> str:
    """调用 MiniMax Chat API"""
    api_key = config.MINIMAX_API_KEY
    group_id = config.MINIMAX_GROUP_ID
    if not api_key or not group_id:
        raise RuntimeError("MINIMAX_API_KEY 或 MINIMAX_GROUP_ID 未配置")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            config.MINIMAX_BASE_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "GroupId": group_id,
                "Content-Type": "application/json",
            },
            json={
                "model": model or config.CHAT_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"MiniMax API 错误: {response.status_code} {response.text}")
        data = response.json()
        return data["choices"][0]["message"]["content"]


# ─── 证据约束生成 ───────────────────────────────────────

async def generate_answer(
    query: str,
    retrieved_chunks: list[dict],
    mode: Literal["default", "survey", "compare"] = "default",
) -> dict:
    """
    证据约束生成主流程

    返回:
        {
            "answer": str,
            "citations": [{"chunk_id": str, "paper_title": str, "page_range": str, ...}],
            "mode": str,
            "latency_ms": int,
        }
    """
    start = time.time()

    # 构建 evidence 文本
    evidence_texts = []
    citations = []
    for i, chunk in enumerate(retrieved_chunks):
        paper = get_paper(chunk["paper_id"])
        chunk_text = chunk.get("chunk_text", "")[:500]  # 截断，太长浪费 token
        paper_title = paper["title"] if paper else chunk["paper_id"]
        page_range = chunk.get("page_range", "")

        citation = {
            "index": i + 1,
            "chunk_id": chunk["chunk_id"],
            "paper_id": chunk["paper_id"],
            "paper_title": paper_title,
            "page_range": page_range,
            "chunk_type": chunk.get("chunk_type", "body"),
            "preview": chunk_text[:200],
        }
        citations.append(citation)

        ref_marker = f"[{i+1}]"  # 引用序号（论文内索引，不是 chunk_id）
        evidence_texts.append(f"【证据 {i+1}】{paper_title}（{page_range}）\n{chunk_text}")

    evidence_section = "\n\n".join(evidence_texts)

    # 选择 system prompt
    if mode == "survey":
        system_prompt = SURVEY_SYSTEM_PROMPT
    elif mode == "compare":
        system_prompt = COMPARE_SYSTEM_PROMPT
    else:
        system_prompt = SYSTEM_PROMPT

    user_message = f"【用户问题】\n{query}\n\n【证据】\n{evidence_section}\n\n请根据以上证据回答问题。"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        answer = await call_minimax(messages)
    except Exception as e:
        answer = f"[生成失败: {e}]"

    latency_ms = int((time.time() - start) * 1000)

    return {
        "answer": answer,
        "citations": citations,
        "mode": mode,
        "latency_ms": latency_ms,
        "chunks_used": len(retrieved_chunks),
    }


# ─── Query 改写（轻量扩展）──────────────────────────────

def rewrite_query(query: str) -> str:
    """
    简单的 query 改写：
    - 同义词扩展（中英文）
    - 研究方法词扩展
    """
    rewrites = [
        ("碳边境调节", "CBAM"),
        ("碳边境", "carbon border adjustment"),
        ("环境规制", "environmental regulation"),
        ("绿色创新", "green innovation"),
        ("did", "倍差法 双重差分"),
        ("倍差法", "DID 双重差分"),
        ("工具变量", "instrumental variable IV"),
    ]
    rewritten = query
    for old, new in rewrites:
        if old.lower() in rewritten.lower():
            rewritten = rewritten + " " + new
    return rewritten


# ─── Chunk 类型过滤 ────────────────────────────────────

def filter_chunks_by_type(
    chunks: list[dict],
    preferred_types: list[str] | None = None,
) -> list[dict]:
    """过滤：优先保留方法/结论类 chunks，减少背景/引言噪音"""
    if not preferred_types:
        preferred_types = ["method", "conclusion", "table"]
    priority = {t: i for i, t in enumerate(preferred_types)}

    def sort_key(c: dict) -> tuple[int, float]:
        t = c.get("chunk_type", "body")
        score = c.get("rrf_score", 0)
        return (priority.get(t, 99), -score)

    return sorted(chunks, key=sort_key)
