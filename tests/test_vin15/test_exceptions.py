"""Yêu cầu ngoại lệ có lưu vết: tạo, quyền, HITL, hệ quả khi duyệt, audit."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.core import clock
from src.models.orm import AuditEvent, ExceptionRequest, Milestone
from tests.test_vin15.conftest import internship_of


def _late(db, username="sv04"):
    i = internship_of(db, username)
    m = next(m for m in i.milestones if m.status == "overdue")
    return i, m, {
        "kind": "late_extension", "milestone_id": m.id, "reason": "Doanh nghiệp đổi lịch, xin gia hạn quá hạn",
        "payload": {"requested_due_date": (clock.today() + timedelta(days=5)).isoformat()},
    }


async def test_create_and_approve_late_extension(api, db):
    i, m, body = _late(db)
    r = await api.call("POST", f"/internships/{i.id}/exceptions", "sv04", json=body)
    assert r.status_code == 201, r.text
    ex = r.json()
    assert ex["status"] == "open" and ex["ai_summary"]["label"]

    queue = (await api.call("GET", "/approvals/queue", "gv01")).json()
    assert [e["id"] for e in queue["exceptions"]] == [ex["id"]]

    # thiếu lý do → 422, hạn giữ nguyên
    r = await api.call("POST", f"/exceptions/{ex['id']}/decision", "gv01", json={"decision": "approved", "reason": ""})
    assert r.status_code == 422
    r = await api.call("POST", f"/exceptions/{ex['id']}/decision", "gv01",
                       json={"decision": "approved", "reason": "Có xác nhận của doanh nghiệp"})
    assert r.status_code == 200 and r.json()["status"] == "approved"

    db.expire_all()
    m2 = db.get(Milestone, m.id)
    assert m2.due_date.isoformat() == body["payload"]["requested_due_date"] and m2.status == "pending"
    trail = (await api.call("GET", f"/internships/{i.id}/audit", "gv01")).json()
    assert any(e["entity"] == "exception" and e["action"] == "status:open->approved" for e in trail)
    assert any(e["action"] == "due_date_changed" and e["after"]["exception_id"] == ex["id"] for e in trail)


async def test_credit_recognition_only_records_decision(api, db):
    i = internship_of(db, "sv05")
    body = {"kind": "credit_recognition", "reason": "Đề nghị quy đổi tín chỉ thực tập", "payload": {"credits": 4}}
    ex = (await api.call("POST", f"/internships/{i.id}/exceptions", "sv05", json=body)).json()
    r = await api.call("POST", f"/exceptions/{ex['id']}/decision", "gv02",
                       json={"decision": "rejected", "reason": "Chưa đủ giờ thực tập"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"


async def test_validation_and_duplicates(api, db):
    i, m, body = _late(db)
    bad = {**body, "payload": {"requested_due_date": (m.due_date - timedelta(days=1)).isoformat()}}
    assert (await api.call("POST", f"/internships/{i.id}/exceptions", "sv04", json=bad)).status_code == 422
    far = {**body, "payload": {"requested_due_date": (m.due_date + timedelta(days=90)).isoformat()}}
    assert (await api.call("POST", f"/internships/{i.id}/exceptions", "sv04", json=far)).status_code == 422
    r = await api.call("POST", f"/internships/{i.id}/exceptions", "sv04", json=body)
    assert r.status_code == 201
    assert (await api.call("POST", f"/internships/{i.id}/exceptions", "sv04", json=body)).status_code == 409
    assert (await api.call("POST", f"/exceptions/{r.json()['id']}/cancel", "sv04")).json()["status"] == "cancelled"
    zero = {"kind": "credit_recognition", "reason": "Quy đổi tín chỉ thực tập", "payload": {"credits": 0}}
    assert (await api.call("POST", f"/internships/{i.id}/exceptions", "sv04", json=zero)).status_code == 422


async def test_access_control_and_hitl(api, db):
    i, _, body = _late(db)
    ex = (await api.call("POST", f"/internships/{i.id}/exceptions", "sv04", json=body)).json()
    decision = {"decision": "approved", "reason": "ok lý do"}
    # SV không tự duyệt; SV khác không xem được
    assert (await api.call("POST", f"/exceptions/{ex['id']}/decision", "sv04", json=decision)).status_code == 403
    assert (await api.call("GET", f"/internships/{i.id}/exceptions", "sv05")).status_code == 403
    assert (await api.call("POST", f"/internships/{i.id}/exceptions", "gv01", json=body)).status_code == 403
    # chưa quyết định thì không đổi hạn
    db.expire_all()
    assert db.get(ExceptionRequest, ex["id"]).status == "open"
    denied = db.scalars(select(AuditEvent).where(AuditEvent.action == "access_denied")).all()
    assert denied


async def test_list_scoped_for_lecturer(api, db):
    i, _, body = _late(db)
    await api.call("POST", f"/internships/{i.id}/exceptions", "sv04", json=body)
    rows = (await api.call("GET", "/exceptions?status=open", "gv01")).json()
    assert len(rows) == 1
    assert (await api.call("GET", "/exceptions", "sv04")).status_code == 403


def _row(i, kind="credit_recognition", milestone_id=None, status="open"):
    return ExceptionRequest(internship_id=i.id, kind=kind, milestone_id=milestone_id, requested_by=i.student_id,
                            reason="Đề nghị ngoại lệ", payload={}, status=status)


def test_db_rejects_duplicate_open_exception_even_if_precheck_is_bypassed(db):
    # Mô phỏng đua: hai bản ghi mở cùng (hồ sơ, loại, mốc) — kiểm tra trước khi ghi có thể cùng lọt qua
    i = internship_of(db, "sv05")
    db.add(_row(i))
    db.flush()
    db.add(_row(i))  # milestone_id NULL cũng phải bị coi là trùng (COALESCE)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_db_allows_new_open_exception_after_previous_one_is_closed(db):
    i = internship_of(db, "sv05")
    db.add(_row(i, status="cancelled"))
    db.add(_row(i, status="rejected"))
    db.add(_row(i))
    db.flush()  # chỉ bản "open" bị ràng buộc; đã đóng thì tạo lại được
    other_kind = _row(i, kind="late_extension", milestone_id=i.milestones[0].id)
    db.add(other_kind)
    db.flush()
