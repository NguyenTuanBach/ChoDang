"""``MonitorReviewer``: so khớp nội dung đề cương/nhật ký (BE đã che PII) với chuẩn đầu ra của khóa, trả đề xuất cờ.

Không có công cụ ghi: chỉ trả ``findings``; BE kiểm loại cờ rồi tự ghi cờ (``actor_kind=agent``). Không đổi trạng thái nào.
"""

from __future__ import annotations

import json
from typing import Any

from vin15_agent.core.ai_client import AiClient
from vin15_agent.core.pii import PiiRedactor
from vin15_agent.core.prompts import PromptLoader
from vin15_agent.core.structured import StructuredOutputError, ask_json

ALLOWED_KINDS = frozenset({"outcome_mismatch", "weak_evidence"})
ALLOWED_SEVERITIES = frozenset({"info", "warning"})


class MonitorReviewer:
    def __init__(self, ai: AiClient, prompts: PromptLoader):
        self._ai = ai
        self._prompts = prompts

    async def review(self, payload: dict[str, Any]) -> dict[str, Any]:
        redactor = PiiRedactor()
        user = redactor.redact_text(json.dumps(payload, ensure_ascii=False))  # che lần nữa phòng BE sót
        try:
            parsed = await ask_json(self._ai, self._prompts.render("monitor_review.system"), user, max_tokens=1000)
        except StructuredOutputError:
            return {"findings": []}
        findings = []
        for item in (parsed.get("findings") or [])[:5]:
            if not isinstance(item, dict):
                continue
            kind, severity, reason = str(item.get("kind", "")), str(item.get("severity", "info")), str(item.get("reason", "")).strip()
            if kind in ALLOWED_KINDS and severity in ALLOWED_SEVERITIES and reason:
                findings.append(
                    {
                        "kind": kind,
                        "severity": severity,
                        "reason": reason[:500],
                        "suggestion": str(item.get("suggestion", ""))[:300],
                        "outcomes": [str(c) for c in (item.get("outcomes") or [])][:10],
                    }
                )
        return {"findings": findings}
