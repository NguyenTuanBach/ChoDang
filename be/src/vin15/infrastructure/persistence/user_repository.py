"""Đọc tài khoản người dùng (``app_user``)."""

from __future__ import annotations

from vin15.domain.model.user import Role, User, UserStatus

from .database import Database


def _to_user(row: dict) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        full_name=row["full_name"],
        role=Role(row["role"]),
        status=UserStatus(row["status"]),
        invited_by=row["invited_by"],
    )


_COLUMNS = "id, email, full_name, role, status, invited_by"


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
