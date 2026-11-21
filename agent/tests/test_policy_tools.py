"""Tool tra quy định và tool cá nhân (task 8.2, 23.1): ghi seen_chunks, lỗi, đăng ký theo vai trò."""

import asyncio
import json

import pytest

from fakes import DURATION, FakeAi, FakeBe
from vin15_agent.core.tools import TurnContext
from vin15_agent.policy_assistant.be_client import BeToolsClient
from vin15_agent.policy_assistant.registry import build_registry
from vin15_agent.policy_assistant.tools.get_policy_clause import GetPolicyClauseTool
from vin15_agent.policy_assistant.tools.personal import PERSONAL_TOOLS
from vin15_agent.policy_assistant.tools.search_policy import SearchPolicyTool


def setup(be=None, ai=None, role="student"):
    be = be or FakeBe()
    client = BeToolsClient("http://be", "tok", transport=be.transport())
    ctx = TurnContext(actor_role=role, today="2026-11-21")
    return be, client, ai or FakeAi(), ctx


def run(coro):
    return asyncio.run(coro)


def test_search_embeds_query_and_records_seen_chunks():
    be, client, ai, ctx = setup()
    result = run(SearchPolicyTool(client, ai).run({"query": "thời lượng thực tập tối thiểu", "top_k": 3}, ctx))
    assert result.ok and result.data["status"] == "ok" and result.data["mode"] == "hybrid"
    assert DURATION["chunk_id"] in ctx.seen_chunks and ctx.seen_chunks[DURATION["chunk_id"]]["text"] == DURATION["text"]
    sent = json.loads(be.requests[0].content)
    assert sent["query_vector"] == [0.1, 0.2, 0.3] and sent["top_k"] == 3 and set(sent) == {"query", "query_vector", "top_k"}
    assert ai.embed_calls == [["thời lượng thực tập tối thiểu"]]
    assert "Tìm thấy" in result.summary


def test_search_falls_back_to_keyword_when_embedding_fails_or_unsupported():
    for ai in (FakeAi(embed_ok=False),):
        be, client, _, ctx = setup(ai=ai)
        result = run(SearchPolicyTool(client, ai).run({"query": "thời lượng thực tập"}, ctx))
        assert result.ok and result.data["mode"] == "keyword"
        assert json.loads(be.requests[0].content)["query_vector"] is None


def test_search_no_match_and_validation():
    be, client, ai, ctx = setup()
    tool = SearchPolicyTool(client, ai)
    result = run(tool.run({"query": "zzzz qqqq"}, ctx))
    assert result.ok and result.data == {"status": "no_match", "mode": "hybrid", "chunks": []} and ctx.seen_chunks == {}
    assert not run(tool.run({"query": "  "}, ctx)).ok
    assert run(tool.run({"query": "x" * 2000, "top_k": 99}, ctx)).ok
    sent = json.loads(be.requests[-1].content)
    assert len(sent["query"]) == 500 and sent["top_k"] == 8
    assert tool.describe({"query": "tra gì đó"}).endswith("tra gì đó")


def test_search_maps_be_errors_to_failed_tool_result():
    _, client, ai, ctx = setup(be=FakeBe(fail_status=503))
    result = run(SearchPolicyTool(client, ai).run({"query": "thời lượng"}, ctx))
    assert not result.ok and result.error.code == "be_error"


def test_get_clause_records_clause_and_neighbors_and_not_found():
    be, client, _, ctx = setup()
    tool = GetPolicyClauseTool(client)
    ok = run(tool.run({"chunk_id": DURATION["chunk_id"], "with_neighbors": True}, ctx))
    assert ok.ok and ok.data["chunk"]["chunk_id"] == DURATION["chunk_id"] and ok.data["neighbors"]
    assert {DURATION["chunk_id"], ok.data["neighbors"][0]["chunk_id"]} <= ctx.seen_chunks.keys()
    missing = run(tool.run({"chunk_id": "khong-co"}, ctx))
    assert not missing.ok and missing.error.code == "not_found"
    assert not run(tool.run({"chunk_id": "../me/progress"}, ctx)).ok
    assert all("me/" not in p for p in be.paths())


@pytest.mark.parametrize("name,endpoint", [(n, e) for n, e, _, _ in PERSONAL_TOOLS])
def test_personal_tools_call_matching_endpoint_without_subject(name, endpoint):
    be, client, ai, ctx = setup()
    tool = build_registry("student", client, ai).get(name)
    result = run(tool.run({}, ctx))
    assert result.ok and result.data["available"] is True
    assert be.paths() == [f"GET /api/agent-tools/me/{endpoint}"]
    assert be.requests[0].url.query == b""  # không có tham số chủ thể nào trong URL


def test_personal_tool_no_record_and_forbidden():
    _, client, ai, ctx = setup(be=FakeBe(personal=None))
    result = run(build_registry("student", client, ai).get("get_my_progress").run({}, ctx))
    assert result.ok and result.data == {"available": False, "reason": "no_internship_record"} and "Chưa có hồ sơ" in result.summary
    _, client, ai, ctx = setup(be=FakeBe(forbidden_personal=True))
    result = run(build_registry("student", client, ai).get("get_my_progress").run({}, ctx))
    assert not result.ok and result.error.code == "forbidden_role"


def test_registry_by_role():
    _, client, ai, _ = setup()
    student = build_registry("student", client, ai).names()
    assert student == [
        "search_policy", "get_policy_clause", "get_my_internship", "get_my_milestones", "get_my_progress", "get_my_credit_checklist", "get_my_requests", "navigate_to",
    ]  # fmt: skip
    for role in ("lecturer", "admin"):
        assert build_registry(role, client, ai).names() == [
            "search_policy", "get_policy_clause", "get_staff_queue", "list_risk_flags", "get_dashboard_summary", "list_internships", "navigate_to",
        ]  # fmt: skip
    assert build_registry("student", client, ai).data_tool_names() == frozenset(n for n in student if n.startswith("get_my_"))  # navigate_to không phải tool dữ liệu
    assert build_registry("lecturer", client, ai).data_tool_names() == frozenset({"get_staff_queue", "list_risk_flags", "get_dashboard_summary", "list_internships"})
