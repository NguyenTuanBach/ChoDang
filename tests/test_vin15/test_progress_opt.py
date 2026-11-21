"""Tối ưu nhóm 2: múi giờ (OQ-9), overdue tức thì, số query không tăng theo số hồ sơ (N+1), sửa lỗi nhỏ."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import event, select

from src.api.vin15.monitor_routes import list_flags
from src.api.vin15.summary_routes import Filters, build_rows
from src.core import clock
from src.models.orm import Cohort, Evidence, Internship, LogEntry, Notification, User
from src.seed import _demo_pdf
from src.services import monitor
from src.services.lifecycle import generate_milestones
from tests.test_vin15.conftest import internship_of

TODAY = clock.today()
VN = ZoneInfo("Asia/Ho_Chi_Minh")
PDF = _demo_pdf("test")
FAKE_PDF = b"%PDF-1.4\n%test\n%%EOF\n"  # qua kiểm tra magic bytes nhưng không mở được


def _png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- múi giờ + lịch chạy

def test_local_midnight_is_converted_to_utc():
    # 00:00 18/11 giờ VN = 17:00 17/11 UTC
    assert clock.local_midnight_utc(datetime(2026, 11, 18).date()) == datetime(2026, 11, 17, 17, 0)


def test_scheduler_runs_status_job_after_midnight_and_full_run_at_monitor_hour():
    at, full = monitor.next_run(datetime(2026, 11, 18, 23, 0, tzinfo=VN), 7)
    assert at == datetime(2026, 11, 19, 0, 5, tzinfo=VN) and not full
    at, full = monitor.next_run(datetime(2026, 11, 19, 0, 5, tzinfo=VN), 7)
    assert at == datetime(2026, 11, 19, 7, 0, tzinfo=VN) and full
    at, full = monitor.next_run(datetime(2026, 11, 19, 7, 0, tzinfo=VN), 7)
    assert at == datetime(2026, 11, 20, 0, 5, tzinfo=VN) and not full


def test_milestone_becomes_overdue_on_event_without_daily_job(db):
    i = internship_of(db, "sv05")
    m = next(m for m in i.milestones if m.status == "pending")
    m.due_date = TODAY - timedelta(days=1)
    db.flush()
    monitor.run_for_event(db, i)
    assert m.status == "overdue"
    assert any(f.flag_type == "overdue" and f.milestone_id == m.id for f in monitor._open_flags(db, [i.id])[i.id])


# ---------------------------------------------------------------- N+1

def _add_internships(db, start: int, n: int) -> None:
    cohort = db.scalar(select(Cohort))
    gv = db.scalar(select(User).where(User.username == "gv01"))
    for k in range(start, start + n):
        sv = User(username=f"load{k}", password_hash="x", role="student", full_name=f"SV tải {k}",
                  student_code=f"LT{k:05d}", program="CNTT", lecturer_id=gv.id)
        db.add(sv)
        db.flush()
        i = Internship(student_id=sv.id, lecturer_id=gv.id, cohort_id=cohort.id, status="in_progress",
                       company_name=f"Công ty {k}", start_date=TODAY - timedelta(days=30),
                       end_date=TODAY + timedelta(days=40))
        db.add(i)
        db.flush()
        generate_milestones(i)
        db.add(LogEntry(internship_id=i.id, week_no=1, content="Tuần đầu làm quen", hours=5))
    db.commit()


def _count_queries(db, fn) -> int:
    engine = db.get_bind()
    count = 0

    def on_execute(*_):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", on_execute)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", on_execute)
    return count


def test_query_count_does_not_grow_with_internships(db):
    gv = db.scalar(select(User).where(User.username == "gv01"))
    admin = db.scalar(select(User).where(User.username == "admin"))

    def measure() -> tuple[int, int, int]:
        monitor.run_all(db, TODAY)  # lần đầu có thể tạo cờ; đo lần thứ hai (không còn gì để ghi)
        db.expire_all()
        return (
            _count_queries(db, lambda: monitor.run_all(db, TODAY)),
            _count_queries(db, lambda: build_rows(db, admin, Filters(q=None))),
            _count_queries(db, lambda: list_flags(status="open", user=gv, db=db)),
        )

    _add_internships(db, 0, 3)
    small = measure()
    _add_internships(db, 3, 30)
    db.expire_all()
    assert measure() == small


# ---------------------------------------------------------------- sửa lỗi nhỏ

async def test_extension_must_be_requested_within_3_days_after_due(api, db):
    i = internship_of(db, "sv03")
    m = next(m for m in i.milestones if m.code == "giua_ky")
    body = {"reason": "Doanh nghiệp đổi lịch dự án"}
    m.due_date = TODAY - timedelta(days=4)
    db.commit()
    r = await api.call("POST", f"/milestones/{m.id}/extensions", "sv03",
                       json={**body, "requested_due_date": (TODAY + timedelta(days=5)).isoformat()})
    assert r.status_code == 422 and r.json()["detail"]["citation"]["path"] == "Điều 10 / Khoản 2"
    m.due_date = TODAY - timedelta(days=3)
    db.commit()
    r = await api.call("POST", f"/milestones/{m.id}/extensions", "sv03",
                       json={**body, "requested_due_date": (TODAY + timedelta(days=5)).isoformat()})
    assert r.status_code == 201, r.text


async def test_templates_reject_unknown_evidence_and_second_outline_link(api):
    cohort = (await api.call("GET", "/admin/cohort", "admin")).json()
    base = [{k: t[k] for k in ("code", "name", "anchor", "offset_days", "required_evidence", "linked_to", "citation")}
            for t in cohort["templates"]]
    bad = [*base, {"code": "x1", "name": "Mốc lạ", "anchor": "end", "offset_days": 1, "required_evidence": ["video"]}]
    r = await api.call("PUT", "/admin/cohort/templates", "admin", json=bad)
    assert r.status_code == 422 and "video" in r.json()["detail"]
    two = [*base, {"code": "x2", "name": "Đề cương lần 2", "anchor": "mid", "offset_days": 0, "linked_to": "outline"}]
    assert (await api.call("PUT", "/admin/cohort/templates", "admin", json=two)).status_code == 422


async def test_missing_file_on_disk_is_404(api, db):
    m = next(m for m in internship_of(db, "sv03").milestones if m.code == "giua_ky")
    r = await api.call("POST", f"/milestones/{m.id}/evidence", "sv03",
                       data={"evidence_type": "midterm_report"}, files={"file": ("bc.pdf", PDF, "application/pdf")})
    assert r.status_code == 201
    url = (await api.call("GET", f"/evidence/{r.json()['id']}/url", "sv03")).json()["url"]
    Path(db.get(Evidence, r.json()["id"]).path).unlink()
    assert (await api.client.get(url)).status_code == 404


async def test_cannot_attach_to_accepted_log(api, db):
    i = internship_of(db, "sv03")
    lecturer = db.get(User, i.lecturer_id).username
    log = i.logs[0]
    r = await api.call("POST", f"/logs/{log.id}/review", lecturer, json={"decision": "accepted"})
    assert r.status_code == 200
    r = await api.call("POST", f"/logs/{log.id}/attachments", "sv03", files={"file": ("a.pdf", PDF, "application/pdf")})
    assert r.status_code == 409


async def test_queue_lists_submitted_milestones_and_pending_logs(api, db):
    i = internship_of(db, "sv03")
    lecturer = db.get(User, i.lecturer_id).username
    m = next(m for m in i.milestones if m.code == "giua_ky")
    r = await api.call("POST", f"/milestones/{m.id}/evidence", "sv03",
                       data={"evidence_type": "other"}, files={"file": ("phu-luc.pdf", PDF, "application/pdf")})
    assert r.status_code == 201
    assert (await api.call("POST", f"/milestones/{m.id}/submit", "sv03")).status_code == 200
    q = (await api.call("GET", "/approvals/queue", lecturer)).json()
    item = next(x for x in q["milestones"] if x["id"] == m.id)
    assert item["student"]["full_name"] == db.get(User, i.student_id).full_name
    assert item["missing_evidence"] == ["Báo cáo giữa kỳ"] and item["evidence"][0]["filename"] == "phu-luc.pdf"
    assert {log["id"] for log in q["logs"]} == {log.id for log in i.logs if log.status == "pending"}
    # GV khác không thấy mục của SV không được phân công
    other = "gv01" if lecturer != "gv01" else "gv02"
    assert m.id not in [x["id"] for x in (await api.call("GET", "/approvals/queue", other)).json()["milestones"]]


async def test_evidence_preview_inline_pdf_image_and_docx_text(api, db):
    import io

    from docx import Document

    m = next(m for m in internship_of(db, "sv03").milestones if m.code == "giua_ky")

    async def upload(name, content, mime):
        r = await api.call("POST", f"/milestones/{m.id}/evidence", "sv03",
                           data={"evidence_type": "other"}, files={"file": (name, content, mime)})
        return r.json()["id"]

    # File hỏng nộp TRƯỚC khi có check_readable (dữ liệu cũ) → preview báo "broken" kèm lý do
    from src.config import get_settings

    legacy = Path(get_settings().upload_dir) / "legacy.pdf"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(FAKE_PDF)
    ev = Evidence(milestone_id=m.id, internship_id=m.internship_id, evidence_type="other", filename="cu.pdf",
                  path=str(legacy), mime="application/pdf", size=len(FAKE_PDF), sha256="x", uploaded_by=m.internship.student_id)
    db.add(ev)
    db.commit()
    p = (await api.call("GET", f"/evidence/{ev.id}/preview", "sv03")).json()
    assert p["kind"] == "broken" and "hỏng" in p["problem"]

    pdf_id = await upload("bc.pdf", PDF, "application/pdf")
    p = (await api.call("GET", f"/evidence/{pdf_id}/preview", "sv03")).json()
    assert p["kind"] == "pdf" and p["url"].endswith("&inline=1")
    r = await api.client.get(p["url"])
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert (await api.client.get(p["download_url"])).headers["content-disposition"].startswith("attachment")

    png_id = await upload("anh.png", _png(), "image/png")
    assert (await api.call("GET", f"/evidence/{png_id}/preview", "sv03")).json()["kind"] == "image"

    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Báo cáo giữa kỳ: hoàn thành module API")
    doc.save(buf)
    docx_id = await upload("bc.docx", buf.getvalue(), "application/octet-stream")
    p = (await api.call("GET", f"/evidence/{docx_id}/preview", "sv03")).json()
    assert p["kind"] == "text" and "module API" in p["text"]
    # docx không bao giờ trả inline, kể cả khi client xin inline=1
    r = await api.client.get(p["download_url"] + "&inline=1")
    assert r.headers["content-disposition"].startswith("attachment")
    assert (await api.call("GET", f"/evidence/{pdf_id}/preview", "sv04")).status_code == 403


async def test_upload_rejects_unreadable_files(api, db):
    import io

    from pypdf import PdfWriter

    m = next(m for m in internship_of(db, "sv03").milestones if m.code == "giua_ky")

    async def upload(name, content):
        return await api.call("POST", f"/milestones/{m.id}/evidence", "sv03",
                              data={"evidence_type": "other"}, files={"file": (name, content, "application/octet-stream")})

    r = await upload("hong.pdf", FAKE_PDF)
    assert r.status_code == 422 and "PDF bị hỏng" in r.json()["detail"]
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.encrypt("matkhau")
    locked = io.BytesIO()
    writer.write(locked)
    r = await upload("khoa.pdf", locked.getvalue())
    assert r.status_code == 422 and "mật khẩu" in r.json()["detail"]
    r = await upload("gia.docx", b"PK\x03\x04" + b"0" * 64)
    assert r.status_code == 422 and "Word" in r.json()["detail"]
    r = await upload("hong.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32)
    assert r.status_code == 422 and "ảnh" in r.json()["detail"]
    assert (await upload("ok.pdf", PDF)).status_code == 201
    assert (await upload("ok.png", _png())).status_code == 201


async def test_read_all_and_assignment_notifications(api, db):
    sv = db.scalar(select(User).where(User.username == "sv03"))
    gv = db.scalar(select(User).where(User.username == "gv02"))
    assert (await api.call("POST", "/admin/assign", "admin", json={"student_id": sv.id, "lecturer_id": gv.id})).status_code == 200
    assert any(n["kind"] == "assignment" for n in (await api.call("GET", "/notifications", "gv02")).json())
    unread = db.scalars(select(Notification).where(Notification.user_id == sv.id, Notification.read_at.is_(None))).all()
    assert (await api.call("POST", "/notifications/read-all", "sv03")).json() == {"marked": len(unread)}
    assert (await api.call("POST", "/notifications/read-all", "sv03")).json() == {"marked": 0}
