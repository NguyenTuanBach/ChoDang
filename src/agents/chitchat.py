"""Nhánh trò chuyện của trợ lý chính sách: LLM trả lời tin nhắn KHÔNG có căn cứ quy chế mạnh.

Dùng khi truy hồi không tìm được đoạn quy định đủ khớp (lời chào, cảm ơn kiểu lóng như "thanh kiu", chuyện ngoài lề,
câu quy chế diễn đạt quá xa văn bản). Câu quy chế thật vẫn đi đường truy hồi → trích dẫn → kiểm chứng.

An toàn: chạy SAU guard đầu vào (injection/dữ liệu SV khác đã bị chặn); prompt cấm nêu số liệu/cam kết; đầu ra phải
qua `check_policy_output` (PII, cam kết) và bị cắt gọn, bỏ ký hiệu trích dẫn. Lỗi/quá hạn → rơi về câu trả lời cố định.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable

from src.agents.prompts import SHARED_RULES, load_prompt
from src.services.llm import get_llm

ChatFn = Callable[[dict], Awaitable[str]]

CHAT_BUDGET_SECONDS = 6.0
MAX_CHARS = 600
_CITATION = re.compile(r"\[\[chunk:\d+\]\]|\[\d+(?:\s*,\s*\d+)*\]")


async def llm_chitchat(state: dict) -> str:
    """Model rẻ (`model_classify`): trả lời ngắn, không cần suy luận sâu."""
    prompt = load_prompt("policy_chitchat.md").replace("{{shared_rules}}", SHARED_RULES)
    result = await get_llm("classify").ainvoke([("system", prompt), ("human", state.get("redacted_query", ""))])
    return str(result.content)


def clean_reply(text: str) -> str:
    """Bỏ ký hiệu trích dẫn, gom khoảng trắng, cắt gọn ở cuối câu."""
    text = re.sub(r"[ \t]+", " ", _CITATION.sub("", text)).strip()
    if len(text) <= MAX_CHARS:
        return text
    cut = text[:MAX_CHARS]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: end + 1] if end > 80 else cut.rstrip() + "…").strip()
