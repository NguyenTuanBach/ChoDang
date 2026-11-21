"""Tác tử giám sát theo luật (R10, UC-100 → UC-105).

Chạy với Actor(kind="system"): không thể đi vào cạnh quyết định (P1).
Không tạo trùng cờ đang mở nhờ UNIQUE(open_key) + kiểm tra trước (P4).
Cờ không còn đúng điều kiện được đóng tự động — tránh nhắc việc đã xong.
Mọi "hôm nay"/giờ chạy theo giờ trường (src.core.clock, OQ-9).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.config import get_settings
from src.core import audit, clock
from src.core.audit import Actor
from src.db import session_factory
from src.models.orm import Internship, Milestone, RiskFlag
from src.services.lifecycle import close_flag, daily_status_job, mark_overdue
from src.services.notifications import notify
from src.workflow.rules import evaluate_monitor

logger = logging.getLogger("vin15.monitor")

_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
_ACTIVE = ("approved", "in_progress")

DISMISS_SUPPRESS_DAYS = 7
STATUS_JOB_TIME = time(0, 5)  # chuyển overdue/in_progress ngay sau khi sang ngày mới (giờ trường)

DismissKey = tuple[int, str, "int | None"]


def open_key(internship_id: int, flag_type: str, milestone_id: int | None) -> str:
    return f"{internship_id}:{flag_type}:{milestone_id or 0}"


def _open_flags(db: Session, internship_ids: list[int]) -> dict[int, list[RiskFlag]]:
    out: dict[int, list[RiskFlag]] = {i: [] for i in internship_ids}
    if internship_ids:
        stmt = select(RiskFlag).where(RiskFlag.internship_id.in_(internship_ids), RiskFlag.open_key.is_not(None))
        for flag in db.scalars(stmt):
            out[flag.internship_id].append(flag)
    return out


def _dismissed_keys(db: Session, internship_ids: list[int], today: date) -> set[DismissKey]:
    """Cờ GV đã bác bỏ trong 7 ngày → không tạo lại (tránh spam cảnh báo sai). 1 query cho cả lô."""
    if not internship_ids:
        return set()
    since = clock.local_midnight_utc(today - timedelta(days=DISMISS_SUPPRESS_DAYS))
    rows = db.execute(
        select(RiskFlag.internship_id, RiskFlag.flag_type, RiskFlag.milestone_id).where(
            RiskFlag.internship_id.in_(internship_ids), RiskFlag.status == "dismissed", RiskFlag.closed_at >= since,
        )
    )
    return {(iid, flag_type, mid) for iid, flag_type, mid in rows}


def run_for(
    db: Session,
    internship: Internship,
    today: date,
    *,
    open_flags: list[RiskFlag] | None = None,
    dismissed: set[DismissKey] | None = None,
) -> list[RiskFlag]:
    """Đánh giá 1 hồ sơ, upsert cờ. Trả về các cờ MỚI tạo.

    `open_flags`/`dismissed` do run_all nạp sẵn cho cả lô; gọi lẻ (sau sự kiện) thì tự query.
    """
    if internship.status not in _ACTIVE:
        return []
    system = Actor.system()
    mark_overdue(db, internship, today)
    findings = evaluate_monitor(internship, today)
    wanted = {open_key(internship.id, f.rule_id, f.milestone_id): f for f in findings}
    if open_flags is None:
        open_flags = _open_flags(db, [internship.id])[internship.id]
    if dismissed is None:
        dismissed = _dismissed_keys(db, [internship.id], today)
    existing = {flag.open_key: flag for flag in open_flags}
    for key, flag in existing.items():
        if key not in wanted:
            close_flag(db, flag, "resolved", system, "Đóng tự động: điều kiện cảnh báo không còn")
        elif flag.reason != wanted[key].message:
            # Cùng cờ, nội dung đổi (quá hạn thêm ngày, thiếu thêm tuần nhật ký) → cập nhật, không nhắc lại
            flag.reason = wanted[key].message

    created: list[RiskFlag] = []
    for key, finding in wanted.items():
        if key in existing or (internship.id, finding.rule_id, finding.milestone_id) in dismissed:
            continue
        flag = RiskFlag(
            internship_id=internship.id, milestone_id=finding.milestone_id, flag_type=finding.rule_id,
            severity=finding.severity, reason=finding.message, evidence_refs=finding.evidence, open_key=key,
        )
        db.add(flag)
        db.flush()
        audit.record(db, system, "risk_flag", flag.id, "created", after={"type": flag.flag_type, "severity": flag.severity})
        notify(db, internship.student_id, "risk_flag", f"Nhắc việc: {finding.message}", link=f"#/internship/{internship.id}")
        if _SEVERITY_RANK[flag.severity] >= _SEVERITY_RANK["warning"]:
            notify(db, internship.lecturer_id, "risk_flag",
                   f"Cảnh báo SV {internship.student.full_name}: {finding.message}", link="#/flags")
        created.append(flag)
    return created


def run_all(db: Session, today: date | None = None) -> dict:
    today = today or clock.today()
    status = daily_status_job(db, today)
    # Nạp sẵn mọi thứ evaluate_monitor/notify dùng tới — số query không tăng theo số hồ sơ
    internships = db.scalars(
        select(Internship).where(Internship.status.in_(_ACTIVE)).options(
            selectinload(Internship.cohort), selectinload(Internship.student), selectinload(Internship.logs),
            selectinload(Internship.milestones).selectinload(Milestone.evidence),
        )
    ).all()
    ids = [i.id for i in internships]
    open_flags = _open_flags(db, ids)
    dismissed = _dismissed_keys(db, ids, today)
    created = 0
    for internship in internships:
        created += len(run_for(db, internship, today, open_flags=open_flags[internship.id], dismissed=dismissed))
    db.commit()
    logger.info("monitor run: %s, flags created=%d", status, created)
    return {**status, "flags_created": created}


def run_status(db: Session, today: date | None = None) -> dict:
    """Chỉ chuyển trạng thái (00:05). Cờ + thông báo đợi tới MONITOR_HOUR — không nhắn SV lúc nửa đêm."""
    status = daily_status_job(db, today or clock.today())
    db.commit()
    logger.info("status job: %s", status)
    return status


def run_for_event(db: Session, internship: Internship) -> None:
    """Gọi sau sự kiện (nộp nhật ký/minh chứng/đổi trạng thái) — R10.1."""
    run_for(db, internship, clock.today())


def next_run(now: datetime, monitor_hour: int) -> tuple[datetime, bool]:
    """Lần chạy kế tiếp sau `now` (có tzinfo) và đó có phải lần chạy đầy đủ (run_all) không."""
    candidates = [
        (datetime.combine(now.date() + timedelta(days=d), at, now.tzinfo), full)
        for d in (0, 1)
        for at, full in ((STATUS_JOB_TIME, False), (time(monitor_hour), True))
    ]
    return min((c for c in candidates if c[0] > now), key=lambda c: (c[0], not c[1]))


async def scheduler_loop() -> None:
    """run_all một lần khi khởi động, rồi mỗi ngày: run_status lúc 00:05 và run_all lúc MONITOR_HOUR (giờ trường)."""
    settings = get_settings()
    full = True
    while True:
        try:
            db = session_factory()()
            try:
                (run_all if full else run_status)(db)
            finally:
                db.close()
        except Exception as exc:  # job lỗi không được làm sập API
            logger.error("FAILED monitor run: %s", exc)
        now = clock.now()
        at, full = next_run(now, settings.monitor_hour)
        await asyncio.sleep((at - now).total_seconds())
