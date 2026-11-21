"""Hàm dùng chung cho repository khi đổi trạng thái: khóa dòng, kiểm trạng thái hiện tại, cập nhật. Chạy trong transaction của repository."""

from __future__ import annotations

import re

from psycopg import Connection

from vin15.domain.exception import ResourceNotFoundError, StateConflictError

#: Chỉ những bảng có cột ``status`` do state machine quản lý (tên bảng không bao giờ lấy từ người dùng).
_TABLES = frozenset({"internship", "outline", "milestone", "request", "risk_flag", "credit_assessment"})
_COLUMN = re.compile(r"^[a-z_]+$")


class _Now:
    """Giá trị đặc biệt: đặt cột bằng ``now()`` của DB."""


NOW = _Now()


def lock_status(conn: Connection, table: str, row_id: int, expected: str) -> dict:
    """Khóa dòng và kiểm đang ở trạng thái ``expected`` (tránh hai người quyết cùng lúc)."""
    if table not in _TABLES:
        raise ValueError(f"Bảng không có state machine: {table}")
    row = conn.execute(f"select * from {table} where id = %s for update", (row_id,)).fetchone()
    if row is None:
        raise ResourceNotFoundError("Không tìm thấy bản ghi")
    if row["status"] != expected:
        raise StateConflictError(f"Trạng thái đã thay đổi (hiện là '{row['status']}'), hãy tải lại")
    return row


def set_status(conn: Connection, table: str, row_id: int, status: str, **columns: object) -> None:
    if table not in _TABLES:
        raise ValueError(f"Bảng không có state machine: {table}")
    assignments = ["status = %s"]
    params: list[object] = [status]
    for name, value in columns.items():
        if not _COLUMN.match(name):
            raise ValueError(f"Tên cột không hợp lệ: {name}")
        if value is NOW:
            assignments.append(f"{name} = now()")
        else:
            assignments.append(f"{name} = %s")
            params.append(value)
    params.append(row_id)
    conn.execute(f"update {table} set {', '.join(assignments)} where id = %s", params)
