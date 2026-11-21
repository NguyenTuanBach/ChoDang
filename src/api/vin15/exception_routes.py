"""Yêu cầu ngoại lệ có lưu vết (gia hạn quá hạn, công nhận quy đổi tín chỉ) — GV quyết định (HITL)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.api.vin15.deps import load_evidence, load_exception, load_internship, scoped_internships
from src.api.vin15.serializers import exception_out
from src.core import clock
from src.core.auth import actor_of, current_user, require_role
from src.db import get_db
from src.models.orm import ExceptionRequest, Internship, User
from src.services import exceptions, monitor
from src.workflow.state_machine import transition

router = APIRouter(tags=["exceptions"])


class ExceptionIn(BaseModel):
    kind: Literal["late_extension", "credit_recognition"]
    reason: str = Field(min_length=10, max_length=2000)
    milestone_id: int | None = None
    payload: dict = Field(default_factory=dict)
    evidence_id: int | None = None


class ExceptionDecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(default="", max_length=2000)


@router.get("/internships/{internship_id}/exceptions")
def list_for_internship(internship_id: int, user: User = Depends(current_user),
                        db: Session = Depends(get_db)) -> list[dict]:
    i = load_internship(db, user, internship_id)
    rows = db.scalars(select(ExceptionRequest).where(ExceptionRequest.internship_id == i.id)
                      .options(joinedload(ExceptionRequest.milestone)).order_by(ExceptionRequest.id.desc())).all()
    return [exception_out(e) for e in rows]


@router.post("/internships/{internship_id}/exceptions", status_code=201)
def create_exception(internship_id: int, body: ExceptionIn, user: User = Depends(require_role("student")),
                     db: Session = Depends(get_db)) -> dict:
    i = load_internship(db, user, internship_id)
    if i.status not in ("approved", "in_progress"):
        raise HTTPException(status_code=409, detail="Chỉ gửi ngoại lệ khi hồ sơ đã được duyệt")
    if body.evidence_id is not None and load_evidence(db, user, body.evidence_id).internship_id != i.id:
        raise HTTPException(status_code=422, detail="Minh chứng không thuộc hồ sơ này")
    req = exceptions.create(db, user, i, body.kind, body.reason, body.milestone_id, body.payload, body.evidence_id,
                            actor_of(user), clock.today())
    db.commit()
    return exception_out(req)


@router.get("/exceptions")
def list_exceptions(status: Literal["open", "decided", "all"] = Query("all"),
                    user: User = Depends(require_role("lecturer", "admin")), db: Session = Depends(get_db)) -> list[dict]:
    stmt = (select(ExceptionRequest).where(ExceptionRequest.internship_id.in_(
        scoped_internships(user).with_only_columns(Internship.id))).order_by(ExceptionRequest.id.desc()))
    if status == "open":
        stmt = stmt.where(ExceptionRequest.status == "open")
    elif status == "decided":
        stmt = stmt.where(ExceptionRequest.status != "open")
    return [exception_out(e) for e in db.scalars(stmt).all()]


@router.post("/exceptions/{exception_id}/cancel")
def cancel_exception(exception_id: int, user: User = Depends(require_role("student")),
                     db: Session = Depends(get_db)) -> dict:
    req = load_exception(db, user, exception_id)
    transition(db, "exception", req, "cancelled", actor_of(user))
    db.commit()
    return exception_out(req)


@router.post("/exceptions/{exception_id}/decision")
def decide_exception(exception_id: int, body: ExceptionDecisionIn, user: User = Depends(require_role("lecturer")),
                     db: Session = Depends(get_db)) -> dict:
    req = load_exception(db, user, exception_id)
    exceptions.decide(db, req, body.decision, body.reason, actor_of(user))
    db.flush()
    monitor.run_for_event(db, req.internship)
    db.commit()
    return exception_out(req)
