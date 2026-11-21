"""Danh sách hồ sơ có lọc + xuất CSV (A11), hàng chờ duyệt xếp theo ưu tiên (A12), chi tiết một hồ sơ, dashboard (D7, D8), xem audit.

Phạm vi: giảng viên chỉ thấy sinh viên mình phụ trách; quản trị viên thấy toàn bộ (X1).
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime

from vin15.domain.authorization import require_view_internship
from vin15.domain.clock import Clock
from vin15.domain.exception import ForbiddenRoleError, ResourceNotFoundError
from vin15.domain.model.user import Role, User
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.infrastructure.persistence.monitoring_repository import MonitoringRepository
from vin15.infrastructure.persistence.report_repository import ReportRepository
from vin15.infrastructure.persistence.request_repository import RequestRepository
from vin15.service.credit.credit_decision_service import CreditDecisionService
from vin15.service.milestone.milestone_service import MilestoneService

_SEVERITY_WEIGHT = {"critical": 40, "warning": 20, "info": 5}
_KIND_WEIGHT = {"credit_approval": 25, "credit_assessment": 20, "internship_submitted": 15, "outline_submitted": 12, "milestone_submitted": 10, "request": 18, "risk_flag": 0}


def _staff_scope(user: User) -> int | None:
    """``None`` = toàn bộ (QTV); ngược lại id giảng viên."""
    if user.role == Role.ADMIN:
        return None
    if user.role == Role.LECTURER:
        return user.id
    raise ForbiddenRoleError("Chỉ giảng viên hoặc quản trị viên dùng chức năng này")


class ReportService:
    def __init__(
        self,
        reports: ReportRepository,
        cases: CaseRepository,
        requests: RequestRepository,
        monitoring: MonitoringRepository,
        milestones: MilestoneService,
        credit: CreditDecisionService,
        clock: Clock,
    ):
        self._reports = reports
        self._cases = cases
        self._requests = requests
        self._monitoring = monitoring
        self._milestones = milestones
        self._credit = credit
        self._clock = clock

    # ---- Danh sách (A11) ----
    def list_internships(
        self,
        user: User,
        *,
        status: str | None = None,
        milestone_code: str | None = None,
        milestone_status: str | None = None,
        flagged: bool = False,
        cohort: str | None = None,
    ) -> list[dict]:
        return self._reports.list_internships(
            self._clock(),
            lecturer_id=_staff_scope(user),
            status=status or None,
            milestone_code=milestone_code or None,
            milestone_status=milestone_status or None,
            flagged=flagged,
            cohort=cohort or None,
        )

    def export_csv(self, user: User, **filters) -> str:
        rows = self.list_internships(user, **filters)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["Mã hồ sơ", "Khóa", "Sinh viên", "Mã SV", "Email", "Giảng viên", "Doanh nghiệp", "Trạng thái", "Bắt đầu", "Kết thúc", "Mốc quá hạn", "Mốc chờ duyệt", "Cờ đang mở"])
        for r in rows:
            writer.writerow(
                [r["id"], r["cohort"], r["student_name"], r["student_code"] or "", r["student_email"], r["lecturer_name"] or "", r["company_name"], r["status"],
                 r["start_date"] or "", r["end_date"] or "", r["overdue_milestones"], r["submitted_milestones"], r["open_flags"]]
            )
        return "﻿" + out.getvalue()  # BOM để Excel đọc đúng tiếng Việt

    # ---- Hàng chờ (A12) ----
    def queue(self, user: User) -> list[dict]:
        role = user.role.value
        scope = _staff_scope(user)
        items = self._reports.queue_items(role, user.id)
        for r in self._requests.pending_requests("admin" if scope is None else "lecturer", scope):
            items.append(
                {"kind": "request", "internship_id": r["internship_id"], "ref_id": r["id"], "student_name": r["student_name"],
                 "title": "Yêu cầu gia hạn mốc" if r["kind"] == "milestone_extension" else f"Yêu cầu ngoại lệ: {r['exception_type_name']}",
                 "since": r["created_at"], "due_date": r["new_due_date"], "severity": None}
            )
        now = datetime.now().astimezone()
        today = self._clock()
        for item in items:
            item["priority"] = self._priority(item, now, today)
        return sorted(items, key=lambda i: -i["priority"])

    @staticmethod
    def _priority(item: dict, now: datetime, today: date) -> int:
        score = _KIND_WEIGHT.get(item["kind"], 5) + _SEVERITY_WEIGHT.get(item.get("severity") or "", 0)
        since = item.get("since")
        if since is not None:
            score += min(30, max(0, (now - since).days) * 2)
        due = item.get("due_date")
        if due is not None:
            days = (due - today).days
            score += 25 if days < 0 else 15 if days <= 3 else 0
        return score

    # ---- Chi tiết một hồ sơ ----
    def detail(self, viewer: User, internship_id: int) -> dict:
        row = self._cases.get_internship(internship_id)
        if row is None:
            raise ResourceNotFoundError("Không tìm thấy hồ sơ")
        require_view_internship(viewer, row["user_id"], row["lecturer_id"])
        is_staff = viewer.role != Role.STUDENT
        detail = {
            "internship": row,
            "documents": self._cases.documents(internship_id),
            "milestones": self._milestones.views(internship_id),
            "outlines": self._cases.outlines(internship_id),
            "journals": self._cases.journals(internship_id),
            "evidence": self._cases.evidence_for_internship(internship_id),
            "requests": [{**r, "attachments": self._requests.attachments(r["id"])} for r in self._requests.requests_for_internship(internship_id)],
            "revisions": self._cases.revisions(internship_id) if is_staff else [],
            "flags": self._monitoring.flags(lecturer_id=None, internship_id=internship_id) if is_staff else [],
            "suggestions": self._monitoring.suggestions(internship_id) if is_staff else [],
        }
        if row["status"] in ("pending_credit", "credit_review", "completed", "closed_no_credit") or (is_staff and row["status"] == "in_progress"):
            detail["credit"] = self._credit.view(viewer, internship_id)
        return detail

    # ---- Dashboard (D7, D8) ----
    def dashboard(self, user: User, cohort: str | None = None) -> dict:
        return self._reports.dashboard(self._clock(), _staff_scope(user), cohort or None)

    def dashboard_csv(self, user: User, cohort: str | None = None) -> str:
        data = self.dashboard(user, cohort)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["Nhóm", "Chỉ tiêu", "Giá trị"])
        for r in data["internships_by_status"]:
            writer.writerow(["Hồ sơ theo trạng thái", r["status"], r["n"]])
        for r in data["milestones_by_status"]:
            writer.writerow(["Mốc theo trạng thái", r["status"], r["n"]])
        active, late = data["active_internships"], data["late_internships"]
        writer.writerow(["Trễ hạn", "Hồ sơ đang thực tập có mốc quá hạn", late])
        writer.writerow(["Trễ hạn", "Tỷ lệ trễ hạn", f"{(late / active):.0%}" if active else "0%"])
        for r in data["flags"]:
            writer.writerow(["Cờ rủi ro", f"{r['severity']} / {r['status']}", r["n"]])
        for r in data["decision_times"]:
            writer.writerow(["Thời gian ra quyết định (trung vị, ngày)", r["kind"], "" if r["median_days"] is None else f"{r['median_days']:.1f}"])
        for r in data["credit_outcomes"]:
            writer.writerow(["Công nhận tín chỉ", r["status"], r["n"]])
        return "﻿" + out.getvalue()

    def audit(self, user: User, limit: int = 200, entity: str | None = None, actor_id: int | None = None) -> list[dict]:
        if user.role != Role.ADMIN:
            raise ForbiddenRoleError("Chỉ quản trị viên xem nhật ký kiểm toán")
        return self._reports.audit_events(min(max(limit, 1), 500), entity or None, actor_id)
