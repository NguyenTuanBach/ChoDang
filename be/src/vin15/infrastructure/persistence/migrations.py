"""Áp migration SQL kiểu Flyway: ``resources/db/migration/V<số>__<mô tả>.sql``.

- Chạy theo thứ tự số (V2 trước V10), mỗi file một transaction.
- Ghi bảng ``schema_history``; file đã áp mà nội dung đổi (checksum lệch) thì dừng, không âm thầm bỏ qua.
- Khóa advisory để nhiều tiến trình khởi động cùng lúc không áp trùng.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from vin15.config.resources import MIGRATION_DIR

from .database import Database

_NAME = re.compile(r"^V(\d+)__([A-Za-z0-9_]+)\.sql$")
_LOCK_KEY = 8_015_001  # khóa advisory riêng của VIN-15


class MigrationError(Exception):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str
    checksum: str


def discover_migrations(directory: Path = MIGRATION_DIR) -> list[Migration]:
    """Đọc và sắp xếp migration theo số phiên bản. File sai tên hoặc trùng phiên bản thì báo lỗi."""
    found: dict[int, Migration] = {}
    for path in directory.glob("*.sql"):
        match = _NAME.match(path.name)
        if match is None:
            raise MigrationError(f"Tên migration sai định dạng V<số>__<mô_tả>.sql: {path.name}")
        version = int(match.group(1))
        if version in found:
            raise MigrationError(f"Trùng phiên bản migration V{version}")
        sql = path.read_text(encoding="utf-8")
        found[version] = Migration(version, match.group(2), sql, hashlib.sha256(sql.encode()).hexdigest())
    return [found[v] for v in sorted(found)]


class SqlMigrator:
    def __init__(self, database: Database, directory: Path = MIGRATION_DIR):
        self._db = database
        self._directory = directory

    def migrate(self) -> list[int]:
        """Áp các migration chưa chạy. Trả về danh sách phiên bản vừa áp."""
        migrations = discover_migrations(self._directory)
        applied_now: list[int] = []
        with self._db.connection() as conn:
            conn.execute("select pg_advisory_lock(%s)", (_LOCK_KEY,))
            try:
                conn.execute(
                    "create table if not exists schema_history ("
                    "version integer primary key, description text not null, checksum text not null, "
                    "applied_at timestamptz not null default now())"
                )
                conn.commit()
                done = {row["version"]: row["checksum"] for row in conn.execute("select version, checksum from schema_history")}
                for migration in migrations:
                    if migration.version in done:
                        if done[migration.version] != migration.checksum:
                            raise MigrationError(f"Migration V{migration.version} đã áp dụng nhưng nội dung đã bị sửa")
                        continue
                    conn.execute(migration.sql)
                    conn.execute(
                        "insert into schema_history (version, description, checksum) values (%s, %s, %s)",
                        (migration.version, migration.description, migration.checksum),
                    )
                    conn.commit()
                    applied_now.append(migration.version)
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.execute("select pg_advisory_unlock(%s)", (_LOCK_KEY,))
                conn.commit()
        return applied_now
