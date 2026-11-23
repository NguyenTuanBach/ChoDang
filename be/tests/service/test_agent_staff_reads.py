"""``AgentStaffReads``: phạm vi do người dùng của agent-token quyết (qua ReportService/MonitoringService), trường trả về tối thiểu."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from tests.fakes import ADMIN, LECTURER, STUDENT_A, FakeUsers
from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.model.agent_tool import VIA_AGENT_TOKEN, AgentToolSubject
from vin15.service.agent.agent_staff_reads import MAX_ITEMS, AgentStaffReads


class FakeReports:
    def __init__(self) -> None:
        self.seen_users: list = []

    def queue(self, user):
        self.seen_users.append(user)
        since = datetime(2026, 11, 18, 8, 0, tzinfo=UTC)
        row = {"kind": "request", "internship_id": 7, "student_name": "An", "title": "Yêu cầu gia hạn mốc", "since": since, "due_date": date(2026, 11, 25), "severity": None, "priority": 30, "email": "x@y.z"}
        return [row] * (MAX_ITEMS + 5)

    def dashboard(self, user, cohort=None):
        self.seen_users.append(user)
        return {
            "internships_by_status": [{"status": "in_progress", "n": 9}], "milestones_by_status": [{"status": "pending", "n": 4}],
            "late_internships": 3, "active_internships": 9,
            "flags": [{"severity": "warning", "status": "open", "n": 2}, {"severity": "warning", "status": "resolved", "n": 5}, {"severity": "info", "status": "acknowledged", "n": 1}],
            "credit_outcomes": [], "decision_times": [], "sync_jobs": [],
        }  # fmt: skip

    def list_internships(self, user, *, status=None, cohort=None, **_):
        self.seen_users.append(user)
        base = {"cohort": "K2026", "status": "in_progress", "student_name": "An", "student_email": "an@x.test", "company_name": "Cty", "start_date": None, "end_date": None, "submitted_milestones": 0, "open_flags": 0}
        return [{**base, "id": 1, "overdue_milestones": 2}, {**base, "id": 2, "overdue_milestones": 0}]


class FakeMonitoring:
    def flags(self, user, status=None, internship_id=None):
        return [{"id": 3, "internship_id": 7, "student_name": "An", "kind": "overdue_milestone", "severity": "warning", "status": "open", "reason": "Mốc M3 quá hạn", "created_at": datetime(2026, 11, 21, 1, 0), "evidence": {"secret": 1}}]


def subject(user) -> AgentToolSubject:
    return AgentToolSubject(user.id, user.role.value, VIA_AGENT_TOKEN)


@pytest.fixture
def reads():
    reports = FakeReports()
    return AgentStaffReads(FakeUsers(ADMIN, LECTURER, STUDENT_A), reports, FakeMonitoring()), reports


def test_scope_comes_from_the_subject_user(reads):
    service, reports = reads
    service.queue(subject(LECTURER))
    service.dashboard(subject(ADMIN), None)
    service.internships(subject(LECTURER), None, False, None)
    assert [u.id for u in reports.seen_users] == [LECTURER.id, ADMIN.id, LECTURER.id]


def test_queue_is_capped_and_has_no_extra_fields(reads):
    service, _ = reads
    result = service.queue(subject(LECTURER))
    assert result.total == MAX_ITEMS + 5 and len(result.items) == MAX_ITEMS
    assert result.items[0].since == date(2026, 11, 18) and not hasattr(result.items[0], "email")


def test_dashboard_counts_only_open_flags_and_labels_scope(reads):
    service, _ = reads
    admin, lecturer = service.dashboard(subject(ADMIN), None), service.dashboard(subject(LECTURER), None)
    assert admin.open_flags_by_severity == {"warning": 2, "info": 1} and admin.late_internships == 3 and admin.internships_by_status == {"in_progress": 9}
    assert admin.scope == "toàn hệ thống" and lecturer.scope != admin.scope


def test_internships_overdue_filter_and_no_contact_fields(reads):
    service, _ = reads
    result = service.internships(subject(LECTURER), None, True, None)
    assert result.total == 1 and result.items[0].id == 1 and not hasattr(result.items[0], "student_email")


@pytest.mark.parametrize(
    ("query", "ids"),
    [
        ("Nguyễn Văn An", [1]), ("nguyen van an", [1]), ("nguyen an", [1]), ("  TRẦN  ", [2]), ("đức", [3]), ("sv2026002", [2]),
        ("an", [1]),  # đầu từ: không khớp "Trần" (tran), "Toàn" (toan)
        ("Lê", []),
    ],  # fmt: skip
)
def test_internships_filter_by_student_name_or_code(reads, query, ids):
    service, reports = reads
    base = {"cohort": "K2026", "status": "in_progress", "company_name": "Cty", "start_date": None, "end_date": None, "overdue_milestones": 0, "submitted_milestones": 0, "open_flags": 0}
    rows = [
        {**base, "id": 1, "student_name": "Nguyễn Văn An", "student_code": "SV2026001"},
        {**base, "id": 2, "student_name": "Trần Thị Bình", "student_code": "SV2026002"},
        {**base, "id": 3, "student_name": "Phạm Đức Toàn", "student_code": None},
    ]
    reports.list_internships = lambda user, **_: rows
    result = service.internships(subject(LECTURER), None, False, None, query)
    assert [i.id for i in result.items] == ids and result.total == len(ids)


def test_flags_drop_internal_fields(reads):
    service, _ = reads
    item = service.flags(subject(LECTURER), "open").items[0]
    assert item.reason == "Mốc M3 quá hạn" and not hasattr(item, "evidence") and item.created_at == date(2026, 11, 21)


def test_unknown_user_is_rejected(reads):
    service, _ = reads
    with pytest.raises(AuthenticationRequiredError):
        service.queue(AgentToolSubject(9999, "lecturer", VIA_AGENT_TOKEN))
