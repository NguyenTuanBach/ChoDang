"""Đọc dữ liệu cho tool agent của **giảng viên/quản trị viên** (hàng chờ, cờ rủi ro, dashboard, danh sách hồ sơ).

Chỉ-đọc, tái dùng ``ReportService``/``MonitoringService`` nên phạm vi dữ liệu do BE quyết (giảng viên: sinh viên mình phụ trách,
quản trị viên: toàn bộ) từ người dùng của agent-token; agent/LLM không truyền được phạm vi. Chỉ trả trường tối thiểu: không email/SĐT/MST.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.model.agent_tool import AgentToolSubject
from vin15.domain.model.user import User
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.service.dashboard.report_service import ReportService
from vin15.service.monitoring.monitoring_service import MonitoringService
from vin15.service.policy.policy_search_service import normalize

MAX_ITEMS = 30


def _matches_student(row: dict[str, Any], query: str) -> bool:
    """Khớp tên theo đầu từ, không dấu, không phân biệt hoa thường: mỗi từ của chuỗi tìm là phần đầu của một từ trong tên
    ("an" khớp "Nguyễn Văn An" nhưng không khớp "Trần", "Toàn"; "nguyen an" khớp "Nguyễn Văn An"). Hoặc mã sinh viên chứa chuỗi tìm."""
    needle = normalize(query).split()
    if not needle:
        return False
    words = normalize(str(row.get("student_name") or "")).split()
    code = normalize(str(row.get("student_code") or ""))
    return all(any(w.startswith(n) for w in words) for n in needle) or (len(needle) == 1 and bool(code) and needle[0] in code)


_OPEN_FLAG_STATUSES = ("open", "acknowledged")


def _day(value: date | datetime | None) -> date | None:
    return value.date() if isinstance(value, datetime) else value


@dataclass(frozen=True)
class QueueItem:
    kind: str
    internship_id: int
    student_name: str
    title: str
    since: date | None
    due_date: date | None
    severity: str | None
    priority: int


@dataclass(frozen=True)
class QueueResult:
    total: int
    items: list[QueueItem]


@dataclass(frozen=True)
class FlagItem:
    id: int
    internship_id: int
    student_name: str
    kind: str
    severity: str
    status: str
    reason: str
    created_at: date | None


@dataclass(frozen=True)
class FlagsResult:
    total: int
    items: list[FlagItem]


@dataclass(frozen=True)
class DashboardResult:
    scope: str
    active_internships: int
    late_internships: int
    internships_by_status: dict[str, int]
    milestones_by_status: dict[str, int]
    open_flags_by_severity: dict[str, int]
    credit_outcomes: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class InternshipItem:
    id: int
    cohort: str
    status: str
    student_name: str
    company_name: str
    start_date: date | None
    end_date: date | None
    overdue_milestones: int
    submitted_milestones: int
    open_flags: int


@dataclass(frozen=True)
class InternshipsResult:
    total: int
    items: list[InternshipItem]


class AgentStaffReads:
    def __init__(self, users: UserRepository, reports: ReportService, monitoring: MonitoringService):
        self._users = users
        self._reports = reports
        self._monitoring = monitoring

    def _user(self, subject: AgentToolSubject) -> User:
        user = self._users.find_by_id(subject.user_id)
        if user is None:
            raise AuthenticationRequiredError("Người dùng của agent-token không còn tồn tại")
        return user

    def queue(self, subject: AgentToolSubject) -> QueueResult:
        rows: list[dict[str, Any]] = self._reports.queue(self._user(subject))
        items = [
            QueueItem(r["kind"], r["internship_id"], r["student_name"], r["title"], _day(r.get("since")), _day(r.get("due_date")), r.get("severity"), r["priority"])
            for r in rows[:MAX_ITEMS]
        ]
        return QueueResult(len(rows), items)

    def flags(self, subject: AgentToolSubject, status: str | None) -> FlagsResult:
        rows = self._monitoring.flags(self._user(subject), status or None)
        items = [
            FlagItem(r["id"], r["internship_id"], r["student_name"], r["kind"], r["severity"], r["status"], r["reason"], _day(r.get("created_at")))
            for r in rows[:MAX_ITEMS]
        ]
        return FlagsResult(len(rows), items)

    def dashboard(self, subject: AgentToolSubject, cohort: str | None) -> DashboardResult:
        user = self._user(subject)
        data = self._reports.dashboard(user, cohort or None)
        open_flags: dict[str, int] = {}
        for f in data["flags"]:
            if f["status"] in _OPEN_FLAG_STATUSES:
                open_flags[f["severity"]] = open_flags.get(f["severity"], 0) + f["n"]
        return DashboardResult(
            scope="toàn hệ thống" if user.role.value == "admin" else "sinh viên bạn phụ trách",
            active_internships=data["active_internships"],
            late_internships=data["late_internships"],
            internships_by_status={r["status"]: r["n"] for r in data["internships_by_status"]},
            milestones_by_status={r["status"]: r["n"] for r in data["milestones_by_status"]},
            open_flags_by_severity=open_flags,
            credit_outcomes={r["status"]: r["n"] for r in data["credit_outcomes"]},
        )

    def internships(
        self, subject: AgentToolSubject, status: str | None, overdue_only: bool, cohort: str | None, student: str | None = None
    ) -> InternshipsResult:
        rows = self._reports.list_internships(self._user(subject), status=status or None, cohort=cohort or None)
        if overdue_only:
            rows = [r for r in rows if r["overdue_milestones"] > 0]
        if student and student.strip():
            rows = [r for r in rows if _matches_student(r, student)]
        items = [
            InternshipItem(
                r["id"], r["cohort"], r["status"], r["student_name"], r["company_name"], r.get("start_date"), r.get("end_date"),
                r["overdue_milestones"], r["submitted_milestones"], r["open_flags"],
            )
            for r in rows[:MAX_ITEMS]
        ]  # fmt: skip
        return InternshipsResult(len(rows), items)
