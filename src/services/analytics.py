"""Số liệu tổng hợp toàn khóa cho dashboard (GV/QTV).

Chỉ ĐỌC và tổng hợp — không ghi gì, không gọi AI. Phạm vi theo người gọi (P5): GV chỉ thấy SV được phân công,
QTV thấy tất cả (dùng `scoped_internships`). Mọi con số tính từ dữ liệu đã có, giải thích được; truy vấn cố định
(không N+1): hồ sơ + mốc/SV nạp một lượt, cờ/gia hạn/ngoại lệ/nhật ký mỗi loại một truy vấn.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.api.vin15.deps import scoped_internships
from src.models.orm import ExceptionRequest, ExtensionRequest, Internship, LogEntry, Milestone, RiskFlag, User

INTERNSHIP_STATUSES = ("draft", "submitted", "revision_requested", "approved", "in_progress", "completed", "rejected")
MILESTONE_STATUSES = ("accepted", "submitted", "pending", "overdue", "rejected")
SEVERITIES = ("critical", "warning", "info")
_SEVERITY_RANK = {"critical": 3, "warning": 2, "info": 1}
_ACTIVE = ("approved", "in_progress", "completed")
TOP_AT_RISK = 5


def _pct(part: int, whole: int) -> int | None:
    return round(100 * part / whole) if whole else None


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _decision_days(rows) -> float | None:
    """Số ngày trung bình từ lúc gửi đến lúc có quyết định (chỉ các yêu cầu đã được quyết định)."""
    days = [(r.decided_at - r.created_at).total_seconds() / 86400 for r in rows if r.decided_at and r.created_at]
    return _avg(days)


def _request_stats(rows) -> dict:
    by_status = Counter(r.status for r in rows)
    return {
        "total": len(rows), "open": by_status["open"], "approved": by_status["approved"],
        "rejected": by_status["rejected"], "cancelled": by_status["cancelled"],
        "avg_decision_days": _decision_days(rows),
    }


def cohort_dashboard(db: Session, user: User, today: date) -> dict:
    internships = db.scalars(
        scoped_internships(user).options(selectinload(Internship.milestones), selectinload(Internship.student),
                                         selectinload(Internship.lecturer))
    ).all()
    # Truy vấn con theo phạm vi thay vì truyền danh sách id: không chạm giới hạn số tham số của DB khi có hàng nghìn hồ sơ
    scope = scoped_internships(user).with_only_columns(Internship.id)
    flags = db.scalars(select(RiskFlag).where(RiskFlag.internship_id.in_(scope), RiskFlag.open_key.is_not(None))).all()
    extensions = db.scalars(select(ExtensionRequest).join(Milestone).where(Milestone.internship_id.in_(scope))
                            .options(selectinload(ExtensionRequest.milestone))).all()
    exceptions = db.scalars(select(ExceptionRequest).where(ExceptionRequest.internship_id.in_(scope))).all()
    logs = db.scalars(select(LogEntry).where(LogEntry.internship_id.in_(scope))).all()
    by_intern = {i.id: i for i in internships}

    # ---- hồ sơ theo trạng thái + KPI
    status_counts = Counter(i.status for i in internships)
    flagged = {f.internship_id for f in flags}
    overdue_interns = {m.internship_id for i in internships for m in i.milestones if m.status == "overdue"}
    started = [i for i in internships if i.status in _ACTIVE]
    all_ms = [m for i in started for m in i.milestones]
    accepted_ms = sum(1 for m in all_ms if m.status == "accepted")

    # ---- tiến độ theo mốc (gộp theo mã mốc, giữ thứ tự mẫu)
    per_milestone: dict[str, dict] = {}
    for i in started:
        for m in i.milestones:
            row = per_milestone.setdefault(m.code, {"code": m.code, "name": m.name, "ordinal": m.ordinal,
                                                    **dict.fromkeys(MILESTONE_STATUSES, 0), "total": 0})
            row[m.status if m.status in MILESTONE_STATUSES else "pending"] += 1
            row["total"] += 1
    milestone_rows = sorted(per_milestone.values(), key=lambda r: r["ordinal"])
    for r in milestone_rows:
        r["accepted_pct"] = _pct(r["accepted"], r["total"])

    # ---- cảnh báo
    flag_types = Counter(f.flag_type for f in flags)
    flag_severity = Counter(f.severity for f in flags)
    at_risk = []
    for iid in flagged:
        i = by_intern[iid]
        mine = [f for f in flags if f.internship_id == iid]
        top = max(mine, key=lambda f: _SEVERITY_RANK.get(f.severity, 0))
        at_risk.append({"internship_id": iid, "student": i.student.full_name, "student_code": i.student.student_code,
                        "open_flags": len(mine), "max_severity": top.severity, "top_reason": top.reason})
    at_risk.sort(key=lambda r: (_SEVERITY_RANK.get(r["max_severity"], 0), r["open_flags"]), reverse=True)

    # ---- nhật ký tuần
    log_status = Counter(entry.status for entry in logs)
    reviewed = log_status["accepted"] + log_status["returned"]

    # ---- tải theo giảng viên (GV chỉ thấy chính mình do phạm vi)
    lecturers: dict[int, dict] = {}
    for i in internships:
        if i.lecturer is None:
            continue
        row = lecturers.setdefault(i.lecturer.id, {"lecturer_id": i.lecturer.id, "name": i.lecturer.full_name,
                                                   "students": 0, "pending_reviews": 0, "open_flags": 0})
        row["students"] += 1
        row["pending_reviews"] += int(i.status == "submitted") + sum(1 for m in i.milestones if m.status == "submitted")
    for r in extensions:
        if r.status == "open" and (i := by_intern.get(r.milestone.internship_id)) and i.lecturer:
            lecturers[i.lecturer.id]["pending_reviews"] += 1
    for r in exceptions:
        if r.status == "open" and (i := by_intern.get(r.internship_id)) and i.lecturer:
            lecturers[i.lecturer.id]["pending_reviews"] += 1
    for entry in logs:
        if entry.status == "pending" and (i := by_intern.get(entry.internship_id)) and i.lecturer:
            lecturers[i.lecturer.id]["pending_reviews"] += 1
    for f in flags:
        if (i := by_intern.get(f.internship_id)) and i.lecturer:
            lecturers[i.lecturer.id]["open_flags"] += 1

    # ---- theo ngành
    programs: dict[str, dict] = defaultdict(lambda: {"internships": 0, "completed": 0, "ms_total": 0, "ms_accepted": 0})
    for i in internships:
        p = programs[i.student.program or "(chưa rõ)"]
        p["internships"] += 1
        p["completed"] += int(i.status == "completed")
        if i.status in _ACTIVE:
            p["ms_total"] += len(i.milestones)
            p["ms_accepted"] += sum(1 for m in i.milestones if m.status == "accepted")
    program_rows = [{"program": name, "internships": p["internships"], "completed": p["completed"],
                     "milestone_pct": _pct(p["ms_accepted"], p["ms_total"])} for name, p in sorted(programs.items())]

    return {
        "as_of": today.isoformat(),
        "scope": "all" if user.role == "admin" else "assigned",
        "kpis": {
            "internships": len(internships), "in_progress": status_counts["in_progress"],
            "completed": status_counts["completed"], "flagged_internships": len(flagged),
            "overdue_internships": len(overdue_interns),
            "milestone_completion_pct": _pct(accepted_ms, len(all_ms)),
            "completion_pct": _pct(status_counts["completed"], len(started)),
        },
        "internship_status": [{"status": s, "count": status_counts[s]} for s in INTERNSHIP_STATUSES],
        "milestones": milestone_rows,
        "risk": {
            "open_flags": len(flags),
            "by_severity": [{"severity": s, "count": flag_severity[s]} for s in SEVERITIES],
            "by_type": [{"type": t, "count": c} for t, c in flag_types.most_common()],
            "at_risk_students": at_risk[:TOP_AT_RISK],
        },
        "requests": {"extensions": _request_stats(extensions), "exceptions": _request_stats(exceptions),
                     "exceptions_by_kind": [{"kind": k, "count": c} for k, c in
                                            Counter(r.kind for r in exceptions).most_common()]},
        "logs": {
            "total": len(logs), "accepted": log_status["accepted"], "returned": log_status["returned"],
            "pending": log_status["pending"], "accepted_pct": _pct(log_status["accepted"], reviewed),
            "avg_hours_per_week": _avg([entry.hours for entry in logs]),
        },
        "lecturers": sorted(lecturers.values(), key=lambda r: r["pending_reviews"], reverse=True),
        "programs": program_rows,
    }
