"""
Phase 1：RAG 问答 — 跨论文分析与文献综述

新增：
- 方法论审计 Prompt（跨论文对比方法论/模型/数据来源）
- 文献综述 Prompt（生成结构化 Markdown 综述）
- 支持 paper_ids 限定范围检索
"""

import json
import os
import re
import time
import requests
import urllib3
from typing import Literal

from dotenv import load_dotenv
load_dotenv()

import logging
logger = logging.getLogger(__name__)

from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID, MINIMAX_CHAT_ENDPOINT, CHAT_MODEL
from data import get_paper


# ══════════════════════════════════════════════════════
# System Prompts（按场景分化）
# ══════════════════════════════════════════════════════

SYSTEM_PROMPT_DEFAULT = """你是一个专业的研究助手，基于论文片段回答学术问题。

回答格式（Markdown）：
- 用 **加粗** 强调关键结论
- 用 `> 引用块` 显示原文摘录
- 列表呈现对比信息
- 结论后用论文主题或页码标注来源
- 禁止大段连续文字，用空行分隔段落

规则：
- 只基于论文内容回答，不编造
- 证据不足时直接说"证据不足"
- 完整回答，不要在中途停止
- 用中文，学术语气
- **禁止在答案中写思考过程**（不要写"让我分析一下"、"根据某论文"这类分析过程）
- **禁止输出原始参考文献**：不要在答案中粘贴文献标题、作者、期刊名等参考文献原文（这些信息来自 PDF 扫描文字，格式杂乱，直接标注论文主题或页码）"""

