"""``POST /api/assistant/ws-ticket`` và ``WS /api/assistant/ws``: vé, Origin, auth, busy, cancel, rate limit, kích thước, ping/idle."""

from __future__ import annotations

import asyncio
import json
import threading

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.conftest import make_settings
from tests.fakes import ADMIN, LECTURER, STUDENT_A, STUDENT_B, TODAY, FakeChats, FakeUsers
from vin15.config.container import Container
from vin15.main import create_app
from vin15.presentation.controller import assistant_controller

ORIGIN = {"origin": "http://localhost:3000"}


class FakeOrchestrator:
    """Thay ``AssistantOrchestrator``: ghi lại lời gọi; câu hỏi "chạy lâu" chờ ``cancel`` hoặc ``release``."""

    def __init__(self):
        self.calls = []
        self.finished = threading.Event()
        self.release = threading.Event()
        self.cancelled = threading.Event()

    async def run_turn(self, user, conversation_id, turn_id, question, send, cancel=None):
        self.calls.append((user.id, conversation_id, turn_id, question))

        async def emit(frame):  # như orchestrator thật: FE rớt thì bỏ qua khung, không làm hỏng lượt
            try:
                await send(frame)
            except Exception:
                pass

        ref = {"turn_id": turn_id, "conversation_id": "1"}
        await emit({"type": "status", "step": "searching", "text": "Đang tra", **ref})
        if question == "chạy lâu":
            while not self.release.is_set():
                if cancel is not None and cancel.is_set():
                    self.cancelled.set()
                    await emit({"type": "error", "code": "cancelled", "message": "Đã hủy", **ref})
                    self.finished.set()
                    return
                await asyncio.sleep(0.02)
        await emit(
            {
                "type": "final",
                "answer": "ok",
                "citations": [],
                "verdict": "answered",
                "degraded": False,
                "usage": {},
                "trace_id": "tr",
                "message_id": "9",
                **ref,
            }
        )
        self.finished.set()


def build(**overrides):
    settings = make_settings(
        agent_dev_default_user_email="sv.a@example.test", jwt_secret="j" * 40, assistant_ws_auth_seconds=0.5, **overrides
    )
    container = Container(settings)
    container.clock = lambda: TODAY
    container.user_repository = FakeUsers(ADMIN, LECTURER, STUDENT_A, STUDENT_B)
    container.chat_repository = FakeChats()
    container.assistant_orchestrator = FakeOrchestrator()
    return container


@pytest.fixture
def container():
    return build()


@pytest.fixture
def client(container):
    with TestClient(create_app(container.settings, container)) as test_client:
        yield test_client


def ticket(client, headers=None) -> str:
    response = client.post("/api/assistant/ws-ticket", headers=headers or {})
    assert response.status_code == 200, response.text
    return response.json()["ticket"]


def open_ws(client, headers=ORIGIN):
    return client.websocket_connect("/api/assistant/ws", headers=headers)


def authed(client, user_headers=None):
    t = ticket(client, user_headers)  # lấy vé trước khi mở WebSocket (hạn auth chỉ vài giây)
    ws = open_ws(client).__enter__()
    ws.send_json({"type": "auth", "ticket": t})
    assert ws.receive_json() == {"type": "ready"}
    return ws


def finish(ws):
    """Đóng phiên WebSocket đã mở bằng ``authed`` (thoát context để TestClient dọn luồng nền)."""
    ws.__exit__(None, None, None)


def ask(ws, question="Thời lượng?", turn_id="t1", conversation_id=None):
    ws.send_json({"type": "ask", "conversation_id": conversation_id, "turn_id": turn_id, "question": question})


def expect_close(ws, code):
    """Đọc (bỏ qua ping) cho tới khi server đóng; kiểm mã đóng."""
    with pytest.raises(WebSocketDisconnect) as info:
        for _ in range(50):
            frame = ws.receive_json()
            assert frame["type"] == "ping", frame
    assert info.value.code == code


# ---- Vé ----
def test_ws_ticket_for_dev_default_user_has_contract_shape(client, container):
    body = client.post("/api/assistant/ws-ticket").json()
    assert set(body) == {"ticket", "expires_in"} and body["expires_in"] == 30 and len(body["ticket"]) >= 24
    assert container.ws_ticket_store.consume(body["ticket"]) == STUDENT_A.id


def test_ws_ticket_with_session_token_uses_that_user(client, container):
    token = container.token_service.create(STUDENT_B.id, "student")
    t = client.post("/api/assistant/ws-ticket", headers={"Authorization": f"Bearer {token}"}).json()["ticket"]
    assert container.ws_ticket_store.consume(t) == STUDENT_B.id


def test_ws_ticket_requires_a_user_outside_dev():
    container = build()
    settings = make_settings(jwt_secret="j" * 40)  # không có người dùng mặc định
    other = Container(settings)
    other.user_repository = container.user_repository
    with TestClient(create_app(settings, other)) as client:
        assert client.post("/api/assistant/ws-ticket").status_code == 401


