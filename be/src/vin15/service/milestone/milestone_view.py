"""Dựng dòng mốc cho người xem: trạng thái hiệu lực, số ngày còn lại, việc cần làm tiếp (hàm thuần)."""

from __future__ import annotations

from datetime import date

from vin15.domain.model.internship import MilestoneRecord, MilestoneView


def effective_status(milestone: MilestoneRecord, today: date) -> str:
    """Mốc ``pending``/``rejected`` đã quá hạn được coi là ``overdue`` (hệ thống đánh dấu quá hạn, docs mục 6.2)."""
    if milestone.status in ("pending", "rejected") and milestone.due_date < today:
        return "overdue"
    return milestone.status


def next_action(milestone: MilestoneRecord, status: str, today: date) -> str:
    due = f"{milestone.due_date:%d/%m/%Y}"
    match status:
        case "pending":
            return f"Nộp {milestone.name} trước ngày {due}"
        case "rejected":
            return f"Sửa theo nhận xét và nộp lại {milestone.name} trước ngày {due}"
        case "submitted":
            return "Chờ giảng viên chấp nhận, chưa cần làm thêm"
        case "accepted":
            return "Đã hoàn tất, không cần làm thêm"
        case _:
            late = (today - milestone.due_date).days
            return f"Đã quá hạn {late} ngày (hạn {due}): nộp ngay hoặc tạo yêu cầu gia hạn mốc để giảng viên xem xét"


def milestone_view(milestone: MilestoneRecord, today: date) -> MilestoneView:
    status = effective_status(milestone, today)
    return MilestoneView(
        code=milestone.code,
        name=milestone.name,
        due_date=milestone.due_date,
        status=status,
        days_left=(milestone.due_date - today).days,
        next_action=next_action(milestone, status, today),
    )
