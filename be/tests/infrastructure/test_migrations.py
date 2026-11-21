import re

import pytest

from vin15.infrastructure.persistence.migrations import MigrationError, discover_migrations


def write(directory, name, sql="select 1;"):
    (directory / name).write_text(sql, encoding="utf-8")


def test_sorted_by_number_not_by_text(tmp_path):
    for name in ("V10__ten.sql", "V2__ten.sql", "V1__ten.sql"):
        write(tmp_path, name)
    assert [m.version for m in discover_migrations(tmp_path)] == [1, 2, 10]


def test_rejects_bad_name(tmp_path):
    write(tmp_path, "migration.sql")
    with pytest.raises(MigrationError, match="sai định dạng"):
        discover_migrations(tmp_path)


def test_rejects_duplicate_version(tmp_path):
    write(tmp_path, "V1__a.sql")
    write(tmp_path, "V01__b.sql")
    with pytest.raises(MigrationError, match="Trùng"):
        discover_migrations(tmp_path)


def test_checksum_changes_with_content(tmp_path):
    write(tmp_path, "V1__a.sql", "select 1;")
    first = discover_migrations(tmp_path)[0].checksum
    write(tmp_path, "V1__a.sql", "select 2;")
    assert discover_migrations(tmp_path)[0].checksum != first


def test_real_migrations_are_valid_and_start_at_v1():
    migrations = discover_migrations()
    assert migrations and migrations[0].version == 1


def test_every_table_enables_row_level_security():
    """Supabase mở schema public qua khóa anon: bảng nào thiếu RLS là lộ dữ liệu."""
    for migration in discover_migrations():
        tables = re.findall(r"create table (?:if not exists )?(\w+)", migration.sql, flags=re.I)
        for table in tables:
            assert re.search(rf"alter table {table} enable row level security", migration.sql, flags=re.I), (
                f"V{migration.version}: bảng {table} chưa bật RLS"
            )


def test_audit_event_is_append_only():
    sql = " ".join(m.sql for m in discover_migrations()).lower()
    assert "audit_event_no_change" in sql
    assert "before update or delete on audit_event" in sql