def test_ws_ticket_endpoint_is_rate_limited(client):
    statuses = [client.post("/api/assistant/ws-ticket").status_code for _ in range(32)]
    assert statuses[:30] == [200] * 30 and statuses[30:] == [429, 429]


# ---- Bắt tay và xác thực ----
def test_disallowed_origin_is_refused_at_handshake(client):
    with pytest.raises(Exception) as info, open_ws(client, {"origin": "https://evil.example"}):
        pass
    assert "403" in repr(info.value) or isinstance(info.value, WebSocketDisconnect)


def test_missing_origin_allowed_in_dev_but_not_in_production():
    dev = build()
    with TestClient(create_app(dev.settings, dev)) as client:
        t = ticket(client)
        with client.websocket_connect("/api/assistant/ws") as ws:
            ws.send_json({"type": "auth", "ticket": t})
            assert ws.receive_json() == {"type": "ready"}
    settings = make_settings(
        app_env="production",
        jwt_secret="j" * 40,
        database_url="postgresql://u:p@h:5432/db",
        migrations_enabled=False,
        cors_origins="https://truong.edu.vn",
        agent_api_url="http://agent:8100",
        agent_api_service_token="real-secret",
        app_admin_emails="qtv@truong.edu.vn",
    )
    prod = Container(settings)
    prod.database = None  # không mở kết nối thật
    with TestClient(create_app(settings, prod)) as client:
        for headers in ({}, {"origin": "http://localhost:3000"}):
            with pytest.raises(Exception):  # noqa: B017 - bị từ chối lúc bắt tay
                with client.websocket_connect("/api/assistant/ws", headers=headers):
                    pass


def test_auth_ok_sends_ready_then_ping_pong(client):
    ws = authed(client)
    ws.send_json({"type": "ping"})
    assert ws.receive_json() == {"type": "pong"}
    finish(ws)


@pytest.mark.parametrize(
    "frame",
    [
        {"type": "auth", "ticket": "sai-ve"},
        {"type": "ask", "turn_id": "t", "question": "q"},
        {"type": "auth"},
        {"type": "auth", "ticket": 5},
    ],
)
def test_bad_first_frame_closes_4401(client, frame):
    with open_ws(client) as ws:
        ws.send_json(frame)
        expect_close(ws, 4401)


def test_garbage_first_frame_closes_4401(client):
    with open_ws(client) as ws:
        ws.send_text("không phải json")
        expect_close(ws, 4401)


def test_ticket_cannot_be_reused(client):
    t = ticket(client)
    with open_ws(client) as ws:
        ws.send_json({"type": "auth", "ticket": t})
        assert ws.receive_json()["type"] == "ready"
    with open_ws(client) as ws:
        ws.send_json({"type": "auth", "ticket": t})
        expect_close(ws, 4401)


def test_no_auth_within_deadline_closes_4401(client):
    with open_ws(client) as ws:
        expect_close(ws, 4401)  # assistant_ws_auth_seconds=0.5 trong build()


# ---- Lượt hỏi ----
def test_ask_forwards_orchestrator_frames_and_passes_arguments(client, container):
    ws = authed(client)
    ask(ws, "Thời lượng tối thiểu?", "t42", "7")
    assert ws.receive_json()["type"] == "status"
    final = ws.receive_json()
    assert final["type"] == "final" and final["message_id"] == "9" and final["turn_id"] == "t42"
    assert container.assistant_orchestrator.calls == [(STUDENT_A.id, "7", "t42", "Thời lượng tối thiểu?")]
    finish(ws)


def test_ask_when_turn_running_is_busy_then_works_after_finish(client, container):
    orchestrator = container.assistant_orchestrator
    ws = authed(client)
    ask(ws, "chạy lâu", "t1")
    assert ws.receive_json()["type"] == "status"
    ask(ws, "câu thứ hai", "t2")
    busy = ws.receive_json()
    assert busy["type"] == "error" and busy["code"] == "busy" and busy["turn_id"] == "t2"
    assert len(orchestrator.calls) == 1
    orchestrator.release.set()
    assert ws.receive_json()["type"] == "final"
    orchestrator.release.clear()
    ask(ws, "câu thứ ba", "t3")
    assert ws.receive_json()["type"] == "status" and ws.receive_json()["type"] == "final"
    finish(ws)


def test_cancel_reaches_the_running_turn_only_for_its_turn_id(client, container):
    orchestrator = container.assistant_orchestrator
    ws = authed(client)
    ask(ws, "chạy lâu", "t1")
    assert ws.receive_json()["type"] == "status"
    ws.send_json({"type": "cancel", "turn_id": "khac"})  # sai turn_id: bỏ qua
    ws.send_json({"type": "ping"})
    assert ws.receive_json() == {"type": "pong"} and not orchestrator.cancelled.is_set()
    ws.send_json({"type": "cancel", "turn_id": "t1"})
    frame = ws.receive_json()
    assert frame["type"] == "error" and frame["code"] == "cancelled" and orchestrator.cancelled.is_set()
    finish(ws)


