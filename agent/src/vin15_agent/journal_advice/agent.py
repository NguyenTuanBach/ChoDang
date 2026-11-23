"""``JournalAdvisor``: nhận xét lịch tuần tới trong nhật ký đã ổn chưa (BE đã che PII), trả một đoạn gợi ý ngắn.

Không có công cụ ghi và không quyết định gì: chỉ trả ``advice``; sinh viên đọc rồi tự quyết định có đính vào nhật ký hay không.
"""

from __future__ import annotations

import json
from typing import Any

from vin15_agent.core.ai_client import AiClient
from vin15_agent.core.pii import PiiRedactor
from vin15_agent.core.prompts import PromptLoader
from vin15_agent.core.structured import StructuredOutputError, ask_json

MAX_ADVICE_CHARS = 1500


class JournalAdvisor:
    def __init__(self, ai: AiClient, prompts: PromptLoader):
        self._ai = ai
        self._prompts = prompts

    async def advise(self, payload: dict[str, Any]) -> dict[str, Any]:
        redactor = PiiRedactor()
        user = redactor.redact_text(json.dumps(payload, ensure_ascii=False))  # che lần nữa phòng BE sót
        try:
            parsed = await ask_json(self._ai, self._prompts.render("journal_advice.system"), user, max_tokens=500)
        except StructuredOutputError:
            return {"advice": ""}
        return {"advice": str(parsed.get("advice", "")).strip()[:MAX_ADVICE_CHARS]}
