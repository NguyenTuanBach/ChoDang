"""Gia hạn mốc, ngoại lệ, danh mục loại ngoại lệ, thẩm định công nhận tín chỉ và hàng đợi đồng bộ LMS."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from psycopg.types.json import Jsonb

from vin15.domain.exception import ResourceNotFoundError, StateConflictError
from vin15.domain.model.audit import AuditEntry

from .audit_repository import insert_audit
from .database import Database
from .transitions import NOW, lock_status, set_status

_REQUEST_SELECT = (
    "select r.*, i.user_id as owner_id, i.lecturer_id, i.status as internship_status, u.full_name as student_name, "
    "t.name as exception_type_name from request r join internship i on i.id = r.internship_id join app_user u on u.id = i.user_id "
    "left join exception_type t on t.code = r.exception_type_code "
)


def _entity(audit: AuditEntry, entity_id: int) -> AuditEntry:
    return replace(audit, entity_id=entity_id)


class RequestRepository:
    def __init__(self, database: Database):
        self._db = database

    # ---- Danh mục loại ngoại lệ ----
    def exception_types(self, *, active_only: bool = True) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select code, name, affects_credit, active from exception_type " + ("where active " if active_only else "") + "order by code"
            ).fetchall()

    def get_exception_type(self, code: str) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute("select code, name, affects_credit, active from exception_type where code = %s", (code,)).fetchone()

    def upsert_exception_type(self, code: str, name: str, affects_credit: bool, active: bool, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "insert into exception_type (code, name, affects_credit, active) values (%s, %s, %s, %s) "
                "on conflict (code) do update set name = excluded.name, affects_credit = excluded.affects_credit, active = excluded.active",
                (code, name, affects_credit, active),
            )
            insert_audit(conn, audit)

    # ---- Yêu cầu ----
    def create_request(
        self,
        internship_id: int,
        kind: str,
        *,
        exception_type_code: str | None,
        milestone_code: str | None,
        reason: str,
        new_due_date: date | None,
        affects_credit: bool,
        audit: AuditEntry,
    ) -> int:
        with self._db.connection() as conn:
            if kind == "milestone_extension":
                clash = conn.execute(
                    "select 1 from request where internship_id = %s and kind = 'milestone_extension' and milestone_code = %s and status = 'open'",
                    (internship_id, milestone_code),
                ).fetchone()
                if clash:
                    raise StateConflictError("Đã có yêu cầu gia hạn đang chờ cho mốc này")
            row = conn.execute(
                "insert into request (internship_id, kind, exception_type_code, milestone_code, reason, new_due_date, affects_credit) "
                "values (%s, %s, %s, %s, %s, %s, %s) returning id",
                (internship_id, kind, exception_type_code, milestone_code, reason, new_due_date, affects_credit),
            ).fetchone()
            insert_audit(conn, _entity(audit, row["id"]))
        return row["id"]

    def get_request(self, request_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(_REQUEST_SELECT + "where r.id = %s", (request_id,)).fetchone()

    def requests_for_internship(self, internship_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(_REQUEST_SELECT + "where r.internship_id = %s order by r.created_at desc, r.id desc", (internship_id,)).fetchall()

    def pending_requests(self, decider: str, lecturer_id: int | None) -> list[dict]:
        """Yêu cầu đang chờ người duyệt: GV (loại thường, SV mình phụ trách) hoặc QTV (loại ảnh hưởng tín chỉ)."""
        with self._db.connection() as conn:
            if decider == "admin":
                return conn.execute(_REQUEST_SELECT + "where r.status = 'open' and r.affects_credit order by r.created_at").fetchall()
            return conn.execute(
                _REQUEST_SELECT + "where r.status = 'open' and not r.affects_credit and i.lecturer_id = %s order by r.created_at", (lecturer_id,)
            ).fetchall()

    def decide_request(
        self,
        request_id: int,
        target: str,
        decider_id: int,
        reason: str,
        audit: AuditEntry,
        *,
        milestone_update: tuple[int, date, AuditEntry | None] | None = None,
    ) -> None:
        """Quyết định yêu cầu. Gia hạn được duyệt thì cập nhật hạn mốc (và đưa mốc quá hạn về chờ nộp nếu hạn mới còn hiệu lực)."""
        with self._db.connection() as conn:
            lock_status(conn, "request", request_id, "open")
            set_status(conn, "request", request_id, target, decision_reason=reason, decided_by=decider_id, decided_at=NOW)
            insert_audit(conn, _entity(audit, request_id))
            if milestone_update:
                milestone_id, new_due, revive_audit = milestone_update
                conn.execute("update milestone set due_date = %s where id = %s", (new_due, milestone_id))
                if revive_audit is not None:
                    set_status(conn, "milestone", milestone_id, "pending")
                    insert_audit(conn, _entity(revive_audit, milestone_id))

    def cancel_request(self, request_id: int, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            lock_status(conn, "request", request_id, "open")
            set_status(conn, "request", request_id, "cancelled", decided_at=NOW)
            insert_audit(conn, _entity(audit, request_id))

    def add_attachment(self, request_id: int, filename: str, mime: str, size: int, sha256: str, key: str) -> int:
        with self._db.connection() as conn:
            return conn.execute(
                "insert into request_attachment (request_id, filename, mime, size_bytes, sha256, storage_key) values (%s, %s, %s, %s, %s, %s) returning id",
                (request_id, filename, mime, size, sha256, key),
            ).fetchone()["id"]

    def attachments(self, request_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, filename, mime, size_bytes, uploaded_at from request_attachment where request_id = %s order by id", (request_id,)
            ).fetchall()

    def get_attachment(self, attachment_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(
                "select a.*, r.internship_id, i.user_id as owner_id, i.lecturer_id, r.affects_credit from request_attachment a "
                "join request r on r.id = a.request_id join internship i on i.id = r.internship_id where a.id = %s",
                (attachment_id,),
            ).fetchone()

    # ---- Thẩm định công nhận tín chỉ ----
    def latest_assessment(self, internship_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(
                "select * from credit_assessment where internship_id = %s order by id desc limit 1", (internship_id,)
            ).fetchone()

    def record_lecturer_assessment(
        self,
        internship_id: int,
        passed: bool,
        lecturer_id: int,
        note: str,
        checklist: list[dict],
        assessment_audit: AuditEntry,
        internship_audit: AuditEntry,
    ) -> int:
        """GV thẩm định: đạt → hồ sơ ``credit_review``; chưa đạt → trả về ``in_progress``. Cùng transaction với bản ghi thẩm định."""
        with self._db.connection() as conn:
            lock_status(conn, "internship", internship_id, "pending_credit")
            row = conn.execute(
                "insert into credit_assessment (internship_id, status, checklist, lecturer_id, lecturer_note, lecturer_at) "
                "values (%s, %s, %s, %s, %s, now()) returning id",
                (internship_id, "lecturer_passed" if passed else "lecturer_returned", Jsonb(checklist), lecturer_id, note),
            ).fetchone()
            set_status(conn, "internship", internship_id, "credit_review" if passed else "in_progress", decision_reason="" if passed else note, decided_at=NOW)
            insert_audit(conn, _entity(assessment_audit, row["id"]))
            insert_audit(conn, _entity(internship_audit, internship_id))
        return row["id"]

    def record_admin_decision(
        self,
        internship_id: int,
        approved: bool,
        admin_id: int,
        reason: str,
        assessment_audit: AuditEntry,
        internship_audit: AuditEntry,
        *,
        sync: tuple[str, str, int] | None = None,
    ) -> None:
        """QTV phê duyệt cuối. Duyệt thì tạo việc đồng bộ LMS **trong cùng transaction** (chỉ ghi LMS sau khi duyệt, D8)."""
        with self._db.connection() as conn:
            lock_status(conn, "internship", internship_id, "credit_review")
            assessment = conn.execute(
                "select id, status from credit_assessment where internship_id = %s and status = 'lecturer_passed' order by id desc limit 1 for update",
                (internship_id,),
            ).fetchone()
            if assessment is None:
                raise ResourceNotFoundError("Chưa có thẩm định của giảng viên")
            set_status(conn, "credit_assessment", assessment["id"], "approved" if approved else "denied", admin_id=admin_id, admin_reason=reason, admin_at=NOW)
            set_status(conn, "internship", internship_id, "completed" if approved else "closed_no_credit", decision_reason=reason, decided_at=NOW)
            insert_audit(conn, _entity(assessment_audit, assessment["id"]))
            insert_audit(conn, _entity(internship_audit, internship_id))
            if approved and sync:
                student_code, course_code, credits = sync
                conn.execute(
                    "insert into credit_sync_job (internship_id, student_code, course_code, credits) values (%s, %s, %s, %s) "
                    "on conflict (internship_id) do nothing",
                    (internship_id, student_code, course_code, credits),
                )

    # ---- Hàng đợi đồng bộ LMS ----
    def sync_jobs(self, status: str | None = None) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select j.id, j.internship_id, j.student_code, j.course_code, j.credits, j.status, j.attempts, j.last_error, j.created_at, j.synced_at, "
                "u.full_name as student_name from credit_sync_job j join internship i on i.id = j.internship_id join app_user u on u.id = i.user_id "
                "where (%s::text is null or j.status = %s) order by j.id desc limit 200",
                (status, status),
            ).fetchall()

    def due_sync_jobs(self, limit: int = 10) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, internship_id, student_code, course_code, credits, attempts from credit_sync_job "
                "where status = 'pending' and next_attempt_at <= now() order by id limit %s",
                (limit,),
            ).fetchall()

    def mark_sync(self, job_id: int, ok: bool, error: str, max_attempts: int) -> bool:
        """Cập nhật kết quả đồng bộ. Trả về ``True`` nếu job vừa chuyển sang ``failed`` (hết số lần thử)."""
        with self._db.connection() as conn:
            if ok:
                conn.execute(
                    "update credit_sync_job set status = 'synced', synced_at = now(), attempts = attempts + 1, last_error = '' where id = %s", (job_id,)
                )
                return False
            row = conn.execute(
                "update credit_sync_job set attempts = attempts + 1, last_error = %s, "
                "status = case when attempts + 1 >= %s then 'failed' else 'pending' end, "
                "next_attempt_at = now() + (least(power(2, attempts + 1), 60) || ' minutes')::interval where id = %s returning status",
                (error[:500], max_attempts, job_id),
            ).fetchone()
            return bool(row and row["status"] == "failed")

    def retry_sync(self, job_id: int) -> None:
        with self._db.connection() as conn:
            row = conn.execute(
                "update credit_sync_job set status = 'pending', attempts = 0, next_attempt_at = now() where id = %s and status = 'failed' returning id",
                (job_id,),
            ).fetchone()
            if row is None:
                raise StateConflictError("Chỉ thử lại được việc đồng bộ đã thất bại")


