"""Tiền thẩm cho giảng viên (C6): tóm tắt đề cương, so khớp chuẩn đầu ra, ghi chú minh chứng — **gợi ý của AI**, lưu kèm nhãn.

Agent chỉ trả văn bản/cấu trúc; không có nút hay đường nào để agent chấp nhận hoặc trả lại thay giảng viên.
"""

from __future__ import annotations

from vin15.domain.authorization import require_view_internship
from vin15.domain.exception import ForbiddenRoleError, InvalidInputError, ResourceNotFoundError
from vin15.domain.model.user import Role, User
from vin15.domain.pii import PiiRedactor
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.infrastructure.persistence.config_repository import ConfigRepository
from vin15.infrastructure.persistence.monitoring_repository import MonitoringRepository

_LIMIT = 4000


class PreReviewService:
    def __init__(self, cases: CaseRepository, config: ConfigRepository, monitoring: MonitoringRepository, agent: AgentApiClient, redactor: PiiRedactor):
        self._cases = cases
        self._config = config
        self._monitoring = monitoring
        self._agent = agent
        self._redactor = redactor

    async def review(self, lecturer: User, internship_id: int, subject_kind: str, subject_id: int) -> dict:
        if lecturer.role not in (Role.LECTURER, Role.ADMIN):
            raise ForbiddenRoleError("Chỉ giảng viên hoặc quản trị viên dùng tiền thẩm")
        row = self._cases.get_internship(internship_id)
        if row is None:
            raise ResourceNotFoundError("Không tìm thấy hồ sơ")
        require_view_internship(lecturer, row["user_id"], row["lecturer_id"])
        redact = self._redactor.redact_text
        outcomes = self._config.learning_outcomes(row["cohort"])
        payload: dict = {"kind": subject_kind, "outcomes": [{"code": o["code"], "description": o["description"]} for o in outcomes]}
        if subject_kind == "outline":
            outline = next((o for o in self._cases.outlines(internship_id) if o["id"] == subject_id), None)
            if outline is None:
                raise ResourceNotFoundError("Không tìm thấy đề cương")
            payload.update(content=redact(outline["content"])[:_LIMIT], declared_outcome_codes=list(outline["outcome_codes"]))
        elif subject_kind == "milestone":
            milestone = next((m for m in self._cases.milestones(internship_id) if m["id"] == subject_id), None)
            if milestone is None:
                raise ResourceNotFoundError("Không tìm thấy mốc")
            evidence = [e for e in self._cases.evidence_for_internship(internship_id) if e["milestone_id"] == subject_id]
            payload.update(
                milestone={"code": milestone["code"], "name": milestone["name"]},
                evidence=[{"title": redact(e["title"]), "mime": e["mime"], "size_bytes": e["size_bytes"]} for e in evidence],
                journals=[redact(j["content"])[:600] for j in self._cases.journals(internship_id)[:6] if j["content"]],
            )
        else:
            raise InvalidInputError("Chỉ tiền thẩm được đề cương hoặc mốc")
        body = await self._agent.call("/v1/pre-review", payload)
        summary = str(body.get("summary", "")).strip()
        if not summary:
            raise InvalidInputError("Agent không trả kết quả tiền thẩm")
        details = {k: body.get(k) for k in ("outcome_matches", "concerns", "evidence_notes") if body.get(k) is not None}
        suggestion_id = self._monitoring.add_suggestion(internship_id, subject_kind, subject_id, summary[:2000], details)
        return {"id": suggestion_id, "subject_kind": subject_kind, "subject_id": subject_id, "summary": summary, "details": details}
