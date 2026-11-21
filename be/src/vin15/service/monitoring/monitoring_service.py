"""Giám sát chủ động (C1-C8): quét theo luật + nhờ agent đánh giá phần cần LLM; tạo cờ cho GV, nhắc sinh viên theo mẫu cố định.

- Agent **không có công cụ ghi**: BE gửi ảnh chụp đã che PII, agent trả kết luận có cấu trúc, BE kiểm rồi tự ghi cờ (``actor_kind=agent``).
- Chống spam ép ở BE (không tin agent): ≤ 1 lần/ngày, ≤ 3 lần/(mốc, lý do), 07:00-21:00; lần thứ 3 leo thang thành cờ (8.3).
- Cờ không lặp khi chưa đổi và không tái tạo cờ đã bác (dấu vân tay duy nhất trên mỗi hồ sơ).
- Cờ do người xử lý (ghi nhận / giải quyết / bác bỏ có lý do) qua state machine.
"""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import anyio.to_thread

from vin15.domain.authorization import actor_of
from vin15.domain.exception import AgentTimeoutError, AgentUnavailableError, ForbiddenRoleError, ResourceNotFoundError, ScopeDeniedError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import Role, User
from vin15.domain.pii import PiiRedactor
from vin15.domain.statemachine import RISK_FLAG, Subject
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.case_repository import CaseRepository
from vin15.infrastructure.persistence.monitoring_repository import MonitoringRepository
from vin15.service.credit.credit_checklist_service import CreditChecklistService
from vin15.service.monitoring.detector import FlagCandidate, ReminderCandidate, detect, render_reminder
from vin15.service.notification.notification_service import NotificationService

log = logging.getLogger(__name__)

#: Loại cờ agent được tạo (phần cần hiểu nội dung); các loại khác chỉ do luật tất định tạo.
AGENT_FLAG_KINDS = frozenset({"outcome_mismatch", "weak_evidence"})
_SEVERITIES = frozenset({"info", "warning", "critical"})
_TEXT_LIMIT = 1500


