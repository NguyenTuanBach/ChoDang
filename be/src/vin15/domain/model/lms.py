"""Dữ liệu trao đổi với LMS (mini hoặc thật). Khóa sinh viên là mã sinh viên, không phải id nội bộ."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PrerequisiteStatus:
    met: bool
    #: Học phần tiên quyết chưa đạt (mô tả để hiển thị).
    missing: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GradeRecord:
    course_code: str
    course_name: str
    credits: int
    score: float
    term: str


@dataclass(frozen=True)
class CreditEntry:
    course_code: str
    course_name: str
    credits: int
    source: str
    posted_at: datetime


@dataclass(frozen=True)
class StudentRecord:
    student_code: str
    full_name: str
    grades: list[GradeRecord] = field(default_factory=list)
    credits: list[CreditEntry] = field(default_factory=list)

    @property
    def total_credits(self) -> int:
        return sum(entry.credits for entry in self.credits)
