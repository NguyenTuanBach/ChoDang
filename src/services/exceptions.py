"""Yêu cầu ngoại lệ có lưu vết (HITL bắt buộc).

Mọi quyết định đi qua `transition()` nên agent/hệ thống không thể tự duyệt (P1).
AI chỉ ghi `ai_summary` làm gợi ý. Hệ quả của quyết định `approved` nằm ở `_apply()`:
- late_extension: dời hạn mốc, gỡ overdue, đóng cờ liên quan — cùng transaction với quyết định.
- credit_recognition: chỉ ghi nhận quyết định (Hội đồng Khoa chốt số tín chỉ ngoài hệ thống).
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core import audit
from src.core.audit import Actor
from src.models.orm import ExceptionRequest, Internship, Milestone, RiskFlag, User, utcnow
from src.services import lifecycle
from src.services.notifications import notify
from src.services.pii import Redactor
from src.services.reviewer import summarize_exception
from src.workflow.state_machine import transition

KINDS = ("late_extension", "credit_recognition")
MAX_LATE_EXTENSION_DAYS = 30
KIND_LABELS = {"late_extension": "gia hạn quá hạn", "credit_recognition": "công nhận/quy đổi tín chỉ"}


def _validate(db: Session, internship: Internship, kind: str, milestone_id: int | None,
              payload: dict) -> tuple[Milestone | None, dict]:
    if kind == "late_extension":
        m = db.get(Milestone, milestone_id) if milestone_id else None
        if m is None or m.internship_id != internship.id:
            raise HTTPException(status_code=422, detail="Cần chọn mốc thuộc hồ sơ này")
        if m.status == "accepted":
            raise HTTPException(status_code=409, detail="Mốc đã được chấp nhận không cần ngoại lệ")
        try:
            new_due = date.fromisoformat(str(payload.get("requested_due_date")))
        except ValueError:
            raise HTTPException(status_code=422, detail="Cần nhập hạn mới hợp lệ (YYYY-MM-DD)") from None
        if new_due <= m.due_date:
            raise HTTPException(status_code=422, detail="Hạn mới phải sau hạn hiện tại")
        if new_due > m.due_date + timedelta(days=MAX_LATE_EXTENSION_DAYS):
            raise HTTPException(status_code=422, detail=f"Ngoại lệ gia hạn không quá {MAX_LATE_EXTENSION_DAYS} ngày")
        return m, {"requested_due_date": new_due.isoformat(), "previous_due_date": m.due_date.isoformat()}
    if kind == "credit_recognition":
        try:
            credits = float(payload.get("credits"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="Cần nhập số tín chỉ đề nghị công nhận") from None
        if not 0 < credits <= 30:
            raise HTTPException(status_code=422, detail="Số tín chỉ đề nghị phải trong khoảng (0, 30]")
        return None, {"credits": credits, "basis": str(payload.get("basis", ""))[:500]}
    raise HTTPException(status_code=422, detail=f"Loại ngoại lệ không hỗ trợ: {kind}")


def create(db: Session, user: User, internship: Internship, kind: str, reason: str, milestone_id: int | None,
           payload: dict, evidence_id: int | None, actor: Actor, today: date) -> ExceptionRequest:
    milestone, clean = _validate(db, internship, kind, milestone_id, payload)
    dup = select(ExceptionRequest.id).where(
        ExceptionRequest.internship_id == internship.id, ExceptionRequest.kind == kind,
        ExceptionRequest.status == "open",
        ExceptionRequest.milestone_id == milestone.id if milestone else ExceptionRequest.milestone_id.is_(None))
    if db.scalar(dup):
        raise HTTPException(status_code=409, detail="Đã có yêu cầu ngoại lệ cùng loại đang chờ duyệt")
    req = ExceptionRequest(internship_id=internship.id, milestone_id=milestone.id if milestone else None, kind=kind,
                           requested_by=user.id, reason=reason.strip(), payload=clean, evidence_id=evidence_id)
    db.add(req)
    try:
        db.flush()
    except IntegrityError:  # hai request đồng thời cùng lọt qua kiểm tra trên → index duy nhất của DB chặn
        raise HTTPException(status_code=409, detail="Đã có yêu cầu ngoại lệ cùng loại đang chờ duyệt") from None
    audit.record(db, actor, "exception", req.id, "created", after={"kind": kind, **clean}, reason=req.reason)
    redactor = Redactor({"HO_TEN": user.full_name, "MSSV": user.student_code, "EMAIL": user.email})
    req.ai_summary = summarize_exception(db, req, redactor, today)
    notify(db, internship.lecturer_id, "approval",
           f"{user.full_name} gửi yêu cầu ngoại lệ ({KIND_LABELS[kind]})", link="#/queue")
    return req


def decide(db: Session, req: ExceptionRequest, decision: str, reason: str, actor: Actor) -> None:
    transition(db, "exception", req, decision, actor, reason)  # chốt HITL: chỉ GV phụ trách (người) đi qua được
    req.decided_by = actor.user_id
    req.decided_at = utcnow()
    req.decision_reason = reason.strip()
    if decision == "approved":
        _apply(db, req, actor)
    label = "được duyệt" if decision == "approved" else "bị từ chối"
    notify(db, req.internship.student_id, "decision",
           f"Yêu cầu ngoại lệ ({KIND_LABELS[req.kind]}) {label}", reason, link="#/")


def _apply(db: Session, req: ExceptionRequest, actor: Actor) -> None:
    if req.kind != "late_extension" or req.milestone is None:
        return  # credit_recognition: chỉ ghi nhận quyết định + audit
    m = req.milestone
    before = m.due_date
    m.due_date = date.fromisoformat(req.payload["requested_due_date"])
    audit.record(db, actor, "milestone", m.id, "due_date_changed",
                 before={"due_date": before.isoformat()},
                 after={"due_date": m.due_date.isoformat(), "exception_id": req.id},
                 reason=f"Ngoại lệ #{req.id} đã duyệt")
    if m.status == "overdue":
        transition(db, "milestone", m, "pending", actor, f"Ngoại lệ #{req.id}")
    flags = db.scalars(select(RiskFlag).where(
        RiskFlag.milestone_id == m.id, RiskFlag.flag_type.in_(("overdue", "due_soon")),
        RiskFlag.open_key.is_not(None))).all()
    for flag in flags:
        lifecycle.close_flag(db, flag, "resolved", actor, f"Đóng tự động: ngoại lệ #{req.id} đã duyệt")
