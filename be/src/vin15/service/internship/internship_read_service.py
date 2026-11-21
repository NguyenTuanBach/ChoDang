"""Đọc dữ liệu thực tập của **một sinh viên** cho tool ``get_my_*``: hồ sơ, mốc, tiến độ, yêu cầu.

Mọi hàm nhận ``user_id`` do BE quyết (agent-token hoặc người dùng mặc định ở dev), không bao giờ từ agent/LLM.
Chưa có hồ sơ thì trả ``available=False, reason=no_internship_record`` thay vì đoán.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vin15.domain.clock import Clock
from vin15.domain.model.internship import (
    NO_RECORD,
    EvidenceProgress,
    InternshipRecord,
    JournalProgress,
    MilestoneView,
    RequestRecord,
)
from vin15.infrastructure.persistence.internship_repository import InternshipRepository
from vin15.service.milestone.milestone_view import milestone_view
from vin15.service.progress.progress_calculator import evidence_progress, journal_progress


@dataclass(frozen=True)
class Availability:
    available: bool
    reason: str | None = None


@dataclass(frozen=True)
class InternshipResult(Availability):
    internship: InternshipRecord | None = None


@dataclass(frozen=True)
class MilestonesResult(Availability):
    milestones: list[MilestoneView] = field(default_factory=list)


@dataclass(frozen=True)
class ProgressResult(Availability):
    journal: JournalProgress = field(default_factory=JournalProgress)
    evidence: EvidenceProgress = field(default_factory=EvidenceProgress)


@dataclass(frozen=True)
class RequestsResult(Availability):
    requests: list[RequestRecord] = field(default_factory=list)


class InternshipReadService:
    def __init__(self, repository: InternshipRepository, clock: Clock):
        self._repo = repository
        self._clock = clock

    def internship(self, user_id: int) -> InternshipResult:
        record = self._repo.latest_internship(user_id)
        return InternshipResult(True, internship=record) if record else InternshipResult(False, NO_RECORD)

    def milestones(self, user_id: int) -> MilestonesResult:
        record = self._repo.latest_internship(user_id)
        if record is None:
            return MilestonesResult(False, NO_RECORD)
        today = self._clock()
        views = [milestone_view(m, today) for m in self._repo.milestones(record.id)]
        return MilestonesResult(True, milestones=sorted(views, key=lambda v: v.code))

    def progress(self, user_id: int) -> ProgressResult:
        record = self._repo.latest_internship(user_id)
        if record is None:
            return ProgressResult(False, NO_RECORD)
        journal = journal_progress(record.start_date, record.end_date, self._clock(), self._repo.journal_week_starts(record.id))
        evidence = evidence_progress(self._repo.milestones(record.id), self._repo.evidence(record.id))
        return ProgressResult(True, journal=journal, evidence=evidence)

    def requests(self, user_id: int) -> RequestsResult:
        record = self._repo.latest_internship(user_id)
        if record is None:
            return RequestsResult(False, NO_RECORD)
        return RequestsResult(True, requests=self._repo.requests(record.id))
