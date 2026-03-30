"""
Phase 0：RAG 问答 — 使用 Claude Haiku 生成带引用的答案
"""

import anthropic
from typing import Any


# ─── System Prompt ────────────────────────────────────
SYSTEM_PROMPT = """你是一个专业的研究助手，擅长基于提供的论文片段回答用户的学术问题。

回答规则：
1. 只基于上下文中的论文片段回答，不要编造内容
2. 如果上下文没有相关信息，明确告知用户"没有找到相关内容"
3. 回答要准确，引用时标注论文标题和页码
4. 使用中文回答，学术语气

输出格式：
- 先给出答案主体
- 然后在"引用"部分列出参考的论文片段
"""


# ─── 上下文组装 ────────────────────────────────────────
def build_context(chunks: list[dict]) -> str:
    """将检索到的 chunks 组装成 LLM 上下文"""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(
            f"【片段 {i}】\n"
            f"论文 ID: {chunk['paper_id']}\n"
            f"页码: {chunk['page_number']}\n"
            f"内容: {chunk['content']}"
        )
    return "\n\n".join(context_parts)


# ─── 生成答案 ──────────────────────────────────────────
async def generate_answer(
    question: str,
    chunks: list[dict],
    anthropic_api_key: str,
    model: str = "claude-sonnet-4-20250514",
) -> tuple[str, list[dict]]:
    """
    调用 Claude Haiku，基于检索到的 chunks 生成答案
    Returns: (answer_text, citations)
    """
    if not anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY 未设置")

    if not chunks:
        return "抱歉，我在你的论文库中没有找到相关内容。", []

    context = build_context(chunks)

    user_message = f"""基于以下论文片段回答问题：

问题：{question}

---
{context}
---

请根据以上片段回答问题，并在"引用"部分标注参考来源。"""

    client = anthropic.Anthropic(api_key=anthropic_api_key)

    response = client.messages.create(
        model="claude-haiku-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_message,
            }
        ],
    )

    answer_text = response.content[0].text

    # 构建 citations
    citations = []
    for chunk in chunks:
        citations.append({
            "paper_id": chunk["paper_id"],
            "chunk_index": chunk["chunk_index"],
            "page_number": chunk["page_number"],
            "content": chunk["content"][:300],  # 引用前 300 字符
        })

    return answer_text, citations
