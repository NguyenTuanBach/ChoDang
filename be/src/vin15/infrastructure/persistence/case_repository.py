"""Hồ sơ thực tập (ghi + đọc đầy đủ), đề cương, mốc, nhật ký, minh chứng. Mỗi thao tác đổi trạng thái chạy trong **một transaction**
cùng bản ghi audit (BR-S3); service tính sẵn ``AuditEntry`` bằng state machine rồi chuyển xuống đây.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from psycopg.types.json import Jsonb

from vin15.domain.exception import ResourceNotFoundError, StateConflictError
from vin15.domain.model.audit import ActorKind, AuditEntry

from .audit_repository import insert_audit
from .database import Database
from .transitions import NOW, lock_status, set_status

PROFILE_FIELDS = (
    "company_name",
    "company_tax_code",
    "company_address",
    "position",
    "mentor_name",
    "mentor_email",
    "mentor_phone",
    "job_description",
    "start_date",
    "end_date",
    "mode",
)

_INTERNSHIP_SELECT = (
    "select i.*, u.full_name as student_name, u.email as student_email, u.student_code, l.full_name as lecturer_name "
    "from internship i join app_user u on u.id = i.user_id left join app_user l on l.id = i.lecturer_id "
)


class CaseRepository:
    def __init__(self, database: Database):
        self._db = database

    # ------------------------------------------------------------------ hồ sơ ----
    def get_internship(self, internship_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(_INTERNSHIP_SELECT + "where i.id = %s", (internship_id,)).fetchone()

    def student_internship(self, user_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(_INTERNSHIP_SELECT + "where i.user_id = %s order by i.id desc limit 1", (user_id,)).fetchone()

    def create_internship(self, user_id: int, cohort: str, lecturer_id: int | None, audit: AuditEntry) -> int:
        with self._db.connection() as conn:
            row = conn.execute(
                "insert into internship (user_id, cohort, status, lecturer_id) values (%s, %s, 'draft', %s) "
                "on conflict (user_id, cohort) do nothing returning id",
                (user_id, cohort, lecturer_id),
            ).fetchone()
            if row is None:
                raise StateConflictError("Sinh viên đã có hồ sơ thực tập trong khóa này")
            insert_audit(conn, _entity(audit, row["id"]))
        return row["id"]

    def update_profile(self, internship_id: int, fields: dict[str, Any], confirmations: dict[str, str] | None) -> None:
        """Sửa nội dung nháp; chỉ khi hồ sơ ở ``draft`` hoặc ``revision_requested`` (đã nộp thì không sửa tại chỗ, BR-S4)."""
        clean = {k: v for k, v in fields.items() if k in PROFILE_FIELDS}
        with self._db.connection() as conn:
            row = conn.execute("select status, field_confirmations from internship where id = %s for update", (internship_id,)).fetchone()
            if row is None:
                raise ResourceNotFoundError("Không tìm thấy hồ sơ")
            if row["status"] not in ("draft", "revision_requested"):
                raise StateConflictError("Hồ sơ đã nộp, không sửa tại chỗ")
            merged = {**row["field_confirmations"], **(confirmations or {})}
            assignments = [f"{name} = %s" for name in clean] + ["field_confirmations = %s"]
            conn.execute(
                f"update internship set {', '.join(assignments)} where id = %s", [*clean.values(), Jsonb(merged), internship_id]
            )

    def submit_internship(self, internship_id: int, source: str, audit: AuditEntry) -> None:
        """Nộp hồ sơ: chụp một phiên bản (BR-S4) và chuyển trạng thái."""
        with self._db.connection() as conn:
            row = lock_status(conn, "internship", internship_id, source)
            version = row["version"] + 1 if source == "revision_requested" else row["version"]
            snapshot = {k: _jsonable(row[k]) for k in (*PROFILE_FIELDS, "field_confirmations")}
            conn.execute(
                "insert into internship_revision (internship_id, version, snapshot) values (%s, %s, %s)",
                (internship_id, version, Jsonb(snapshot)),
            )
            set_status(conn, "internship", internship_id, "submitted", version=version, submitted_at=NOW, decision_reason="")
            insert_audit(conn, _entity(audit, internship_id))

    def decide_internship(
        self,
        internship_id: int,
        source: str,
        target: str,
        audit: AuditEntry,
        *,
        reason: str = "",
        milestones: list[dict] | None = None,
    ) -> None:
        """Quyết định về hồ sơ (xác nhận / yêu cầu sửa / từ chối ...). Xác nhận có thể kèm sinh mốc từ mẫu trong cùng transaction."""
        with self._db.connection() as conn:
            lock_status(conn, "internship", internship_id, source)
            set_status(conn, "internship", internship_id, target, decision_reason=reason, decided_at=NOW)
            for m in milestones or []:
                conn.execute(
                    "insert into milestone (internship_id, code, name, due_date, status, decided_at) values (%s, %s, %s, %s, %s, %s) "
                    "on conflict (internship_id, code) do nothing",
                    (internship_id, m["code"], m["name"], m["due_date"], m["status"], None),
                )
            insert_audit(conn, _entity(audit, internship_id))

    def change_internship_status(self, internship_id: int, source: str, target: str, audit: AuditEntry, *, reason: str = "") -> None:
        with self._db.connection() as conn:
            lock_status(conn, "internship", internship_id, source)
            set_status(conn, "internship", internship_id, target, decision_reason=reason, decided_at=NOW)
            insert_audit(conn, _entity(audit, internship_id))

    # ------------------------------------------------------------------ giấy tiếp nhận ----
    def add_document(self, internship_id: int, filename: str, mime: str, size: int, sha256: str, key: str, uploaded_by: int) -> int:
        with self._db.connection() as conn:
            return conn.execute(
                "insert into internship_document (internship_id, filename, mime, size_bytes, sha256, storage_key, uploaded_by) "
                "values (%s, %s, %s, %s, %s, %s, %s) returning id",
                (internship_id, filename, mime, size, sha256, key, uploaded_by),
            ).fetchone()["id"]

    def documents(self, internship_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, kind, filename, mime, size_bytes, uploaded_at from internship_document where internship_id = %s order by id",
                (internship_id,),
            ).fetchall()

    def get_document(self, document_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(
                "select d.*, i.user_id as owner_id, i.lecturer_id from internship_document d join internship i on i.id = d.internship_id "
                "where d.id = %s",
                (document_id,),
            ).fetchone()

    def revisions(self, internship_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select version, snapshot, submitted_at from internship_revision where internship_id = %s order by version desc",
                (internship_id,),
            ).fetchall()

    def other_companies_with_tax_code(self, tax_code: str, exclude_internship_id: int) -> list[dict]:
        """Hồ sơ khác cùng mã số thuế (phát hiện doanh nghiệp trùng, A6) — chỉ trả tên và khóa, không lộ sinh viên."""
        with self._db.connection() as conn:
            return conn.execute(
                "select distinct company_name from internship where company_tax_code = %s and id <> %s and company_name <> ''",
                (tax_code, exclude_internship_id),
            ).fetchall()

    # ------------------------------------------------------------------ mốc ----
    def milestones(self, internship_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, internship_id, code, name, due_date, status, note, submitted_at, decided_at from milestone "
                "where internship_id = %s order by code",
                (internship_id,),
            ).fetchall()

    def get_milestone(self, milestone_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(
                "select m.*, i.user_id as owner_id, i.lecturer_id, i.status as internship_status from milestone m "
                "join internship i on i.id = m.internship_id where m.id = %s",
                (milestone_id,),
            ).fetchone()

    def milestone_by_code(self, internship_id: int, code: str) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(
                "select m.*, i.user_id as owner_id, i.lecturer_id, i.status as internship_status from milestone m "
                "join internship i on i.id = m.internship_id where m.internship_id = %s and m.code = %s",
                (internship_id, code),
            ).fetchone()

    def submit_milestone(self, milestone_id: int, source: str, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            lock_status(conn, "milestone", milestone_id, source)
            set_status(conn, "milestone", milestone_id, "submitted", submitted_at=NOW, note="")
            insert_audit(conn, _entity(audit, milestone_id))

    def review_milestone(self, milestone_id: int, accepted: bool, reviewer_id: int, reason: str, audit: AuditEntry) -> None:
        """Chấp nhận / trả lại mốc; minh chứng đang chờ của mốc đổi trạng thái theo (HITL của GV)."""
        with self._db.connection() as conn:
            lock_status(conn, "milestone", milestone_id, "submitted")
            target = "accepted" if accepted else "rejected"
            set_status(conn, "milestone", milestone_id, target, note=reason, decided_by=reviewer_id, decided_at=NOW)
            conn.execute(
                "update evidence set status = %s, reviewer_comment = %s, reviewed_by = %s, reviewed_at = now() "
                "where milestone_id = %s and status = 'submitted'",
                (target, reason, reviewer_id, milestone_id),
            )
            insert_audit(conn, _entity(audit, milestone_id))

    def accept_milestone_system(self, milestone_id: int, source: str, audit: AuditEntry, decided_by: int) -> None:
        """Mốc M2 được chấp nhận khi đề cương được duyệt: hệ quả của quyết định người của GV (audit ghi người đó)."""
        with self._db.connection() as conn:
            lock_status(conn, "milestone", milestone_id, source)
            set_status(conn, "milestone", milestone_id, "accepted", decided_by=decided_by, decided_at=NOW)
            insert_audit(conn, _entity(audit, milestone_id))

    def mark_overdue(self, today: date) -> list[int]:
        """Hệ thống đánh dấu mốc quá hạn (mục 6.2). Trả về mã mốc vừa đổi."""
        changed: list[int] = []
        with self._db.connection() as conn:
            rows = conn.execute(
                "select m.id, m.status, m.code, m.internship_id from milestone m join internship i on i.id = m.internship_id "
                "where m.status in ('pending', 'rejected') and m.due_date < %s and i.status in ('confirmed', 'in_progress', 'pending_credit') "
                "for update of m",
                (today,),
            ).fetchall()
            for row in rows:
                set_status(conn, "milestone", row["id"], "overdue")
                insert_audit(
                    conn,
                    AuditEntry(
                        actor_kind=ActorKind.SYSTEM,
                        entity="milestone",
                        entity_id=row["id"],
                        action=f"{row['status']}->overdue",
                        before={"status": row["status"]},
                        after={"status": "overdue", "code": row["code"]},
                        reason="Quá hạn nộp (hệ thống đánh dấu)",
                    ),
                )
                changed.append(row["id"])
        return changed

    # ------------------------------------------------------------------ đề cương ----
    def outlines(self, internship_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, internship_id, version, content, outcome_codes, status, feedback, submitted_at, decided_at "
                "from outline where internship_id = %s order by version desc",
                (internship_id,),
            ).fetchall()

    def get_outline(self, outline_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(
                "select o.*, i.user_id as owner_id, i.lecturer_id, i.status as internship_status from outline o "
                "join internship i on i.id = o.internship_id where o.id = %s",
                (outline_id,),
            ).fetchone()

    def add_outline(self, internship_id: int, content: str, outcome_codes: list[str], audit: AuditEntry) -> int:
        with self._db.connection() as conn:
            conn.execute("select 1 from internship where id = %s for update", (internship_id,)).fetchone()
            pending = conn.execute("select 1 from outline where internship_id = %s and status = 'submitted'", (internship_id,)).fetchone()
            if pending:
                raise StateConflictError("Đề cương đang chờ giảng viên duyệt")
            version = conn.execute("select coalesce(max(version), 0) + 1 as v from outline where internship_id = %s", (internship_id,)).fetchone()["v"]
            row = conn.execute(
                "insert into outline (internship_id, version, content, outcome_codes) values (%s, %s, %s, %s) returning id",
                (internship_id, version, content, outcome_codes),
            ).fetchone()
            insert_audit(conn, _entity(audit, row["id"]))
        return row["id"]

    def decide_outline(
        self,
        outline_id: int,
        target: str,
        decider_id: int,
        feedback: str,
        outline_audit: AuditEntry,
        *,
        internship_change: tuple[int, str, str, AuditEntry] | None = None,
        milestone_accept: tuple[int, str, AuditEntry] | None = None,
    ) -> None:
        """Quyết định đề cương cùng hệ quả (hồ sơ ``confirmed`` → ``in_progress``/``rejected``; mốc M2 được chấp nhận) trong một transaction."""
        with self._db.connection() as conn:
            lock_status(conn, "outline", outline_id, "submitted")
            set_status(conn, "outline", outline_id, target, feedback=feedback, decided_by=decider_id, decided_at=NOW)
            insert_audit(conn, _entity(outline_audit, outline_id))
            if internship_change:
                internship_id, source, new_status, audit = internship_change
                lock_status(conn, "internship", internship_id, source)
                set_status(conn, "internship", internship_id, new_status, decision_reason=feedback if new_status == "rejected" else "", decided_at=NOW)
                insert_audit(conn, _entity(audit, internship_id))
            if milestone_accept:
                milestone_id, source, audit = milestone_accept
                lock_status(conn, "milestone", milestone_id, source)
                set_status(conn, "milestone", milestone_id, "accepted", decided_by=decider_id, decided_at=NOW)
                insert_audit(conn, _entity(audit, milestone_id))

    # ------------------------------------------------------------------ nhật ký ----
    def journals(self, internship_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, internship_id, week_start, content, submitted_at, lecturer_comment, commented_at from journal_entry "
                "where internship_id = %s order by week_start desc",
                (internship_id,),
            ).fetchall()

    def add_journal(self, internship_id: int, week_start: date, content: str, audit: AuditEntry) -> int:
        with self._db.connection() as conn:
            row = conn.execute(
                "insert into journal_entry (internship_id, week_start, content) values (%s, %s, %s) "
                "on conflict (internship_id, week_start) do nothing returning id",
                (internship_id, week_start, content),
            ).fetchone()
            if row is None:
                raise StateConflictError("Tuần này đã có nhật ký (nội dung đã nộp không sửa tại chỗ)")
            insert_audit(conn, _entity(audit, row["id"]))
        return row["id"]

    def get_journal(self, journal_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(
                "select j.*, i.user_id as owner_id, i.lecturer_id from journal_entry j join internship i on i.id = j.internship_id "
                "where j.id = %s",
                (journal_id,),
            ).fetchone()

    def comment_journal(self, journal_id: int, comment: str, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "update journal_entry set lecturer_comment = %s, commented_at = now() where id = %s", (comment, journal_id)
            )
            insert_audit(conn, _entity(audit, journal_id))

    # ------------------------------------------------------------------ minh chứng ----
    def evidence_for_internship(self, internship_id: int) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select e.id, e.milestone_id, m.code as milestone_code, e.title, e.filename, e.mime, e.size_bytes, e.status, "
                "e.reviewer_comment, e.submitted_at from evidence e join milestone m on m.id = e.milestone_id "
                "where m.internship_id = %s order by m.code, e.id",
                (internship_id,),
            ).fetchall()

    def add_evidence(
        self, milestone_id: int, title: str, filename: str, mime: str, size: int, sha256: str, key: str, uploaded_by: int, audit: AuditEntry
    ) -> int:
        with self._db.connection() as conn:
            row = conn.execute(
                "insert into evidence (milestone_id, title, filename, mime, size_bytes, sha256, storage_key, uploaded_by) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s) returning id",
                (milestone_id, title, filename, mime, size, sha256, key, uploaded_by),
            ).fetchone()
            insert_audit(conn, _entity(audit, row["id"]))
        return row["id"]

    def get_evidence(self, evidence_id: int) -> dict | None:
        with self._db.connection() as conn:
            return conn.execute(
                "select e.*, m.code as milestone_code, m.internship_id, i.user_id as owner_id, i.lecturer_id from evidence e "
                "join milestone m on m.id = e.milestone_id join internship i on i.id = m.internship_id where e.id = %s",
                (evidence_id,),
            ).fetchone()

    def count_active_evidence(self, milestone_id: int) -> int:
        with self._db.connection() as conn:
            return conn.execute(
                "select count(*) as n from evidence where milestone_id = %s and status <> 'rejected'", (milestone_id,)
            ).fetchone()["n"]

    def duplicate_evidence(self, internship_id: int, sha256: str, exclude_evidence_id: int) -> bool:
        with self._db.connection() as conn:
            return (
                conn.execute(
                    "select 1 from evidence e join milestone m on m.id = e.milestone_id "
                    "where m.internship_id = %s and e.sha256 = %s and e.id <> %s and e.sha256 <> '' limit 1",
                    (internship_id, sha256, exclude_evidence_id),
                ).fetchone()
                is not None
            )



def _entity(audit: AuditEntry, entity_id: int) -> AuditEntry:
    return replace(audit, entity_id=entity_id)


def _jsonable(value: Any) -> Any:
    return value.isoformat() if isinstance(value, date) else value
