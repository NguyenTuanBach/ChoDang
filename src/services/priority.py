"""Điểm ưu tiên cho hàng chờ duyệt của GV — luật xác định, luôn kèm lý do hiển thị.

Không dùng AI để xếp hạng: thứ tự hiển thị quyết định đơn nào được xử lý trước, nên phải
giải thích được và test được; chấm "mức khẩn" bằng model còn phải gửi lý do cá nhân của SV
sang model. Điểm chỉ dùng để SẮP XẾP — không đơn nào được tự duyệt/từ chối (HITL).

Trọng số ở `priority` trong config/cohort.yaml; thiếu khóa nào thì dùng DEFAULTS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.core import clock
from src.models.orm import (
    ExceptionRequest,
    ExtensionRequest,
    Internship,
    LogEntry,
    Milestone,
    Outline,
    RiskFlag,
    User,
    utcnow,
)
from src.workflow.rules import load_cohort_config

DEFAULTS: dict = {
    # điểm nền theo loại: gia hạn chặn tiến độ SV nên cao nhất, nhật ký thấp nhất
    "base": {"exceptions": 25, "extensions": 20, "internships": 15, "outlines": 15, "milestones": 10, "logs": 0},
    "deadline_overdue": 50,  # hạn liên quan đã qua (SV đang bị chặn)
    "deadline_soon": 30,  # hạn liên quan còn ≤ deadline_days ngày
    "deadline_days": 3,
    "start_soon": 30,  # hồ sơ chờ duyệt, ngày bắt đầu thực tập còn ≤ start_days ngày
    "start_days": 7,
    "wait_per_day": 2,  # mỗi ngày chờ
    "wait_cap": 20,
    "risk_per_flag": 10,  # mỗi cờ mức warning trở lên đang mở của SV
    "risk_cap": 20,
    "levels": {"high": 50, "medium": 25},
}


def _config() -> dict:
    cfg = {**DEFAULTS, **load_cohort_config().get("priority", {})}
    cfg["base"] = {**DEFAULTS["base"], **cfg.get("base", {})}
    cfg["levels"] = {**DEFAULTS["levels"], **cfg.get("levels", {})}
    return cfg


@dataclass
class PriorityContext:
    today: date
    now: datetime  # UTC naive, cùng quy ước với các cột DateTime
    cfg: dict
    flags: dict[int, int] = field(default_factory=dict)  # internship_id → số cờ warning+ đang mở

    # ------------------------------------------------------------ từng loại mục

    def internship(self, i: Internship) -> dict:
        reasons = []
        if i.start_date:
            left = (i.start_date - self.today).days
            if left < 0:
                reasons.append((self.cfg["deadline_overdue"], f"Ngày bắt đầu thực tập đã qua {-left} ngày"))
            elif left <= self.cfg["start_days"]:
                reasons.append((self.cfg["start_soon"], "Bắt đầu thực tập hôm nay" if left == 0
                                else f"Bắt đầu thực tập sau {left} ngày"))
        return self._score("internships", i.id, i.updated_at, reasons)

    def outline(self, o: Outline) -> dict:
        due = next((m.due_date for m in o.internship.milestones if m.linked_to == "outline"), None)
        return self._score("outlines", o.internship_id, o.submitted_at, self._deadline(due, "Hạn đề cương"))

    def exception(self, e: ExceptionRequest) -> dict:
        reasons = self._deadline(e.milestone.due_date, f"Mốc '{e.milestone.name}'") if e.milestone else []
        return self._score("exceptions", e.internship_id, e.created_at, reasons)

    def extension(self, e: ExtensionRequest) -> dict:
        m = e.milestone
        return self._score("extensions", m.internship_id, e.created_at, self._deadline(m.due_date, f"Mốc '{m.name}'"))

    def milestone(self, m: Milestone) -> dict:
        return self._score("milestones", m.internship_id, m.submitted_at, [])

    def log(self, log: LogEntry) -> dict:
        return self._score("logs", log.internship_id, log.created_at, [])

    # ------------------------------------------------------------ luật chung

    def _deadline(self, due: date | None, label: str) -> list[tuple[int, str]]:
        if due is None:
            return []
        left = (due - self.today).days
        if left < 0:
            return [(self.cfg["deadline_overdue"], f"{label} đã quá hạn {-left} ngày")]
        if left <= self.cfg["deadline_days"]:
            return [(self.cfg["deadline_soon"], f"{label} đến hạn hôm nay" if left == 0 else f"{label} còn {left} ngày")]
        return []

    def _score(self, kind: str, internship_id: int, since: datetime | None, reasons: list[tuple[int, str]]) -> dict:
        reasons = list(reasons)
        if since is not None and (days := (self.now - since).days) >= 1:
            reasons.append((min(days * self.cfg["wait_per_day"], self.cfg["wait_cap"]), f"Đã chờ {days} ngày"))
        if n := self.flags.get(internship_id, 0):
            reasons.append((min(n * self.cfg["risk_per_flag"], self.cfg["risk_cap"]), f"SV có {n} cảnh báo đang mở"))
        score = self.cfg["base"].get(kind, 0) + sum(points for points, _ in reasons)
        levels = self.cfg["levels"]
        level = "high" if score >= levels["high"] else "medium" if score >= levels["medium"] else "normal"
        return {
            "score": score, "level": level,
            "reasons": [text for points, text in sorted(reasons, key=lambda r: -r[0]) if points > 0],
            "since": since.isoformat() if since else None,
        }


def context(db: Session, lecturer: User) -> PriorityContext:
    """1 query đếm cờ đang mở (warning+) theo hồ sơ của GV — dùng chung cho cả hàng chờ."""
    rows = db.execute(
        select(RiskFlag.internship_id, func.count()).join(Internship, Internship.id == RiskFlag.internship_id)
        .where(Internship.lecturer_id == lecturer.id, RiskFlag.open_key.is_not(None),
               RiskFlag.severity.in_(("warning", "critical")))
        .group_by(RiskFlag.internship_id)
    )
    return PriorityContext(today=clock.today(), now=utcnow(), cfg=_config(), flags=dict(rows.all()))
