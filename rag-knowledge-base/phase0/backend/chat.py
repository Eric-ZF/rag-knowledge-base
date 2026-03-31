"""
Phase 0：RAG 问答 — 使用 MiniMax MiniMax-Text-01 生成带引用的答案

MiniMax API 通过 OpenAI-compatible 端点提供 Chat 功能：
  Base URL: https://api.minimax.chat/v1
  Model:     MiniMax-Text-01（200K context）
  Auth:      Bearer <api_key> + GroupId header
"""

import os
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from config import MINIMAX_API_KEY, MINIMAX_GROUP_ID, MINIMAX_CHAT_ENDPOINT, CHAT_MODEL


# ─── System Prompt ────────────────────────────────────
SYSTEM_PROMPT = """你是一个专业的研究助手，擅长基于提供的论文片段回答用户的学术问题。

回答规则（严格遵守）：
1. 只基于上下文中的论文片段回答，**绝对不要编造**论文中不存在的内容
2. 如果上下文片段不足以回答问题，明确说"论文库中没有足够证据回答此问题"
3. **必须**在回答中每个事实陈述后，通过【片段X】格式标注来源
4. 优先使用片段中的原文描述，而非改写
5. 使用中文回答，学术语气，保持严谨

输出格式：
1. 先给出答案主体（每个关键结论后标注【片段X】）
2. 在"引用"部分列出所有参考片段的编号、内容和页码
3. 如果无法回答，说明原因

示例格式：
答案：CBAM是欧盟的碳边境调节机制【片段1】...
引用：
- 【片段1】论文ID: xxx, 页码: 3, 内容: "碳边境调节机制(CBAM)..."
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


# ─── MiniMax Chat Client ──────────────────────────────
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
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        """
        发送对话请求到 MiniMax
        
        Args:
            messages: [{"role": "user"/"assistant"/"system", "content": "..."}]
            model: 模型名，默认 MiniMax-Text-01
            max_tokens: 最大生成长度
            temperature: 随机性（学术问答偏保守）
        
        Returns:
            生成的文本
        """
        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "GroupId": self.group_id,
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        response = self.session.post(
            self.endpoint,
            headers=headers,
            json=payload,
            timeout=60,
        )

        data = response.json()

        # 检查错误
        if response.status_code != 200:
            raise RuntimeError(
                f"MiniMax API 错误 [{response.status_code}]: "
                f"{data.get('error', {}).get('message', data)}"
            )

        if "choices" not in data or not data["choices"]:
            raise RuntimeError(f"MiniMax 返回格式异常: {data}")

        return data["choices"][0]["message"]["content"]


# ─── 生成答案 ──────────────────────────────────────────
async def generate_answer(
    question: str,
    chunks: list[dict],
    anthropic_api_key: str = "",  # Phase 0 用 MiniMax，忽略此参数
    model: str = CHAT_MODEL,
) -> tuple[str, list[dict]]:
    """
    调用 MiniMax MiniMax-Text-01，基于检索到的 chunks 生成答案
    Phase 0 使用 MiniMax API（OpenAI-compatible）

    Returns: (answer_text, citations)
    """
    if not MINIMAX_API_KEY or not MINIMAX_GROUP_ID:
        raise ValueError(
            "MINIMAX_API_KEY 和 MINIMAX_GROUP_ID 必须设置\n"
            "获取 Group ID: https://platform.minimax.chat/user/login"
        )

    if not chunks:
        return "抱歉，我在你的论文库中没有找到相关内容。", []

    context = build_context(chunks)

    user_message = f"""基于以下论文片段回答问题：

问题：{question}

---
{context}
---

请根据以上片段回答问题，并在"引用"部分标注参考来源。"""

    client = MiniMaxChatClient(
        api_key=MINIMAX_API_KEY,
        group_id=MINIMAX_GROUP_ID,
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    answer_text = client.chat(
        messages=messages,
        model=model,
        max_tokens=1024,
        temperature=0.3,  # 偏低，学术回答要准确不要发散
    )

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
