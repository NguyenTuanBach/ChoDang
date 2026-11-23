"""Seed dữ liệu giả + tool cá nhân + hội thoại trên Postgres thật (schema riêng): P13 (seed idempotent), P5 (đúng chủ thể), P8 (audit),
điều kiện tín chỉ T1-T6 từ số liệu DB, ChatRepository."""

from __future__ import annotations

from datetime import date

import psycopg
import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from tests.fakes import TODAY
from vin15.config.container import Container
from vin15.devtools.dev_seed import STUDENT_A_EMAIL, STUDENT_B_EMAIL, STUDENT_C_EMAIL, STUDENT_D_EMAIL, SeedRefusedError, read_policy_files, run_seed
from vin15.main import create_app

SERVICE = {"Authorization": "Bearer svc-token"}
COUNT_TABLES = (
    "app_user",
    "internship",
    "milestone",
    "journal_entry",
    "evidence",
    "request",
    "policy_document",
    "policy_version",
    "policy_chunk",
)


def make_container(database, **overrides) -> Container:
    settings = make_settings(agent_api_service_token="svc-token", jwt_secret="j" * 40, **overrides)
    container = Container(settings)
    container.database = database
    container.clock = lambda: TODAY
    return container


def counts(db) -> dict[str, int]:
    with db.connection() as conn:
        return {t: conn.execute(f"select count(*) as n from {t}").fetchone()["n"] for t in COUNT_TABLES}


@pytest.fixture(scope="module")
def seeded(pg_db):
    with pg_db.connection() as conn:
        conn.execute(
            "truncate chat_message, chat_conversation, request, evidence, journal_entry, milestone, internship, "
            "policy_chunk, policy_version, policy_document, audit_event, app_user restart identity cascade"
        )
    container = make_container(pg_db)
    import asyncio

    report = asyncio.run(run_seed(container))
    return container, report


def tool(container, email: str | None = None):
    """TestClient cho agent-tools với chủ thể là ``email`` (người dùng mặc định ở dev)."""
    container = make_container(container.database, agent_dev_default_user_email=email or "")
    return TestClient(create_app(container.settings, container))


# ---- Seed ----
def test_seed_creates_expected_people_policies_and_publishes(seeded):
    container, report = seeded
    assert report.users == 6 and report.internships == 3 and report.policy_versions == 3 and report.policy_published_now == 3
    with container.database.connection() as conn:
        roles = {r["email"]: r["role"] for r in conn.execute("select email, role from app_user")}
        versions = {
            (r["code"], r["version_label"]): r
            for r in conn.execute(
                "select d.code, v.version_label, v.status, v.is_sample, v.effective_to from policy_version v join policy_document d on d.id = v.document_id"
            )
        }
    assert roles == {
        "qtv@example.test": "admin",
        "gv@example.test": "lecturer",
        STUDENT_A_EMAIL: "student",
        STUDENT_B_EMAIL: "student",
        STUDENT_C_EMAIL: "student",
        STUDENT_D_EMAIL: "student",
    }
    assert all(v["is_sample"] for v in versions.values())
    assert versions[("QD-TC-02", "v1")]["status"] == "superseded" and versions[("QD-TC-02", "v1")]["effective_to"] == date(2025, 12, 31)
    assert versions[("QD-TC-02", "v2")]["status"] == "published" and versions[("QD-TT-01", "v1")]["status"] == "published"


def test_seed_is_idempotent_p13(seeded):
    import asyncio

    container, _ = seeded
    before = counts(container.database)
    report = asyncio.run(run_seed(container))
    assert counts(container.database) == before
    assert report.policy_published_now == 0 and report.policy_versions == 3


def test_seed_refuses_production_without_touching_db(pg_db):
    container = make_container(pg_db)
    prod = Container(make_settings(app_env="production"))
    prod.database = container.database
    import asyncio

    before = counts(pg_db)
    with pytest.raises(SeedRefusedError, match="production"):
        asyncio.run(run_seed(prod))
    assert counts(pg_db) == before


def test_seed_policy_files_are_wellformed_and_chunkable():
    from vin15.service.policy.policy_chunker import PolicyChunker

    files = read_policy_files()
    assert [(f.code, f.version) for f in files] == [("QD-TC-02", "v1"), ("QD-TC-02", "v2"), ("QD-TT-01", "v1")]
    for f in files:
        assert f.is_sample and "mẫu" in f.title
        assert len(PolicyChunker().chunk(f.text)) >= 2


