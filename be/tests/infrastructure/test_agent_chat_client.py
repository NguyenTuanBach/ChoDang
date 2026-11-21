"""``AgentApiClient.chat()`` và ``embed()`` với agent giả (WebSocket server thật trên localhost, HTTP giả bằng MockTransport)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from tests.fake_agent import fake_agent
from vin15.domain.exception import AgentTimeoutError, AgentUnavailableError
from vin15.infrastructure.agent_api import AgentApiClient

START = {
    "type": "start",
    "conversation_id": "1",
    "turn_id": "t1",
    "question": "hỏi",
    "history": [],
    "actor": {"role": "student", "agent_token": "x"},
    "today": "2026-11-21",
}


async def collect(client, **kw):
    return [frame async for frame in client.chat(START, **kw)]


@pytest.mark.anyio
async def test_streams_frames_until_final_and_sends_start():
    received = []

    async def handler(ws):
        received.append(json.loads(await ws.recv()))
        for frame in ({"type": "ready"}, {"type": "token", "delta": "Xin"}, {"type": "final", "answer": "Xin chào", "trace_id": "tr"}):
            await ws.send(json.dumps(frame))
        await ws.close(1000)

    async with fake_agent(handler) as url:
        frames = await collect(AgentApiClient(url, "tok"))
    assert [f["type"] for f in frames] == ["ready", "token", "final"]
    assert received[0]["question"] == "hỏi" and received[0]["actor"]["agent_token"] == "x"


@pytest.mark.anyio
async def test_stops_after_error_frame():
    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"type": "error", "code": "busy", "message": "bận"}))
        await ws.send(json.dumps({"type": "token", "delta": "không đọc"}))

    async with fake_agent(handler) as url:
        frames = await collect(AgentApiClient(url, "tok"))
    assert [f["type"] for f in frames] == ["error"]


@pytest.mark.anyio
async def test_wrong_service_token_is_unavailable():
    async def handler(ws):
        await ws.recv()

    async with fake_agent(handler) as url:
        with pytest.raises(AgentUnavailableError, match="4401"):  # agent thật: nhận kết nối rồi đóng 4401
            await collect(AgentApiClient(url, "sai-token"))


@pytest.mark.anyio
async def test_cancel_event_sends_cancel_frame_and_keeps_reading():
    seen = []

    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"type": "status", "step": "searching", "text": "..."}))
        seen.append(json.loads(await ws.recv()))  # chờ khung cancel
        await ws.send(json.dumps({"type": "error", "code": "cancelled", "message": "đã hủy"}))

    cancel = asyncio.Event()
    async with fake_agent(handler) as url:
        frames = []
        async for frame in AgentApiClient(url, "tok").chat(START, cancel=cancel):
            frames.append(frame["type"])
            if frame["type"] == "status":
                cancel.set()
    assert seen == [{"type": "cancel"}] and frames == ["status", "error"]


@pytest.mark.anyio
async def test_connection_closed_before_final_is_unavailable():
    async def handler(ws):
        await ws.recv()
        await ws.close(1011)

    async with fake_agent(handler) as url:
        with pytest.raises(AgentUnavailableError, match="1011"):
            await collect(AgentApiClient(url, "tok"))


@pytest.mark.anyio
async def test_deadline_raises_timeout():
    async def handler(ws):
        await ws.recv()
        await asyncio.sleep(1)

    async with fake_agent(handler) as url:
        with pytest.raises(AgentTimeoutError):
            await collect(AgentApiClient(url, "tok"), deadline_seconds=0.3)


@pytest.mark.anyio
async def test_closing_generator_early_closes_connection():
    closed = asyncio.Event()

    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"type": "token", "delta": "a"}))
        try:
            await ws.recv()
        except Exception:
            closed.set()

    async with fake_agent(handler) as url:
        gen = AgentApiClient(url, "tok").chat(START)
        assert (await gen.__anext__())["type"] == "token"
        await gen.aclose()
        await asyncio.wait_for(closed.wait(), 2)


@pytest.mark.anyio
async def test_unreachable_or_disabled_agent_is_unavailable():
    with pytest.raises(AgentUnavailableError, match="AGENT_API_URL"):
        await collect(AgentApiClient("", "tok"))
    with pytest.raises(AgentUnavailableError):
        await collect(AgentApiClient("http://127.0.0.1:1", "tok"))


@pytest.mark.anyio
async def test_embed_posts_texts_and_returns_vectors():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "m", "dimensions": 3, "vectors": [[0.1, 0.2, 0.3]]})

    client = AgentApiClient("http://agent.test", "tok", transport=httpx.MockTransport(handler))
    result = await client.embed(["a"])
    assert seen == {"auth": "Bearer tok", "body": {"texts": ["a"]}}
    assert result.model == "m" and result.vectors == [[0.1, 0.2, 0.3]]


@pytest.mark.anyio
async def test_embed_llm_unavailable_maps_to_agent_unavailable():
    client = AgentApiClient(
        "http://agent.test",
        "tok",
        transport=httpx.MockTransport(lambda r: httpx.Response(503, json={"error": {"code": "llm_unavailable"}})),
    )
    with pytest.raises(AgentUnavailableError, match="503"):
        await client.embed(["a"])
