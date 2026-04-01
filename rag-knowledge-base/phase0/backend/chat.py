"""
Phase 1：RAG 问答 — 跨论文分析与文献综述

新增：
- 方法论审计 Prompt（跨论文对比方法论/模型/数据来源）
- 文献综述 Prompt（生成结构化 Markdown 综述）
- 支持 paper_ids 限定范围检索
"""

import os
import re
from typing import Literal

from dotenv import load_dotenv
load_dotenv()

from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID, MINIMAX_CHAT_ENDPOINT, CHAT_MODEL


# ══════════════════════════════════════════════════════
# System Prompts（按场景分化）
# ══════════════════════════════════════════════════════

SYSTEM_PROMPT_DEFAULT = """你是一个专业的研究助手，基于论文片段回答学术问题。

回答格式：
一、回答：[完整回答，结论后用[片段X]标注来源]
二、引用：[片段X]，页码Y，来源内容

规则：
- 只基于论文内容回答，不编造
- 证据不足时直接说"证据不足"
- 完整回答，不要在中途停止
- 用中文，学术语气"""


SYSTEM_PROMPT_METHODOLOGY = """你是一个专业的学术研究助手，专门分析论文中的方法论。

任务：从检索到的论文片段中，识别并对比各论文的研究方法。

输出格式（Markdown）：

## 方法论分析

### 1. 实证模型分布
[列出使用了实证模型的论文，说明各用了什么模型（OLS/DID/CGE等）]

### 2. 数据来源分类
[按数据来源分组：官方统计数据/企业年报/调查数据/实验数据等]

### 3. 理论基础
[各论文依赖什么理论框架]

### 4. 方法论对比
[表格对比：论文 | 方法 | 数据 | 理论基础]

---
每条结论必须用 [片段X] 标注来源，片段编号见论文片段末尾。
用中文，学术语气，完整输出。"""


SYSTEM_PROMPT_SURVEY = """你是一个资深学术研究员，擅长撰写高质量文献综述。

任务：基于检索到的论文片段，写一篇结构化文献综述。

输出格式（严格遵循）：

## {theme} — 文献综述

### 一、研究概述
[该主题的研究背景和意义，2-3段落]

### 二、主要理论框架
[该领域主要理论基础，引用相关片段]

### 三、研究方法论分布
[各论文采用的方法分类统计（实证/理论/案例/实验等），重点标注使用的实证模型]

### 四、数据来源分析
[数据来源分类，含各来源的论文数量和代表论文]

### 五、主要发现与结论
[按主题或观点分组，列出各论文的核心发现]

### 六、研究空白与未来方向
[现有研究的不足，未来可以深入的方向]

### 七、参考文献
[格式：作者(年份). 论文标题. 期刊. 链接]

---
格式要求：
- Markdown 输出，可直接复制到 Word/LaTeX
- 每个论点后用 [片段X] 标注来源
- 用中文，学术语气
- 完整输出，不要在中途停止
- 尽量综合多篇论文，不要只依赖一篇
"""


# ══════════════════════════════════════════════════════
# 上下文组装
# ══════════════════════════════════════════════════════

def build_context(chunks: list[dict]) -> str:
    """将检索到的 chunks 组装成 LLM 上下文（带片段编号）"""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("title") or chunk.get("paper_id", "未知论文")
        context_parts.append(
            f"[片段 {i}]\n"
            f"论文: {title}\n"
            f"页码: {chunk.get('page_number', '?')}\n"
            f"内容: {chunk['content']}"
        )
    return "\n\n".join(context_parts)


def build_survey_context(chunks: list[dict], theme: str) -> str:
    """
    为文献综述构建上下文，按论文分组，同一论文的片段聚合在一起
    """
    # 按 paper_id 分组
    by_paper: dict[str, list[dict]] = {}
    for chunk in chunks:
        pid = chunk["paper_id"]
        by_paper.setdefault(pid, []).append(chunk)

    sections = []
    for i, (pid, paper_chunks) in enumerate(by_paper.items(), 1):
        title = paper_chunks[0].get("title") or pid
        contents = "\n".join(
            f"[{j+1}] 来自第{p.get('page_number','?')}页：{p['content']}"
            for j, p in enumerate(paper_chunks)
        )
        sections.append(
            f"【论文 {i}: {title}】\n{contents}"
        )

    return (
        f"文献综述主题：{theme}\n\n"
        + "\n\n".join(sections)
        + "\n\n提示：以上片段编号 [1]-[N] 对应下方论文，引用时使用片段编号。"
    )


