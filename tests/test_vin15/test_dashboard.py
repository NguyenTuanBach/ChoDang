"""Dashboard toàn khóa: phạm vi theo vai trò, số liệu nhất quán với dữ liệu, chỉ đọc."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select

from src.core import clock
from src.models.orm import AuditEvent, Internship, RiskFlag, User
from tests.test_vin15.conftest import internship_of


async def _dash(api, user):
    r = await api.call("GET", "/dashboard", user)
    assert r.status_code == 200, r.text
    return r.json()


async def test_admin_sees_everything_and_numbers_match_database(api, db):
    d = await _dash(api, "admin")
    total = db.scalar(select(func.count(Internship.id)))
    assert d["scope"] == "all" and d["kpis"]["internships"] == total
    assert sum(s["count"] for s in d["internship_status"]) == total
    open_flags = db.scalar(select(func.count(RiskFlag.id)).where(RiskFlag.open_key.is_not(None)))
    assert d["risk"]["open_flags"] == open_flags == sum(s["count"] for s in d["risk"]["by_severity"])
    # mỗi dòng mốc: các trạng thái cộng lại bằng tổng; % hoàn thành trong 0..100
    for m in d["milestones"]:
        assert m["accepted"] + m["submitted"] + m["pending"] + m["overdue"] + m["rejected"] == m["total"]
        assert 0 <= m["accepted_pct"] <= 100
    assert d["programs"] and sum(p["internships"] for p in d["programs"]) == total


async def test_lecturer_is_scoped_to_assigned_students(api, db):
    admin = await _dash(api, "admin")
    gv = await _dash(api, "gv01")
    mine = db.scalar(select(func.count(Internship.id)).where(
        Internship.lecturer_id == db.scalar(select(User.id).where(User.username == "gv01"))))
    assert gv["scope"] == "assigned" and gv["kpis"]["internships"] == mine < admin["kpis"]["internships"]
    assert [r["name"] for r in gv["lecturers"]] and len(gv["lecturers"]) == 1  # GV chỉ thấy tải của chính mình
    assert all(r["student"] for r in gv["risk"]["at_risk_students"])


async def test_students_cannot_open_dashboard(api):
    assert (await api.call("GET", "/dashboard", "sv03")).status_code == 403


async def test_at_risk_list_is_sorted_by_severity_and_capped(api):
    d = await _dash(api, "admin")
    rank = {"critical": 3, "warning": 2, "info": 1}
    rows = d["risk"]["at_risk_students"]
    assert len(rows) <= 5
    keys = [(rank[r["max_severity"]], r["open_flags"]) for r in rows]
    assert keys == sorted(keys, reverse=True)


async def test_exception_and_extension_stats_reflect_requests(api, db):
    before = (await _dash(api, "admin"))["requests"]
    i = internship_of(db, "sv05")
    body = {"kind": "credit_recognition", "reason": "Đề nghị quy đổi tín chỉ thực tập", "payload": {"credits": 3}}
    ex = (await api.call("POST", f"/internships/{i.id}/exceptions", "sv05", json=body)).json()
    mid = (await _dash(api, "admin"))["requests"]["exceptions"]
    assert mid["total"] == before["exceptions"]["total"] + 1 and mid["open"] == before["exceptions"]["open"] + 1
    await api.call("POST", f"/exceptions/{ex['id']}/decision", "gv02", json={"decision": "approved", "reason": "Đủ điều kiện"})
    after = (await _dash(api, "admin"))["requests"]
    assert after["exceptions"]["approved"] == before["exceptions"]["approved"] + 1
    assert after["exceptions"]["avg_decision_days"] is not None
    assert {"kind": "credit_recognition", "count": 1} in after["exceptions_by_kind"]
    assert before["extensions"]["open"] >= 1  # sv04 có sẵn một yêu cầu gia hạn đang chờ


async def test_log_and_lecturer_workload_numbers(api, db):
    d = await _dash(api, "admin")
    logs = d["logs"]
    assert logs["total"] == logs["accepted"] + logs["returned"] + logs["pending"]
    assert logs["avg_hours_per_week"] is None or logs["avg_hours_per_week"] > 0
    assert sum(r["students"] for r in d["lecturers"]) <= d["kpis"]["internships"]
    assert d["lecturers"] == sorted(d["lecturers"], key=lambda r: r["pending_reviews"], reverse=True)
    assert d["as_of"] == clock.today().isoformat() and clock.today() + timedelta(days=0)


async def test_dashboard_is_read_only(api, db):
    before = db.scalar(select(func.count(AuditEvent.id)))
    await _dash(api, "admin")
    await _dash(api, "gv01")
    db.expire_all()
    assert db.scalar(select(func.count(AuditEvent.id))) == before


def test_empty_scope_returns_none_percentages_without_error(db):
    # Giảng viên chưa có sinh viên nào: mẫu số bằng 0 → phần trăm là None (giao diện hiện "—"), không lỗi chia cho 0
    from src.services.analytics import cohort_dashboard

    nobody = User(id=987654, username="gv-empty", password_hash="x", role="lecturer", full_name="GV chưa có SV")
    d = cohort_dashboard(db, nobody, clock.today())
    assert d["kpis"]["internships"] == 0 and d["kpis"]["milestone_completion_pct"] is None
    assert d["kpis"]["completion_pct"] is None
    assert d["milestones"] == [] and d["lecturers"] == [] and d["programs"] == []
    assert d["risk"]["open_flags"] == 0 and d["risk"]["at_risk_students"] == []
    assert d["logs"]["total"] == 0 and d["logs"]["accepted_pct"] is None and d["logs"]["avg_hours_per_week"] is None
    assert d["requests"]["extensions"]["total"] == 0 and d["requests"]["extensions"]["avg_decision_days"] is None
