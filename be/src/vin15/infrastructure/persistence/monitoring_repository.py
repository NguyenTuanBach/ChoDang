"""Cờ rủi ro, nhật ký nhắc nhở, gợi ý AI (nhóm C). Agent chỉ **tạo** cờ/nhắc; trạng thái cờ do người đổi qua state machine."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from psycopg.types.json import Jsonb

from vin15.domain.model.audit import AuditEntry

from .audit_repository import insert_audit
from .database import Database
from .transitions import NOW, lock_status, set_status

_FLAG_SELECT = (
    "select f.*, i.user_id as owner_id, i.lecturer_id, u.full_name as student_name from risk_flag f "
    "join internship i on i.id = f.internship_id join app_user u on u.id = i.user_id "
)


class MonitoringRepository:
    def __init__(self, database: Database):
        self._db = database

    # ---- Cờ ----
    def create_flag(
        self,
        internship_id: int,
        kind: str,
        severity: str,
        reason: str,
        evidence: dict,
        suggestion: str,
        fingerprint: str,
        created_by_kind: str,
        audit: AuditEntry,
    ) -> int | None:
        """Tạo cờ; ``None`` nếu đã có cờ cùng dấu vân tay (không lặp khi chưa đổi, không tái tạo cờ đã bác — C4, C8)."""
        with self._db.connection() as conn:
            row = conn.execute(
                "insert into risk_flag (internship_id, kind, severity, reason, evidence, suggestion, fingerprint, created_by_kind) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s) on conflict (internship_id, fingerprint) do nothing returning id",
                (internship_id, kind, severity, reason, Jsonb(evidence), suggestion, fingerprint, created_by_kind),
            ).fetchone()
            if row is None:
                return None
            insert_audit(conn, replace(audit, entity_id=row["id"]))
        return row["id"]

    def get_flag(self, flag_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(_FLAG_SELECT + "where f.id = %s", (flag_id,)).fetchone()

    def flags(self, *, lecturer_id: int | None, status: str | None = None, internship_id: int | None = None) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                _FLAG_SELECT + "where (%s::bigint is null or i.lecturer_id = %s) and (%s::text is null or f.status = %s) "
                "and (%s::bigint is null or f.internship_id = %s) "
                "order by case f.severity when 'critical' then 0 when 'warning' then 1 else 2 end, f.created_at desc limit 300",
                (lecturer_id, lecturer_id, status, status, internship_id, internship_id),
            ).fetchall()

    def change_flag(self, flag_id: int, source: str, target: str, decider_id: int, reason: str, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            lock_status(conn, "risk_flag", flag_id, source)
            set_status(conn, "risk_flag", flag_id, target, decided_by=decider_id, decided_at=NOW, decision_reason=reason)
            insert_audit(conn, replace(audit, entity_id=flag_id))

    # ---- Nhắc nhở ----
    def reminders_count(self, internship_id: int, milestone_code: str, reason: str, since: datetime | None = None) -> int:
        with self._db.connection() as conn:
            return conn.execute(
                "select count(*) as n from reminder_log where internship_id = %s and milestone_code = %s and reason = %s "
                "and (%s::timestamptz is null or sent_at >= %s)",
                (internship_id, milestone_code, reason, since, since),
            ).fetchone()["n"]

    def log_reminder(self, internship_id: int, milestone_code: str, reason: str, template: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "insert into reminder_log (internship_id, milestone_code, reason, template) values (%s, %s, %s, %s)",
                (internship_id, milestone_code, reason, template),
            )

    # ---- Gợi ý AI (tiền thẩm) ----
    def add_suggestion(self, internship_id: int, subject_kind: str, subject_id: int, summary: str, details: dict) -> int:
        with self._db.connection() as conn:
            return conn.execute(
                "insert into ai_suggestion (internship_id, subject_kind, subject_id, summary, details) values (%s, %s, %s, %s, %s) returning id",
                (internship_id, subject_kind, subject_id, summary, Jsonb(details)),
            ).fetchone()["id"]

    def suggestions(self, internship_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, subject_kind, subject_id, summary, details, created_at from ai_suggestion "
                "where internship_id = %s order by id desc limit 20",
                (internship_id,),
            ).fetchall()

    # ---- Ứng viên giám sát ----
    def active_internships(self) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select i.id, i.user_id, i.lecturer_id, i.status, i.start_date, i.end_date, i.cohort, u.full_name as student_name "
                "from internship i join app_user u on u.id = i.user_id "
                "where i.status in ('confirmed', 'in_progress', 'pending_credit') and u.status = 'active' order by i.id"
            ).fetchall()
