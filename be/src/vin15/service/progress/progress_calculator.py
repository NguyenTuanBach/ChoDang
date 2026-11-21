"""Tính tiến độ nhật ký tuần và minh chứng từ dữ liệu thô (hàm thuần, không đụng DB)."""

from __future__ import annotations

from datetime import date, timedelta

from vin15.domain.model.internship import EvidenceProgress, EvidenceRecord, JournalProgress, MilestoneRecord

#: Mốc cần minh chứng (báo cáo giữa kỳ, báo cáo cuối kỳ, phiếu đánh giá doanh nghiệp), docs/nghiep-vu-thuc-tap.md mục 9.1.
EVIDENCE_REQUIRED_CODES = ("M3", "M4", "M5")


def total_weeks(start: date, end: date) -> int:
    return max(0, -(-((end - start).days + 1) // 7))


def expected_weeks(start: date | None, end: date | None, today: date) -> int:
    """Số tuần đã **kết thúc** tính tới hôm nay (tuần k gồm 7 ngày từ ``start + 7k``), không quá tổng số tuần của đợt."""
    if start is None or today < start:
        return 0
    elapsed = (today - start).days // 7
    return min(elapsed, total_weeks(start, end)) if end is not None else elapsed


def journal_progress(start: date | None, end: date | None, today: date, week_starts: list[date]) -> JournalProgress:
    """Tuần k được tính là đã nộp nếu có nhật ký có ``week_start`` nằm trong 7 ngày của tuần đó."""
    expected = expected_weeks(start, end, today)
    if start is None:
        return JournalProgress()
    missing: list[date] = []
    submitted = 0
    for k in range(expected):
        first = start + timedelta(days=7 * k)
        last = first + timedelta(days=6)
        if any(first <= entry <= last for entry in week_starts):
            submitted += 1
        else:
            missing.append(first)
    return JournalProgress(submitted=submitted, expected=expected, missing_weeks=missing)


def evidence_progress(milestones: list[MilestoneRecord], evidence: list[EvidenceRecord]) -> EvidenceProgress:
    required = [code for code in EVIDENCE_REQUIRED_CODES if any(m.code == code for m in milestones)]
    submitted = sum(1 for code in required if any(e.milestone_code == code and e.status != "rejected" for e in evidence))
    return EvidenceProgress(submitted=submitted, required=len(required))