SYSTEM_PROMPT_RETRY = """你是一个专业的研究助手，基于论文片段回答学术问题。上一轮回答质量不够好，请改进。

回答格式（Markdown）：
- 用 **加粗** 强调关键结论
- 用 `> 引用块` 显示原文摘录
- 列表呈现对比信息
- 结论后用论文主题或页码标注来源
- 禁止大段连续文字，用空行分隔段落

重点改进要求：
- 确保每个结论都有对应引用支撑，不要留空白
- 如果原答案说"证据不足"，说明哪个方面仍然证据不足，不要空着不说
- 完整回答，不要在中途停止
- 用中文，学术语气
- **禁止在答案中写思考过程**
- **禁止输出原始参考文献**"""


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
结论后标注来源论文，片段编号见论文片段末尾。
用中文，学术语气，完整输出。
- **禁止输出原始参考文献**：不要在答案中粘贴文献标题、作者、期刊名等参考文献原文"""


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
- 结论后标注来源论文
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
        page = chunk.get('page_number', '')
        prefix = f"（{title}{f' 第{page}页' if page else ''}）"
        context_parts.append(f"{prefix}\n{chunk['content']}")
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
        contents = "\n\n".join(
            f"第{p.get('page_number','?')}页：{p['content']}"
            for p in paper_chunks
        )
        sections.append(
            f"【论文：{title}】\n{contents}"
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
        response_format: dict | None = None,
    ) -> str:
        """发送对话请求到 MiniMax，支持 529 重试"""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "GroupId": self.group_id,
            "Content-Type": "application/json",
        }
        
        last_error = None
        for attempt in range(3):
            try:
                # Fix 5: 缩短超时 120s→60s，减少半截回答等待时间
                resp = self.session.post(self.endpoint, json=payload, headers=headers, timeout=(10, 60))
                if resp.status_code == 529:
                    last_error = f"MiniMax 529 (attempt {attempt+1}/3)"
                    time.sleep(1 + attempt * 2)
                    continue
                resp.raise_for_status()
                result = resp.json()
                # 防御性检查
                if not result:
                    last_error = f"MiniMax 返回空响应 (attempt {attempt+1}/3)"
                    time.sleep(1 + attempt * 2)
                    continue
                if "choices" not in result or not result["choices"]:
                    last_error = f"MiniMax choices 为空 (attempt {attempt+1}/3)"
                    time.sleep(1 + attempt * 2)
                    continue
                content = result["choices"][0]["message"]["content"]
                if content is None:
                    last_error = f"MiniMax content 为空 (attempt {attempt+1}/3)"
                    time.sleep(1 + attempt * 2)
                    continue
                # Fix 5: 半截回答检测 — 回答以句子中途结尾时触发重试
                if _is_truncated(content):
                    last_error = f"MiniMax 回答疑似半截 (attempt {attempt+1}/3): 末尾='{content[-50:]}'"
                    time.sleep(1 + attempt * 2)
                    continue
                return content
            except requests.exceptions.HTTPError as e:
                last_error = f"HTTP {e.response.status_code}: {e}"
                if e.response.status_code in (529, 502, 503, 504):
                    time.sleep(1 + attempt * 2)
                    continue
                raise
            except (KeyError, IndexError, TypeError) as e:
                raise ValueError(f"MiniMax 响应格式异常 ({type(e).__name__}): {e}, resp={resp.text[:200] if 'resp' in dir() else 'N/A'}")
        
        raise RuntimeError(f"MiniMax API 3次重试均失败: {last_error}")

    def stream_chat(
        self,
        messages: list[dict],
        model: str = CHAT_MODEL,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ):
        """流式发送对话请求到 MiniMax（SSE），逐块产出 token"""
        import urllib3
        http = urllib3.PoolManager()
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "GroupId": self.group_id,
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(3):
            try:
                resp = http.request(
                    "POST",
                    self.endpoint,
                    body=json.dumps(payload),
                    headers=headers,
                    timeout=urllib3.Timeout(connect=10, read=60),
                    preload_content=False,
                )
                if resp.status == 529:
                    last_error = f"MiniMax 529 (attempt {attempt+1}/3)"
                    time.sleep(1 + attempt * 2)
                    resp.close()
                    continue
                if resp.status >= 400:
                    body = resp.read(1024).decode("utf-8", errors="replace")
                    resp.close()
                    raise RuntimeError(f"HTTP {resp.status}: {body[:200]}")
                
                # 逐行解析 SSE 流
                chunk_data = b""
                for line in resp.stream(64):
                    chunk_data += line
                    while b"\n" in chunk_data:
                        line_bytes, chunk_data = chunk_data.split(b"\n", 1)
                        line_str = line_bytes.decode("utf-8", errors="replace").strip()
                        if not line_str.startswith("data: "):
                            continue
                        data_str = line_str[6:].strip()
                        if data_str == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            # MiniMax 流式格式：choices[0].delta.content
                            content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                return
            except Exception as e:
                last_error = str(e)
                if attempt < 2:
                    time.sleep(1 + attempt * 2)
                    continue
                raise RuntimeError(f"MiniMax 流式请求失败: {last_error}")


# ══════════════════════════════════════════════════════
# LLM 调用入口
# ══════════════════════════════════════════════════════

def _is_truncated(text: str) -> bool:
    """
    检测回答是否疑似半截（LLM 输出被截断）。
    判断规则：
    - 末尾有未闭合的 Markdown 列表/表格/引用块
    - 末尾是连接号/括号/逗号/冒号等不成句的字符
    - 末尾有未闭合的加粗/斜体标签
    """
    if not text or len(text.strip()) < 20:
        return False
    text = text.rstrip()
    # 未闭合的 Markdown 列表（- item 后面没换行或空行）
    if re.search(r'\n[-*]\s+[\u4e00-\u9fff\w]', text[-100:]) and not re.search(r'\n\n', text[-50:]):
        return True
    # 未闭合的引用块
    if text.count('>') % 2 == 1 and text[-1] == '>':
        return True
    # 末尾是连接号/括号/逗号/冒号等不成句的字符
    if re.search(r'[,，:：;；]$', text):
        return True
    # 末尾有未闭合的加粗/斜体（中文书名号等）
    if re.search(r'[*_]{1,2}[^\s]', text[-20:]) and not re.search(r'[*_]{1,2}\s', text[-20:]):
        return True
    # 表格行未闭合（| 结尾）
    if re.search(r'\|\s*$', text):
        return True
    return False


def _call_minimax(messages: list[dict], max_tokens: int = 4096, temperature: float = 0.3,
                  response_format: dict | None = None) -> str:
    """统一 MiniMax 调用"""
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise ValueError("MINIMAX_API_KEY 和 MINIMAX_GROUP_ID 必须设置")
    client = MiniMaxChatClient(api_key=MINIMAX_API_KEY, group_id=MINIMAX_GROUP_ID)
    return client.chat(messages=messages, model=CHAT_MODEL, max_tokens=max_tokens,
                       temperature=temperature, response_format=response_format)


def strip_thinking_tags(text: str | None) -> str:
    """去除 LLM 思考过程标签和内容（支持多种格式）"""
    if not text:
        return ""
    try:
        # 先移除完整 thinking block（标签+内容）
        text = re.sub(r"＜.*?＞[\s\S]*?＜/.*?＞", "", text)     # 全角整块
        text = re.sub(r"<[^\>]*think[^\>]*>[\s\S]*?</[^\>]*think[^\>]*>", "", text, flags=re.IGNORECASE)
        # 移除孤立标签（内容已strip掉，标签残留）
        text = re.sub(r"＜/?think＞", "", text)
        text = re.sub(r"<think>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<\/think>", "", text, flags=re.IGNORECASE)
        # 移除 MiniMax 存货标签 〖存货〗...〖存货〗
        START = chr(0x3010) + chr(0x8003) + chr(0x5B58)
        END   = chr(0x3011) + chr(0x8003) + chr(0x5B58)
        text = text.replace(START, "").replace(END, "")
        # 清理多余空行
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
    except Exception:
        return str(text).strip()

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

    # 过滤掉参考文献类 chunks（PDF 原文的参考文献部分文字杂乱，不适合作为上下文）
    original_count = len(chunks)
    chunks = [c for c in chunks if c.get("section_type") != "reference"]
    if not chunks:
        return "抱歉，我在你的论文库中没有找到相关内容。", [], {}
    if len(chunks) < original_count:
        logger.debug(f"[generate_answer] 过滤掉 {original_count - len(chunks)} 条参考文献 chunks")

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

    # 查 paper title（优先用 papers_db 里的标题，因为有完整信息）
    paper_titles = {}
    for c in chunks:
        pid = c["paper_id"]
        if pid not in paper_titles:
            p = get_paper(pid)
            paper_titles[pid] = (p.get("title") if p else "") or c.get("title") or ""

    citations = [
        {
            "paper_id": c["paper_id"],
            "title": paper_titles.get(c["paper_id"], ""),
            "chunk_index": c["chunk_index"],
            "page_number": c.get("page_number", 0),
            "content": (c.get("content") or c.get("text") or ""),
        }
        for c in chunks
    ]

    # 对非迭代版本也做一次快速评分
    try:
        scores = evaluate_answer(question, answer_text, chunks)
    except Exception:
        scores = {"total": 100, "relevance": 100, "coverage": 100,
                  "citation_quality": 100, "factual_grounding": 100, "completeness": 100}

    meta = {
        "mode": mode,
        "paper_count": len({c["paper_id"] for c in chunks}),
        "chunk_count": len(chunks),
        "self_eval": {
            "total": scores.get("total"),
            "relevance": scores.get("relevance"),
            "coverage": scores.get("coverage"),
            "citation_quality": scores.get("citation_quality"),
            "factual_grounding": scores.get("factual_grounding"),
            "completeness": scores.get("completeness"),
        },
    }

    return answer_text, citations, meta


# ══════════════════════════════════════════════════════
# Self-Evaluation & Iterative Refinement（自我评分 + 迭代改进）
# ══════════════════════════════════════════════════════

EVALUATION_PROMPT_JSON = """请对以下答案评分。直接返回 JSON 对象，不要有其他内容。

