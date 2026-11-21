"""Nạp, xuất bản và tìm kiếm quy định trên Postgres thật (schema riêng): P4 (hiệu lực), no_match, chỉ-từ-khóa, RRF, tính hiệu lực theo ngày."""

from __future__ import annotations

from datetime import date

import pytest

from vin15.domain.exception import InvalidInputError, ResourceNotFoundError, StateConflictError
from vin15.infrastructure.agent_api import AgentApiClient, EmbeddingResult
from vin15.infrastructure.persistence.policy_repository import PolicyRepository
from vin15.service.policy.policy_chunker import PolicyChunker
from vin15.service.policy.policy_ingest_service import PolicyIngestService
from vin15.service.policy.policy_publish_service import PolicyPublishService
from vin15.service.policy.policy_search_service import PolicySearchService

TODAY = date(2026, 11, 21)

TEXT_V1 = """# Quy chế thực tập (mẫu)
## Điều 1. Phạm vi
Quy chế áp dụng cho sinh viên đi thực tập tại doanh nghiệp.
## Điều 3. Thời lượng
1. Thời lượng thực tập tối thiểu là 6 tuần liên tục để được xét quy đổi tín chỉ.
2. Thực tập từ xa được tính tương đương nếu có giảng viên đồng ý.
## Điều 4. Nhật ký
Sinh viên nộp nhật ký hằng tuần cho giảng viên hướng dẫn đúng hạn.
"""
TEXT_V2 = TEXT_V1.replace("6 tuần", "8 tuần")

#: Điều 3 trong văn bản mẫu ngắn; hạ ngưỡng "điều ngắn" để vẫn tách theo khoản.
CHUNKER = PolicyChunker(short_article_chars=60)
KEYWORDS = {"thời lượng": 0, "nhật ký": 1, "phạm vi": 2}


class FakeAgent(AgentApiClient):
    """Agent giả: embedding one-hot theo từ khóa để kiểm tìm kiếm vector xác định."""

    def __init__(self, enabled: bool = True):
        super().__init__("http://agent.test" if enabled else "", "tok")
        self.calls = 0

    async def embed(self, texts):
        self.calls += 1
        return EmbeddingResult("fake-embed", [vector_for(t) for t in texts])


def vector_for(text: str) -> list[float]:
    vector = [0.0] * 1536
    for word, index in KEYWORDS.items():
        if word in text.lower():
            vector[index] = 1.0
    if not any(vector):
        vector[100] = 1.0
    return vector


def query_vector(index: int) -> list[float]:
    vector = [0.0] * 1536
    vector[index] = 1.0
    return vector


@pytest.fixture
def repo(clean_db):
    return PolicyRepository(clean_db)


@pytest.fixture
def admin_id(clean_db):
    with clean_db.connection() as conn:
        return conn.execute(
            "insert into app_user (email, role, status) values ('qtv@example.test', 'admin', 'active') returning id"
        ).fetchone()["id"]


def search_service(repo, today=TODAY, tau=0.25):
    return PolicySearchService(repo, lambda: today, tau)


def publish_service(repo, today=TODAY):
    return PolicyPublishService(repo, lambda: today)


async def ingest(repo, text=TEXT_V1, label="v1", start=date(2026, 1, 1), end=None, agent=None, sample=True):
    service = PolicyIngestService(repo, agent or FakeAgent(), CHUNKER)
    return await service.ingest(
        doc_code="QD-TT-01",
        doc_title="Quy chế thực tập",
        issuer="Phòng đào tạo",
        version_label=label,
        effective_from=start,
        effective_to=end,
        is_sample=sample,
        text=text,
    )


@pytest.mark.anyio
async def test_ingest_creates_draft_chunks_with_embeddings(repo):
    result = await ingest(repo)
    assert (result.chunk_count, result.embedded_count, result.created) == (4, 4, True)
    assert result.version.status == "draft" and result.version.is_sample
    chunks = repo.list_chunks(result.version.id)
    assert [c.chunk_id for c in chunks] == ["QD-TT-01@v1/d1", "QD-TT-01@v1/d3/k1", "QD-TT-01@v1/d3/k2", "QD-TT-01@v1/d4"]
    assert repo.chunks_missing_embedding(result.version.id) == []


@pytest.mark.anyio
async def test_ingest_without_agent_still_works_keyword_only(repo, admin_id):
    result = await ingest(repo, agent=FakeAgent(enabled=False))
    assert result.embedded_count == 0 and len(repo.chunks_missing_embedding(result.version.id)) == 4
    publish_service(repo).publish(result.version.id, admin_id)
    found = search_service(repo).search("thời lượng tối thiểu")
    assert found.mode == "keyword" and found.status == "ok"


