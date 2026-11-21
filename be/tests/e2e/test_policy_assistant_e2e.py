"""Task 19: BE thật + agent thật (tiến trình riêng) + LLM giả, qua WebSocket FE↔BE như trình duyệt. Chạy: ``make e2e``."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from tests.e2e.conftest import SERVICE_TOKEN
from vin15.domain.exception import AgentUnavailableError
from vin15.infrastructure.agent_api.agent_client import AgentApiClient

pytestmark = pytest.mark.e2e

GROUNDED = "Thời lượng thực tập tối thiểu là bao nhiêu tuần để được quy đổi tín chỉ?"


def types(frames):
    return [f["type"] for f in frames]


def test_grounded_question_streams_steps_and_cites_a_real_chunk(fresh):
    frames = fresh.ask(GROUNDED)
    final = frames[-1]
    assert final["type"] == "final" and final["verdict"] == "answered" and not final["degraded"]
    assert {"status", "tool_call", "tool_result", "token"} <= set(types(frames))
    assert any(f["type"] == "tool_call" and f["name"] == "search_policy" for f in frames)
    assert final["citations"] and f"[cite:{final['citations'][0]['chunk_id']}]" in final["answer"]
    assert "".join(f["delta"] for f in frames if f["type"] == "token").strip() == final["answer"].strip()
    # Trích dẫn trỏ tới đoạn có thật ở BE (tool tra nguyên văn bằng service token).
    chunk_id = final["citations"][0]["chunk_id"]
    response = httpx.get(f"{fresh.be_url}/api/agent-tools/policy/chunks/{chunk_id}", headers={"Authorization": f"Bearer {SERVICE_TOKEN}"})
    assert response.status_code == 200 and response.json()["chunk"]["chunk_id"] == chunk_id
    assert final["citations"][0]["is_sample"] is True
    # Đã lưu: lấy lại qua REST.
    detail = fresh.session.get(f"/api/assistant/conversations/{final['conversation_id']}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"] and detail["messages"][1]["content"] == final["answer"]


def test_question_without_basis_gets_not_found_template(fresh):
    frames = fresh.ask("Thời tiết hôm nay ở Hà Nội thế nào?")
    final = frames[-1]
    assert final["type"] == "final" and final["verdict"] == "no_match" and final["citations"] == []
    assert "[cite:" not in final["answer"]


def test_llm_down_returns_degraded_answer_with_verbatim_clauses(fresh):
    fresh.fake.fail_chat = fresh.fake.fail_embeddings = True
    final = fresh.ask(GROUNDED)[-1]
    assert final["type"] == "final" and final["degraded"] is True and final["verdict"] == "degraded"
    assert final["citations"]  # nguyên văn từ khóa, không cần LLM


def test_cancel_stops_the_turn(fresh):
    fresh.fake.delay_seconds = 8
    frames = fresh.ask(GROUNDED, cancel_after_first_frame=True, timeout=15)
    assert frames[-1]["type"] == "error" and frames[-1]["code"] == "cancelled"
    assert "final" not in types(frames)


def test_personal_and_policy_tools_run_for_the_default_student_and_are_audited(fresh):
    before = _agent_audit_count(fresh)
    frames = fresh.ask("[me] Tôi còn thiếu gì để được quy đổi tín chỉ?")
    names = {f["name"] for f in frames if f["type"] == "tool_call"}
    assert {"get_my_credit_checklist", "search_policy"} <= names
    assert frames[-1]["type"] == "final" and frames[-1]["citations"]
    assert _agent_audit_count(fresh) >= before + 2  # P8: mỗi lời gọi tool một audit_event actor_kind='agent'


def test_real_agent_closes_4401_for_wrong_service_token(fresh):
    client = AgentApiClient(fresh.agent_url, "sai-token", timeout=5)

    async def run():
        start = {
            "type": "start", "conversation_id": "c", "turn_id": "t", "question": "hỏi", "history": [],
            "actor": {"role": "student", "agent_token": ""}, "today": "2026-11-21",
        }  # fmt: skip
        async for _ in client.chat(start):
            pass

    with pytest.raises(AgentUnavailableError, match="4401"):
        asyncio.run(run())


def _agent_audit_count(stack) -> int:
    with stack.database.connection() as conn:
        return conn.execute("select count(*) as n from audit_event where actor_kind = 'agent'").fetchone()["n"]
