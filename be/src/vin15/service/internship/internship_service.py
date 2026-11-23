"""Hồ sơ thực tập (A3-A6): sinh viên khai báo, kiểm, nộp; giảng viên xác nhận / yêu cầu sửa / từ chối (HITL, có lý do, có audit).

Nội dung đã nộp được chụp phiên bản và không sửa tại chỗ (BR-S4). Xác nhận hồ sơ sinh mốc từ mẫu của QTV.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from vin15.domain.authorization import actor_of, require_view_internship
from vin15.domain.clock import Clock
from vin15.domain.exception import InvalidInputError, ResourceNotFoundError, ScopeDeniedError, StateConflictError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import Role, User
from vin15.domain.ports import FileStorage
from vin15.domain.statemachine import INTERNSHIP, Subject
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.infrastructure.persistence.config_repository import ConfigRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.service.files.upload import RECEIPT_TYPES, store_upload
from vin15.service.notification.notification_service import NotificationService
from vin15.service.policy.policy_search_service import PolicySearchService

_TAX_CODE = re.compile(r"^\d{10}(-\d{3})?$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^[0-9+()\-.\s]{8,20}$")
_REQUIRED = {
    "company_name": "Tên doanh nghiệp",
    "company_tax_code": "Mã số thuế",
    "company_address": "Địa chỉ doanh nghiệp",
    "position": "Vị trí thực tập",
    "mentor_name": "Người hướng dẫn",
    "mentor_email": "Email người hướng dẫn",
    "job_description": "Mô tả công việc",
}
_EDITABLE = ("draft", "revision_requested")
_DATE_FIELDS = ("start_date", "end_date", "receipt_letter_date")
_DOC_PREFIX = "internship"


def milestone_due(anchor: str, offset_days: int, start: date, end: date) -> date:
    base = {"start": start, "end": end, "mid": start + timedelta(days=(end - start).days // 2)}[anchor]
    return base + timedelta(days=offset_days)


class InternshipService:
    def __init__(
        self,
        cases: CaseRepository,
        users: UserRepository,
        config: ConfigRepository,
        policies: PolicySearchService,
        notifications: NotificationService,
        storage: FileStorage,
        clock: Clock,
        *,
        cohort: str,
        min_weeks: int,
        upload_max_bytes: int,
    ):
        self._cases = cases
        self._users = users
        self._config = config
        self._policies = policies
        self._notifications = notifications
        self._storage = storage
        self._clock = clock
        self._cohort = cohort
        self._min_weeks = min_weeks
        self._max_bytes = upload_max_bytes

    # ---- Sinh viên ----
    def mine(self, student: User) -> dict | None:
        return self._cases.student_internship(student.id)

    def save_draft(self, student: User, fields: dict, confirmations: dict[str, str] | None = None) -> dict:
        current = self._cases.student_internship(student.id)
        if current is None:
            advisor = self._users.find_by_id(student.id)
            self._cases.create_internship(
                student.id,
                self._cohort,
                advisor.advisor_id if advisor else None,
                AuditEntry(
                    actor_kind=ActorKind.HUMAN,
                    actor_id=student.id,
                    actor_role=student.role.value,
                    entity="internship",
                    action="create",
                    after={"status": "draft", "cohort": self._cohort},
                    reason="Sinh viên tạo hồ sơ thực tập",
                ),
            )
            current = self._cases.student_internship(student.id)
        assert current is not None
        # Cột văn bản không cho NULL: trường bỏ trống lưu là chuỗi rỗng; ngày bỏ trống lưu NULL; hình thức không gửi thì giữ nguyên.
        fields = {k: ("" if v is None and k not in _DATE_FIELDS else v) for k, v in fields.items() if not (k == "mode" and v is None)}
        self._check_fields(fields)
        self._cases.update_profile(current["id"], fields, confirmations)
        return self._cases.get_internship(current["id"]) or current

    @staticmethod
    def _check_fields(fields: dict) -> None:
        start, end = fields.get("start_date"), fields.get("end_date")
        if start and end and end < start:
            raise InvalidInputError("Ngày kết thúc phải sau ngày bắt đầu")
        if fields.get("mode") not in (None, "onsite", "remote", "hybrid"):
            raise InvalidInputError("Hình thức thực tập phải là onsite, remote hoặc hybrid")

    def upload_document(self, student: User, filename: str, data: bytes) -> dict:
        current = self._cases.student_internship(student.id)
        if current is None:
            # Cho tải giấy trước khi gõ gì (vd. đính kèm trong ngăn Trợ lý): tạo hồ sơ nháp rỗng.
            current = self.save_draft(student, {})
        if current["status"] not in _EDITABLE:
            raise StateConflictError("Hồ sơ đã nộp, không tải thêm tệp")
        stored = store_upload(self._storage, f"{_DOC_PREFIX}/{current['id']}", filename, data, RECEIPT_TYPES, self._max_bytes)
        doc_id = self._cases.add_document(current["id"], stored.filename, stored.mime, stored.size, stored.sha256, stored.key, student.id)
        return {"id": doc_id, "filename": stored.filename, "mime": stored.mime, "size_bytes": stored.size}

    def document_bytes(self, viewer: User, document_id: int) -> tuple[bytes, str, str]:
        doc = self._cases.get_document(document_id)
        if doc is None:
            raise ResourceNotFoundError("Không tìm thấy tệp")
        require_view_internship(viewer, doc["owner_id"], doc["lecturer_id"])
        return self._storage.get(doc["storage_key"]), doc["mime"], doc["filename"]

    def validate(self, internship: dict) -> list[dict]:
        """Kiểm hồ sơ trước khi nộp (A5, A6). Mục sai quy định kèm trích dẫn điều khoản đang hiệu lực khi tra được."""
        checks: list[dict] = []
        for field, label in _REQUIRED.items():
            ok = bool(str(internship.get(field) or "").strip())
            checks.append({"code": f"required:{field}", "label": f"{label} đã điền", "ok": ok, "level": "error", "detail": "" if ok else "Còn thiếu", "citation": None})
        tax = str(internship.get("company_tax_code") or "").strip()
        if tax:
            ok = bool(_TAX_CODE.match(tax))
            checks.append({"code": "tax_code_format", "label": "Mã số thuế đúng định dạng (10 hoặc 13 số)", "ok": ok, "level": "error", "detail": "" if ok else f"'{tax}' không hợp lệ", "citation": None})
            others = self._cases.other_companies_with_tax_code(tax, internship["id"])
            if others:
                names = ", ".join(sorted({o["company_name"] for o in others}))
                checks.append({"code": "company_duplicate", "label": "Doanh nghiệp chưa trùng hồ sơ khác", "ok": False, "level": "warning", "detail": f"Đã có hồ sơ khác cùng MST ({names}); kiểm tra lại cho đúng doanh nghiệp", "citation": None})
        email = str(internship.get("mentor_email") or "").strip()
        if email:
            checks.append({"code": "mentor_email", "label": "Email người hướng dẫn hợp lệ", "ok": bool(_EMAIL.match(email)), "level": "error", "detail": "", "citation": None})
        phone = str(internship.get("mentor_phone") or "").strip()
        if phone:
            checks.append({"code": "mentor_phone", "label": "Số điện thoại người hướng dẫn hợp lệ", "ok": bool(_PHONE.match(phone)), "level": "warning", "detail": "", "citation": None})
        start, end = internship.get("start_date"), internship.get("end_date")
        dates_ok = start is not None and end is not None
        checks.append({"code": "dates", "label": "Đã nhập thời gian thực tập", "ok": dates_ok, "level": "error", "detail": "" if dates_ok else "Cần ngày bắt đầu và kết thúc", "citation": None})
        if dates_ok:
            weeks = ((end - start).days + 1) // 7
            ok = weeks >= self._min_weeks
            checks.append(
                {
                    "code": "min_duration",
                    "label": f"Thời lượng tối thiểu {self._min_weeks} tuần",
                    "ok": ok,
                    "level": "error",
                    "detail": f"Hồ sơ có {weeks} tuần" + ("" if ok else f", thiếu {self._min_weeks - weeks} tuần"),
                    "citation": self._duration_citation(),
                }
            )
            future = start >= self._clock()
            checks.append({"code": "start_in_future", "label": "Ngày bắt đầu chưa qua", "ok": future, "level": "warning", "detail": "" if future else "Ngày bắt đầu đã qua; hạn các mốc có thể đã quá", "citation": None})
        has_doc = bool(self._cases.documents(internship["id"]))
        checks.append({"code": "receipt_letter", "label": "Đã tải giấy tiếp nhận", "ok": has_doc, "level": "warning", "detail": "" if has_doc else "Nên tải giấy tiếp nhận của doanh nghiệp", "citation": None})
        return checks

    def _duration_citation(self) -> dict | None:
        try:
            result = self._policies.search("thời lượng thực tập tối thiểu tuần", top_k=1)
        except Exception:
            return None
        if result.status != "ok" or not result.chunks:
            return None
        chunk = result.chunks[0]
        return {
            "chunk_id": chunk.chunk_id,
            "doc_title": chunk.doc_title,
            "version": chunk.version,
            "article_no": chunk.article_no,
            "clause_no": chunk.clause_no,
            "text": chunk.text[:400],
            "is_sample": chunk.is_sample,
        }

    def submit(self, student: User) -> dict:
        current = self._cases.student_internship(student.id)
        if current is None:
            raise StateConflictError("Chưa có hồ sơ để nộp")
        errors = [c for c in self.validate(current) if not c["ok"] and c["level"] == "error"]
        if errors:
            raise InvalidInputError("Hồ sơ chưa đạt: " + "; ".join(f"{c['label']} ({c['detail']})" if c["detail"] else c["label"] for c in errors))
        if current["lecturer_id"] is None:
            raise InvalidInputError("Chưa có giảng viên phụ trách; liên hệ quản trị viên để được phân công")
        source = current["status"]
        transition = INTERNSHIP.transition(source, "submitted", actor_of(student), Subject(current["user_id"], current["lecturer_id"]))
        self._cases.submit_internship(current["id"], source, INTERNSHIP.audit(transition, actor_of(student), current["id"]))
        self._notifications.notify(
            current["lecturer_id"],
            "Hồ sơ thực tập chờ xác nhận",
            f"{student.full_name} đã nộp hồ sơ thực tập.",
            kind="internship_submitted",
            link=f"/lecturer/internships/{current['id']}",
            email=True,
        )
        return self._cases.get_internship(current["id"]) or current

    # ---- Giảng viên ----
    def decide(self, lecturer: User, internship_id: int, action: str, reason: str = "") -> dict:
        row = self._cases.get_internship(internship_id)
        if row is None:
            raise ResourceNotFoundError("Không tìm thấy hồ sơ")
        if lecturer.role != Role.LECTURER:
            raise ScopeDeniedError("Chỉ giảng viên phụ trách được quyết định hồ sơ")
        target = {"confirm": "confirmed", "request_revision": "revision_requested", "reject": "rejected"}.get(action)
        if target is None:
            raise InvalidInputError("Quyết định không hợp lệ")
        actor = actor_of(lecturer)
        transition = INTERNSHIP.transition(row["status"], target, actor, Subject(row["user_id"], row["lecturer_id"]), reason)
        milestones = None
        extra = None
        if target == "confirmed":
            if row["start_date"] is None or row["end_date"] is None:
                raise InvalidInputError("Hồ sơ thiếu thời gian thực tập")
            milestones = self._milestones_from_templates(row["start_date"], row["end_date"])
            extra = {"milestones": [m["code"] for m in milestones]}
        self._cases.decide_internship(
            internship_id, row["status"], target, INTERNSHIP.audit(transition, actor, internship_id, extra=extra), reason=reason.strip(), milestones=milestones
        )
        titles = {
            "confirmed": "Hồ sơ thực tập đã được xác nhận. Hãy nộp đề cương.",
            "revision_requested": "Giảng viên yêu cầu sửa hồ sơ thực tập.",
            "rejected": "Hồ sơ thực tập bị từ chối.",
        }
        self._notifications.notify(
            row["user_id"], titles[target], reason.strip(), kind=f"internship_{target}", link="/student/internship", email=True
        )
        return self._cases.get_internship(internship_id) or row

    def _milestones_from_templates(self, start: date, end: date) -> list[dict]:
        out = []
        for t in self._config.milestone_templates():
            due = milestone_due(t["anchor"], t["offset_days"], start, end)
            # M1 là "hồ sơ được xác nhận": đạt ngay khi giảng viên xác nhận.
            out.append({"code": t["code"], "name": t["name"], "due_date": due, "status": "accepted" if t["code"] == "M1" else "pending"})
        return out


