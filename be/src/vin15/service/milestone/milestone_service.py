"""Mốc, nhật ký tuần và minh chứng (A8-A10). Sinh viên nộp, giảng viên chấp nhận / trả lại (HITL); hệ thống đánh dấu quá hạn."""

from __future__ import annotations

from datetime import date, timedelta

from vin15.domain.authorization import actor_of, require_view_internship
from vin15.domain.clock import Clock
from vin15.domain.exception import InvalidInputError, ResourceNotFoundError, ScopeDeniedError, StateConflictError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.internship import MilestoneRecord
from vin15.domain.model.user import User
from vin15.domain.ports import FileStorage
from vin15.domain.statemachine import MILESTONE, Subject
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.service.files.upload import EVIDENCE_TYPES, store_upload
from vin15.service.milestone.milestone_view import milestone_view
from vin15.service.notification.notification_service import NotificationService
from vin15.service.progress.progress_calculator import EVIDENCE_REQUIRED_CODES

#: Mốc sinh viên nộp. M1 (hồ sơ) và M2 (đề cương) đạt qua quyết định của giảng viên ở bước hồ sơ/đề cương.
SUBMITTABLE = ("M3", "M4", "M5")
_WORKING = ("in_progress", "pending_credit")
MAX_PLAN_ITEMS = 20
MAX_ITEM_CHARS = 300


def normalize_plan_items(items: list[dict] | None) -> list[dict]:
    """Danh sách việc ``[{"text", "done"}]``: bỏ dòng trống, cắt độ dài, giới hạn số dòng."""
    cleaned: list[dict] = []
    for item in items or []:
        text = str(item.get("text", "")).strip()
        if text:
            cleaned.append({"text": text[:MAX_ITEM_CHARS], "done": bool(item.get("done", False))})
    if len(cleaned) > MAX_PLAN_ITEMS:
        raise InvalidInputError(f"Tối đa {MAX_PLAN_ITEMS} việc trong kế hoạch")
    return cleaned


