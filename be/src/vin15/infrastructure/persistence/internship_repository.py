"""Đọc hồ sơ thực tập, mốc, nhật ký, minh chứng, yêu cầu — luôn theo một sinh viên (``user_id``)."""

from __future__ import annotations

from datetime import date

from vin15.domain.model.internship import EvidenceRecord, InternshipRecord, MilestoneRecord, RequestRecord

from .database import Database


class InternshipRepository:
    def __init__(self, database: Database):
        self._db = database

    def latest_internship(self, user_id: int) -> InternshipRecord | None:
        """Hồ sơ mới nhất của sinh viên (theo ngày bắt đầu rồi mã), kèm tên giảng viên; không lấy email/SĐT."""
        with self._db.connection() as conn:
            row = conn.execute(
                "select i.id, i.cohort, i.status, i.start_date, i.end_date, i.mode, l.full_name as lecturer_name "
                "from internship i left join app_user l on l.id = i.lecturer_id "
                "where i.user_id = %s order by i.start_date desc nulls last, i.id desc limit 1",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return InternshipRecord(
            row["id"], row["cohort"], row["status"], row["start_date"], row["end_date"], row["mode"], row["lecturer_name"] or None
        )

    def by_id(self, internship_id: int) -> tuple[InternshipRecord, int] | None:
        """Hồ sơ theo id (cho giảng viên/QTV), kèm ``user_id`` của sinh viên."""
        with self._db.connection() as conn:
            row = conn.execute(
                "select i.id, i.user_id, i.cohort, i.status, i.start_date, i.end_date, i.mode, l.full_name as lecturer_name "
                "from internship i left join app_user l on l.id = i.lecturer_id where i.id = %s",
                (internship_id,),
            ).fetchone()
        if row is None:
            return None
        record = InternshipRecord(
            row["id"], row["cohort"], row["status"], row["start_date"], row["end_date"], row["mode"], row["lecturer_name"] or None
        )
        return record, row["user_id"]

    def milestones(self, internship_id: int) -> list[MilestoneRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "select code, name, due_date, status from milestone where internship_id = %s order by code", (internship_id,)
            ).fetchall()
        return [MilestoneRecord(r["code"], r["name"], r["due_date"], r["status"]) for r in rows]

    def evidence(self, internship_id: int) -> list[EvidenceRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "select m.code, e.status from evidence e join milestone m on m.id = e.milestone_id "
                "where m.internship_id = %s order by m.code, e.id",
                (internship_id,),
            ).fetchall()
        return [EvidenceRecord(r["code"], r["status"]) for r in rows]

    def journal_week_starts(self, internship_id: int) -> list[date]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "select week_start from journal_entry where internship_id = %s order by week_start", (internship_id,)
            ).fetchall()
        return [r["week_start"] for r in rows]

    def requests(self, internship_id: int) -> list[RequestRecord]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "select kind, status, created_at from request where internship_id = %s order by created_at desc, id desc", (internship_id,)
            ).fetchall()
        return [RequestRecord(r["kind"], r["status"], r["created_at"]) for r in rows]
