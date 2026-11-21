"""Điểm ưu tiên hàng chờ GV (services/priority.py): luật xác định, có lý do, chỉ để sắp xếp."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from src.core import clock
from src.models.orm import User
from src.services import priority
from tests.test_vin15.conftest import internship_of

TODAY = clock.today()


def _ctx(**cfg):
    return priority.PriorityContext(today=TODAY, now=priority.utcnow(), cfg={**priority._config(), **cfg})


async def test_queue_items_carry_priority_and_overdue_extension_ranks_first(api, db):
    lecturer = db.get(User, internship_of(db, "sv04").lecturer_id).username
    q = (await api.call("GET", "/approvals/queue", lecturer)).json()
    items = [x for key in ("internships", "outlines", "milestones", "extensions", "logs") for x in q[key]]
    assert items and all({"score", "level", "reasons", "since"} <= x["priority"].keys() for x in items)
    ext = q["extensions"][0]["priority"]  # seed: gia hạn cho mốc giấy tiếp nhận đã quá hạn
    assert ext["level"] == "high" and any("đã quá hạn" in r for r in ext["reasons"])
    assert ext["score"] == max(x["priority"]["score"] for x in items)
    for log in q["logs"]:
        assert log["priority"]["score"] < ext["score"]


async def test_internship_starting_soon_gets_reason(api, db):
    i = internship_of(db, "sv02")  # seed: hồ sơ đang chờ duyệt
    i.start_date = TODAY + timedelta(days=2)
    db.commit()
    lecturer = db.get(User, i.lecturer_id).username
    item = next(x for x in (await api.call("GET", "/approvals/queue", lecturer)).json()["internships"] if x["id"] == i.id)
    assert "Bắt đầu thực tập sau 2 ngày" in item["priority"]["reasons"]
    assert item["priority"]["level"] in ("medium", "high")


def test_deadline_rules_and_wait_cap():
    ctx = _ctx()
    assert ctx._deadline(TODAY - timedelta(days=1), "Mốc A") == [(ctx.cfg["deadline_overdue"], "Mốc A đã quá hạn 1 ngày")]
    assert ctx._deadline(TODAY, "Mốc A") == [(ctx.cfg["deadline_soon"], "Mốc A đến hạn hôm nay")]
    assert ctx._deadline(TODAY + timedelta(days=30), "Mốc A") == []
    waited = ctx._score("logs", 0, ctx.now - timedelta(days=100), [])
    assert waited["score"] == ctx.cfg["wait_cap"] and waited["reasons"] == ["Đã chờ 100 ngày"]
    fresh = ctx._score("logs", 0, ctx.now, [])
    assert fresh == {"score": 0, "level": "normal", "reasons": [], "since": fresh["since"]}


def test_risk_flags_raise_priority_and_reasons_sorted_by_weight():
    ctx = _ctx()
    ctx.flags = {7: 3}
    p = ctx._score("milestones", 7, ctx.now - timedelta(days=2), [])
    assert p["reasons"] == ["SV có 3 cảnh báo đang mở", "Đã chờ 2 ngày"]  # nặng hơn đứng trước
    assert p["score"] == ctx.cfg["base"]["milestones"] + ctx.cfg["risk_cap"] + 2 * ctx.cfg["wait_per_day"]


def test_weights_come_from_cohort_yaml(monkeypatch):
    monkeypatch.setattr(priority, "load_cohort_config", lambda: {"priority": {"base": {"logs": 99}, "levels": {"high": 90}}})
    cfg = priority._config()
    assert cfg["base"]["logs"] == 99 and cfg["base"]["extensions"] == priority.DEFAULTS["base"]["extensions"]
    assert cfg["levels"] == {"high": 90, "medium": priority.DEFAULTS["levels"]["medium"]}


def test_context_counts_only_warning_flags_of_own_students(db):
    gv = db.get(User, internship_of(db, "sv04").lecturer_id)
    other = db.scalar(select(User).where(User.role == "lecturer", User.id != gv.id))
    assert priority.context(db, gv).flags.get(internship_of(db, "sv04").id, 0) >= 1
    assert internship_of(db, "sv04").id not in priority.context(db, other).flags
