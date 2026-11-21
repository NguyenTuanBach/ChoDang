"""Chạy migration trên Postgres thật (pgserver, nhúng sẵn, không cần Docker). Bỏ qua nếu không có pgserver."""

import shutil
import tempfile

import psycopg
import pytest

from vin15.config.resources import MIGRATION_DIR
from vin15.infrastructure.persistence.database import Database
from vin15.infrastructure.persistence.migrations import MigrationError, SqlMigrator

pgserver = pytest.importorskip("pgserver")


@pytest.fixture(scope="module")
def uri():
    directory = tempfile.mkdtemp()
    server = pgserver.get_server(directory)
    yield server.get_uri()
    server.cleanup()


@pytest.fixture
def db(uri):
    """Mỗi test một schema sạch: dọn các bảng của VIN-15 trước khi chạy."""
    with psycopg.connect(uri, autocommit=True) as conn:
        conn.execute("drop table if exists audit_event, app_user, schema_history cascade")
        conn.execute("drop function if exists audit_event_append_only() cascade")
    database = Database(uri, 1, 2)
    database.open()
    yield database
    database.close()


def test_applies_baseline_once_and_is_idempotent(db):
    assert SqlMigrator(db).migrate() == [1]
    assert SqlMigrator(db).migrate() == []
    with db.connection() as conn:
        assert [r["version"] for r in conn.execute("select version from schema_history")] == [1]
        assert db.ping()


def test_row_level_security_is_on(db):
    SqlMigrator(db).migrate()
    with db.connection() as conn:
        rows = conn.execute("select relname, relrowsecurity from pg_class where relname in ('app_user', 'audit_event')").fetchall()
    assert {r["relname"]: r["relrowsecurity"] for r in rows} == {"app_user": True, "audit_event": True}


def test_audit_event_cannot_be_updated_or_deleted(db):
    SqlMigrator(db).migrate()
    with db.connection() as conn:
        conn.execute("insert into audit_event (actor_kind, entity, action) values ('human', 'internship', 'submit')")
    for statement in ("update audit_event set action = 'x'", "delete from audit_event"):
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"), db.connection() as conn:
            conn.execute(statement)


def test_user_constraints(db):
    SqlMigrator(db).migrate()
    insert = "insert into app_user (email, role) values (%s, %s)"
    with db.connection() as conn:
        conn.execute(insert, ("sv@truong.edu.vn", "student"))
    with pytest.raises(psycopg.errors.UniqueViolation), db.connection() as conn:
        conn.execute(insert, ("sv@truong.edu.vn", "student"))
    with pytest.raises(psycopg.errors.CheckViolation), db.connection() as conn:  # email phải viết thường
        conn.execute(insert, ("SV2@truong.edu.vn", "student"))
    with pytest.raises(psycopg.errors.CheckViolation), db.connection() as conn:  # vai trò lạ
        conn.execute(insert, ("x@truong.edu.vn", "hacker"))


def test_edited_migration_is_detected(db, tmp_path):
    shutil.copytree(MIGRATION_DIR, tmp_path / "m")
    migrator = SqlMigrator(db, tmp_path / "m")
    migrator.migrate()
    baseline = tmp_path / "m" / "V1__baseline.sql"
    baseline.write_text(baseline.read_text(encoding="utf-8") + "\n-- đã sửa\n", encoding="utf-8")
    with pytest.raises(MigrationError, match="đã bị sửa"):
        migrator.migrate()


def test_app_startup_migrates_and_reports_database_up(uri, db):
    from fastapi.testclient import TestClient

    from tests.conftest import make_settings
    from vin15.main import create_app

    with TestClient(create_app(make_settings(database_url=uri))) as client:
        assert client.get("/api/health/readiness").json() == {"status": "UP", "components": {"database": "UP"}}
    with db.connection() as conn:
        assert conn.execute("select count(*) as n from schema_history").fetchone()["n"] == 1
