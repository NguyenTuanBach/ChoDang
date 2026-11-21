"""Mốc, minh chứng, nhật ký tuần, yêu cầu gia hạn (R4, R5, R12)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from src.api.vin15.deps import load_evidence, load_extension, load_internship, load_log, load_milestone
from src.api.vin15.serializers import evidence_out, extension_out, log_out, milestone_out
from src.core import audit, clock
from src.core.auth import actor_of, current_user, require_role
from src.core.security import sign_file_url, verify_file_signature
from src.db import get_db
from src.models.orm import Evidence, ExtensionRequest, Internship, LogEntry, Milestone, User, utcnow
from src.services import lifecycle, monitor, priority
from src.services.documents import UnreadableDocument, extract_text
from src.services.evidence_review import review_evidence
from src.services.notifications import notify
from src.services.pii import Redactor
from src.services.priority import PriorityContext
from src.services.reviewer import summarize_extension
from src.services.storage import ALLOWED, FileRejected, pdf_problem, save_file
from src.workflow.rules import DEFAULT_LOG_GRACE_DAYS, load_cohort_config, missing_log_weeks
from src.workflow.state_machine import transition

router = APIRouter(tags=["progress"])

DEFAULT_MAX_EXTENSION_DAYS = 14  # dùng khi cohort.yaml không khai báo rules.extension.max_days
DEFAULT_REQUEST_GRACE_DAYS = 3  # Điều 10 Khoản 2: gửi trước hoặc chậm nhất 3 ngày sau hạn mốc
# Xem trực tiếp trên trình duyệt: PDF (trình xem PDF) và ảnh. DOCX trình duyệt không hiển thị → trích văn bản.
_INLINE_KIND = {"application/pdf": "pdf", "image/png": "image", "image/jpeg": "image"}
_DOCX_MIME = ALLOWED[".docx"][0]
PREVIEW_TEXT_CHARS = 20_000


class ReviewIn(BaseModel):
    decision: Literal["accepted", "rejected"]
    comment: str = Field(default="", max_length=2000)


class LogIn(BaseModel):
    week_no: int = Field(ge=1, le=52)
    content: str = Field(min_length=10, max_length=5000)
    difficulties: str = Field(default="", max_length=2000)
    hours: float = Field(ge=0, le=80)


class LogReviewIn(BaseModel):
    decision: Literal["accepted", "returned"]
    comment: str = Field(default="", max_length=2000)


class ExtensionIn(BaseModel):
    requested_due_date: date
    reason: str = Field(min_length=10, max_length=2000)
    evidence_id: int | None = None


class ExtensionDecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=2000)


async def _store(file: UploadFile) -> tuple[str, object]:
    content = await file.read()
    try:
        return file.filename or "upload", save_file(file.filename or "upload", content)
    except FileRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------- mốc & minh chứng

@router.get("/internships/{internship_id}/milestones")
def list_milestones(internship_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    i = load_internship(db, user, internship_id)
    rows = db.scalars(select(Milestone).where(Milestone.internship_id == i.id)
                      .options(selectinload(Milestone.evidence)).order_by(Milestone.ordinal)).all()
    today = clock.today()
    return [milestone_out(m, today) for m in rows]


@router.post("/milestones/{milestone_id}/evidence", status_code=201)
async def upload_evidence(milestone_id: int, evidence_type: str = Form(...), file: UploadFile = File(...),
                          user: User = Depends(require_role("student")), db: Session = Depends(get_db)) -> dict:
    m = load_milestone(db, user, milestone_id)
    if evidence_type not in load_cohort_config().get("evidence_types", {}):
        raise HTTPException(status_code=422, detail=f"Loại minh chứng không hợp lệ: {evidence_type}")
    if m.status == "accepted":
        raise HTTPException(status_code=409, detail="Mốc đã được chấp nhận, không nộp thêm minh chứng")
    _, stored = await _store(file)
    ev = Evidence(milestone_id=m.id, internship_id=m.internship_id, evidence_type=evidence_type,
                  filename=stored.filename, path=stored.path, mime=stored.mime, size=stored.size,
                  sha256=stored.sha256, uploaded_by=user.id)
    db.add(ev)
    db.flush()
    audit.record(db, actor_of(user), "milestone", m.id, "evidence_uploaded", after={"evidence_id": ev.id, "type": evidence_type})
    db.refresh(m)
    monitor.run_for_event(db, m.internship)
    db.commit()
    return evidence_out(ev)


@router.post("/milestones/{milestone_id}/submit")
def submit_milestone(milestone_id: int, user: User = Depends(require_role("student")), db: Session = Depends(get_db)) -> dict:
    m = load_milestone(db, user, milestone_id)
    if m.linked_to == "outline":
        raise HTTPException(status_code=409, detail="Mốc này tự cập nhật khi bạn nộp đề cương")
    transition(db, "milestone", m, "submitted", actor_of(user))
    m.submitted_at = utcnow()
    notify(db, m.internship.lecturer_id, "milestone", f"{user.full_name} đã nộp mốc '{m.name}'",
           link=f"#/internship/{m.internship_id}")
    monitor.run_for_event(db, m.internship)
    db.commit()
    return milestone_out(m)


@router.post("/milestones/{milestone_id}/review")
def review_milestone(milestone_id: int, body: ReviewIn, user: User = Depends(require_role("lecturer")),
                     db: Session = Depends(get_db)) -> dict:
    m = load_milestone(db, user, milestone_id)
    if m.linked_to == "outline":
        raise HTTPException(status_code=409, detail="Mốc này theo kết quả duyệt đề cương")
    if body.decision == "rejected" and not body.comment.strip():
        raise HTTPException(status_code=422, detail="Trả lại minh chứng cần ghi nhận xét")
    transition(db, "milestone", m, body.decision, actor_of(user), body.comment)
    m.comment = body.comment.strip()
    lifecycle.maybe_complete(db, m.internship)
    label = "được chấp nhận" if body.decision == "accepted" else "bị trả lại"
    notify(db, m.internship.student_id, "milestone", f"Mốc '{m.name}' {label}", body.comment, link="#/")
    monitor.run_for_event(db, m.internship)
    db.commit()
    return milestone_out(m)


@router.get("/evidence/{evidence_id}/url")
def evidence_url(evidence_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    ev = load_evidence(db, user, evidence_id)
    return {"url": sign_file_url(ev.id)}


@router.get("/evidence/{evidence_id}/preview")
def evidence_preview(evidence_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Xem minh chứng ngay trên web, không phải tải về. Cùng phạm vi truy cập với /url (P5)."""
    ev = load_evidence(db, user, evidence_id)
    out = {"id": ev.id, "filename": ev.filename, "mime": ev.mime, "size": ev.size,
           "download_url": sign_file_url(ev.id)}
    if not Path(ev.path).is_file():
        return {**out, "kind": "missing"}
    if (kind := _INLINE_KIND.get(ev.mime)) == "pdf" and (problem := pdf_problem(ev.path)):
        # File cũ nộp trước khi có check_readable — trình xem PDF chỉ báo lỗi tiếng Anh
        return {**out, "kind": "broken", "problem": problem}
    if kind:
        return {**out, "kind": kind, "url": out["download_url"] + "&inline=1"}
    if ev.mime == _DOCX_MIME:
        try:
            text = extract_text(ev.filename, Path(ev.path).read_bytes())
        except UnreadableDocument:
            text = ""
        if text.strip():
            return {**out, "kind": "text", "text": text[:PREVIEW_TEXT_CHARS], "truncated": len(text) > PREVIEW_TEXT_CHARS}
    return {**out, "kind": "none"}


