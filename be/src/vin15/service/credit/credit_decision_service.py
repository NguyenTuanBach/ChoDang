"""Kết thúc thực tập và công nhận tín chỉ (D4): SV nộp đủ → GV thẩm định (bảng T1-T6) → QTV phê duyệt cuối → hàng đợi ghi LMS.

Hệ thống chỉ hiển thị đạt/chưa đạt từng điều kiện; kết luận do người quyết. Ghi LMS chỉ được tạo trong transaction phê duyệt của QTV.
"""

from __future__ import annotations

from dataclasses import asdict

from vin15.domain.authorization import actor_of, require_view_internship
from vin15.domain.exception import InvalidInputError, ResourceNotFoundError, StateConflictError
from vin15.domain.model.user import User
from vin15.domain.statemachine import CREDIT_REQUEST, INTERNSHIP, Subject
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.infrastructure.persistence.request_repository import RequestRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.service.credit.credit_checklist_service import CreditChecklistService
from vin15.service.notification.notification_service import NotificationService


class CreditDecisionService:
    def __init__(
        self,
        cases: CaseRepository,
        requests: RequestRepository,
        users: UserRepository,
        checklist: CreditChecklistService,
        notifications: NotificationService,
        course_code: str,
        credits: int,
    ):
        self._cases = cases
        self._requests = requests
        self._users = users
        self._checklist = checklist
        self._notifications = notifications
        self._course = course_code
        self._credits = credits

    def view(self, viewer: User, internship_id: int) -> dict:
        row = self._cases.get_internship(internship_id)
        if row is None:
            raise ResourceNotFoundError("Không tìm thấy hồ sơ")
        require_view_internship(viewer, row["user_id"], row["lecturer_id"])
        checklist = self._checklist.checklist_for_internship(internship_id)
        return {
            "items": [asdict(i) for i in checklist.items],
            "all_met": checklist.all_met,
            "assessment": self._requests.latest_assessment(internship_id),
        }

    # ---- Sinh viên ----
    def submit_for_credit(self, student: User) -> None:
        row = self._cases.student_internship(student.id)
        if row is None or row["status"] != "in_progress":
            raise StateConflictError("Chỉ nộp kết thúc thực tập khi đang thực tập")
        by_code = {m["code"]: m for m in self._cases.milestones(row["id"])}
        for code, label in (("M4", "báo cáo cuối kỳ"), ("M5", "phiếu đánh giá của doanh nghiệp")):
            if code not in by_code or by_code[code]["status"] not in ("submitted", "accepted"):
                raise InvalidInputError(f"Cần nộp {label} (mốc {code}) trước khi kết thúc thực tập")
        actor = actor_of(student)
        t = INTERNSHIP.transition("in_progress", "pending_credit", actor, Subject(row["user_id"], row["lecturer_id"]))
        self._cases.change_internship_status(row["id"], "in_progress", "pending_credit", INTERNSHIP.audit(t, actor, row["id"]))
        if row["lecturer_id"]:
            self._notifications.notify(
                row["lecturer_id"], "Sinh viên nộp kết thúc thực tập", f"{student.full_name} chờ thẩm định công nhận tín chỉ.",
                kind="credit_assessment", link=f"/lecturer/internships/{row['id']}", email=True,
            )

    # ---- Giảng viên thẩm định ----
    def assess(self, lecturer: User, internship_id: int, passed: bool, note: str = "") -> None:
        row = self._cases.get_internship(internship_id)
        if row is None:
            raise ResourceNotFoundError("Không tìm thấy hồ sơ")
        actor = actor_of(lecturer)
        subject = Subject(row["user_id"], row["lecturer_id"])
        checklist = self._checklist.checklist_for_internship(internship_id)
        if passed and not checklist.all_met:
            unmet = ", ".join(i.code for i in checklist.items if not i.met)
            raise InvalidInputError(f"Chưa đủ điều kiện để thẩm định đạt (chưa đạt: {unmet}). Hãy xử lý hoặc trả hồ sơ lại cho sinh viên")
        target_status = "credit_review" if passed else "in_progress"
        it = INTERNSHIP.transition("pending_credit", target_status, actor, subject, note)
        at = CREDIT_REQUEST.transition("pending", "lecturer_passed" if passed else "lecturer_returned", actor, subject, note)
        self._requests.record_lecturer_assessment(
            internship_id, passed, lecturer.id, note.strip(), [asdict(i) for i in checklist.items],
            CREDIT_REQUEST.audit(at, actor, internship_id), INTERNSHIP.audit(it, actor, internship_id),
        )
        if passed:
            self._notifications.notify_many(
                self._users.admin_ids(), "Hồ sơ chờ phê duyệt công nhận tín chỉ", row["student_name"], kind="credit_approval", link="/admin/credit", email=True
            )
        else:
            self._notifications.notify(row["user_id"], "Giảng viên trả hồ sơ kết thúc thực tập", note.strip(), kind="credit_returned", link="/student/final", email=True)

    # ---- QTV phê duyệt cuối ----
    def decide(self, admin: User, internship_id: int, approve: bool, reason: str = "") -> None:
        row = self._cases.get_internship(internship_id)
        if row is None:
            raise ResourceNotFoundError("Không tìm thấy hồ sơ")
        actor = actor_of(admin)
        subject = Subject(row["user_id"], row["lecturer_id"])
        it = INTERNSHIP.transition("credit_review", "completed" if approve else "closed_no_credit", actor, subject, reason)
        at = CREDIT_REQUEST.transition("lecturer_passed", "approved" if approve else "denied", actor, subject, reason)
        sync = None
        if approve:
            if not row["student_code"]:
                raise InvalidInputError("Sinh viên chưa có mã sinh viên (cần để ghi sang LMS): hãy cập nhật mã sinh viên trước khi phê duyệt")
            sync = (row["student_code"], self._course, self._credits)
        self._requests.record_admin_decision(
            internship_id, approve, admin.id, reason.strip(), CREDIT_REQUEST.audit(at, actor, internship_id), INTERNSHIP.audit(it, actor, internship_id), sync=sync
        )
        self._notifications.notify(
            row["user_id"], "Kết quả công nhận tín chỉ thực tập: " + ("được công nhận" if approve else "không được công nhận"), reason.strip(),
            kind="credit_decided", link="/student/final", email=True,
        )
        if row["lecturer_id"]:
            self._notifications.notify(row["lecturer_id"], f"QTV đã quyết định công nhận tín chỉ: {row['student_name']}", reason.strip(), kind="credit_decided")
