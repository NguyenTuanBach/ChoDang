"""``OutlineReviewer``: quét đề cương (BE đã che PII), nêu chỗ cần sửa theo từng phần, nhận diện chuẩn đầu ra được phủ, nhận xét tổng quát.

Không có công cụ ghi và không quyết định gì: chỉ trả gợi ý; BE kiểm chuẩn đầu ra có thật rồi tự lưu, giảng viên mới là người duyệt.
"""

from __future__ import annotations

import json
from typing import Any

from vin15_agent.core.ai_client import AiClient
from vin15_agent.core.pii import PiiRedactor
from vin15_agent.core.prompts import PromptLoader
from vin15_agent.core.structured import StructuredOutputError, ask_json

MAX_ISSUES = 6


class OutlineReviewer:
    def __init__(self, ai: AiClient, prompts: PromptLoader):
        self._ai = ai
        self._prompts = prompts

    async def review(self, payload: dict[str, Any]) -> dict[str, Any]:
        redactor = PiiRedactor()
        user = redactor.redact_text(json.dumps(payload, ensure_ascii=False))  # che lần nữa phòng BE sót
        known = {str(o.get("code")) for o in payload.get("outcomes") or [] if isinstance(o, dict)}
        try:
            parsed = await ask_json(self._ai, self._prompts.render("outline_review.system"), user, max_tokens=900)
        except StructuredOutputError:
            return {"summary": "", "issues": [], "outcome_codes": []}
        issues = []
        for item in (parsed.get("issues") or [])[:MAX_ISSUES]:
            if not isinstance(item, dict):
                continue
            message = str(item.get("message", "")).strip()
            if message:
                issues.append({"section": str(item.get("section", "")).strip()[:60], "message": message[:400]})
        codes = [str(c) for c in (parsed.get("outcome_codes") or []) if str(c) in known]
        return {"summary": str(parsed.get("summary", "")).strip()[:1500], "issues": issues, "outcome_codes": list(dict.fromkeys(codes))}