问题：{question}
答案：{answer}
参考：{context}

要求：返回一个 JSON 对象，包含以下字段（分值0-100）：
- relevance: 检索相关性（答案是否切题，召回内容与问题是否匹配）
- coverage: 要点覆盖（答案是否覆盖了参考内容的主要信息）
- citation_quality: 引用质量（引用格式是否正确，引用位置是否匹配内容）
- factual_grounding: 事实依据（答案是否基于参考内容，有无幻觉）
- completeness: 完整性（答案是否完整，有无回避问题的部分）

只返回 JSON，例如：{{"relevance":75,"coverage":60,"citation_quality":80,"factual_grounding":70,"completeness":65}}"""

WEIGHTS = {
    "relevance": 0.30,
    "coverage": 0.15,
    "citation_quality": 0.20,
    "factual_grounding": 0.30,
    "completeness": 0.05,
}

_FALLBACK_SCORES = {"relevance": 50, "coverage": 50, "citation_quality": 50, "factual_grounding": 50, "completeness": 50}


def evaluate_answer(question: str, answer: str, chunks: list[dict]) -> dict:
    """
    用 LLM 评判答案质量，返回各维度分数和总分（0-100）
    优先使用 JSON 模式解析，失败则降级为正则解析
    """
    context = build_context(chunks)
    prompt = EVALUATION_PROMPT_JSON.format(question=question, answer=answer, context=context)
    messages = [
        {"role": "system", "content": "你是一个严格的学术质量评审员。评分客观公正，给分吝啬。直接返回 JSON。"},
        {"role": "user", "content": prompt},
    ]

    # 尝试 JSON 模式
    raw = None
    json_mode_used = False
    try:
        raw = _call_minimax(messages, max_tokens=512, temperature=0.0,
                            response_format={"type": "json_object"})
        raw = strip_thinking_tags(raw).strip()
        json_mode_used = True
        # 尝试解析 JSON
        import json
        # 去掉可能的 markdown 代码块
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        # 提取数值字段
        scores = {}
        total = 0.0
        for key, weight in WEIGHTS.items():
            val = parsed.get(key)
            if isinstance(val, (int, float)):
                scores[key] = int(val)
                total += val * weight
        if scores:
            scores["total"] = round(total, 1)
            scores["raw_evaluation"] = raw
            scores["json_mode"] = True
            return scores
    except Exception as e:
        logger.warning(f"[evaluate_answer] JSON 解析失败（{type(e).__name__}），降级为正则: {e}")

    # JSON 失败，降级为正则解析
    if raw is None:
        return {**_FALLBACK_SCORES, "total": 50.0, "raw_evaluation": "", "json_mode": False}

    scores = {}
    total = 0.0
    import re
    for line in raw.strip().split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip().lower()
        m = re.search(r"\d+", val.strip())
        if m:
            score = int(m.group())
            if key in WEIGHTS:
                scores[key] = score
                total += score * WEIGHTS[key]

    if not scores:
        scores = {**_FALLBACK_SCORES}
        total = 50.0

    scores["total"] = round(total, 1)
    scores["raw_evaluation"] = raw
    scores["json_mode"] = False
    return scores


def _build_citations(chunks: list[dict]) -> list[dict]:
    """从 chunks 构建带 paper title 的 citations"""
    paper_titles = {}
    for c in chunks:
        pid = c["paper_id"]
        if pid not in paper_titles:
            p = get_paper(pid)
            paper_titles[pid] = (p.get("title") if p else "") or c.get("title") or ""
    return [
        {
            "paper_id": c["paper_id"],
            "title": paper_titles.get(c["paper_id"], ""),
            "chunk_index": c["chunk_index"],
            "page_number": c.get("page_number", 0),
            "content": (c.get("content") or c.get("text") or ""),
        }
        for c in chunks
    ]


def _enrich_chunks(chunks: list[dict]) -> list[dict]:
    """给 chunks 补充缺失字段"""
    for c in chunks:
        c.setdefault("combined_score", c.get("combined_score", 1.0))
        c.setdefault("is_evidence", c.get("chunk_type") == "evidence")
    return chunks


async def generate_answer_with_self_eval(
    question: str,
    chunks: list[dict],
    mode: Literal["default", "methodology", "survey"] = "default",
) -> tuple[str, list[dict], dict]:
    """
    带自我评分和迭代改进的答案生成。

    迭代策略（最多3轮）：
    - Round 1: top_k chunks → 生成 → 评分
    - Round 2: 分数 < 60 → 扩充 chunks（取更高分段落）→ 重试
    - Round 3: 分数仍 < 60 → 聚焦 evidence chunks → 最后一次

    最终输出分数最高的答案（不丢弃任何结果）
    """
    if not chunks:
        return "抱歉，我在你的论文库中没有找到相关内容。", [], {}

    # 过滤 reference chunks（PDF 参考文献文字杂乱）
    chunks = [c for c in chunks if c.get("section_type") != "reference"]
    if not chunks:
        return "抱歉，我在你的论文库中没有找到相关内容。", [], {}

    chunks = _enrich_chunks(chunks)

    best_answer = None
    best_score = 0
    best_citations = []
    best_meta = {}
    current_chunks = chunks[:]

    threshold = 60.0

    for round_num in range(1, 4):  # 最多3轮
        if mode == "methodology":
            user_message = (
                f"请分析以下论文片段的方法论：\n\n{build_context(current_chunks)}\n\n"
                f"用户问题：{question}"
            )
            max_tokens = 4096
        elif mode == "survey":
            user_message = build_survey_context(current_chunks, question)
            max_tokens = 8192
        else:
            user_message = (
                f"基于以下论文片段回答问题：\n\n问题：{question}\n\n"
                f"---\n{build_context(current_chunks)}\n\n"
                f"请根据以上片段回答问题，并在引用部分标注参考来源。"
            )
            max_tokens = 4096

        sp = SYSTEM_PROMPT_DEFAULT if round_num == 1 else SYSTEM_PROMPT_RETRY
        messages = [
            {"role": "system", "content": sp},
            {"role": "user", "content": user_message},
        ]

        answer_text = _call_minimax(messages, max_tokens=max_tokens, temperature=0.3)
        answer_text = strip_thinking_tags(answer_text)

        scores = evaluate_answer(question, answer_text, current_chunks)
        score = scores.get("total", 0)

        logger.debug(f"[self_eval round {round_num}] score={score} | "
              f"rel={scores.get('relevance','?')} | cov={scores.get('coverage','?')} | "
              f"cit={scores.get('citation_quality','?')} | gnd={scores.get('factual_grounding','?')} | "
              f"comp={scores.get('completeness','?')} | chunks={len(current_chunks)}")

        citations = _build_citations(current_chunks)
        meta = {
            "mode": mode,
            "paper_count": len({c["paper_id"] for c in current_chunks}),
            "chunk_count": len(current_chunks),
            "round": round_num,
            "self_eval": {
                "total": scores.get("total"),
                "relevance": scores.get("relevance"),
                "coverage": scores.get("coverage"),
                "citation_quality": scores.get("citation_quality"),
                "factual_grounding": scores.get("factual_grounding"),
                "completeness": scores.get("completeness"),
            },
        }

        if score > best_score:
            best_score = score
            best_answer = answer_text
            best_citations = citations
            best_meta = meta

        if score >= threshold or round_num == 3:
            break

        # 未达阈值，准备重试：扩充 chunks
        if round_num == 1:
            existing_ids = {(c["paper_id"], c["chunk_index"]) for c in current_chunks}
            extra = [
                c for c in sorted(chunks, key=lambda x: x.get("combined_score", 0), reverse=True)
                if (c["paper_id"], c["chunk_index"]) not in existing_ids
            ]
            current_chunks = current_chunks + extra[:8]
        else:
            # 再失败：聚焦 evidence chunks
            evidence = [c for c in chunks if c.get("is_evidence")]
            others = [c for c in chunks if not c.get("is_evidence")]
            current_chunks = (evidence + others)[:12]

    logger.info(f"[self_eval] 最终选择 round {best_meta.get('round','?')} | best_score={best_score}")
    return best_answer, best_citations, best_meta
