"""Agent giả: WebSocket server thật trên localhost, kiểm service token ở bắt tay như agent thật."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager, contextmanager

from websockets.asyncio.server import serve

FINAL = {
    "type": "final",
    "answer": "Thời lượng tối thiểu là 8 tuần. [cite:QD-TT-01@v1/d3/k1]",
    "citations": [
        {
            "chunk_id": "QD-TT-01@v1/d3/k1",
            "doc_code": "QD-TT-01",
            "doc_title": "Quy chế thực tập (mẫu)",
            "version": "v1",
            "article": "3",
            "clause": "1",
            "effective_from": "2026-01-01",
            "is_sample": True,
            "quote": "Thời lượng thực tập tối thiểu là 8 tuần.",
        }
    ],
    "verdict": "answered",
    "degraded": False,
    "usage": {"prompt_tokens": 100, "completion_tokens": 20, "provider": "openai", "model": "gpt-x"},
    "trace_id": "tr-1",
}


@asynccontextmanager
async def fake_agent(handler, token="tok"):
    """``handler(ws)`` chạy sau khi service token đúng. Như agent thật: token sai thì **chấp nhận kết nối rồi đóng mã 4401**
    (không từ chối HTTP 401 ở bắt tay). Trả URL ``http://127.0.0.1:<cổng>``."""

    async def guarded(ws):
        if ws.request.headers.get("Authorization") != f"Bearer {token}":
            await ws.close(4401, "service token không hợp lệ")
            return
        await handler(ws)

    async with serve(guarded, "127.0.0.1", 0) as server:
        yield f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}"


def script(*frames, record=None):
    """Handler phát lần lượt ``frames`` sau khi nhận ``start`` (ghi vào ``record`` nếu có) rồi đóng 1000."""

    async def handler(ws):
        start = json.loads(await ws.recv())
        if record is not None:
            record.append(start)
        for frame in frames:
            await ws.send(json.dumps(frame))
        await ws.close(1000)

    return handler


@contextmanager
def fake_agent_in_thread(handler, token="tok"):
    """Như ``fake_agent`` nhưng chạy trong luồng riêng (cho test đồng bộ dùng ``TestClient``)."""
    import asyncio
    import threading

    ready: dict = {}
    started, stop = threading.Event(), threading.Event()

    def runner():
        async def main():
            async with fake_agent(handler, token) as url:
                ready["url"] = url
                started.set()
                while not stop.is_set():
                    await asyncio.sleep(0.02)

        asyncio.run(main())

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    assert started.wait(5)
    try:
        yield ready["url"]
    finally:
        stop.set()
        thread.join(5)