def test_seeded_policies_answer_with_current_version_only(seeded):
    container, _ = seeded
    search = container.policy_search_service
    hits = search.search("điều kiện thời lượng thực tập tối thiểu bao nhiêu tuần để quy đổi tín chỉ").chunks
    # Chỉ từ khóa (seed không có vector) không phân biệt được điều 2 và điều 4 cùng nói về thời lượng: chỉ đòi chunk có "8 tuần"
    # nằm trong top 3 và hạng nhất thuộc bản v2 hiện hành; xếp hạng chính xác hơn là việc của vector (hybrid).
    assert hits and hits[0].doc_code == "QD-TC-02" and hits[0].version == "v2"
    assert any("8 tuần" in c.text and c.version == "v2" for c in hits[:3])
    assert all(c.version != "v1" for c in hits if c.doc_code == "QD-TC-02")
    assert search.search("gia hạn mốc cần gửi trước bao nhiêu ngày").chunks[0].chunk_id.startswith("QD-TT-01@v1/d7")
    assert search.search("thời tiết hôm nay ở Hà Nội thế nào").status == "no_match"
    with pytest.raises(Exception, match="Không tìm thấy"):
        search.get_chunk("QD-TC-02@v1/d1/k1")  # bản hết hiệu lực


# ---- Tool cá nhân trên dữ liệu seed ----
def test_student_a_late_and_missing_journal(seeded):
    client = tool(seeded[0], STUDENT_A_EMAIL)
    milestones = {m["code"]: m for m in client.get("/api/agent-tools/me/milestones", headers=SERVICE).json()["milestones"]}
    assert milestones["M3"]["status"] == "overdue" and milestones["M3"]["days_left"] == -5 and milestones["M4"]["status"] == "pending"
    progress = client.get("/api/agent-tools/me/progress", headers=SERVICE).json()
    assert progress["journal"] == {"submitted": 4, "expected": 6, "missing_weeks": ["2026-10-31", "2026-11-14"]}
    assert progress["evidence"] == {"submitted": 0, "required": 3}
    requests = client.get("/api/agent-tools/me/requests", headers=SERVICE).json()["requests"]
    assert [(r["kind"], r["status"]) for r in requests] == [("milestone_extension", "open")]
    internship = client.get("/api/agent-tools/me/internship", headers=SERVICE).json()["internship"]
    assert internship["status"] == "in_progress" and internship["lecturer_name"].startswith("Cô Nguyễn") and internship["mode"] == "onsite"


def test_student_b_submitted_final_report(seeded):
    client = tool(seeded[0], STUDENT_B_EMAIL)
    assert client.get("/api/agent-tools/me/internship", headers=SERVICE).json()["internship"]["status"] == "pending_credit"
    items = {i["code"]: i for i in client.get("/api/agent-tools/me/credit-checklist", headers=SERVICE).json()["items"]}
    assert items["T1"]["met"] and items["T1"]["value"] == "12 tuần" and items["T2"]["met"]
    assert not items["T3"]["met"] and items["T3"]["value"] == "3/5 mốc"
    assert items["T4"]["met"] and items["T4"]["value"] == "11/12 tuần (92%)"
    assert not items["T5"]["met"] and items["T6"]["met"]
    milestones = {m["code"]: m for m in client.get("/api/agent-tools/me/milestones", headers=SERVICE).json()["milestones"]}
    assert milestones["M4"]["status"] == "submitted" and "Chờ giảng viên" in milestones["M4"]["next_action"]


def test_credit_checklist_for_a_has_unmet_conditions(seeded):
    body = tool(seeded[0], STUDENT_A_EMAIL).get("/api/agent-tools/me/credit-checklist", headers=SERVICE).json()
    met = {i["code"]: i["met"] for i in body["items"]}
    assert met == {"T1": False, "T2": True, "T3": False, "T4": False, "T5": False, "T6": True} and body["all_met"] is False


def test_student_c_has_no_record_and_staff_are_forbidden(seeded):
    container = seeded[0]
    body = tool(container, STUDENT_C_EMAIL).get("/api/agent-tools/me/internship", headers=SERVICE).json()
    assert body["available"] is False and body["reason"] == "no_internship_record"
    for email in ("gv@example.test", "qtv@example.test"):
        response = tool(container, email).get("/api/agent-tools/me/milestones", headers=SERVICE)
        assert response.status_code == 403 and response.json()["error"]["code"] == "forbidden_role"


def test_switching_subject_never_leaks_other_students_data_p5(seeded):
    container = seeded[0]
    for email, status in ((STUDENT_A_EMAIL, "in_progress"), (STUDENT_B_EMAIL, "pending_credit")):
        client = tool(container, email)
        for _ in range(2):
            body = client.get("/api/agent-tools/me/internship", params={"user_id": 1, "student_id": 2}, headers=SERVICE).json()
            assert body["internship"]["status"] == status