def test_turn_keeps_running_and_finishes_after_frontend_drops(client, container):
    orchestrator = container.assistant_orchestrator
    ws = authed(client)
    ask(ws, "chạy lâu", "t1")
    assert ws.receive_json()["type"] == "status"
    finish(ws)  # FE rớt giữa lượt
    assert not orchestrator.finished.wait(0.2)  # lượt chưa bị hủy
    orchestrator.release.set()
    assert orchestrator.finished.wait(3)  # chạy hết (và orchestrator thật sẽ lưu final)


def test_ask_rate_limit_returns_rate_limited_without_calling_agent():
    container = build(assistant_ask_per_minute=2)
    with TestClient(create_app(container.settings, container)) as client:
        ws = authed(client)
        for i in range(2):
            ask(ws, "hỏi", f"t{i}")
            assert ws.receive_json()["type"] == "status" and ws.receive_json()["type"] == "final"
        ask(ws, "hỏi thêm", "t3")
        limited = ws.receive_json()
        assert (
            limited["type"] == "error" and limited["code"] == "rate_limited" and limited["retry_after"] >= 1 and limited["turn_id"] == "t3"
        )
        assert len(container.assistant_orchestrator.calls) == 2
        finish(ws)


def test_connection_limit_per_user_closes_4429():
    container = build(assistant_max_connections_per_user=1)
    with TestClient(create_app(container.settings, container)) as client:
        first = authed(client)
        t = ticket(client)
        with open_ws(client) as second:
            second.send_json({"type": "auth", "ticket": t})
            assert second.receive_json()["code"] == "rate_limited"
            expect_close(second, 4429)
        finish(first)
        # Sau khi đóng kết nối đầu, mở lại được.
        again = authed(client)
        finish(again)


def test_connection_limit_is_per_user():
    container = build(assistant_max_connections_per_user=1)
    token_b = container.token_service.create(STUDENT_B.id, "student")
    with TestClient(create_app(container.settings, container)) as client:
        a = authed(client)
        b = authed(client, {"Authorization": f"Bearer {token_b}"})
        finish(a)
        finish(b)


def test_invalid_frames_get_error_without_closing(client, container):
    ws = authed(client)
    ws.send_text("{không phải json")
    assert ws.receive_json()["code"] == "invalid_frame"
    ws.send_json([1, 2])
    assert ws.receive_json()["code"] == "invalid_frame"
    ws.send_json({"type": "bay-bay"})
    assert ws.receive_json()["code"] == "invalid_frame"
    for bad in (
        {"type": "ask", "turn_id": "", "question": "q"},
        {"type": "ask", "turn_id": "t 1 có khoảng trắng", "question": "q"},
        {"type": "ask", "turn_id": "t1", "question": "   "},
        {"type": "ask", "turn_id": "t1", "question": 5},
        {"type": "ask", "turn_id": "t1", "question": "x" * 2001},
        {"type": "ask", "turn_id": "t1", "question": "q", "conversation_id": ["x"]},
        {"type": "auth", "ticket": "lại"},
    ):
        ws.send_json(bad)
        assert ws.receive_json()["code"] == "invalid_frame", bad
    assert container.assistant_orchestrator.calls == []
    ws.send_json({"type": "ping"})
    assert ws.receive_json() == {"type": "pong"}
    finish(ws)


def test_oversized_frame_closes_1009():
    container = build(assistant_max_frame_bytes=1000)
    with TestClient(create_app(container.settings, container)) as client:
        ws = authed(client)
        ws.send_text(json.dumps({"type": "ask", "turn_id": "t1", "question": "x" * 2000}))
        expect_close(ws, 1009)
        finish(ws)


def test_idle_connection_gets_ping_then_closed_4408(client, monkeypatch):
    monkeypatch.setattr(assistant_controller, "PING_SECONDS", 0.1)
    monkeypatch.setattr(assistant_controller, "IDLE_SECONDS", 0.35)
    ws = authed(client)
    assert ws.receive_json() == {"type": "ping"}  # BE chủ động ping khi im lặng
    expect_close(ws, 4408)
    finish(ws)


def test_replying_to_ping_keeps_connection_alive(client, monkeypatch):
    monkeypatch.setattr(assistant_controller, "PING_SECONDS", 0.1)
    monkeypatch.setattr(assistant_controller, "IDLE_SECONDS", 0.35)
    ws = authed(client)
    for _ in range(6):  # ~0.6 s > IDLE nếu không trả lời
        assert ws.receive_json() == {"type": "ping"}
        ws.send_json({"type": "pong"})
    finish(ws)


def test_without_database_ws_closes_1011():
    settings = make_settings(jwt_secret="j" * 40)
    container = Container(settings)
    with TestClient(create_app(settings, container)) as client:
        t = container.ws_ticket_store.issue(1)
        with client.websocket_connect("/api/assistant/ws", headers=ORIGIN) as ws:
            ws.send_json({"type": "auth", "ticket": t})
            expect_close(ws, 1011)
