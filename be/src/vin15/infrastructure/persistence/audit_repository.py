"""Ghi nhật ký kiểm toán chỉ-thêm (``audit_event``)."""

from __future__ import annotations

from psycopg import Connection
from psycopg.types.json import Jsonb

from vin15.domain.model.audit import AuditEntry

from .database import Database


def insert_audit(conn: Connection, entry: AuditEntry) -> int:
    """Ghi một bản ghi bằng kết nối đang mở (để cùng transaction với thay đổi dữ liệu)."""
    row = conn.execute(
        "insert into audit_event (actor_id, actor_kind, actor_role, entity, entity_id, action, before, after, reason) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id",
        (
            entry.actor_id,
            entry.actor_kind.value,
            entry.actor_role,
            entry.entity,
            entry.entity_id,
            entry.action,
            Jsonb(entry.before) if entry.before is not None else None,
            Jsonb(entry.after) if entry.after is not None else None,
            entry.reason,
        ),
    ).fetchone()
    return row["id"]


class AuditRepository:
    def __init__(self, database: Database):
        self._db = database

    def record(self, entry: AuditEntry) -> int:
        with self._db.connection() as conn:
            return insert_audit(conn, entry)
