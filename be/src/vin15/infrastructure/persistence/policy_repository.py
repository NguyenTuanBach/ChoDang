"""Kho văn bản quy định: văn bản, phiên bản, đoạn (chunk), tìm kiếm lai và xuất bản.

Mọi truy vấn phục vụ agent (``search``, ``find_chunk``) chỉ thấy phiên bản ``published`` có hiệu lực tại ngày ``today``
do **BE** truyền vào (không bao giờ lấy từ agent/LLM).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, timedelta

import psycopg
from psycopg import Connection

from vin15.domain.exception import ResourceNotFoundError, StateConflictError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.policy import (
    ChunkDraft,
    PolicyChunk,
    PolicyVersion,
    VersionStatus,
    make_chunk_id,
)

from .audit_repository import insert_audit
from .database import Database

_CHUNK_ID = re.compile(r"^(?P<code>[^@/]+)@(?P<label>[^/]+)/d(?P<article>[^/]+)(?:/k(?P<clause>[^/]+))?$")

#: Các cột công khai của một chunk kèm thông tin văn bản/phiên bản.
_CHUNK_SELECT = (
    "c.id, c.ordinal, c.version_id, c.article_no, c.clause_no, c.heading, c.text, "
    "v.version_label, v.effective_from, v.effective_to, v.is_sample, d.code as doc_code, d.title as doc_title"
)

#: Điều kiện "đang hiệu lực tại :today" (``%(today)s``).
_EFFECTIVE = "v.status = 'published' and v.effective_from <= %(today)s and (v.effective_to is null or %(today)s <= v.effective_to)"

_SEARCH_SQL = f"""
with eligible as (
    select c.id, c.tsv, to_tsvector('simple', f_unaccent(c.text)) as text_tsv, c.embedding
    from policy_chunk c
    join policy_version v on v.id = c.version_id
    where {_EFFECTIVE}
),
total as (select count(*)::float8 as n from eligible),
tok as (
    select t, (select count(*) from eligible e where e.tsv @@ to_tsquery('simple', t)) as df
    from unnest(%(tokens)s::text[]) as t
),
-- Bỏ từ không có trong kho, và từ có ở hầu hết đoạn (không phân biệt được gì).
usable as (select t, df from tok, total where df > 0 and (total.n < 10 or df <= 0.6 * total.n)),
kw as (
    -- Điểm = tổng độ hiếm (idf) của các từ khớp; từ chỉ khớp ở tiêu đề điều (chung cho mọi khoản của điều) tính 0,4 so với khớp ở nội dung.
    select e.id, row_number() over (
        order by sum(ln((total.n + 1) / (u.df + 0.5)) * case when e.text_tsv @@ to_tsquery('simple', u.t) then 1.0 else 0.4 end) desc, e.id
    ) as r
    from eligible e cross join usable u cross join total
    where e.tsv @@ to_tsquery('simple', u.t)
    group by e.id, total.n
    having count(*) >= %(min_match)s
    order by 2
    limit 20
),
vec as (
    select id, row_number() over (order by embedding <=> %(qvec)s::vector) as r, 1 - (embedding <=> %(qvec)s::vector) as sim
    from eligible
    where %(qvec)s::vector is not null and embedding is not null
    order by embedding <=> %(qvec)s::vector
    limit 20
),
vec_ok as (select id, r from vec where sim >= %(tau)s),
fused as (
    select id, sum(1.0 / (60 + r)) as score
    from (select id, r from kw union all select id, r from vec_ok) s
    group by id
    order by score desc
    limit %(top_k)s
)
select f.score, {_CHUNK_SELECT}
from fused f
join policy_chunk c on c.id = f.id
join policy_version v on v.id = c.version_id
join policy_document d on d.id = v.document_id
order by f.score desc, c.version_id, c.ordinal
"""


def _to_chunk(row: dict, score: float | None = None) -> PolicyChunk:
    return PolicyChunk(
        chunk_id=make_chunk_id(row["doc_code"], row["version_label"], row["article_no"], row["clause_no"]),
        doc_code=row["doc_code"],
        doc_title=row["doc_title"],
        version=row["version_label"],
        article_no=row["article_no"],
        clause_no=row["clause_no"],
        heading=row["heading"],
        text=row["text"],
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
        is_sample=row["is_sample"],
        score=score,
    )


def _to_version(row: dict) -> PolicyVersion:
    return PolicyVersion(
        id=row["id"],
        document_id=row["document_id"],
        doc_code=row["doc_code"],
        doc_title=row["doc_title"],
        version_label=row["version_label"],
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
        status=VersionStatus(row["status"]),
        is_sample=row["is_sample"],
        chunk_count=row.get("chunk_count", 0),
        embedded_count=row.get("embedded_count", 0),
    )


def vector_literal(vector: Sequence[float]) -> str:
    """Dạng văn bản của kiểu ``vector`` Postgres: ``[0.1,0.2,...]``."""
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"


_VERSION_SELECT = (
    "select v.id, v.document_id, v.version_label, v.effective_from, v.effective_to, v.status, v.is_sample, "
    "d.code as doc_code, d.title as doc_title, (select count(*) from policy_chunk c where c.version_id = v.id) as chunk_count, "
    "(select count(*) from policy_chunk c where c.version_id = v.id and c.embedding is not null) as embedded_count "
    "from policy_version v join policy_document d on d.id = v.document_id"
)


class PolicyRepository:
    def __init__(self, database: Database):
        self._db = database

    # ---- Nạp ----
    def find_version(self, doc_code: str, version_label: str) -> PolicyVersion | None:
        with self._db.connection() as conn:
            row = conn.execute(f"{_VERSION_SELECT} where d.code = %s and v.version_label = %s", (doc_code, version_label)).fetchone()
        return _to_version(row) if row else None

    def get_version(self, version_id: int) -> PolicyVersion | None:
        with self._db.connection() as conn:
            row = conn.execute(f"{_VERSION_SELECT} where v.id = %s", (version_id,)).fetchone()
        return _to_version(row) if row else None

    def list_versions(self) -> list[PolicyVersion]:
        with self._db.connection() as conn:
            rows = conn.execute(f"{_VERSION_SELECT} order by d.code, v.effective_from, v.id").fetchall()
        return [_to_version(r) for r in rows]

    def create_draft(
        self,
        *,
        doc_code: str,
        doc_title: str,
        issuer: str,
        version_label: str,
        effective_from: date,
        effective_to: date | None,
        is_sample: bool,
        chunks: Sequence[ChunkDraft],
    ) -> PolicyVersion:
        """Tạo văn bản (nếu chưa có) + một phiên bản ``draft`` + các chunk trong một transaction."""
        try:
            with self._db.connection() as conn:
                doc = conn.execute(
                    "insert into policy_document (code, title, issuer) values (%s, %s, %s) "
                    "on conflict (code) do update set title = excluded.title, issuer = excluded.issuer returning id",
                    (doc_code, doc_title, issuer),
                ).fetchone()
                version = conn.execute(
                    "insert into policy_version (document_id, version_label, effective_from, effective_to, is_sample) "
                    "values (%s, %s, %s, %s, %s) returning id",
                    (doc["id"], version_label, effective_from, effective_to, is_sample),
                ).fetchone()
                with conn.cursor() as cur:
                    cur.executemany(
                        "insert into policy_chunk (version_id, ordinal, article_no, clause_no, heading, text) values (%s, %s, %s, %s, %s, %s)",
                        [(version["id"], c.ordinal, c.article_no, c.clause_no, c.heading, c.text) for c in chunks],
                    )
        except psycopg.errors.UniqueViolation as error:
            raise StateConflictError(f"Phiên bản {version_label} của {doc_code} đã tồn tại") from error
        except psycopg.errors.CheckViolation as error:
            raise StateConflictError("Ngày hiệu lực không hợp lệ (effective_to phải sau effective_from)") from error
        found = self.get_version(version["id"])
        assert found is not None
        return found

    def chunks_missing_embedding(self, version_id: int) -> list[tuple[int, str, str]]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "select id, heading, text from policy_chunk where version_id = %s and embedding is null order by ordinal", (version_id,)
            ).fetchall()
        return [(r["id"], r["heading"], r["text"]) for r in rows]

    def set_embeddings(self, items: Sequence[tuple[int, Sequence[float]]], model: str) -> None:
        with self._db.connection() as conn, conn.cursor() as cur:
            cur.executemany(
                "update policy_chunk set embedding = %s::vector, embedding_model = %s where id = %s",
                [(vector_literal(vector), model, chunk_id) for chunk_id, vector in items],
            )

    def list_chunks(self, version_id: int) -> list[PolicyChunk]:
        with self._db.connection() as conn:
            rows = conn.execute(
                f"select {_CHUNK_SELECT} from policy_chunk c join policy_version v on v.id = c.version_id "
                "join policy_document d on d.id = v.document_id where c.version_id = %s order by c.ordinal",
                (version_id,),
            ).fetchall()
        return [_to_chunk(r) for r in rows]

    # ---- Xuất bản ----
    def publish_version(self, version_id: int, actor_id: int, today: date, *, actor_role: str = "admin") -> PolicyVersion:
        """Xuất bản một bản ``draft`` trong một transaction.

        Bản đang ``published`` cùng văn bản mà khoảng hiệu lực chạm bản mới thì bị đóng ``effective_to`` = ngày trước khi bản mới
        có hiệu lực; bản đã hết hiệu lực (``effective_to`` < hôm nay) chuyển ``superseded``. Bản cũ còn hiệu lực đến ngày đó
        giữ ``published`` để tìm kiếm vẫn thấy cho tới khi bản mới có hiệu lực.
        """
        try:
            with self._db.connection() as conn:
                version = conn.execute("select * from policy_version where id = %s for update", (version_id,)).fetchone()
                if version is None:
                    raise ResourceNotFoundError("Không tìm thấy phiên bản văn bản")
                if version["status"] != "draft":
                    raise StateConflictError("Chỉ xuất bản được phiên bản ở trạng thái nháp")
                if conn.execute("select 1 from policy_chunk where version_id = %s limit 1", (version_id,)).fetchone() is None:
                    raise StateConflictError("Phiên bản chưa có đoạn nào để xuất bản")
                closed = self._close_previous(conn, version, today)
                conn.execute(
                    "update policy_version set status = 'published', published_by = %s, published_at = now() where id = %s",
                    (actor_id, version_id),
                )
                insert_audit(
                    conn,
                    AuditEntry(
                        actor_kind=ActorKind.HUMAN,
                        actor_id=actor_id,
                        actor_role=actor_role,
                        entity="policy_version",
                        entity_id=version_id,
                        action="publish",
                        before={"status": "draft"},
                        after={"status": "published", "closed_versions": closed},
                        reason=f"effective_from={version['effective_from']}",
                    ),
                )
        except psycopg.errors.ExclusionViolation as error:
            raise StateConflictError("Khoảng hiệu lực chồng lên một phiên bản đã xuất bản của cùng văn bản") from error
        found = self.get_version(version_id)
        assert found is not None
        return found

    @staticmethod
    def _close_previous(conn: Connection, version: dict, today: date) -> list[int]:
        closed: list[int] = []
        siblings = conn.execute(
            "select id, effective_from, effective_to from policy_version "
            "where document_id = %s and status = 'published' and id <> %s order by effective_from",
            (version["document_id"], version["id"]),
        ).fetchall()
        for old in siblings:
            ends_after_new_starts = old["effective_to"] is None or old["effective_to"] >= version["effective_from"]
            starts_before_new_ends = version["effective_to"] is None or old["effective_from"] <= version["effective_to"]
            if not (ends_after_new_starts and starts_before_new_ends):
                continue
            if old["effective_from"] >= version["effective_from"]:
                raise StateConflictError("Phiên bản mới phải có hiệu lực sau phiên bản đang hiện hành của cùng văn bản")
            new_end = version["effective_from"] - timedelta(days=1)
            status = "superseded" if new_end < today else "published"
            conn.execute("update policy_version set effective_to = %s, status = %s where id = %s", (new_end, status, old["id"]))
            closed.append(old["id"])
        return closed

    # ---- Tra cứu cho agent ----
    def search(
        self,
        *,
        today: date,
        tokens: Sequence[str],
        min_match: int,
        query_vector: Sequence[float] | None,
        threshold: float,
        top_k: int,
    ) -> list[PolicyChunk]:
        params = {
            "today": today,
            "tokens": list(tokens),
            "min_match": min_match,
            "qvec": vector_literal(query_vector) if query_vector is not None else None,
            "tau": threshold,
            "top_k": top_k,
        }
        with self._db.connection() as conn:
            rows = conn.execute(_SEARCH_SQL, params).fetchall()
        return [_to_chunk(r, round(float(r["score"]), 6)) for r in rows]

    def find_chunk(self, chunk_id: str, today: date, with_neighbors: bool) -> tuple[PolicyChunk, list[PolicyChunk]] | None:
        match = _CHUNK_ID.match(chunk_id)
        if match is None:
            return None
        with self._db.connection() as conn:
            row = conn.execute(
                f"select {_CHUNK_SELECT} from policy_chunk c join policy_version v on v.id = c.version_id "
                f"join policy_document d on d.id = v.document_id where {_EFFECTIVE} and d.code = %(code)s and v.version_label = %(label)s "
                "and c.article_no = %(article)s and c.clause_no is not distinct from %(clause)s",
                {"today": today, **{k: match.group(k) for k in ("code", "label", "article", "clause")}},
            ).fetchone()
            if row is None:
                return None
            neighbors: list[dict] = []
            if with_neighbors:
                neighbors = conn.execute(
                    f"select {_CHUNK_SELECT} from policy_chunk c join policy_version v on v.id = c.version_id "
                    "join policy_document d on d.id = v.document_id "
                    "where c.version_id = %s and c.ordinal in (%s, %s) order by c.ordinal",
                    (row["version_id"], row["ordinal"] - 1, row["ordinal"] + 1),
                ).fetchall()
        return _to_chunk(row), [_to_chunk(n) for n in neighbors]
