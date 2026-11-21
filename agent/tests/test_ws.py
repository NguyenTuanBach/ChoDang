"""WebSocket của agent và /v1/embeddings (task 9): bắt tay, khung, cancel (P12), giới hạn khung. LLM giả + BE giả."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from fakes import DURATION, FakeAi, FakeBe, reply
from vin15_agent.core.ai_client import AiClient, LlmEndpoint, LlmUnavailableError
from vin15_agent.policy_assistant.protocol import MAX_FRAME_BYTES
from vin15_agent.runtime.http import policy_assistant as ws_module
from vin15_agent.runtime.http.app import create_app
from vin15_agent.shared.settings import Settings

D = DURATION["chunk_id"]
AUTH = {"Authorization": "Bearer tok"}
PATH = "/v1/policy-assistant/ws"
START = {
    "type": "start", "conversation_id": "c1", "turn_id": "t1", "question": "Thực tập tối thiểu bao lâu?",
    "history": [], "actor": {"role": "student", "agent_token": ""}, "today": "2026-11-21",
}  # fmt: skip


def make_client(ai=None, be=None, **settings_kw):
    settings = Settings(_env_file=None, agent_api_service_token="tok", be_api_url="http://be", agent_turn_seconds=5, **settings_kw)
    ai = ai or FakeAi(reply("", [("c1", "search_policy", {"query": "thời lượng"})]), reply(f"Cần 8 tuần [cite:{D}]."))
    be = be or FakeBe()
    return TestClient(create_app(settings, ai_client=ai, be_transport=be.transport())), ai, be


def drain(ws):
    frames = []
    while True:
        frames.append(ws.receive_json())
        if frames[-1]["type"] in ("final", "error"):
            return frames


def close_code(ws) -> int:
    with pytest.raises(WebSocketDisconnect) as exc:
        ws.receive_json()
    return exc.value.code


# ---------------------------------------------------------------- bắt tay


def test_full_turn_frames_in_contract_order_and_close_1000():
    client, ai, be = make_client()
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_json(START)
        frames = drain(ws)
        assert close_code(ws) == 1000
    kinds = [f["type"] for f in frames]
    assert kinds[0] == "ready" and kinds[-1] == "final"
    assert {"status", "tool_call", "tool_result", "token"} <= set(kinds)
    final = frames[-1]
    assert final["verdict"] == "answered" and final["degraded"] is False and final["citations"][0]["chunk_id"] == D
    assert set(final) == {"type", "answer", "citations", "verdict", "degraded", "usage", "trace_id"}
    assert "".join(f["delta"] for f in frames if f["type"] == "token") == final["answer"]
    assert set(final["citations"][0]) == {"chunk_id", "doc_code", "doc_title", "version", "article", "clause", "effective_from", "is_sample", "quote"}


def test_wrong_or_missing_service_token_closes_4401_without_running_anything():
    client, ai, be = make_client()
    for headers in ({}, {"Authorization": "Bearer sai"}, {"Authorization": "Basic tok"}):
        with client.websocket_connect(PATH, headers=headers) as ws:
            assert close_code(ws) == 4401
    assert ai.calls == [] and be.requests == []


def test_first_frame_must_be_valid_start_else_1003():
    client, _, _ = make_client()
    for payload in ("không phải json", json.dumps({"type": "ping"}), json.dumps({"type": "cancel"}), json.dumps({"type": "start"}), json.dumps([1])):
        with client.websocket_connect(PATH, headers=AUTH) as ws:
            ws.send_text(payload)
            assert close_code(ws) == 1003, payload
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_bytes(b"\x00\x01")
        assert close_code(ws) == 1003


def test_oversized_frame_closes_1009():
    client, ai, _ = make_client()
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_text(json.dumps({**START, "question": "x" * (MAX_FRAME_BYTES + 10)}))
        assert close_code(ws) == 1009
    assert ai.calls == []


def test_no_start_in_time_closes_4408(monkeypatch):
    monkeypatch.setattr(ws_module, "START_TIMEOUT_SECONDS", 0.1)
    client, _, _ = make_client()
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        assert close_code(ws) == 4408


def test_busy_when_too_many_concurrent_turns():
    client, ai, _ = make_client(assistant_max_concurrent_turns=0)
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_json(START)
        assert ws.receive_json()["code"] == "busy"
        assert close_code(ws) == 1000
    assert ai.calls == []


# ---------------------------------------------------------------- trong lượt: ping, cancel, rớt kết nối


def _blocking_ai(state):
    async def hang(messages, kw):
        state["entered"] += 1
        try:
            await asyncio.Event().wait()
        finally:
            state["cancelled"] = True

    return FakeAi(hang)


def test_ping_is_answered_with_pong_during_turn():
    state = {"entered": 0, "cancelled": False}
    client, _, _ = make_client(ai=_blocking_ai(state))
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_json(START)
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "ping"})
        seen = []
        while (f := ws.receive_json())["type"] != "pong":
            seen.append(f["type"])
        ws.send_json({"type": "cancel"})
        assert drain(ws)[-1]["code"] == "cancelled"


def test_cancel_stops_turn_and_sends_cancelled_then_closes_1000_p12():
    state = {"entered": 0, "cancelled": False}
    ai = _blocking_ai(state)
    client, _, be = make_client(ai=ai)
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_json(START)
        while ws.receive_json()["type"] != "status":
            pass
        ws.send_json({"type": "cancel"})
        last = drain(ws)[-1]
        assert last == {"type": "error", "code": "cancelled", "message": "Đã dừng theo yêu cầu."}
        assert close_code(ws) == 1000
    assert state["cancelled"] is True and state["entered"] == 1 and len(ai.calls) == 1  # không có lời gọi LLM mới
    assert be.requests == []


def test_client_disconnect_cancels_running_turn():
    state = {"entered": 0, "cancelled": False}
    client, _, _ = make_client(ai=_blocking_ai(state))
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_json(START)
        while ws.receive_json()["type"] != "status":
            pass
    assert state["cancelled"] is True


def test_start_twice_or_garbage_during_turn_closes_1003():
    state = {"entered": 0, "cancelled": False}
    client, _, _ = make_client(ai=_blocking_ai(state))
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_json(START)
        ws.send_json(START)
        while True:
            try:
                ws.receive_json()
            except WebSocketDisconnect as exc:
                assert exc.code == 1003
                break
    assert state["cancelled"] is True


def test_degraded_turn_over_ws():
    client, ai, _ = make_client(ai=FakeAi(LlmUnavailableError("sập")))
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_json({**START, "question": "thời lượng thực tập tối thiểu"})
        final = drain(ws)[-1]
    assert final["degraded"] is True and final["verdict"] == "degraded"


def test_start_without_token_field_uses_default_and_forwards_agent_token():
    client, _, be = make_client()
    with client.websocket_connect(PATH, headers=AUTH) as ws:
        ws.send_json({**START, "actor": {"role": "student", "agent_token": "AT-1"}})
        drain(ws)
    assert be.requests[0].headers["x-on-behalf-of"] == "AT-1"


# ---------------------------------------------------------------- /v1/embeddings, /v1/info


class _FakeEmbedClient:
    def __init__(self, error=None):
        self.error = error
        self.embeddings = type("E", (), {"create": self._embed})()

    async def _embed(self, **kw):
        if self.error:
            raise self.error
        return type("R", (), {"data": [type("D", (), {"index": i, "embedding": [float(i), 1.0]})() for i, _ in enumerate(kw["input"])]})()


def _embed_app(error=None, caps=frozenset({"embed"})):
    ep = LlmEndpoint(name="openai", client=_FakeEmbedClient(error), model="m", max_tokens_param="max_tokens", capabilities=caps, embedding_model="emb-x")
    settings = Settings(_env_file=None, agent_api_service_token="tok")
    return TestClient(create_app(settings, ai_client=AiClient([ep], temperature=0.1, max_tokens=10)))


def test_embeddings_requires_token_and_validates_input():
    client = _embed_app()
    assert client.post("/v1/embeddings", json={"texts": ["a"]}).status_code == 401
    for bad in ({"texts": []}, {"texts": ["x" * 9000]}, {"texts": ["a"] * 300}, {}):
        assert client.post("/v1/embeddings", json=bad, headers=AUTH).status_code == 422


def test_embeddings_returns_model_dimensions_vectors():
    response = _embed_app().post("/v1/embeddings", json={"texts": ["a", "b"]}, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"model": "emb-x", "dimensions": 2, "vectors": [[0.0, 1.0], [1.0, 1.0]]}


def test_embeddings_llm_unavailable_is_503_with_code():
    response = _embed_app(caps=frozenset()).post("/v1/embeddings", json={"texts": ["a"]}, headers=AUTH)
    assert response.status_code == 503 and response.json()["error"]["code"] == "llm_unavailable"
    unconfigured = TestClient(create_app(Settings(_env_file=None, agent_api_service_token="tok")))
    assert unconfigured.post("/v1/embeddings", json={"texts": ["a"]}, headers=AUTH).status_code == 503


def test_info_lists_policy_assistant(client):
    assert client.get("/v1/info", headers={"Authorization": "Bearer tok"}).json()["agents"] == ["policy_assistant", "intake", "monitor", "pre_review"]
