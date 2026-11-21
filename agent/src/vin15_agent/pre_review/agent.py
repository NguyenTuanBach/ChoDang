"""``PreReviewer``: giảm công đọc cho giảng viên. Chỉ trả văn bản và cấu trúc gợi ý; không chấp nhận/trả lại thay giảng viên."""

from __future__ import annotations

import json
from typing import Any

from vin15_agent.core.ai_client import AiClient
from vin15_agent.core.pii import PiiRedactor
from vin15_agent.core.prompts import PromptLoader
from vin15_agent.core.structured import ask_json


class PreReviewer:
    def __init__(self, ai: AiClient, prompts: PromptLoader):
        self._ai = ai
        self._prompts = prompts

    async def review(self, payload: dict[str, Any]) -> dict[str, Any]:
        user = PiiRedactor().redact_text(json.dumps(payload, ensure_ascii=False))
        parsed = await ask_json(self._ai, self._prompts.render("pre_review.system"), user, max_tokens=1400)
        known = {o.get("code") for o in payload.get("outcomes", []) if isinstance(o, dict)}
        matches = [
            {"code": str(m.get("code")), "covered": bool(m.get("covered")), "note": str(m.get("note", ""))[:300]}
            for m in (parsed.get("outcome_matches") or [])
            if isinstance(m, dict) and m.get("code") in known
        ][:20]
        return {
            "summary": str(parsed.get("summary", "")).strip()[:1500],
            "outcome_matches": matches,
            "concerns": [str(c)[:300] for c in (parsed.get("concerns") or [])][:8],
            "evidence_notes": [str(c)[:300] for c in (parsed.get("evidence_notes") or [])][:8],
        }
