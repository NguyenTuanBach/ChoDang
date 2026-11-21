"""AI hỗ trợ đọc minh chứng (services/evidence_review.py): gợi ý cho GV, che PII, không tự quyết."""

from __future__ import annotations

import io

from docx import Document

from src.api.vin15 import progress_routes
from src.models.orm import Evidence, User
from src.seed import _demo_pdf
from src.services import evidence_review
from tests.test_vin15.conftest import internship_of


def _docx(*paragraphs: str) -> bytes:
    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


async def _upload(api, db, student: str, code: str, evidence_type: str, name: str, content: bytes) -> Evidence:
    m = next(m for m in internship_of(db, student).milestones if m.code == code)
    r = await api.call("POST", f"/milestones/{m.id}/evidence", student,
                       data={"evidence_type": evidence_type}, files={"file": (name, content, "application/octet-stream")})
    assert r.status_code == 201, r.text
    return db.get(Evidence, r.json()["id"])


def _report(db, student: str) -> bytes:
    i = internship_of(db, student)
    s = i.student
    return _docx(
        f"Báo cáo giữa kỳ của {s.full_name}, MSSV {s.student_code}, email {s.email}.",
        f"Đơn vị thực tập: {i.company_name}, mã số thuế {i.company_tax_code}.",
        "Công việc đã thực hiện: phân tích yêu cầu và xây dựng API cho module báo cáo nội bộ của nhóm.",
        "Kết quả: hoàn thành thiết kế cơ sở dữ liệu và 12 endpoint, đã có kiểm thử tự động cho từng endpoint.",
        "Khó khăn: chưa quen quy trình review code; giải pháp là đọc tài liệu và hỏi người hướng dẫn hằng ngày.",
    )


async def test_rules_review_checklist_summary_and_limits(api, db):
    ev = await _upload(api, db, "sv03", "giua_ky", "midterm_report", "giua-ky.docx", _report(db, "sv03"))
    r = evidence_review.review_evidence(db, ev)
    assert r["source"] == "rules" and r["evidence_label"] == "Báo cáo giữa kỳ"
    found = {c["item"]: c["found"] for c in r["checklist"]}
    assert found["Mô tả công việc đã làm"] and found["Kết quả đạt được"] and found["Khó khăn và cách xử lý"]
    assert found["Kế hoạch giai đoạn tiếp theo"] is False  # báo cáo không nhắc kế hoạch
    assert r["summary"] and "chữ ký" in r["limits"] and r["warnings"] == []
    assert "Gợi ý của AI" in r["label"]


async def test_llm_receives_redacted_text_only(api, db, monkeypatch):
    sent = {}

    class FakeLLM:
        def invoke(self, messages):
            sent["human"] = messages[1][1]
            return type("R", (), {"content": "Báo cáo mô tả công việc xây dựng API và kết quả đạt được."})()

    monkeypatch.setattr(evidence_review, "llm_available", lambda: True)
    monkeypatch.setattr(evidence_review, "get_llm", lambda task: FakeLLM())
    i = internship_of(db, "sv03")
    ev = await _upload(api, db, "sv03", "giua_ky", "midterm_report", "giua-ky.docx", _report(db, "sv03"))
    r = evidence_review.review_evidence(db, ev)
    assert r["source"] == "llm" and r["summary"].startswith("Báo cáo mô tả")
    for secret in (i.student.full_name, i.student.student_code, i.student.email, i.company_name, i.company_tax_code):
        assert secret.lower() not in sent["human"].lower(), secret
    assert "xây dựng API" in sent["human"]  # nội dung công việc vẫn được gửi để tóm tắt


async def test_duplicate_file_across_students_and_wrong_type_warnings(api, db):
    pdf = _demo_pdf("ban-sao")
    await _upload(api, db, "sv03", "giua_ky", "midterm_report", "a.pdf", pdf)
    ev = await _upload(api, db, "sv05", "danh_gia_dn", "company_evaluation", "b.pdf", pdf)
    r = evidence_review.review_evidence(db, ev)
    assert any("sinh viên khác" in w for w in r["warnings"])
    assert any("gần như không có chữ" in w for w in r["warnings"])  # PDF demo chỉ có 2 dòng
    assert any("tên doanh nghiệp" in w for w in r["warnings"])  # phiếu đánh giá không có tên DN đã đăng ký


async def test_endpoint_is_reviewer_only_and_cached(api, db, monkeypatch):
    ev = await _upload(api, db, "sv03", "giua_ky", "midterm_report", "giua-ky.docx", _report(db, "sv03"))
    lecturer = db.get(User, internship_of(db, "sv03").lecturer_id).username
    calls = []
    real = progress_routes.review_evidence
    monkeypatch.setattr(progress_routes, "review_evidence", lambda d, e: calls.append(e.id) or real(d, e))
    first = (await api.call("GET", f"/evidence/{ev.id}/review", lecturer)).json()
    second = (await api.call("GET", f"/evidence/{ev.id}/review", lecturer)).json()
    assert first == second and first["checklist"] and calls == [ev.id]  # lần 2 lấy từ DB
    assert (await api.call("GET", f"/evidence/{ev.id}/review", "sv03")).status_code == 403
    other = "gv01" if lecturer != "gv01" else "gv02"
    assert (await api.call("GET", f"/evidence/{ev.id}/review", other)).status_code == 403


async def test_failure_is_not_cached_and_reports_unavailable(api, db, monkeypatch):
    ev = await _upload(api, db, "sv03", "giua_ky", "midterm_report", "giua-ky.docx", _report(db, "sv03"))
    lecturer = db.get(User, internship_of(db, "sv03").lecturer_id).username
    monkeypatch.setattr(evidence_review, "load_cohort_config", lambda: 1 / 0)  # lỗi bất kỳ bên trong
    assert (await api.call("GET", f"/evidence/{ev.id}/review", lecturer)).json() == {"unavailable": True}
    db.expire_all()
    assert db.get(Evidence, ev.id).ai_review is None
