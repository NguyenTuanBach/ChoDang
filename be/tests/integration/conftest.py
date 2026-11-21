"""Fixture cho test tích hợp trên Postgres thật (Supabase qua ``DATABASE_URL``).

Mỗi module test dùng **một schema riêng** (``vin15_test_<hex>``) rồi xóa khi xong, nên không đụng bảng/dữ liệu có sẵn.
Thiếu ``DATABASE_URL`` hoặc không nối được thì các test dùng ``pg_db`` tự bỏ qua kèm thông báo.
Extension (vector, unaccent, btree_gist) được bật một lần ở mức database (migration cũng làm vậy khi BE khởi động).
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from vin15.config.settings import get_settings
from vin15.infrastructure.persistence.database import Database
from vin15.infrastructure.persistence.migrations import SqlMigrator

_SCHEMA_PREFIX = "vin15_test_"
_EXTENSIONS = ("vector", "unaccent", "btree_gist")
#: Bảng nghiệp vụ, thứ tự xóa an toàn theo khóa ngoại (truncate ... cascade lo phần còn lại).
DATA_TABLES = (
    "chat_message, chat_conversation, request, evidence, journal_entry, milestone, internship, "
    "policy_chunk, policy_version, policy_document, audit_event, app_user"
)


def _database_url() -> str:
    # TEST_DATABASE_URL (vd Postgres local: make be-test-db) ưu tiên hơn; đặt DATABASE_URL cho cả bộ test sẽ làm hỏng test "không có DB".
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL") or get_settings().database_url
    return url.strip() if url.strip().lower().startswith(("postgresql://", "postgres://")) else ""


@pytest.fixture(scope="session")
def pg_url() -> str:
    url = _database_url()
    if not url:
        pytest.skip("Không có DATABASE_URL Postgres: bỏ qua test tích hợp trên Supabase")
    try:
        with psycopg.connect(url, autocommit=True, connect_timeout=10) as conn:
            for name in _EXTENSIONS:
                conn.execute(f"create extension if not exists {name}")
            # Dọn schema test còn sót do lần chạy trước bị ngắt giữa chừng.
            for row in conn.execute("select nspname from pg_namespace where nspname like 'vin15\\_test\\_%'").fetchall():
                conn.execute(f'drop schema if exists "{row[0]}" cascade')
    except psycopg.Error as error:
        pytest.skip(f"Không nối được DATABASE_URL hoặc không bật được extension ({type(error).__name__}): bỏ qua test tích hợp")
    return url


@pytest.fixture(scope="module")
def pg_db(pg_url: str):
    schema = _SCHEMA_PREFIX + uuid.uuid4().hex[:10]
    with psycopg.connect(pg_url, autocommit=True) as conn:
        conn.execute(f'create schema "{schema}"')
    database = Database(pg_url, 1, 4, schema=schema)
    database.open()
    try:
        SqlMigrator(database).migrate()
        yield database
    finally:
        database.close()
        with psycopg.connect(pg_url, autocommit=True) as conn:
            conn.execute(f'drop schema if exists "{schema}" cascade')


@pytest.fixture
def clean_db(pg_db: Database) -> Database:
    """``pg_db`` với dữ liệu đã xóa sạch (chỉ trong schema test)."""
    with pg_db.connection() as conn:
        conn.execute(f"truncate {DATA_TABLES} restart identity cascade")
    return pg_db
