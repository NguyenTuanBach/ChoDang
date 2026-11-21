"""V2-V4 trên Postgres thật: áp dụng được, RLS bật, ràng buộc không chồng hiệu lực (P14), cột tìm kiếm."""

from __future__ import annotations

import psycopg
import pytest

from vin15.infrastructure.persistence.migrations import SqlMigrator


def _doc(conn, code="QD-1"):
    return conn.execute("insert into policy_document (code, title) values (%s, 'Quy chế') returning id", (code,)).fetchone()["id"]


def _version(conn, doc_id, label, start, end=None, status="published"):
    return conn.execute(
        "insert into policy_version (document_id, version_label, effective_from, effective_to, status) values (%s, %s, %s, %s, %s) returning id",
        (doc_id, label, start, end, status),
    ).fetchone()["id"]


def test_all_migrations_apply_and_are_idempotent(pg_db):
    assert SqlMigrator(pg_db).migrate() == []
    with pg_db.connection() as conn:
        versions = [r["version"] for r in conn.execute("select version from schema_history order by version")]
    assert versions[:4] == [1, 2, 3, 4]


def test_every_table_in_test_schema_has_rls(pg_db):
    with pg_db.connection() as conn:
        rows = conn.execute(
            "select c.relname, c.relrowsecurity from pg_class c where c.relkind = 'r' "
            "and c.relnamespace = (select oid from pg_namespace where nspname = current_schema()) and c.relname <> 'schema_history'"
        ).fetchall()
    assert rows
    assert [r["relname"] for r in rows if not r["relrowsecurity"]] == []
    names = {r["relname"] for r in rows}
    assert {
        "policy_document",
        "policy_version",
        "policy_chunk",
        "chat_conversation",
        "chat_message",
        "internship",
        "milestone",
        "journal_entry",
        "evidence",
        "request",
    } <= names


def test_published_versions_of_one_document_cannot_overlap(clean_db):
    with clean_db.connection() as conn:
        doc = _doc(conn)
        _version(conn, doc, "v1", "2025-01-01", "2025-12-31")
        _version(conn, doc, "v2", "2026-01-01")
    with pytest.raises(psycopg.errors.ExclusionViolation), clean_db.connection() as conn:
        _version(conn, doc, "v3", "2026-06-01", "2026-07-01")
    with pytest.raises(psycopg.errors.ExclusionViolation), clean_db.connection() as conn:  # mở không kỳ hạn chồng lên v2
        _version(conn, doc, "v4", "2027-01-01")


def test_overlap_is_allowed_for_drafts_and_other_documents(clean_db):
    with clean_db.connection() as conn:
        doc = _doc(conn)
        _version(conn, doc, "v1", "2026-01-01")
        _version(conn, doc, "v2-nhap", "2026-03-01", status="draft")
        _version(conn, doc, "v0", "2025-01-01", "2025-12-31", status="superseded")
        other = _doc(conn, "QD-2")
        _version(conn, other, "v1", "2026-01-01")


def test_effective_range_must_be_ordered(clean_db):
    with clean_db.connection() as conn:
        doc = _doc(conn)
    with pytest.raises(psycopg.errors.CheckViolation), clean_db.connection() as conn:
        _version(conn, doc, "v1", "2026-02-01", "2026-01-01")


def test_tsv_is_unaccented_and_embedding_is_1536_dim(clean_db):
    with clean_db.connection() as conn:
        doc = _doc(conn)
        version = _version(conn, doc, "v1", "2026-01-01")
        vector = "[" + ",".join(["0.5"] * 1536) + "]"
        conn.execute(
            "insert into policy_chunk (version_id, ordinal, article_no, heading, text, embedding, embedding_model) "
            "values (%s, 0, '3', 'Điều 3. Thời lượng', 'Thời lượng tối thiểu là 8 tuần.', %s::vector, 'm')",
            (version, vector),
        )
        hit = conn.execute(
            "select count(*) as n from policy_chunk where tsv @@ websearch_to_tsquery('simple', f_unaccent('THỜI LƯỢNG'))"
        ).fetchone()
        assert hit["n"] == 1
        miss = conn.execute(
            "select count(*) as n from policy_chunk where tsv @@ websearch_to_tsquery('simple', 'khong-co-tu-nay')"
        ).fetchone()
        assert miss["n"] == 0
    with pytest.raises(psycopg.Error), clean_db.connection() as conn:
        conn.execute(
            "insert into policy_chunk (version_id, ordinal, article_no, text, embedding) values (%s, 1, '3', 'x', %s::vector)",
            (version, "[1,2,3]"),
        )
