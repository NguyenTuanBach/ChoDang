"""Quản trị LMS mini (QTV): học phần, tiên quyết, sinh viên, điểm, nhập CSV. Mọi thay đổi ghi audit."""

from __future__ import annotations

import csv
import io

from vin15.domain.exception import InvalidInputError
from vin15.domain.model.audit import Actor, AuditEntry
from vin15.infrastructure.lms.mini_lms_admin import MiniLmsAdmin
from vin15.infrastructure.persistence.audit_repository import AuditRepository


class LmsAdminService:
    def __init__(self, admin: MiniLmsAdmin, audit: AuditRepository):
        self._admin = admin
        self._audit = audit

    def _record(self, actor: Actor, entity: str, action: str, after: dict) -> None:
        self._audit.record(AuditEntry(actor_kind=actor.kind, actor_id=actor.id, actor_role=actor.role, entity=entity, action=action, after=after))

    def courses(self) -> list[dict]:
        return self._admin.courses()

    def upsert_course(self, actor: Actor, code: str, name: str, credits: int, kind: str) -> None:
        if kind not in ("regular", "internship"):
            raise InvalidInputError("Loại học phần phải là regular hoặc internship")
        self._admin.upsert_course(code.strip().upper(), name.strip(), credits, kind)
        self._record(actor, "lms_course", "upsert", {"code": code, "name": name, "credits": credits, "kind": kind})

    def prerequisites(self, course_code: str) -> list[dict]:
        return self._admin.prerequisites(course_code)

    def set_prerequisite(self, actor: Actor, course_code: str, required_course_code: str, min_score: float) -> None:
        self._admin.set_prerequisite(course_code.strip().upper(), required_course_code.strip().upper(), min_score)
        self._record(actor, "lms_prerequisite", "set", {"course": course_code, "required": required_course_code, "min_score": min_score})

    def remove_prerequisite(self, actor: Actor, course_code: str, required_course_code: str) -> None:
        self._admin.remove_prerequisite(course_code.strip().upper(), required_course_code.strip().upper())
        self._record(actor, "lms_prerequisite", "remove", {"course": course_code, "required": required_course_code})

    def students(self) -> list[dict]:
        return self._admin.students()

    def upsert_student(self, actor: Actor, student_code: str, full_name: str) -> None:
        self._admin.upsert_student(student_code.strip(), full_name.strip())
        self._record(actor, "lms_student", "upsert", {"student_code": student_code})

    def upsert_grade(self, actor: Actor, student_code: str, course_code: str, score: float, term: str) -> None:
        self._admin.upsert_grade(student_code.strip(), course_code.strip().upper(), score, term.strip())
        self._record(actor, "lms_grade", "upsert", {"student_code": student_code, "course": course_code, "score": score})

    def delete_grade(self, actor: Actor, student_code: str, course_code: str) -> None:
        self._admin.delete_grade(student_code.strip(), course_code.strip().upper())
        self._record(actor, "lms_grade", "delete", {"student_code": student_code, "course": course_code})

    def import_grades_csv(self, actor: Actor, content: str) -> dict:
        """CSV có tiêu đề ``student_code,course_code,score,term``. Dòng lỗi được báo lại, không dừng cả tệp."""
        reader = csv.DictReader(io.StringIO(content))
        needed = {"student_code", "course_code", "score"}
        if not reader.fieldnames or not needed <= {name.strip() for name in reader.fieldnames}:
            raise InvalidInputError("CSV cần các cột: student_code, course_code, score (term tùy chọn)")
        imported, errors = 0, []
        for line, row in enumerate(reader, start=2):
            try:
                score = float(str(row["score"]).replace(",", "."))
                if not 0 <= score <= 10:
                    raise ValueError("điểm phải trong khoảng 0-10")
                self._admin.upsert_grade(row["student_code"].strip(), row["course_code"].strip().upper(), score, (row.get("term") or "").strip())
                imported += 1
            except Exception as error:
                errors.append({"line": line, "error": str(error)})
        self._record(actor, "lms_grade", "import_csv", {"imported": imported, "errors": len(errors)})
        return {"imported": imported, "errors": errors}
