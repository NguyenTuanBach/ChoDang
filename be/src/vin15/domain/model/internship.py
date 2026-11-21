"""Dữ liệu thực tập của một sinh viên, đã rút gọn đúng phần trợ lý được xem (không email/SĐT/MST/mã sinh viên)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

#: Trạng thái hồ sơ coi là đã có đề cương được duyệt (docs/nghiep-vu-thuc-tap.md mục 6.1).
OUTLINE_APPROVED_STATUSES = frozenset({"in_progress", "pending_credit", "credit_review", "completed"})


@dataclass(frozen=True)
class InternshipRecord:
    id: int
    cohort: str
    status: str
    start_date: date | None
    end_date: date | None
    mode: str
    lecturer_name: str | None


@dataclass(frozen=True)
class MilestoneRecord:
    code: str
    name: str
    due_date: date
    status: str


@dataclass(frozen=True)
class EvidenceRecord:
    milestone_code: str
    status: str


@dataclass(frozen=True)
class RequestRecord:
    kind: str
    status: str
    created_at: datetime


# ---- Kết quả cho tool ----
NO_RECORD = "no_internship_record"


@dataclass(frozen=True)
class MilestoneView:
    code: str
    name: str
    due_date: date
    status: str
    #: Số ngày còn lại tới hạn (âm nếu đã quá hạn).
    days_left: int
    next_action: str


@dataclass(frozen=True)
class JournalProgress:
    submitted: int = 0
    expected: int = 0
    missing_weeks: list[date] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceProgress:
    submitted: int = 0
    required: int = 0


@dataclass(frozen=True)
class CreditItem:
    code: str
    label: str
    met: bool
    value: str
    threshold: str