@pytest.mark.anyio
async def test_ensure_is_idempotent_and_backfills_embeddings(repo):
    first = await PolicyIngestService(repo, FakeAgent(enabled=False), CHUNKER).ensure(
        doc_code="QD-TT-01", doc_title="Quy chế", version_label="v1", effective_from=date(2026, 1, 1), text=TEXT_V1
    )
    assert first.created and first.embedded_count == 0
    second = await PolicyIngestService(repo, FakeAgent(), CHUNKER).ensure(
        doc_code="QD-TT-01", doc_title="Quy chế", version_label="v1", effective_from=date(2026, 1, 1), text=TEXT_V1
    )
    assert not second.created and second.embedded_count == 4 and len(repo.list_versions()) == 1


@pytest.mark.anyio
async def test_ingest_rejects_bad_format_and_duplicate_version(repo):
    with pytest.raises(InvalidInputError):
        await ingest(repo, text="không có điều nào")
    await ingest(repo)
    with pytest.raises(StateConflictError, match="đã tồn tại"):
        await ingest(repo)


@pytest.mark.anyio
async def test_draft_is_never_searchable_p4(repo, admin_id):
    draft = await ingest(repo)
    search = search_service(repo)
    assert search.search("thời lượng tối thiểu", query_vector(0)).status == "no_match"
    with pytest.raises(ResourceNotFoundError):
        search.get_chunk("QD-TT-01@v1/d3/k1")
    publish_service(repo).publish(draft.version.id, admin_id)
    assert search.search("thời lượng tối thiểu").status == "ok"


@pytest.mark.anyio
async def test_keyword_search_ranks_relevant_clause_first_and_ignores_accents(repo, admin_id):
    version = await ingest(repo)
    publish_service(repo).publish(version.version.id, admin_id)
    search = search_service(repo)
    for query in ("Thời lượng thực tập tối thiểu là bao nhiêu tuần?", "thoi luong toi thieu bao nhieu tuan"):
        result = search.search(query)
        assert result.status == "ok" and result.mode == "keyword"
        top = result.chunks[0]
        assert top.chunk_id == "QD-TT-01@v1/d3/k1" and top.is_sample and top.version == "v1" and top.score and top.score > 0
        assert "6 tuần" in top.text
        assert top.effective_from == date(2026, 1, 1) and top.effective_to is None
    assert len(search.search("thời lượng", top_k=1).chunks) == 1


@pytest.mark.anyio
async def test_no_match_when_no_keyword_and_no_vector(repo, admin_id):
    version = await ingest(repo)
    publish_service(repo).publish(version.version.id, admin_id)
    result = search_service(repo).search("thời tiết hôm nay thế nào")
    assert result.status == "no_match" and result.chunks == []


@pytest.mark.anyio
async def test_vector_threshold_controls_no_match_for_different_tau(repo, admin_id):
    version = await ingest(repo)
    publish_service(repo).publish(version.version.id, admin_id)
    nonsense = "qqq zzz"  # không có từ khóa trùng
    hit = search_service(repo, tau=0.25).search(nonsense, query_vector(1))  # trùng hoàn toàn đoạn nhật ký (sim = 1)
    assert hit.mode == "hybrid" and hit.status == "ok" and hit.chunks[0].chunk_id == "QD-TT-01@v1/d4"
    assert search_service(repo, tau=1.01).search(nonsense, query_vector(1)).status == "no_match"
    orthogonal = search_service(repo, tau=0.25).search(nonsense, query_vector(500))  # sim = 0 < τ
    assert orthogonal.status == "no_match"
    assert search_service(repo, tau=-1.0).search(nonsense, query_vector(500)).status == "ok"  # τ thấp: nhận mọi thứ


@pytest.mark.anyio
async def test_hybrid_fuses_keyword_and_vector_hits(repo, admin_id):
    version = await ingest(repo)
    publish_service(repo).publish(version.version.id, admin_id)
    result = search_service(repo).search("thời lượng tối thiểu", query_vector(0))  # vector: các đoạn "thời lượng"
    assert result.mode == "hybrid"
    ids = [c.chunk_id for c in result.chunks]
    assert ids[0] == "QD-TT-01@v1/d3/k1"  # có ở cả hai danh sách -> điểm RRF cao nhất
    assert set(ids) <= {"QD-TT-01@v1/d3/k1", "QD-TT-01@v1/d3/k2"}


