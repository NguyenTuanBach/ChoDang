"""Nộp đề cương có kiểm tra: luật tất định (đủ bốn phần) + agent AI quét và nhận xét (gợi ý, không thay quyết định của giảng viên).

- Có lỗi chắc chắn (thiếu phần, quá ngắn): **không lưu**, trả danh sách chỗ sai kèm nhận xét AI để sinh viên sửa rồi nộp lại.
- Không có lỗi chắc chắn: lưu phiên bản mới; chuẩn đầu ra do AI nhận diện từ nội dung (không còn tích tay); nhận xét AI lưu kèm để xem lại.
- Agent không trả lời được: vẫn nộp được nếu đạt phần luật, nhận xét AI để trống.
"""

from __future__ import annotations

import base64

from vin15.domain.authorization import require_view_internship
from vin15.domain.exception import AgentTimeoutError, AgentUnavailableError, InvalidInputError, ResourceNotFoundError, StateConflictError
from vin15.domain.model.user import User
from vin15.domain.pii import PiiRedactor
from vin15.domain.ports import FileStorage
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.service.files.upload import EVIDENCE_TYPES, sniff_mime, store_upload
from vin15.service.outline.outline_check import check_outline
from vin15.service.outline.outline_service import OutlineService
from vin15.service.policy.policy_file_reader import read_policy_file

_LIMIT = 12000
_MAX_AI_ISSUES = 8
_EXTRACT_TIMEOUT = 120.0
#: Bốn trường agent trả về (khớp ``SECTIONS`` ở FE); giá trị dài nhất giữ lại.
OUTLINE_FIELDS = ("objective", "tasks", "plan", "results")
_VALUE_LIMIT = 4000
_TEXT_EXTENSIONS = (".txt", ".md", ".markdown")


class OutlineReviewService:
    def __init__(
        self,
        outlines: OutlineService,
        cases: CaseRepository,
        agent: AgentApiClient,
        redactor: PiiRedactor,
        storage: FileStorage | None = None,
        max_bytes: int = 10 * 1024 * 1024,
    ):
        self._storage = storage
        self._max_bytes = max_bytes
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

    def attach_file(self, student: User, outline_id: int, filename: str, data: bytes) -> dict:
        """Lưu tệp đề cương sinh viên đã nộp (để giảng viên mở lại bản gốc). Chỉ chủ hồ sơ, mỗi phiên bản một tệp."""
        row = self._cases.get_outline(outline_id)
        if row is None or row["owner_id"] != student.id:
            raise ResourceNotFoundError("Không tìm thấy đề cương")
        if row.get("file_key"):
            raise StateConflictError("Phiên bản đề cương này đã có tệp đính kèm")
        stored = store_upload(self._storage, f"outline/{row['internship_id']}", filename, data, EVIDENCE_TYPES, self._max_bytes)
        if not self._cases.attach_outline_file(outline_id, stored.filename, stored.mime, stored.size, stored.key):
            self._storage.delete(stored.key)  # có yêu cầu khác gắn tệp trước: bỏ tệp vừa lưu
            raise StateConflictError("Phiên bản đề cương này đã có tệp đính kèm")
        return {"id": outline_id, "file_name": stored.filename, "file_size": stored.size}

    def file_bytes(self, viewer: User, outline_id: int) -> tuple[bytes, str, str]:
        row = self._cases.get_outline(outline_id)
        if row is None or not row.get("file_key"):
            raise ResourceNotFoundError("Đề cương này không có tệp đính kèm")
        require_view_internship(viewer, row["owner_id"], row["lecturer_id"])
        return self._storage.get(row["file_key"]), row["file_mime"], row["file_name"]

    async def extract_file(self, student: User, filename: str, data: bytes) -> dict:
        """Đọc tệp đề cương (PDF, ảnh, DOCX, TXT/MD) và gợi ý bốn phần để điền vào form; không lưu gì, sinh viên kiểm tra rồi mới nộp."""
        row = self._cases.student_internship(student.id)
        if row is None or row["status"] != "confirmed":
            raise StateConflictError("Chỉ tải đề cương khi hồ sơ đã được giảng viên xác nhận")
        mime, payload = self._prepare(filename, data)
        body = await self._agent.call(
            "/v1/intake/extract",
            {"filename": filename[:200], "mime": mime, "content_b64": base64.b64encode(payload).decode(), "fields": list(OUTLINE_FIELDS), "kind": "outline"},
            timeout=_EXTRACT_TIMEOUT,
        )
        fields: dict[str, dict] = {}
        for name, item in (body.get("fields") or {}).items():
            if name not in OUTLINE_FIELDS or not isinstance(item, dict):
                continue
            value = str(item.get("value", "")).strip()
            if value:
                fields[name] = {"value": value[:_VALUE_LIMIT]}
        return {"fields": fields, "notes": str(body.get("notes", ""))[:500]}

    @staticmethod
    def _prepare(filename: str, data: bytes) -> tuple[str, bytes]:
        """Loại tệp thật theo byte; DOCX và TXT/MD được tách chữ ngay ở BE rồi gửi dạng ``text/plain``, PDF và ảnh gửi nguyên cho agent."""
        if not data:
            raise InvalidInputError("Tệp rỗng")
        name = (filename or "").lower()
        mime = sniff_mime(data, filename)
        if mime in ("application/pdf", "image/png", "image/jpeg"):
            return mime, data
        if mime is not None or name.endswith(_TEXT_EXTENSIONS):
            text = read_policy_file(filename, data)  # DOCX hoặc văn bản thuần; lỗi định dạng thì ném InvalidInputError
            return "text/plain", text[:_LIMIT * 2].encode("utf-8")
        raise InvalidInputError("Chỉ đọc được tệp PDF, ảnh (PNG, JPG), DOCX hoặc TXT")

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
