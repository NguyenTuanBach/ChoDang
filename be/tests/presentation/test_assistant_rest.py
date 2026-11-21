"""REST của trợ lý (danh sách/chi tiết hội thoại, vết) và luồng đầu-cuối phía BE: WebSocket FE + orchestrator thật + agent giả."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from tests.fake_agent import FINAL, fake_agent_in_thread, script
from tests.fakes import ADMIN, LECTURER, STUDENT_A, STUDENT_B, TODAY, FakeAudit, FakeChats, FakeUsers
from vin15.config.container import Container
from vin15.main import create_app

ORIGIN = {"origin": "http://localhost:3000"}


def build(agent_url="", **overrides):
    settings = make_settings(
        agent_dev_default_user_email="sv.a@example.test",
        jwt_secret="j" * 40,
        agent_api_url=agent_url,
        agent_api_service_token="tok",
        **overrides,
    )
    container = Container(settings)
    container.clock = lambda: TODAY
    container.user_repository = FakeUsers(ADMIN, LECTURER, STUDENT_A, STUDENT_B)
    container.chat_repository = FakeChats()
    container.audit_repository = FakeAudit()
    return container


def bearer(container, user) -> dict:
    return {"Authorization": f"Bearer {container.token_service.create(user.id, user.role.value)}"}


def seed_turn(container, user, turn="t1", trace_id="tr-1"):
    chats: FakeChats = container.chat_repository
    conversation = chats.create_conversation(user.id, "Thời lượng thực tập")
    chats.add_message(conversation.id, turn, "user", "Thời lượng tối thiểu?")
    chats.add_message(
        conversation.id,
        turn,
        "assistant",
        "8 tuần [cite:QD-TT-01@v1/d3/k1]",
        citations=FINAL["citations"],
        trace={"trace_id": trace_id, "steps": []},
    )
    return conversation


# ---- Hội thoại: chỉ chủ sở hữu ----
def test_list_and_get_own_conversation_have_contract_shape():
    container = build()
    conversation = seed_turn(container, STUDENT_A)
    seed_turn(container, STUDENT_B)
    client = TestClient(create_app(container.settings, container))
    listing = client.get("/api/assistant/conversations").json()  # người dùng mặc định = SV A
    assert [c["id"] for c in listing] == [str(conversation.id)] and set(listing[0]) == {"id", "title", "created_at", "updated_at"}
    detail = client.get(f"/api/assistant/conversations/{conversation.id}").json()
    assert set(detail) == {"id", "title", "messages"} and detail["id"] == str(conversation.id)
    user_msg, assistant_msg = detail["messages"]
    assert set(assistant_msg) == {"id", "turn_id", "role", "content", "citations", "degraded", "created_at"}
    assert (
        user_msg["role"] == "user"
        and assistant_msg["role"] == "assistant"
        and assistant_msg["citations"][0]["chunk_id"] == "QD-TT-01@v1/d3/k1"
    )
    assert "trace" not in assistant_msg  # vết không lộ qua danh sách tin nhắn


def test_other_users_conversation_is_404_and_not_listed():
    container = build()
    theirs = seed_turn(container, STUDENT_B)
    client = TestClient(create_app(container.settings, container))
    assert client.get(f"/api/assistant/conversations/{theirs.id}").status_code == 404
    assert client.get("/api/assistant/conversations/999").status_code == 404
    assert client.get("/api/assistant/conversations/abc").status_code == 404
    assert client.get("/api/assistant/conversations").json() == []
    assert client.get(f"/api/assistant/conversations/{theirs.id}", headers=bearer(container, STUDENT_B)).status_code == 200
    # Ngay cả quản trị viên cũng không đọc nội dung hội thoại của người khác (chỉ vết).
    assert client.get(f"/api/assistant/conversations/{theirs.id}", headers=bearer(container, ADMIN)).status_code == 404


# ---- Vết ----
def test_trace_visible_to_owner_and_admin_only():
    container = build()
    seed_turn(container, STUDENT_B, trace_id="tr-b")
    client = TestClient(create_app(container.settings, container))
    assert client.get("/api/assistant/traces/tr-b").status_code == 404  # SV A (mặc định) không phải chủ
    owner = client.get("/api/assistant/traces/tr-b", headers=bearer(container, STUDENT_B))
    assert owner.status_code == 200 and owner.json()["trace"] == {"trace_id": "tr-b", "steps": []} and owner.json()["turn_id"] == "t1"
    assert client.get("/api/assistant/traces/tr-b", headers=bearer(container, ADMIN)).status_code == 200
    assert client.get("/api/assistant/traces/tr-b", headers=bearer(container, LECTURER)).status_code == 404
    assert client.get("/api/assistant/traces/khong-co", headers=bearer(container, ADMIN)).status_code == 404


def test_rest_endpoints_need_a_user_when_no_dev_default():
    container = build()
    settings = make_settings(jwt_secret="j" * 40)
    prod_like = Container(settings)
    prod_like.user_repository, prod_like.chat_repository = container.user_repository, container.chat_repository
    client = TestClient(create_app(settings, prod_like))
    for path in ("/api/assistant/conversations", "/api/assistant/conversations/1", "/api/assistant/traces/x"):
        assert client.get(path).status_code == 401


# ---- Đầu-cuối phía BE: FE WS -> orchestrator thật -> agent giả ----
def test_end_to_end_ask_streams_saves_and_is_readable_via_rest():
    frames = [
        {"type": "ready"},
        {"type": "status", "step": "searching", "text": "Đang tra quy định"},
        {"type": "tool_call", "name": "search_policy", "label": "Đang tra quy định…"},
        {"type": "tool_result", "name": "search_policy", "ok": True, "summary": "1 đoạn"},
        {"type": "token", "delta": "Thời lượng"},
        FINAL,
    ]
    record = []
    with fake_agent_in_thread(script(*frames, record=record)) as url:
        container = build(url)
        with TestClient(create_app(container.settings, container)) as client:
            t = client.post("/api/assistant/ws-ticket").json()["ticket"]
            with client.websocket_connect("/api/assistant/ws", headers=ORIGIN) as ws:
                ws.send_json({"type": "auth", "ticket": t})
                assert ws.receive_json() == {"type": "ready"}
                ws.send_json({"type": "ask", "conversation_id": None, "turn_id": "t1", "question": "Thời lượng tối thiểu?"})
                received = [ws.receive_json() for _ in range(5)]
            assert [f["type"] for f in received] == ["status", "tool_call", "tool_result", "token", "final"]
            assert all(f["turn_id"] == "t1" and f["conversation_id"] == "1" for f in received)
            final = received[-1]
            assert (
                final["answer"].startswith("Thời lượng tối thiểu là 8 tuần")
                and final["verdict"] == "answered"
                and final["message_id"] == "2"
            )
            assert final["citations"][0]["doc_code"] == "QD-TT-01" and final["trace_id"] == "tr-1"
            # Đã lưu: FE lấy lại qua REST.
            detail = client.get("/api/assistant/conversations/1").json()
            assert [m["role"] for m in detail["messages"]] == ["user", "assistant"] and detail["messages"][1]["content"] == final["answer"]
            assert client.get("/api/assistant/traces/tr-1").json()["trace"]["trace_id"] == "tr-1"
    start = record[0]
    assert start["actor"]["role"] == "student" and start["actor"]["agent_token"] and start["question"] == "Thời lượng tối thiểu?"
    assert [e.action for e in container.audit_repository.entries] == ["answer"]


def test_end_to_end_agent_down_reports_llm_unavailable_and_second_turn_continues_conversation():
    container = build("http://127.0.0.1:1")
    with TestClient(create_app(container.settings, container)) as client:
        t = client.post("/api/assistant/ws-ticket").json()["ticket"]
        with client.websocket_connect("/api/assistant/ws", headers=ORIGIN) as ws:
            ws.send_json({"type": "auth", "ticket": t})
            ws.receive_json()
            ws.send_json({"type": "ask", "conversation_id": None, "turn_id": "t1", "question": "hỏi"})
            error = ws.receive_json()
            assert error["type"] == "error" and error["code"] == "llm_unavailable" and error["conversation_id"] == "1"
            ws.send_json({"type": "ask", "conversation_id": "1", "turn_id": "t2", "question": "hỏi lại"})
            assert ws.receive_json()["code"] == "llm_unavailable"
        assert [m.turn_id for m in container.chat_repository.messages] == ["t1", "t2"]


@pytest.mark.parametrize("path", ["/api/assistant/ws-ticket"])
def test_ticket_only_via_post(path):
    container = build()
    assert TestClient(create_app(container.settings, container)).get(path).status_code == 405
