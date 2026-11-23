"""Nộp đề cương có kiểm tra: luật tất định (đủ bốn phần) + agent AI quét và nhận xét (gợi ý, không thay quyết định của giảng viên).

- Có lỗi chắc chắn (thiếu phần, quá ngắn): **không lưu**, trả danh sách chỗ sai kèm nhận xét AI để sinh viên sửa rồi nộp lại.
- Không có lỗi chắc chắn: lưu phiên bản mới; chuẩn đầu ra do AI nhận diện từ nội dung (không còn tích tay); nhận xét AI lưu kèm để xem lại.
- Agent không trả lời được: vẫn nộp được nếu đạt phần luật, nhận xét AI để trống.
"""

from __future__ import annotations

from vin15.domain.exception import AgentTimeoutError, AgentUnavailableError, StateConflictError
from vin15.domain.model.user import User
from vin15.domain.pii import PiiRedactor
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.service.outline.outline_check import check_outline
from vin15.service.outline.outline_service import OutlineService

_LIMIT = 12000
_MAX_AI_ISSUES = 8


class OutlineReviewService:
    def __init__(self, outlines: OutlineService, cases: CaseRepository, agent: AgentApiClient, redactor: PiiRedactor):
        self._outlines = outlines
        self._cases = cases
        self._agent = agent
        self._redactor = redactor

    async def submit(self, student: User, content: str) -> dict:
        row = self._cases.student_internship(student.id)
        if row is None or row["status"] != "confirmed":
            raise StateConflictError("Chỉ nộp được đề cương khi hồ sơ đã được giảng viên xác nhận")
        text = content.strip()
        rule_issues = check_outline(text)
        outcomes = self._outlines.outcomes_for(row["cohort"])
        ai = await self._review(text, outcomes)
        ai_issues = list(ai["issues"]) if ai else []
        codes = list(ai["outcome_codes"]) if ai else []
        known = {o["code"] for o in outcomes}
        codes = [c for c in dict.fromkeys(codes) if c in known]
        if ai and outcomes and not codes:
            ai_issues.append({"section": "Chuẩn đầu ra", "level": "warning", "message": "Chưa thấy đề cương phủ chuẩn đầu ra nào của khóa; hãy nêu rõ công việc gắn với kiến thức, kỹ năng cần đạt."})
        issues = rule_issues + ai_issues
        summary = ai["summary"] if ai else ""
        if rule_issues:
            return {"saved": False, "id": None, "issues": issues, "summary": summary, "ai": ai is not None, "outcome_codes": []}
        review = {"summary": summary, "issues": issues, "ai": ai is not None}
        outline_id = self._outlines.submit(student, text, codes, ai_review=review)
        return {"saved": True, "id": outline_id, "outcome_codes": codes, **review}

    async def _review(self, text: str, outcomes: list[dict]) -> dict | None:
        payload = {
            "content": self._redactor.redact_text(text)[:_LIMIT],
            "outcomes": [{"code": o["code"], "description": o["description"]} for o in outcomes],
        }
        try:
            body = await self._agent.call("/v1/outline/review", payload)
        except (AgentUnavailableError, AgentTimeoutError):
            return None
        issues = []
        for item in (body.get("issues") or [])[:_MAX_AI_ISSUES]:
            if not isinstance(item, dict):
                continue
            message = str(item.get("message", "")).strip()
            if message:
                issues.append({"section": str(item.get("section", "")).strip()[:60] or "Nội dung", "level": "warning", "message": message[:400]})
        return {
            "summary": str(body.get("summary", "")).strip()[:1500],
            "issues": issues,
            "outcome_codes": [str(c) for c in (body.get("outcome_codes") or []) if isinstance(c, str)][:20],
        }
