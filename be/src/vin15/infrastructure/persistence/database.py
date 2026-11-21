"""Pool kết nối Postgres (Supabase)."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

log = logging.getLogger(__name__)


class Database:
    def __init__(self, url: str, min_size: int = 1, max_size: int = 5, schema: str | None = None):
        """``schema``: đặt ``search_path`` của mọi kết nối (test tích hợp dùng schema riêng để không đụng dữ liệu có sẵn)."""
        if schema is not None and not re.fullmatch(r"\w+", schema):
            raise ValueError("Tên schema chỉ gồm chữ, số, gạch dưới")
        self._schema = schema
        self._pool = ConnectionPool(
            url,
            min_size=min_size,
            max_size=max_size,
            open=False,
            configure=self._configure if schema else None,
            # Supabase pooler ở chế độ transaction (pgbouncer) không hỗ trợ prepared statement.
            kwargs={"prepare_threshold": None, "row_factory": dict_row},
        )

    def _configure(self, conn: Connection) -> None:
        # Extension (vector, unaccent...) nằm ở public hoặc extensions nên vẫn phải có trong đường tìm kiếm.
        conn.execute(f'set search_path to "{self._schema}", public, extensions')
        conn.commit()

    def open(self) -> None:
        self._pool.open(wait=True, timeout=15)

    def close(self) -> None:
        self._pool.close()

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        """Mượn một kết nối. Commit khi thoát bình thường, rollback khi có lỗi."""
        with self._pool.connection() as conn:
            yield conn

    def ping(self) -> bool:
        try:
            with self.connection() as conn:
                conn.execute("select 1")
            return True
        except Exception:
            log.warning("Không ping được database", exc_info=True)
            return False