@router.get("/evidence/{evidence_id}/review")
def evidence_ai_review(evidence_id: int, user: User = Depends(require_role("lecturer", "admin")),
                       db: Session = Depends(get_db)) -> dict:
    """Gợi ý AI đọc minh chứng cho người duyệt. Tính lần đầu rồi lưu (file không đổi sau khi nộp)."""
    ev = load_evidence(db, user, evidence_id)
    if ev.ai_review is None:
        ev.ai_review = review_evidence(db, ev)
        if ev.ai_review is not None:
            db.commit()
    return ev.ai_review or {"unavailable": True}


@router.get("/files/{evidence_id}")
def download(evidence_id: int, exp: int = Query(...), sig: str = Query(...), inline: bool = False,
             db: Session = Depends(get_db)):
    if not verify_file_signature(evidence_id, exp, sig):
        raise HTTPException(status_code=403, detail="Liên kết tải không hợp lệ hoặc đã hết hạn")
    ev = db.get(Evidence, evidence_id)
    if ev is None or not Path(ev.path).is_file():  # file mất trên đĩa → 404, không để FileResponse ném 500
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
    # inline chỉ cho loại trình duyệt tự hiển thị an toàn; còn lại luôn tải về
    disposition = "inline" if inline and ev.mime in _INLINE_KIND else "attachment"
    return FileResponse(ev.path, media_type=ev.mime, filename=ev.filename, content_disposition_type=disposition,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


def review_items(db: Session, lecturer: User, rank: PriorityContext | None = None) -> dict:
    """Mốc đã nộp + nhật ký chờ duyệt của SV được phân công — cho hàng chờ phê duyệt của GV."""
    rank = rank or priority.context(db, lecturer)
    labels = load_cohort_config().get("evidence_types", {})
    milestones = db.scalars(
        select(Milestone).join(Internship).where(
            Internship.lecturer_id == lecturer.id, Milestone.status == "submitted", Milestone.linked_to.is_(None))
        .options(selectinload(Milestone.evidence), selectinload(Milestone.internship).selectinload(Internship.student))
        .order_by(Milestone.submitted_at)
    ).all()
    logs = db.scalars(
        select(LogEntry).join(Internship).where(Internship.lecturer_id == lecturer.id, LogEntry.status == "pending")
        .options(selectinload(LogEntry.attachments), selectinload(LogEntry.internship).selectinload(Internship.student))
        .order_by(LogEntry.created_at)
    ).all()
    today = clock.today()

    def who(i: Internship) -> dict:
        return {"internship_id": i.id, "student": {"id": i.student.id, "full_name": i.student.full_name}}

    return {
        "milestones": [{
            **milestone_out(m, today), **who(m.internship),
            "missing_evidence": [labels.get(t, t) for t in m.required_evidence
                                 if t not in {e.evidence_type for e in m.evidence}],
            "priority": rank.milestone(m),
        } for m in milestones],
        "logs": [{**log_out(log), **who(log.internship), "priority": rank.log(log)} for log in logs],
    }


# ---------------------------------------------------------------- nhật ký (R5)

@router.get("/internships/{internship_id}/logs")
def list_logs(internship_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    i = load_internship(db, user, internship_id)
    rows = db.scalars(select(LogEntry).where(LogEntry.internship_id == i.id)
                      .options(selectinload(LogEntry.attachments)).order_by(LogEntry.week_no)).all()
    return [log_out(log) for log in rows]


@router.get("/internships/{internship_id}/logs/missing")
def missing_logs(internship_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    """Tuần đã qua mà chưa ghi nhật ký — cùng luật với cờ log_missing; tắt rule trong cohort thì trả rỗng."""
    i = load_internship(db, user, internship_id)
    rule = next((r for r in i.cohort.rules.get("monitor", []) if r["check"] == "weekly_log_missing"), None)
    if rule is None:
        return {"weeks": [], "citation": {}}
    grace = rule.get("params", {}).get("grace_days", DEFAULT_LOG_GRACE_DAYS)
    return {"weeks": missing_log_weeks(i, clock.today(), grace), "citation": rule.get("citation", {})}


@router.post("/internships/{internship_id}/logs", status_code=201)
def create_log(internship_id: int, body: LogIn, user: User = Depends(require_role("student")),
               db: Session = Depends(get_db)) -> dict:
    i = load_internship(db, user, internship_id)
    if i.status not in ("approved", "in_progress"):
        raise HTTPException(status_code=409, detail="Chỉ ghi nhật ký khi hồ sơ đã được duyệt")
    log = LogEntry(internship_id=i.id, week_no=body.week_no, content=body.content,
                   difficulties=body.difficulties, hours=body.hours)
    db.add(log)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Đã có nhật ký tuần {body.week_no}") from exc
    audit.record(db, actor_of(user), "log_entry", log.id, "created", after={"week": body.week_no, "hours": body.hours})
    db.refresh(i)
    monitor.run_for_event(db, i)
    db.commit()
    return log_out(log)


@router.patch("/logs/{log_id}")
def update_log(log_id: int, body: LogIn, user: User = Depends(require_role("student")), db: Session = Depends(get_db)) -> dict:
    log = load_log(db, user, log_id)
    if log.status != "returned":
        raise HTTPException(status_code=409, detail="Chỉ sửa nhật ký đã bị trả lại")
    log.content, log.difficulties, log.hours = body.content, body.difficulties, body.hours
    transition(db, "log_entry", log, "pending", actor_of(user))
    db.commit()
    return log_out(log)


@router.post("/logs/{log_id}/review")
def review_log(log_id: int, body: LogReviewIn, user: User = Depends(require_role("lecturer")),
               db: Session = Depends(get_db)) -> dict:
    log = load_log(db, user, log_id)
    if body.decision == "returned" and not body.comment.strip():
        raise HTTPException(status_code=422, detail="Trả lại nhật ký cần ghi nhận xét")
    transition(db, "log_entry", log, body.decision, actor_of(user), body.comment)
    log.comment = body.comment.strip()
    notify(db, log.internship.student_id, "log", f"Nhật ký tuần {log.week_no}: "
           + ("đã được chấp nhận" if body.decision == "accepted" else "cần bổ sung"), body.comment, link="#/logs")
    db.commit()
    return log_out(log)


@router.post("/logs/{log_id}/attachments", status_code=201)
async def log_attachment(log_id: int, file: UploadFile = File(...), user: User = Depends(require_role("student")),
                         db: Session = Depends(get_db)) -> dict:
    log = load_log(db, user, log_id)
    if log.status == "accepted":
        raise HTTPException(status_code=409, detail="Nhật ký đã được chấp nhận, không đính kèm thêm")
    _, stored = await _store(file)
    ev = Evidence(log_entry_id=log.id, internship_id=log.internship_id, evidence_type="other",
                  filename=stored.filename, path=stored.path, mime=stored.mime, size=stored.size,
                  sha256=stored.sha256, uploaded_by=user.id)
    db.add(ev)
    db.flush()
    audit.record(db, actor_of(user), "log_entry", log.id, "attachment_uploaded", after={"evidence_id": ev.id})
    db.commit()
    return evidence_out(ev)


# ---------------------------------------------------------------- gia hạn (R12)

@router.get("/internships/{internship_id}/extensions")
def list_extensions(internship_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    i = load_internship(db, user, internship_id)
    rows = db.scalars(select(ExtensionRequest).join(Milestone).where(Milestone.internship_id == i.id)
                      .options(joinedload(ExtensionRequest.milestone)).order_by(ExtensionRequest.id.desc())).all()
    return [extension_out(e) for e in rows]


@router.post("/milestones/{milestone_id}/extensions", status_code=201)
def request_extension(milestone_id: int, body: ExtensionIn, user: User = Depends(require_role("student")),
                      db: Session = Depends(get_db)) -> dict:
    m = load_milestone(db, user, milestone_id)
    if m.status == "accepted":
        raise HTTPException(status_code=409, detail="Mốc đã được chấp nhận không được gia hạn (Điều 10 Khoản 3)")
    if db.scalar(select(ExtensionRequest.id).where(ExtensionRequest.milestone_id == m.id,
                                                   ExtensionRequest.status == "open")):
        raise HTTPException(status_code=409, detail="Mốc này đang có yêu cầu gia hạn chờ duyệt")
    if body.requested_due_date <= m.due_date:
        raise HTTPException(status_code=422, detail="Hạn mới phải sau hạn hiện tại")
    limit = m.internship.cohort.rules.get("extension", {})
    today = clock.today()
    grace = limit.get("request_grace_days", DEFAULT_REQUEST_GRACE_DAYS)
    if today > m.due_date + timedelta(days=grace):
        # Quá hạn gửi đề nghị → không còn là gia hạn thường; GV xử lý như ngoại lệ (HITL), hệ thống không tự nhận
        raise HTTPException(status_code=422, detail={
            "message": f"Đề nghị gia hạn phải gửi chậm nhất {grace} ngày sau hạn mốc "
                       f"({m.due_date + timedelta(days=grace):%d/%m/%Y}). Liên hệ giảng viên để xử lý ngoại lệ.",
            "citation": limit.get("citation", {})})
    max_days = limit.get("max_days", DEFAULT_MAX_EXTENSION_DAYS)
    if body.requested_due_date > m.due_date + timedelta(days=max_days):
        raise HTTPException(status_code=422, detail={
            "message": f"Mỗi lần gia hạn không quá {max_days} ngày", "citation": limit.get("citation", {})})
    if body.evidence_id is not None:
        ev = load_evidence(db, user, body.evidence_id)
        if ev.internship_id != m.internship_id:
            raise HTTPException(status_code=422, detail="Minh chứng không thuộc hồ sơ này")
    ext = ExtensionRequest(milestone_id=m.id, requested_by=user.id, previous_due_date=m.due_date,
                           requested_due_date=body.requested_due_date, reason=body.reason.strip(),
                           evidence_id=body.evidence_id)
    db.add(ext)
    db.flush()
    db.refresh(ext)
    audit.record(db, actor_of(user), "extension", ext.id, "created",
                 after={"milestone_id": m.id, "requested_due_date": body.requested_due_date.isoformat()})
    redactor = Redactor({"HO_TEN": user.full_name, "MSSV": user.student_code, "EMAIL": user.email})
    ext.ai_summary = summarize_extension(db, ext, redactor, today)
    notify(db, m.internship.lecturer_id, "approval", f"{user.full_name} xin gia hạn mốc '{m.name}'", link="#/queue")
    db.commit()
    return extension_out(ext)


@router.post("/extensions/{extension_id}/cancel")
def cancel_extension(extension_id: int, user: User = Depends(require_role("student")), db: Session = Depends(get_db)) -> dict:
    ext = load_extension(db, user, extension_id)
    transition(db, "extension", ext, "cancelled", actor_of(user))
    db.commit()
    return extension_out(ext)


@router.post("/extensions/{extension_id}/decision")
def decide_extension(extension_id: int, body: ExtensionDecisionIn, user: User = Depends(require_role("lecturer")),
                     db: Session = Depends(get_db)) -> dict:
    ext = load_extension(db, user, extension_id)
    actor = actor_of(user)
    transition(db, "extension", ext, body.decision, actor, body.reason)
    ext.decided_by = user.id
    ext.decided_at = utcnow()
    ext.decision_reason = body.reason.strip()
    if body.decision == "approved":
        lifecycle.apply_extension(db, ext, actor)
    internship: Internship = ext.milestone.internship
    label = "được duyệt" if body.decision == "approved" else "bị từ chối"
    notify(db, internship.student_id, "decision", f"Yêu cầu gia hạn mốc '{ext.milestone.name}' {label}",
           body.reason, link="#/")
    db.flush()
    monitor.run_for_event(db, internship)
    db.commit()
    return extension_out(ext)