def test_agent_token_scopes_the_subject_in_db_and_is_audited_p8(seeded):
    container = seeded[0]
    with container.database.connection() as conn:
        b_id = conn.execute("select id from app_user where email = %s", (STUDENT_B_EMAIL,)).fetchone()["id"]
        before = conn.execute("select count(*) as n from audit_event where actor_kind = 'agent' and entity = 'agent_tool'").fetchone()["n"]
    client = tool(container, STUDENT_A_EMAIL)  # có người dùng mặc định là A, nhưng agent-token của B phải thắng
    token = container.token_service.create(b_id, "student", 5, scope="agent_tools", extra={"conv": "9", "turn": "t7"})
    body = client.get("/api/agent-tools/me/internship", headers={**SERVICE, "X-On-Behalf-Of": token}).json()
    assert body["internship"]["status"] == "pending_credit"
    with container.database.connection() as conn:
        after = conn.execute(
            "select actor_id, actor_role, entity, action, reason, after from audit_event "
            "where actor_kind = 'agent' and entity = 'agent_tool' order by id desc limit 1"
        ).fetchone()
        total = conn.execute("select count(*) as n from audit_event where actor_kind = 'agent' and entity = 'agent_tool'").fetchone()["n"]
    assert total == before + 1
    assert (after["actor_id"], after["actor_role"], after["action"], after["reason"]) == (
        b_id,
        "student",
        "get_my_internship",
        "conv=9 turn=t7",
    )
    assert after["after"]["outcome"] == "ok"


def test_policy_search_endpoint_on_real_db(seeded):
    client = tool(seeded[0], "gv@example.test")  # giảng viên tra quy định được
    body = client.post(
        "/api/agent-tools/policy/search", json={"query": "Nhật ký nộp chậm nhất bao lâu sau khi tuần kết thúc", "top_k": 3}, headers=SERVICE
    ).json()
    assert body["status"] == "ok" and body["mode"] == "keyword" and body["chunks"][0]["chunk_id"].startswith("QD-TT-01@v1/d5")
    assert all(c["is_sample"] for c in body["chunks"])
    chunk_id = body["chunks"][0]["chunk_id"]
    got = client.get(f"/api/agent-tools/policy/chunks/{chunk_id}", params={"with_neighbors": "true"}, headers=SERVICE).json()
    assert got["chunk"]["chunk_id"] == chunk_id and len(got["neighbors"]) >= 1


# ---- ChatRepository ----
def test_chat_repository_roundtrip_ordering_and_trace_lookup(seeded):
    from vin15.infrastructure.persistence.chat_repository import ChatRepository

    container = seeded[0]
    chats = ChatRepository(container.database)
    with container.database.connection() as conn:
        a = conn.execute("select id from app_user where email = %s", (STUDENT_A_EMAIL,)).fetchone()["id"]
        b = conn.execute("select id from app_user where email = %s", (STUDENT_B_EMAIL,)).fetchone()["id"]
    conv = chats.create_conversation(a, "Thời lượng")
    chats.add_message(conv.id, "t1", "user", "Hỏi 1")
    chats.add_message(
        conv.id, "t1", "assistant", "Đáp 1", citations=[{"chunk_id": "x"}], trace={"trace_id": "tr-db", "steps": [1]}, degraded=True
    )
    chats.add_message(conv.id, "t2", "user", "Hỏi 2")
    assert [m.content for m in chats.list_messages(conv.id)] == ["Hỏi 1", "Đáp 1", "Hỏi 2"]
    assert [m.content for m in chats.recent_messages(conv.id, 2)] == ["Đáp 1", "Hỏi 2"]
    reply = chats.list_messages(conv.id)[1]
    assert reply.citations == [{"chunk_id": "x"}] and reply.trace["trace_id"] == "tr-db" and reply.degraded is True
    assert chats.turn_exists(conv.id, "t2") and not chats.turn_exists(conv.id, "t3")
    with pytest.raises(psycopg.errors.UniqueViolation):  # trùng (hội thoại, lượt, vai trò)
        chats.add_message(conv.id, "t1", "user", "trùng")
    found = chats.find_message_by_trace_id("tr-db")
    assert found is not None and found[0].id == reply.id and found[1].user_id == a
    assert chats.find_message_by_trace_id("khong-co") is None
    assert [c.id for c in chats.list_conversations(a)][0] == conv.id and conv.id not in [c.id for c in chats.list_conversations(b)]
    assert chats.get_conversation(conv.id).updated_at >= conv.updated_at
