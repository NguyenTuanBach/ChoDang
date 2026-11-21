"""Tài khoản người dùng (``app_user``): đọc, mời, thu hồi, kích hoạt, gán giảng viên phụ trách. Thay đổi ghi audit cùng transaction."""

from __future__ import annotations

from dataclasses import replace

from psycopg.errors import UniqueViolation

from vin15.domain.exception import ResourceNotFoundError, StateConflictError
from vin15.domain.model.audit import AuditEntry
from vin15.domain.model.user import Role, User, UserStatus

from .audit_repository import insert_audit
from .database import Database


def _to_user(row: dict) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        role=Role(row["role"]),
        status=UserStatus(row["status"]),
        invited_by=row["invited_by"],
        student_code=row.get("student_code"),
        advisor_id=row.get("advisor_id"),
    )


_COLUMNS = "id, email, full_name, role, status, invited_by, student_code, advisor_id"
_FINAL_STATUSES = ("completed", "closed_no_credit", "rejected")


class UserRepository:
    def __init__(self, database: Database):
        self._db = database

    def find_by_id(self, user_id: int) -> User | None:
        with self._db.connection() as conn:
            row = conn.execute(f"select {_COLUMNS} from app_user where id = %s", (user_id,)).fetchone()
        return _to_user(row) if row else None

    def find_by_email(self, email: str) -> User | None:
        with self._db.connection() as conn:
            row = conn.execute(f"select {_COLUMNS} from app_user where email = %s", (email.strip().lower(),)).fetchone()
        return _to_user(row) if row else None

    def list_by_email_suffix(self, suffix: str) -> list[User]:
        """Tài khoản có email kết thúc bằng ``suffix`` (vd ``@example.test``), xếp admin → lecturer → student rồi theo email."""
        pattern = "%" + suffix.strip().lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._db.connection() as conn:
            rows = conn.execute(
                f"select {_COLUMNS} from app_user where email like %s "
                "order by case role when 'admin' then 0 when 'lecturer' then 1 else 2 end, email",
                (pattern,),
            ).fetchall()
        return [_to_user(row) for row in rows]

    def list_by_role(self, role: Role) -> list[User]:
        with self._db.connection() as conn:
            rows = conn.execute(f"select {_COLUMNS} from app_user where role = %s order by email", (role.value,)).fetchall()
        return [_to_user(row) for row in rows]

    def list_students_of(self, lecturer_id: int) -> list[User]:
        with self._db.connection() as conn:
            rows = conn.execute(
                f"select {_COLUMNS} from app_user where role = 'student' and advisor_id = %s order by email", (lecturer_id,)
            ).fetchall()
        return [_to_user(row) for row in rows]

    def admin_ids(self) -> list[int]:
        with self._db.connection() as conn:
            rows = conn.execute("select id from app_user where role = 'admin' and status <> 'revoked' order by id").fetchall()
        return [r["id"] for r in rows]

    def lecturer_ids(self) -> list[int]:
        with self._db.connection() as conn:
            rows = conn.execute("select id from app_user where role = 'lecturer' and status <> 'revoked' order by id").fetchall()
        return [r["id"] for r in rows]

    # ---- Ghi ----
    def ensure_admins(self, emails: list[str]) -> int:
        """Khởi tạo quản trị viên từ ``APP_ADMIN_EMAILS`` (D14). Đã có thì không đổi. Trả về số tài khoản mới."""
        created = 0
        with self._db.connection() as conn:
            for email in emails:
                row = conn.execute(
                    "insert into app_user (email, full_name, role, status) values (%s, %s, 'admin', 'invited') "
                    "on conflict (email) do nothing returning id",
                    (email.strip().lower(), email.split("@")[0]),
                ).fetchone()
                created += 1 if row else 0
        return created

    def insert_invited(
        self,
        email: str,
        full_name: str,
        role: Role,
        invited_by: int,
        audit: AuditEntry,
        *,
        advisor_id: int | None = None,
        student_code: str | None = None,
    ) -> User:
        with self._db.connection() as conn:
            row = conn.execute(
                "insert into app_user (email, full_name, role, status, invited_by, advisor_id, student_code) "
                "values (%s, %s, %s, 'invited', %s, %s, %s) on conflict (email) do nothing "
                f"returning {_COLUMNS}",
                (email.strip().lower(), full_name.strip(), role.value, invited_by, advisor_id, student_code),
            ).fetchone()
            if row is None:
                raise StateConflictError(f"Email {email} đã có tài khoản hoặc lời mời")
            insert_audit(conn, _with_entity_id(audit, row["id"]))
        return _to_user(row)

    def set_status(self, user_id: int, status: UserStatus, audit: AuditEntry, *, only_from: tuple[UserStatus, ...] = ()) -> User:
        with self._db.connection() as conn:
            current = conn.execute("select status from app_user where id = %s for update", (user_id,)).fetchone()
            if current is None:
                raise ResourceNotFoundError("Không tìm thấy tài khoản")
            if only_from and UserStatus(current["status"]) not in only_from:
                raise StateConflictError("Trạng thái tài khoản không cho phép thao tác này")
            row = conn.execute(
                "update app_user set status = %s, activated_at = case when %s = 'active' and activated_at is null then now() else activated_at end "
                f"where id = %s returning {_COLUMNS}",
                (status.value, status.value, user_id),
            ).fetchone()
            insert_audit(conn, _with_entity_id(audit, user_id))
        return _to_user(row)

    def set_advisor(self, student_id: int, lecturer_id: int, audit: AuditEntry) -> User:
        """Gán giảng viên phụ trách; hồ sơ chưa kết thúc của sinh viên đó chuyển theo."""
        with self._db.connection() as conn:
            row = conn.execute(
                f"update app_user set advisor_id = %s where id = %s and role = 'student' returning {_COLUMNS}", (lecturer_id, student_id)
            ).fetchone()
            if row is None:
                raise ResourceNotFoundError("Không tìm thấy sinh viên")
            conn.execute(
                "update internship set lecturer_id = %s where user_id = %s and status <> all(%s)",
                (lecturer_id, student_id, list(_FINAL_STATUSES)),
            )
            insert_audit(conn, _with_entity_id(audit, student_id))
        return _to_user(row)

    def set_student_code(self, student_id: int, student_code: str, audit: AuditEntry) -> None:
        with self._db.connection() as conn:
            try:
                row = conn.execute(
                    "update app_user set student_code = %s where id = %s and role = 'student' returning id", (student_code, student_id)
                ).fetchone()
            except UniqueViolation as error:
                raise StateConflictError("Mã sinh viên đã được dùng cho tài khoản khác") from error
            if row is None:
                raise ResourceNotFoundError("Không tìm thấy sinh viên")
            insert_audit(conn, replace(audit, entity_id=student_id))


def _with_entity_id(audit: AuditEntry, entity_id: int) -> AuditEntry:
    return replace(audit, entity_id=entity_id)