class MonitoringService:
    def __init__(
        self,
        monitoring: MonitoringRepository,
        cases: CaseRepository,
        checklist: CreditChecklistService,
        notifications: NotificationService,
        agent: AgentApiClient,
        redactor: PiiRedactor,
        *,
        timezone: str,
        window: tuple[int, int],
        max_per_day: int,
        max_per_milestone: int,
        outcomes_of,
    ):
        self._monitoring = monitoring
        self._cases = cases
        self._checklist = checklist
        self._notifications = notifications
        self._agent = agent
        self._redactor = redactor
        self._zone = ZoneInfo(timezone)
        self._window = window
        self._max_per_day = max_per_day
        self._max_per_milestone = max_per_milestone
        self._outcomes_of = outcomes_of

    # ---- Xem / xử lý cờ ----
    def flags(self, user: User, status: str | None = None, internship_id: int | None = None) -> list[dict]:
        if user.role == Role.STUDENT:
            raise ForbiddenRoleError("Cờ rủi ro chỉ dành cho giảng viên và quản trị viên")
        return self._monitoring.flags(lecturer_id=None if user.role == Role.ADMIN else user.id, status=status or None, internship_id=internship_id)

    def change_flag(self, user: User, flag_id: int, target: str, reason: str = "") -> None:
        flag = self._monitoring.get_flag(flag_id)
        if flag is None:
            raise ResourceNotFoundError("Không tìm thấy cờ")
        actor = actor_of(user)
        if user.role == Role.LECTURER and flag["lecturer_id"] != user.id:
            raise ScopeDeniedError("Cờ này không thuộc sinh viên bạn phụ trách")
        # Cờ không gắn một thực thể sở hữu theo vai trò GV/QTV: kiểm phạm vi ở trên, state machine kiểm vai trò và lý do.
        transition = RISK_FLAG.transition(flag["status"], target, actor, Subject(flag["owner_id"], user.id if user.role == Role.LECTURER else flag["lecturer_id"]), reason)
        self._monitoring.change_flag(flag_id, flag["status"], target, user.id, reason.strip(), RISK_FLAG.audit(transition, actor, flag_id))

    # ---- Quét ----
    async def scan(self, now: datetime | None = None) -> dict:
        """Quét mọi hồ sơ đang hoạt động. Trả về thống kê (số cờ, số nhắc, số cờ do agent)."""
        stats = {"internships": 0, "flags": 0, "reminders": 0, "agent_flags": 0, "agent": "skipped"}
        local_now = (now or datetime.now(self._zone)).astimezone(self._zone)
        today = local_now.date()
        internships = await anyio.to_thread.run_sync(self._monitoring.active_internships)
        agent_ok = self._agent.enabled
        for row in internships:
            stats["internships"] += 1
            snap = await anyio.to_thread.run_sync(self._snapshot, row)
            flags, reminders = detect(row, snap["milestones"], snap["journal_weeks"], snap["evidence"], snap["unmet"], today)
            for candidate in flags:
                if await anyio.to_thread.run_sync(self._create_flag, row, candidate, "system"):
                    stats["flags"] += 1
            for reminder in reminders:
                if await anyio.to_thread.run_sync(self._send_reminder, row, reminder, local_now):
                    stats["reminders"] += 1
            if agent_ok and row["status"] == "in_progress":
                try:
                    stats["agent_flags"] += await self._agent_review(row, snap)
                    stats["agent"] = "ok"
                except (AgentUnavailableError, AgentTimeoutError):
                    agent_ok = False  # LLM không khả dụng: giữ kết quả theo luật, không dừng quét (X5)
                    stats["agent"] = "unavailable"
        return stats

    def _snapshot(self, row: dict) -> dict:
        checklist = self._checklist.checklist_for_internship(row["id"])
        return {
            "milestones": self._cases.milestones(row["id"]),
            "journal_weeks": [j["week_start"] for j in self._cases.journals(row["id"])],
            "journals": self._cases.journals(row["id"]),
            "evidence": [{"id": e["id"], "sha256": self._evidence_sha(e["id"]), "size_bytes": e["size_bytes"]} for e in self._cases.evidence_for_internship(row["id"])],
            "unmet": [{"code": i.code, "value": i.value, "threshold": i.threshold} for i in checklist.items if not i.met],
            "outlines": self._cases.outlines(row["id"]),
        }

    def _evidence_sha(self, evidence_id: int) -> str:
        ev = self._cases.get_evidence(evidence_id)
        return (ev or {}).get("sha256", "")

    def _create_flag(self, row: dict, c: FlagCandidate, created_by: str) -> bool:
        audit = AuditEntry(
            actor_kind=ActorKind.AGENT if created_by == "agent" else ActorKind.SYSTEM,
            entity="risk_flag",
            action="create",
            after={"kind": c.kind, "severity": c.severity, "internship_id": row["id"]},
            reason=c.reason[:300],
        )
        flag_id = self._monitoring.create_flag(row["id"], c.kind, c.severity, c.reason, c.evidence, c.suggestion, c.fingerprint, created_by, audit)
        if flag_id is None:
            return False
        if row["lecturer_id"]:
            self._notifications.notify(
                row["lecturer_id"], f"Cờ rủi ro ({c.severity}): {row['student_name']}", c.reason, kind="risk_flag", link="/lecturer/flags",
                email=c.severity == "critical",  # cờ nghiêm trọng gửi ngay; còn lại vào email tổng hợp hằng ngày (D15)
            )
        return True

    def _send_reminder(self, row: dict, r: ReminderCandidate, now: datetime) -> bool:
        """Nhắc sinh viên theo mẫu cố định, có giới hạn tần suất; lần thứ ``max_per_milestone`` thì leo thang thành cờ cho GV."""
        start, end = self._window
        if not (start <= now.hour < end):
            return False
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if self._monitoring.reminders_count(row["id"], r.milestone_code, r.reason, day_start) >= self._max_per_day:
            return False
        total = self._monitoring.reminders_count(row["id"], r.milestone_code, r.reason)
        if total >= self._max_per_milestone:
            return False
        text = render_reminder(r.template, r.params)
        self._notifications.notify(row["user_id"], "Nhắc nhở thực tập", text, kind="reminder", link="/student", email=True)
        self._monitoring.log_reminder(row["id"], r.milestone_code, r.reason, r.template)
        if total + 1 >= self._max_per_milestone:
            self._create_flag(
                row,
                FlagCandidate(
                    "reminder_escalation", "warning",
                    f"Đã nhắc sinh viên {self._max_per_milestone} lần ({r.reason}{' ' + r.milestone_code if r.milestone_code else ''}) mà chưa có phản hồi.",
                    "Liên hệ trực tiếp với sinh viên.", f"escalation:{r.reason}:{r.milestone_code}",
                    {"reason": r.reason, "milestone": r.milestone_code, "reminders": total + 1},
                ),
                "system",
            )
        return True

    async def _agent_review(self, row: dict, snap: dict) -> int:
        """Nhờ agent đánh giá lệch chuẩn đầu ra / minh chứng yếu từ nội dung đã che PII. BE kiểm kết quả rồi tự ghi cờ."""
        outcomes = await anyio.to_thread.run_sync(lambda: self._outcomes_of(row["cohort"]))
        latest_outline = next((o for o in snap["outlines"] if o["status"] == "approved"), None)
        if not outcomes or latest_outline is None:
            return 0
        redact = self._redactor.redact_text
        payload = {
            "internship_id": row["id"],
            "outcomes": [{"code": o["code"], "description": o["description"]} for o in outcomes],
            "declared_outcome_codes": list(latest_outline["outcome_codes"]),
            "outline": redact(latest_outline["content"])[:_TEXT_LIMIT],
            "journals": [{"week_start": str(j["week_start"]), "content": redact(j["content"])[:_TEXT_LIMIT // 3]} for j in snap["journals"][:8] if j["content"]],
        }
        if not payload["journals"]:
            return 0
        body = await self._agent.call("/v1/monitor/review", payload)
        created = 0
        for finding in body.get("findings", [])[:5]:
            kind, severity = str(finding.get("kind", "")), str(finding.get("severity", "info"))
            reason = str(finding.get("reason", "")).strip()
            if kind not in AGENT_FLAG_KINDS or severity not in _SEVERITIES or not reason:
                continue  # agent chỉ được đề xuất cờ thuộc loại cho phép
            fingerprint = f"agent:{kind}:{len(latest_outline['content'])}:{len(snap['journals'])}"
            candidate = FlagCandidate(kind, severity, reason[:500], str(finding.get("suggestion", ""))[:300], fingerprint, {"source": "agent", "outcomes": finding.get("outcomes", [])})
            if await anyio.to_thread.run_sync(self._create_flag, row, candidate, "agent"):
                created += 1
        return created

    # ---- Email tổng hợp hằng ngày cho GV (D15) ----
    def daily_digest(self, lecturer_ids: list[int], queue_of) -> int:
        sent = 0
        for lecturer_id in lecturer_ids:
            open_flags = self._monitoring.flags(lecturer_id=lecturer_id, status="open")
            queue = queue_of(lecturer_id)
            if not open_flags and not queue:
                continue
            lines = [f"- {f['student_name']}: {f['reason']}" for f in open_flags[:15]]
            lines += [f"- {q['student_name']}: {q['title']}" for q in queue[:15]]
            self._notifications.notify(
                lecturer_id, f"Tổng hợp hằng ngày: {len(open_flags)} cờ, {len(queue)} việc chờ", "\n".join(lines), kind="digest", link="/lecturer", email=True
            )
            sent += 1
        return sent
