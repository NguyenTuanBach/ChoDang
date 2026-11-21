"""Bảng điều kiện công nhận quy đổi tín chỉ T1-T6 (docs/nghiep-vu-thuc-tap.md mục 9.2), do **BE tính** bằng code tất định.

Hệ thống chỉ hiển thị đạt/chưa đạt từng điều kiện kèm số liệu so ngưỡng; kết luận công nhận do giảng viên/quản trị quyết (HITL).
Ngưỡng lấy từ cấu hình (bản mẫu, khớp bộ quy chế mẫu); thay bằng quy chế thật khi có.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from vin15.domain.clock import Clock
from vin15.domain.model.internship import NO_RECORD, OUTLINE_APPROVED_STATUSES, CreditItem, InternshipRecord, MilestoneRecord
from vin15.infrastructure.persistence.internship_repository import InternshipRepository
from vin15.service.lms.lms_port import LmsPort
from vin15.service.progress.progress_calculator import journal_progress


@dataclass(frozen=True)
class CreditChecklist:
    available: bool
    reason: str | None = None
    items: list[CreditItem] = field(default_factory=list)

    @property
    def all_met(self) -> bool:
        return bool(self.items) and all(item.met for item in self.items)


class CreditChecklistService:
    def __init__(self, repository: InternshipRepository, lms: LmsPort, clock: Clock, min_weeks: int, min_journal_ratio: float):
        self._repo = repository
        self._lms = lms
        self._clock = clock
        self._min_weeks = min_weeks
        self._min_ratio = min_journal_ratio

    def checklist(self, user_id: int) -> CreditChecklist:
        record = self._repo.latest_internship(user_id)
        if record is None:
            return CreditChecklist(False, NO_RECORD)
        today = self._clock()
        milestones = self._repo.milestones(record.id)
        weeks = self._repo.journal_week_starts(record.id)
        items = [
            self._t1(record, today),
            self._t2(record, milestones),
            self._t3(milestones),
            self._t4(record, today, weeks),
            self._t5(milestones),
            self._t6(user_id),
        ]
        return CreditChecklist(True, items=items)

    def _t1(self, record: InternshipRecord, today: date) -> CreditItem:
        threshold = f"≥ {self._min_weeks} tuần"
        if record.start_date is None:
            return CreditItem("T1", "Thời lượng thực tế đạt mức tối thiểu", False, "chưa có ngày bắt đầu", threshold)
        last_day = min(record.end_date, today) if record.end_date else today
        days = max(0, (last_day - record.start_date).days + 1)
        weeks = days // 7
        return CreditItem("T1", "Thời lượng thực tế đạt mức tối thiểu", weeks >= self._min_weeks, f"{weeks} tuần", threshold)

    @staticmethod
    def _t2(record: InternshipRecord, milestones: list[MilestoneRecord]) -> CreditItem:
        approved = record.status in OUTLINE_APPROVED_STATUSES or any(m.code == "M2" and m.status == "accepted" for m in milestones)
        return CreditItem("T2", "Đề cương đã được duyệt", approved, "đã duyệt" if approved else "chưa duyệt", "đã duyệt")

    @staticmethod
    def _t3(milestones: list[MilestoneRecord]) -> CreditItem:
        accepted = sum(1 for m in milestones if m.status == "accepted")
        total = len(milestones)
        met = total > 0 and accepted == total
        return CreditItem(
            "T3",
            "Mọi mốc bắt buộc đã được chấp nhận",
            met,
            f"{accepted}/{total} mốc" if total else "chưa có mốc",
            f"{total}/{total} mốc" if total else "tất cả mốc",
        )

    def _t4(self, record: InternshipRecord, today: date, week_starts: list[date]) -> CreditItem:
        progress = journal_progress(record.start_date, record.end_date, today, week_starts)
        threshold = f"≥ {self._min_ratio:.0%}"
        if progress.expected == 0:
            return CreditItem("T4", "Tỷ lệ tuần có nhật ký đạt ngưỡng", False, "chưa có tuần nào đến hạn", threshold)
        ratio = progress.submitted / progress.expected
        return CreditItem(
            "T4",
            "Tỷ lệ tuần có nhật ký đạt ngưỡng",
            ratio >= self._min_ratio,
            f"{progress.submitted}/{progress.expected} tuần ({ratio:.0%})",
            threshold,
        )

    @staticmethod
    def _t5(milestones: list[MilestoneRecord]) -> CreditItem:
        m5 = next((m for m in milestones if m.code == "M5"), None)
        met = m5 is not None and m5.status == "accepted"
        value = (
            "đã xác thực"
            if met
            else ("đã nộp, chờ giảng viên xác thực" if m5 is not None and m5.status == "submitted" else "chưa có phiếu được xác thực")
        )
        return CreditItem("T5", "Phiếu đánh giá doanh nghiệp đã được giảng viên xác thực", met, value, "đã xác thực")

    def _t6(self, user_id: int) -> CreditItem:
        met = self._lms.prerequisites_met(user_id)
        return CreditItem(
            "T6", "Đủ điều kiện tiên quyết học phần (theo LMS)", met, "đủ điều kiện" if met else "chưa đủ điều kiện", "đủ điều kiện"
        )
