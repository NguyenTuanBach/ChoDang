"""Luật phát hiện rủi ro tất định (docs mục 8.4), không cần LLM nên giám sát vẫn chạy khi LLM không khả dụng (X5).

Hàm thuần: nhận ảnh chụp dữ liệu một hồ sơ, trả về danh sách ứng viên cờ và ứng viên nhắc nhở.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from vin15.service.progress.progress_calculator import journal_progress

SEVERE_OVERDUE_DAYS = 7
CREDIT_WARNING_DAYS = 14


@dataclass(frozen=True)
class FlagCandidate:
    kind: str
    severity: str
    reason: str
    suggestion: str
    fingerprint: str
    evidence: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReminderCandidate:
    milestone_code: str
    #: Lý do nhắc (khóa giới hạn tần suất): ``milestone_overdue`` | ``milestone_due_soon`` | ``journal_missing``.
    reason: str
    #: Mẫu cố định + tham số; nội dung gửi đi không do LLM viết (8.3).
    template: str
    params: dict


REMINDER_TEMPLATES = {
    "milestone_overdue": "Mốc \"{milestone}\" đã quá hạn {days} ngày (hạn {due}). Hãy nộp ngay hoặc tạo yêu cầu gia hạn để giảng viên xem xét.",
    "milestone_due_soon": "Mốc \"{milestone}\" sắp đến hạn vào {due} (còn {days} ngày). Hãy chuẩn bị nộp đúng hạn.",
    "journal_missing": "Bạn chưa nộp nhật ký tuần bắt đầu {week}. Hãy bổ sung nhật ký tuần.",
}


def render_reminder(template: str, params: dict) -> str:
    return REMINDER_TEMPLATES[template].format(**params)


def detect(
    internship: dict, milestones: list[dict], journal_weeks: list[date], evidence: list[dict], checklist_unmet: list[dict], today: date
) -> tuple[list[FlagCandidate], list[ReminderCandidate]]:
    flags: list[FlagCandidate] = []
    reminders: list[ReminderCandidate] = []
    active = internship["status"] in ("in_progress", "pending_credit", "confirmed")
    if not active:
        return flags, reminders

    # 1. Quá hạn mốc.
    for m in milestones:
        if m["status"] not in ("pending", "rejected", "overdue") or m["due_date"] >= today:
            continue
        days = (today - m["due_date"]).days
        severity = "critical" if days >= SEVERE_OVERDUE_DAYS else "warning"
        flags.append(
            FlagCandidate(
                "overdue_milestone",
                severity,
                f"Mốc {m['code']} ({m['name']}) quá hạn {days} ngày.",
                "Liên hệ sinh viên, hoặc xem xét yêu cầu gia hạn nếu có.",
                f"overdue:{m['code']}:{m['due_date']}:{severity}",
                {"milestone": m["code"], "due_date": str(m["due_date"]), "days_overdue": days},
            )
        )
        reminders.append(ReminderCandidate(m["code"], "milestone_overdue", "milestone_overdue", {"milestone": m["name"], "days": days, "due": f"{m['due_date']:%d/%m/%Y}"}))
    for m in milestones:
        if m["status"] == "pending" and 0 <= (m["due_date"] - today).days <= 2:
            reminders.append(
                ReminderCandidate(m["code"], "milestone_due_soon", "milestone_due_soon", {"milestone": m["name"], "days": (m["due_date"] - today).days, "due": f"{m['due_date']:%d/%m/%Y}"})
            )

    # 2. Thiếu nhật ký ≥ 2 tuần liên tiếp (tính các tuần thiếu ở cuối chuỗi đã đến hạn).
    if internship["status"] == "in_progress":
        progress = journal_progress(internship["start_date"], internship["end_date"], today, journal_weeks)
        trailing = _trailing_missing(progress.missing_weeks, progress.expected, internship["start_date"])
        if len(trailing) >= 2:
            flags.append(
                FlagCandidate(
                    "missing_journal",
                    "warning",
                    f"Thiếu nhật ký {len(trailing)} tuần liên tiếp (từ tuần bắt đầu {trailing[0]:%d/%m/%Y}).",
                    "Nhắc sinh viên bổ sung nhật ký; trao đổi nếu có khó khăn.",
                    f"journal:{trailing[0]}",
                    {"missing_weeks": [str(w) for w in trailing]},
                )
            )
        if trailing:
            reminders.append(ReminderCandidate("", "journal_missing", "journal_missing", {"week": f"{trailing[-1]:%d/%m/%Y}"}))

    # 3. Thiếu điều kiện tín chỉ khi còn ≤ 2 tuần.
    end = internship["end_date"]
    if end is not None and internship["status"] == "in_progress" and 0 <= (end - today).days <= CREDIT_WARNING_DAYS:
        codes = [i["code"] for i in checklist_unmet if i["code"] not in ("T5",)]  # T5 (phiếu DN) chỉ có sau khi kết thúc
        if codes:
            flags.append(
                FlagCandidate(
                    "credit_shortfall",
                    "critical",
                    f"Còn {(end - today).days} ngày thực tập, dự báo chưa đủ điều kiện công nhận tín chỉ: " + ", ".join(codes) + ".",
                    "Rà soát điều kiện còn thiếu với sinh viên.",
                    "credit:" + ",".join(codes),
                    {"unmet": [{"code": i["code"], "value": i["value"], "threshold": i["threshold"]} for i in checklist_unmet if i["code"] in codes]},
                )
            )

    # 4. Minh chứng yếu: tệp trùng nội dung hoặc quá nhỏ.
    seen: dict[str, int] = {}
    for e in evidence:
        digest = e.get("sha256") or ""
        if not digest:
            continue
        if digest in seen:
            flags.append(
                FlagCandidate("weak_evidence", "info", f"Minh chứng #{e['id']} trùng nội dung với minh chứng #{seen[digest]}.", "Kiểm tra minh chứng có bị nộp lặp không.", f"evidence-dup:{e['id']}", {"evidence_id": e["id"], "duplicate_of": seen[digest]})
            )
        else:
            seen[digest] = e["id"]
        if 0 < e.get("size_bytes", 0) < 1024:
            flags.append(
                FlagCandidate("weak_evidence", "info", f"Minh chứng #{e['id']} rất nhỏ ({e['size_bytes']} byte), có thể rỗng.", "Mở tệp kiểm tra nội dung.", f"evidence-small:{e['id']}", {"evidence_id": e["id"], "size_bytes": e["size_bytes"]})
            )
    return flags, reminders


def _trailing_missing(missing: list[date], expected: int, start: date | None) -> list[date]:
    """Các tuần thiếu nằm liên tục tới tuần đã đến hạn gần nhất."""
    if not missing or start is None or expected == 0:
        return []
    from datetime import timedelta

    last_week = start + timedelta(days=7 * (expected - 1))
    chain: list[date] = []
    cursor = last_week
    missing_set = set(missing)
    while cursor in missing_set:
        chain.append(cursor)
        cursor -= timedelta(days=7)
    return sorted(chain)