@pytest.mark.anyio
async def test_effective_dates_use_business_today_p4(repo, admin_id):
    v1 = await ingest(repo, start=date(2025, 1, 1), end=date(2025, 12, 31))
    publish_service(repo, date(2025, 6, 1)).publish(v1.version.id, admin_id)
    assert search_service(repo, date(2025, 6, 1)).search("thời lượng tối thiểu").status == "ok"
    assert search_service(repo, date(2025, 1, 1)).search("thời lượng tối thiểu").status == "ok"  # ngày đầu tính
    assert search_service(repo, date(2025, 12, 31)).search("thời lượng tối thiểu").status == "ok"  # ngày cuối tính
    assert search_service(repo, date(2026, 1, 1)).search("thời lượng tối thiểu").status == "no_match"
    assert search_service(repo, date(2024, 12, 31)).search("thời lượng tối thiểu").status == "no_match"
    with pytest.raises(ResourceNotFoundError):
        search_service(repo, date(2026, 11, 21)).get_chunk("QD-TT-01@v1/d3/k1")


@pytest.mark.anyio
async def test_publish_new_version_supersedes_old_and_only_new_is_found(repo, admin_id):
    v1 = await ingest(repo, label="v1", start=date(2025, 1, 1))
    publish_service(repo).publish(v1.version.id, admin_id)
    v2 = await ingest(repo, text=TEXT_V2, label="v2", start=date(2026, 1, 1))
    published = publish_service(repo).publish(v2.version.id, admin_id)
    assert published.status == "published"
    old = repo.get_version(v1.version.id)
    assert old.status == "superseded" and old.effective_to == date(2025, 12, 31)
    found = search_service(repo).search("thời lượng tối thiểu").chunks
    assert {c.version for c in found} == {"v2"} and "8 tuần" in found[0].text
    with pytest.raises(ResourceNotFoundError):
        search_service(repo).get_chunk("QD-TT-01@v1/d3/k1")
    with repo._db.connection() as conn:
        audit = conn.execute("select actor_kind, actor_id, action from audit_event where entity = 'policy_version' order by id").fetchall()
    assert [(a["actor_kind"], a["actor_id"], a["action"]) for a in audit] == [("human", admin_id, "publish")] * 2


@pytest.mark.anyio
async def test_future_dated_version_keeps_old_effective_until_it_starts(repo, admin_id):
    v1 = await ingest(repo, label="v1", start=date(2025, 1, 1))
    publish_service(repo).publish(v1.version.id, admin_id)
    v2 = await ingest(repo, text=TEXT_V2, label="v2", start=date(2027, 1, 1))
    publish_service(repo).publish(v2.version.id, admin_id)
    old = repo.get_version(v1.version.id)
    assert old.status == "published" and old.effective_to == date(2026, 12, 31)  # đóng, nhưng vẫn hiệu lực hôm nay
    assert {c.version for c in search_service(repo).search("thời lượng tối thiểu").chunks} == {"v1"}
    assert {c.version for c in search_service(repo, date(2027, 1, 1)).search("thời lượng tối thiểu").chunks} == {"v2"}


@pytest.mark.anyio
async def test_publish_rules(repo, admin_id):
    v1 = await ingest(repo, label="v1", start=date(2026, 1, 1))
    service = publish_service(repo)
    service.publish(v1.version.id, admin_id)
    with pytest.raises(StateConflictError, match="nháp"):
        service.publish(v1.version.id, admin_id)  # đã published
    backdated = await ingest(repo, text=TEXT_V2, label="v0", start=date(2025, 1, 1))
    with pytest.raises(StateConflictError, match="sau phiên bản"):
        service.publish(backdated.version.id, admin_id)
    assert repo.get_version(v1.version.id).effective_to is None  # transaction hoàn tác, bản cũ không bị đổi
    with pytest.raises(ResourceNotFoundError):
        service.publish(999999, admin_id)


@pytest.mark.anyio
async def test_get_chunk_with_neighbors_and_not_found(repo, admin_id):
    version = await ingest(repo)
    publish_service(repo).publish(version.version.id, admin_id)
    search = search_service(repo)
    lookup = search.get_chunk("QD-TT-01@v1/d3/k1", with_neighbors=True)
    assert lookup.chunk.chunk_id == "QD-TT-01@v1/d3/k1"
    assert [n.chunk_id for n in lookup.neighbors] == ["QD-TT-01@v1/d1", "QD-TT-01@v1/d3/k2"]
    assert search.get_chunk("QD-TT-01@v1/d4").neighbors == []
    for bad in ("QD-TT-01@v1/d9", "khong-hop-le", "QD-TT-01@v9/d1", "QD-TT-01@v1/d3"):
        with pytest.raises(ResourceNotFoundError):
            search.get_chunk(bad)


@pytest.mark.anyio
async def test_query_validation(repo):
    search = search_service(repo)
    with pytest.raises(InvalidInputError):
        search.search("   ")
    with pytest.raises(InvalidInputError, match="1536"):
        search.search("abc", [0.1, 0.2])