# ══════════════════════════════════════════════════════
# MiniMax Chat Client
# ══════════════════════════════════════════════════════

class MiniMaxChatClient:
    """
    MiniMax OpenAI-Compatible Chat Client

    MiniMax 支持 OpenAI-compatible API:
    - POST https://api.minimax.chat/v1/chat/completions
    - Header: Authorization: Bearer <api_key>
    - Header: GroupId: <group_id>
    - Body: { model, messages, max_tokens, ... }
    """

    def __init__(self, api_key: str, group_id: str, endpoint: str = MINIMAX_CHAT_ENDPOINT):
        import requests
        self.api_key = api_key
        self.group_id = group_id
        self.endpoint = endpoint
        self.session = requests.Session()

    def chat(
        self,
        messages: list[dict],
        model: str = CHAT_MODEL,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """发送对话请求到 MiniMax"""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "GroupId": self.group_id,
            "Content-Type": "application/json",
        }
        resp = self.session.post(self.endpoint, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]


# ══════════════════════════════════════════════════════
# LLM 调用入口
# ══════════════════════════════════════════════════════

def _call_minimax(messages: list[dict], max_tokens: int = 4096, temperature: float = 0.3) -> str:
    """统一 MiniMax 调用"""
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise ValueError("MINIMAX_API_KEY 和 MINIMAX_GROUP_ID 必须设置")
    client = MiniMaxChatClient(api_key=MINIMAX_API_KEY, group_id=MINIMAX_GROUP_ID)
    return client.chat(messages=messages, model=CHAT_MODEL, max_tokens=max_tokens, temperature=temperature)


def strip_thinking_tags(text: str) -> str:
    """去除 MiniMax 思考过程标签"""
    # Use chr() to avoid Python AST parser treating them as nodes
    START = chr(0x3010) + chr(0x8003) + chr(0x5B58)   # 之以 (left bracket)
    END   = chr(0x3011) + chr(0x8003) + chr(0x5B58)   # 之存 (right bracket)
    text = text.replace(START, "").replace(END, "")
    return text.strip()

# ══════════════════════════════════════════════════════
# 标准问答
# ══════════════════════════════════════════════════════

async def generate_answer(
    question: str,
    chunks: list[dict],
    mode: Literal["default", "methodology", "survey"] = "default",
) -> tuple[str, list[dict], dict]:
    """
    调用 MiniMax 生成答案，支持多种模式

    Args:
        question: 用户问题
        chunks: 检索到的文档片段
        mode: default | methodology | survey

    Returns: (answer_text, citations, meta)
    """
    if not chunks:
        return "抱歉，我在你的论文库中没有找到相关内容。", [], {}

    if mode == "methodology":
        system_prompt = SYSTEM_PROMPT_METHODOLOGY
        user_message = (
            f"请分析以下论文片段的方法论：\n\n{build_context(chunks)}\n\n"
            f"用户问题：{question}"
        )
        max_tokens = 4096
    elif mode == "survey":
        system_prompt = SYSTEM_PROMPT_SURVEY.format(theme=question)
        user_message = build_survey_context(chunks, question)
        max_tokens = 8192  # 文献综述需要更长的输出
    else:
        system_prompt = SYSTEM_PROMPT_DEFAULT
        user_message = (
            f"基于以下论文片段回答问题：\n\n问题：{question}\n\n"
            f"---\n{build_context(chunks)}\n\n"
            f"请根据以上片段回答问题，并在引用部分标注参考来源。"
        )
        max_tokens = 4096

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    answer_text = _call_minimax(messages, max_tokens=max_tokens, temperature=0.3)
    answer_text = strip_thinking_tags(answer_text)

    citations = [
        {
            "paper_id": c["paper_id"],
            "title": c.get("title") or "",
            "chunk_index": c["chunk_index"],
            "page_number": c.get("page_number", 0),
            "content": c["content"][:300],
        }
        for c in chunks
    ]

    meta = {
        "mode": mode,
        "paper_count": len({c["paper_id"] for c in chunks}),
        "chunk_count": len(chunks),
    }

    return answer_text, citations, meta
