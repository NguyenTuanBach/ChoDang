"""Adapter của LMS mini cho ``LmsPort`` (đọc điều kiện, điểm, sổ tín chỉ; ghi kết quả quy đổi)."""

from __future__ import annotations

from vin15.domain.exception import ResourceNotFoundError
from vin15.domain.model.lms import CreditEntry, GradeRecord, PrerequisiteStatus, StudentRecord
from vin15.infrastructure.persistence.database import Database


class MiniLmsAdapter:
    def __init__(self, database: Database, internship_course_code: str):
        self._db = database
        self._course = internship_course_code

    def prerequisite_status(self, student_code: str | None) -> PrerequisiteStatus:
        with self._db.connection() as conn:
            rows = conn.execute(
                "select p.required_course_code as code, c.name, p.min_score, g.score "
                "from lms_prerequisite p join lms_course c on c.code = p.required_course_code "
                "left join lms_grade g on g.course_code = p.required_course_code and g.student_code = %s "
                "where p.course_code = %s order by p.required_course_code",
                (student_code or "", self._course),
            ).fetchall()
        if not student_code:
            return PrerequisiteStatus(False, ["Chưa có mã sinh viên để tra LMS"])
        missing = [
            f"{r['name']} ({r['code']}): " + (f"điểm {r['score']} < {r['min_score']}" if r["score"] is not None else "chưa có điểm")
            for r in rows
            if r["score"] is None or r["score"] < r["min_score"]
        ]
        return PrerequisiteStatus(not missing, missing)

    def prerequisites_met(self, student_code: str | None) -> bool:
        return self.prerequisite_status(student_code).met

    def student_record(self, student_code: str | None) -> StudentRecord | None:
        if not student_code:
            return None
        with self._db.connection() as conn:
            student = conn.execute("select student_code, full_name from lms_student where student_code = %s", (student_code,)).fetchone()
            if student is None:
                return None
            grades = conn.execute(
                "select g.course_code, c.name, c.credits, g.score, g.term from lms_grade g join lms_course c on c.code = g.course_code "
                "where g.student_code = %s order by g.term, g.course_code",
                (student_code,),
            ).fetchall()
            ledger = conn.execute(
                "select l.course_code, c.name, l.credits, l.source, l.posted_at from lms_credit_ledger l join lms_course c on c.code = l.course_code "
                "where l.student_code = %s order by l.id",
                (student_code,),
            ).fetchall()
        return StudentRecord(
            student["student_code"],
            student["full_name"],
            [GradeRecord(g["course_code"], g["name"], g["credits"], float(g["score"]), g["term"]) for g in grades],
            [CreditEntry(e["course_code"], e["name"], e["credits"], e["source"], e["posted_at"]) for e in ledger],
        )

    def post_credit_result(self, student_code: str, course_code: str, credits: int, external_ref: str) -> None:
        with self._db.connection() as conn:
            if conn.execute("select 1 from lms_student where student_code = %s", (student_code,)).fetchone() is None:
                raise ResourceNotFoundError(f"Sinh viên {student_code} chưa có trong LMS")
            if conn.execute("select 1 from lms_course where code = %s", (course_code,)).fetchone() is None:
                raise ResourceNotFoundError(f"Học phần {course_code} chưa có trong LMS")
            conn.execute(
                "insert into lms_credit_ledger (student_code, course_code, credits, source, external_ref) values (%s, %s, %s, 'internship', %s) "
                "on conflict (external_ref) do nothing",
                (student_code, course_code, credits, external_ref),
            )
