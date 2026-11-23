"""Gọi LLM một lượt để lấy đầu ra JSON có cấu trúc (không tool, không ghi): dùng cho các agent một-lượt (tiền thẩm, giám sát, chuẩn hóa hồ sơ)."""

from __future__ import annotations

import json
import re
from typing import Any

from vin15_agent.core.ai_client import AiClient

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class StructuredOutputError(ValueError):
    """LLM không trả JSON object hợp lệ."""


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = _FENCE.sub("", text.strip())
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise StructuredOutputError("Không có JSON object trong phản hồi")
    try:
        value = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise StructuredOutputError("JSON không hợp lệ") from exc
    if not isinstance(value, dict):
        raise StructuredOutputError("Phản hồi không phải JSON object")
    return value


async def ask_json(ai: AiClient, system: str, user: str, *, max_tokens: int = 1500) -> dict[str, Any]:
    result = await ai.chat([{"role": "system", "content": system}, {"role": "user", "content": user}], temperature=0, max_tokens=max_tokens)
    return parse_json_object(result.text)


async def ask_json_parts(ai: AiClient, system: str, parts: list[dict[str, Any]], *, max_tokens: int = 1500) -> dict[str, Any]:
    """Như ``ask_json`` nhưng nội dung người dùng là danh sách phần (``text`` / ``image_url``); đòi đường LLM có ``vision``."""
    result = await ai.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": parts}], temperature=0, max_tokens=max_tokens, capability="vision"
    )
    return parse_json_object(result.text)
