"""Quản trị dữ liệu LMS mini (giao diện của chính LMS mini: học phần, sinh viên, điểm, tiên quyết). Không thuộc ``LmsPort``:
LMS thật có giao diện quản trị riêng của nó.
"""

from __future__ import annotations

from vin15.domain.exception import ResourceNotFoundError
from vin15.infrastructure.persistence.database import Database


class MiniLmsAdmin:
    def __init__(self, database: Database):
        self._db = database

    def courses(self) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute("select code, name, credits, kind from lms_course order by code").fetchall()

    def upsert_course(self, code: str, name: str, credits: int, kind: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "insert into lms_course (code, name, credits, kind) values (%s, %s, %s, %s) "
                "on conflict (code) do update set name = excluded.name, credits = excluded.credits, kind = excluded.kind",
                (code, name, credits, kind),
            )

    def prerequisites(self, course_code: str) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select p.course_code, p.required_course_code, c.name as required_name, p.min_score from lms_prerequisite p "
                "join lms_course c on c.code = p.required_course_code where p.course_code = %s order by p.required_course_code",
                (course_code,),
            ).fetchall()

    def set_prerequisite(self, course_code: str, required_course_code: str, min_score: float) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "insert into lms_prerequisite (course_code, required_course_code, min_score) values (%s, %s, %s) "
                "on conflict (course_code, required_course_code) do update set min_score = excluded.min_score",
                (course_code, required_course_code, min_score),
            )

    def remove_prerequisite(self, course_code: str, required_course_code: str) -> None:
        with self._db.connection() as conn:
            conn.execute("delete from lms_prerequisite where course_code = %s and required_course_code = %s", (course_code, required_course_code))

    def students(self) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select s.student_code, s.full_name, coalesce((select sum(l.credits) from lms_credit_ledger l where l.student_code = s.student_code), 0) as credits "
                "from lms_student s order by s.student_code"
            ).fetchall()

    def upsert_student(self, student_code: str, full_name: str) -> None:
        with self._db.connection() as conn:
            conn.execute(
                "insert into lms_student (student_code, full_name) values (%s, %s) "
                "on conflict (student_code) do update set full_name = excluded.full_name",
                (student_code, full_name),
            )

    def upsert_grade(self, student_code: str, course_code: str, score: float, term: str) -> None:
        with self._db.connection() as conn:
            if conn.execute("select 1 from lms_student where student_code = %s", (student_code,)).fetchone() is None:
                raise ResourceNotFoundError(f"Chưa có sinh viên {student_code} trong LMS")
            if conn.execute("select 1 from lms_course where code = %s", (course_code,)).fetchone() is None:
                raise ResourceNotFoundError(f"Chưa có học phần {course_code} trong LMS")
            conn.execute(
                "insert into lms_grade (student_code, course_code, score, term) values (%s, %s, %s, %s) "
                "on conflict (student_code, course_code) do update set score = excluded.score, term = excluded.term",
                (student_code, course_code, score, term),
            )

    def delete_grade(self, student_code: str, course_code: str) -> None:
        with self._db.connection() as conn:
            conn.execute("delete from lms_grade where student_code = %s and course_code = %s", (student_code, course_code))
