"""Hỏi AI xem lịch làm việc tuần tới trong nhật ký đã ổn chưa (gợi ý cho sinh viên, không thay quyết định của ai).

BE gửi nội dung đã che PII cùng mốc sắp tới; agent một-lượt (không công cụ ghi) trả một đoạn gợi ý. Không ghi gì vào DB:
sinh viên đọc rồi quyết định có đính gợi ý vào nhật ký khi nộp hay không.
"""

from __future__ import annotations

from vin15.domain.clock import Clock
from vin15.domain.exception import InvalidInputError, StateConflictError
from vin15.domain.model.user import User
from vin15.domain.pii import PiiRedactor
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.service.milestone.milestone_service import normalize_plan_items

_LIMIT = 3000


class JournalAdviceService:
    def __init__(self, cases: CaseRepository, agent: AgentApiClient, redactor: PiiRedactor, clock: Clock):
        self._cases = cases
        self._agent = agent
        self._redactor = redactor
        self._clock = clock

    async def advise(self, student: User, content: str, plan_items: list[dict], blockers: str) -> dict:
        row = self._cases.student_internship(student.id)
        if row is None or row["status"] != "in_progress":
            raise StateConflictError("Chỉ hỏi AI về lịch khi đang thực tập")
        items = normalize_plan_items(plan_items)
        if not items:
            raise InvalidInputError("Hãy thêm ít nhất một việc vào kế hoạch tuần tới trước khi hỏi AI")
        redact = self._redactor.redact_text
        today = self._clock()
        upcoming = [
            {"code": m["code"], "name": m["name"], "due_date": m["due_date"].isoformat() if m["due_date"] else None, "status": m["status"]}
            for m in self._cases.milestones(row["id"])
            if m["status"] in ("pending", "overdue", "rejected")
        ]
        payload = {
            "today": today.isoformat(),
            "internship_end": row["end_date"].isoformat() if row["end_date"] else None,
            "done_this_week": redact(content.strip())[:_LIMIT],
            "plan_items": [{"text": redact(i["text"]), "done": i["done"]} for i in items],
            "blockers": redact(blockers.strip())[:_LIMIT],
            "upcoming_milestones": upcoming,
        }
        body = await self._agent.call("/v1/journal/advice", payload)
        advice = str(body.get("advice", "")).strip()
        if not advice:
            raise InvalidInputError("AI chưa đưa ra được gợi ý, hãy thử lại sau")
        return {"advice": advice[:_LIMIT]}
