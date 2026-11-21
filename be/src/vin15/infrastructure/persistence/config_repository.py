"""Cấu hình do QTV quản lý: mẫu mốc (docs mục 9.1) và chuẩn đầu ra theo khóa (Q5)."""

from __future__ import annotations

from vin15.domain.exception import ResourceNotFoundError
from vin15.domain.model.audit import AuditEntry

from .audit_repository import insert_audit
from .database import Database


class ConfigRepository:
    def __init__(self, database: Database):
        self._db = database

    def milestone_templates(self) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute("select code, name, anchor, offset_days from milestone_template order by code").fetchall()

    def update_milestone_template(self, code: str, name: str, anchor: str, offset_days: int, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            row = conn.execute(
                "update milestone_template set name = %s, anchor = %s, offset_days = %s where code = %s returning code",
                (name, anchor, offset_days, code),
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("Không tìm thấy mốc mẫu")
            insert_audit(conn, audit)

    def learning_outcomes(self, cohort: str) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute("select id, cohort, code, description from learning_outcome where cohort = %s order by code", (cohort,)).fetchall()

    def upsert_learning_outcome(self, cohort: str, code: str, description: str, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "insert into learning_outcome (cohort, code, description) values (%s, %s, %s) "
                "on conflict (cohort, code) do update set description = excluded.description",
                (cohort, code, description),
            )
            insert_audit(conn, audit)

    def delete_learning_outcome(self, outcome_id: int, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            row = conn.execute("delete from learning_outcome where id = %s returning id", (outcome_id,)).fetchone()
            if row is None:
                raise ResourceNotFoundError("Không tìm thấy chuẩn đầu ra")
            insert_audit(conn, audit)
