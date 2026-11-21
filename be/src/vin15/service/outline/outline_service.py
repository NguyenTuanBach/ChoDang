"""Đề cương (A7): SV nộp (có phiên bản, đối chiếu chuẩn đầu ra), GV duyệt / yêu cầu sửa / từ chối (HITL).

Duyệt đề cương kéo theo: hồ sơ ``confirmed`` → ``in_progress`` và mốc M2 được chấp nhận, cùng một transaction. Từ chối đề cương kết thúc đợt thực tập.
"""

from __future__ import annotations

from vin15.domain.authorization import actor_of, require_view_internship
from vin15.domain.exception import InvalidInputError, ResourceNotFoundError, StateConflictError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import User
from vin15.domain.statemachine import INTERNSHIP, MILESTONE, OUTLINE, Subject
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.infrastructure.persistence.config_repository import ConfigRepository
from vin15.service.notification.notification_service import NotificationService


class OutlineService:
    def __init__(self, cases: CaseRepository, config: ConfigRepository, notifications: NotificationService):
        self._cases = cases
        self._config = config
        self._notifications = notifications

    def outcomes_for(self, cohort: str) -> list[dict]:
        return self._config.learning_outcomes(cohort)

    def list_for(self, viewer: User, internship_id: int) -> list[dict]:
        row = self._cases.get_internship(internship_id)
        if row is None:
            raise ResourceNotFoundError("Không tìm thấy hồ sơ")
        require_view_internship(viewer, row["user_id"], row["lecturer_id"])
        return self._cases.outlines(internship_id)

    def submit(self, student: User, content: str, outcome_codes: list[str]) -> int:
        row = self._cases.student_internship(student.id)
        if row is None or row["status"] != "confirmed":
            raise StateConflictError("Chỉ nộp được đề cương khi hồ sơ đã được giảng viên xác nhận")
        text = content.strip()
        if len(text) < 50:
            raise InvalidInputError("Nội dung đề cương cần ít nhất 50 ký tự")
        known = {o["code"] for o in self._config.learning_outcomes(row["cohort"])}
        unknown = [c for c in outcome_codes if c not in known]
        if unknown:
            raise InvalidInputError("Chuẩn đầu ra không có trong khóa: " + ", ".join(unknown))
        outline_id = self._cases.add_outline(
            row["id"],
            text,
            list(dict.fromkeys(outcome_codes)),
            AuditEntry(
                actor_kind=ActorKind.HUMAN,
                actor_id=student.id,
                actor_role=student.role.value,
                entity="outline",
                action="submit",
                after={"status": "submitted", "internship_id": row["id"]},
                reason="Sinh viên nộp đề cương",
            ),
        )
        if row["lecturer_id"]:
            self._notifications.notify(
                row["lecturer_id"],
                "Đề cương chờ duyệt",
                f"{student.full_name} đã nộp đề cương thực tập.",
                kind="outline_submitted",
                link=f"/lecturer/internships/{row['id']}",
                email=True,
            )
        return outline_id

    def decide(self, lecturer: User, outline_id: int, action: str, reason: str = "") -> None:
        outline = self._cases.get_outline(outline_id)
        if outline is None:
            raise ResourceNotFoundError("Không tìm thấy đề cương")
        target = {"approve": "approved", "request_revision": "revision_requested", "reject": "rejected"}.get(action)
        if target is None:
            raise InvalidInputError("Quyết định không hợp lệ")
        actor = actor_of(lecturer)
        subject = Subject(outline["owner_id"], outline["lecturer_id"])
        transition = OUTLINE.transition(outline["status"], target, actor, subject, reason)
        internship_change = None
        milestone_accept = None
        if target in ("approved", "rejected"):
            new_status = "in_progress" if target == "approved" else "rejected"
            t = INTERNSHIP.transition("confirmed", new_status, actor, subject, reason)
            internship_change = (outline["internship_id"], "confirmed", new_status, INTERNSHIP.audit(t, actor, outline["internship_id"]))
        if target == "approved":
            m2 = self._cases.milestone_by_code(outline["internship_id"], "M2")
            if m2 is not None and m2["status"] in ("pending", "overdue"):
                mt = MILESTONE.transition(m2["status"], "accepted", actor, subject)
                milestone_accept = (m2["id"], m2["status"], MILESTONE.audit(mt, actor, m2["id"]))
        self._cases.decide_outline(
            outline_id, target, lecturer.id, reason.strip(), OUTLINE.audit(transition, actor, outline_id),
            internship_change=internship_change, milestone_accept=milestone_accept,
        )
        titles = {"approved": "Đề cương đã được duyệt. Bạn có thể bắt đầu thực tập.", "revision_requested": "Giảng viên yêu cầu sửa đề cương.", "rejected": "Đề cương bị từ chối."}
        self._notifications.notify(outline["owner_id"], titles[target], reason.strip(), kind=f"outline_{target}", link="/student/outline", email=True)