class MilestoneService:
    def __init__(self, cases: CaseRepository, notifications: NotificationService, storage: FileStorage, clock: Clock, upload_max_bytes: int):
        self._cases = cases
        self._notifications = notifications
        self._storage = storage
        self._clock = clock
        self._max_bytes = upload_max_bytes

    # ---- Xem ----
    def views(self, internship_id: int) -> list[dict]:
        """Mốc kèm trạng thái hiệu lực, số ngày còn lại và việc cần làm tiếp (A8)."""
        today = self._clock()
        out = []
        for m in self._cases.milestones(internship_id):
            view = milestone_view(MilestoneRecord(m["code"], m["name"], m["due_date"], m["status"]), today)
            out.append(
                {
                    "id": m["id"],
                    "code": m["code"],
                    "name": m["name"],
                    "due_date": m["due_date"],
                    "status": view.status,
                    "stored_status": m["status"],
                    "days_left": view.days_left,
                    "next_action": view.next_action,
                    "note": m["note"],
                    "submittable": m["code"] in SUBMITTABLE,
                }
            )
        return out

    # ---- Sinh viên ----
    def submit(self, student: User, code: str) -> None:
        row = self._cases.student_internship(student.id)
        if row is None:
            raise ResourceNotFoundError("Chưa có hồ sơ thực tập")
        if code not in SUBMITTABLE:
            raise InvalidInputError("Mốc này không do sinh viên nộp trực tiếp")
        if row["status"] not in _WORKING:
            raise StateConflictError("Chưa thể nộp mốc ở trạng thái hồ sơ hiện tại")
        milestone = self._cases.milestone_by_code(row["id"], code)
        if milestone is None:
            raise ResourceNotFoundError("Không tìm thấy mốc")
        if code in EVIDENCE_REQUIRED_CODES and self._cases.count_active_evidence(milestone["id"]) == 0:
            raise InvalidInputError("Cần tải ít nhất một minh chứng trước khi nộp mốc")
        actor = actor_of(student)
        transition = MILESTONE.transition(milestone["status"], "submitted", actor, Subject(row["user_id"], row["lecturer_id"]))
        self._cases.submit_milestone(milestone["id"], milestone["status"], MILESTONE.audit(transition, actor, milestone["id"]))
        if row["lecturer_id"]:
            self._notifications.notify(
                row["lecturer_id"], f"{milestone['name']} chờ chấp nhận", f"{student.full_name} đã nộp mốc.", kind="milestone_submitted",
                link=f"/lecturer/internships/{row['id']}", email=True,
            )

    def upload_evidence(self, student: User, code: str, filename: str, data: bytes, title: str = "") -> int:
        row = self._cases.student_internship(student.id)
        if row is None or row["status"] not in _WORKING:
            raise StateConflictError("Chỉ tải minh chứng khi đang thực tập")
        milestone = self._cases.milestone_by_code(row["id"], code)
        if milestone is None:
            raise ResourceNotFoundError("Không tìm thấy mốc")
        if milestone["status"] in ("submitted", "accepted"):
            raise StateConflictError("Mốc đã nộp hoặc đã được chấp nhận, không thêm minh chứng")
        stored = store_upload(self._storage, f"evidence/{row['id']}", filename, data, EVIDENCE_TYPES, self._max_bytes)
        return self._cases.add_evidence(
            milestone["id"], title.strip() or stored.filename, stored.filename, stored.mime, stored.size, stored.sha256, stored.key, student.id,
            AuditEntry(actor_kind=ActorKind.HUMAN, actor_id=student.id, actor_role=student.role.value, entity="evidence", action="upload",
                       after={"milestone": code, "sha256": stored.sha256, "size": stored.size}, reason="Tải minh chứng"),
        )

    def evidence_bytes(self, viewer: User, evidence_id: int) -> tuple[bytes, str, str]:
        ev = self._cases.get_evidence(evidence_id)
        if ev is None or not ev["storage_key"]:
            raise ResourceNotFoundError("Không tìm thấy tệp minh chứng")
        require_view_internship(viewer, ev["owner_id"], ev["lecturer_id"])
        return self._storage.get(ev["storage_key"]), ev["mime"], ev["filename"]

    def submit_journal(
        self,
        student: User,
        week_start: date,
        content: str,
        plan_items: list[dict] | None = None,
        blockers: str = "",
        ai_advice: str = "",
    ) -> int:
        row = self._cases.student_internship(student.id)
        if row is None or row["status"] != "in_progress":
            raise StateConflictError("Chỉ nộp nhật ký khi đang thực tập")
        start, end, today = row["start_date"], row["end_date"], self._clock()
        if start is None or week_start < start or (end is not None and week_start > end) or week_start > today:
            raise InvalidInputError("Tuần nhật ký phải nằm trong thời gian thực tập và không ở tương lai")
        if len(content.strip()) < 20:
            raise InvalidInputError("Nội dung nhật ký cần ít nhất 20 ký tự")
        first = start + timedelta(days=7 * ((week_start - start).days // 7))
        return self._cases.add_journal(
            row["id"], first, content.strip(),
            AuditEntry(actor_kind=ActorKind.HUMAN, actor_id=student.id, actor_role=student.role.value, entity="journal", action="submit",
                       after={"week_start": first.isoformat()}, reason="Nộp nhật ký tuần"),
            plan_items=normalize_plan_items(plan_items),
            blockers=blockers.strip()[:2000],
            ai_advice=ai_advice.strip()[:3000],
        )

    def update_journal_items(self, student: User, journal_id: int, plan_items: list[dict]) -> None:
        """Sinh viên tích/bỏ tích việc trong nhật ký của mình (kể cả sau khi nộp); nội dung đã nộp không đổi."""
        j = self._cases.get_journal(journal_id)
        if j is None:
            raise ResourceNotFoundError("Không tìm thấy nhật ký")
        if j["owner_id"] != student.id:
            raise ScopeDeniedError("Chỉ sinh viên sở hữu nhật ký được cập nhật danh sách việc")
        self._cases.set_journal_items(
            journal_id, normalize_plan_items(plan_items),
            AuditEntry(actor_kind=ActorKind.HUMAN, actor_id=student.id, actor_role=student.role.value, entity="journal", action="update_items",
                       reason="Cập nhật việc hoàn thành"),
        )

    # ---- Giảng viên ----
    def review(self, lecturer: User, milestone_id: int, accept: bool, reason: str = "") -> None:
        m = self._cases.get_milestone(milestone_id)
        if m is None:
            raise ResourceNotFoundError("Không tìm thấy mốc")
        target = "accepted" if accept else "rejected"
        actor = actor_of(lecturer)
        transition = MILESTONE.transition(m["status"], target, actor, Subject(m["owner_id"], m["lecturer_id"]), reason)
        self._cases.review_milestone(milestone_id, accept, lecturer.id, reason.strip(), MILESTONE.audit(transition, actor, milestone_id))
        self._notifications.notify(
            m["owner_id"], f"{m['name']}: " + ("đã được chấp nhận" if accept else "bị trả lại"), reason.strip(),
            kind=f"milestone_{target}", link="/student/milestones", email=not accept,
        )

    def comment_journal(self, lecturer: User, journal_id: int, comment: str) -> None:
        j = self._cases.get_journal(journal_id)
        if j is None:
            raise ResourceNotFoundError("Không tìm thấy nhật ký")
        if lecturer.id != j["lecturer_id"]:
            raise ScopeDeniedError("Chỉ giảng viên phụ trách được nhận xét nhật ký")
        if not comment.strip():
            raise InvalidInputError("Nhận xét không được rỗng")
        self._cases.comment_journal(
            journal_id, comment.strip(),
            AuditEntry(actor_kind=ActorKind.HUMAN, actor_id=lecturer.id, actor_role=lecturer.role.value, entity="journal", action="comment",
                       reason="Nhận xét nhật ký"),
        )
        self._notifications.notify(j["owner_id"], "Giảng viên đã nhận xét nhật ký", comment.strip()[:200], kind="journal_comment", link="/student/journal")

    # ---- Hệ thống ----
    def mark_overdue(self) -> int:
        return len(self._cases.mark_overdue(self._clock()))
