"""Máy chủ giả tương thích OpenAI (``/v1/chat/completions``, ``/v1/embeddings``) để chạy agent THẬT mà không cần khóa LLM.

Kịch bản theo câu hỏi cuối của người dùng:
- chứa ``[me]``: gọi song song ``get_my_credit_checklist`` + ``search_policy``;
- còn lại: gọi ``search_policy`` với chính câu hỏi.
Sau khi có kết quả tool: có ``chunk_id`` thì trả lời kèm ``[cite:<chunk_id đầu tiên>]``, không có thì ``[[no_basis]]``.
Embedding: túi từ băm vào 1536 chiều rồi chuẩn hóa, nên câu giống nhau thì gần nhau (đủ cho hybrid + ngưỡng no_match).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import threading
import time

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

DIMENSIONS = 1536
_CHUNK_ID = re.compile(r'"chunk_id":\s*"([^"]+)"')


def embed_text(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for word in re.findall(r"\w+", text.lower()):
        if len(word) < 3:
            continue
        index = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big") % DIMENSIONS
        vector[index] += 1.0
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


class FakeOpenAI:
    def __init__(self, port: int):
        self.port = port
        self.fail_chat = False
        self.fail_embeddings = False
        self.delay_seconds = 0.0
        self.chat_requests: list[dict] = []
        app = Starlette(routes=[Route("/v1/chat/completions", self._chat, methods=["POST"]), Route("/v1/embeddings", self._embed, methods=["POST"])])
        self._server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def start(self) -> None:
        self._thread.start()
        for _ in range(100):
            if self._server.started:
                return
            time.sleep(0.05)
        raise RuntimeError("Máy chủ OpenAI giả không khởi động được")

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)

    def reset(self) -> None:
        self.fail_chat = self.fail_embeddings = False
        self.delay_seconds = 0.0
        self.chat_requests.clear()

    async def _embed(self, request: Request) -> JSONResponse:
        if self.fail_embeddings:
            return JSONResponse({"error": {"message": "giả lập lỗi", "type": "server_error"}}, status_code=500)
        body = await request.json()
        texts = body["input"] if isinstance(body["input"], list) else [body["input"]]
        data = [{"object": "embedding", "index": i, "embedding": embed_text(str(t))} for i, t in enumerate(texts)]
        return JSONResponse({"object": "list", "data": data, "model": "fake-embedding", "usage": {"prompt_tokens": 1, "total_tokens": 1}})

    async def _chat(self, request: Request) -> JSONResponse:
        body = await request.json()
        self.chat_requests.append(body)
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.fail_chat:
            return JSONResponse({"error": {"message": "giả lập lỗi", "type": "server_error"}}, status_code=500)
        messages = body.get("messages", [])
        question = next((m["content"] for m in reversed(messages) if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
        tool_text = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "tool")
        if not tool_text:
            calls = [("search_policy", {"query": question.replace("[me]", "").strip()})]
            if "[me]" in question:
                calls.insert(0, ("get_my_credit_checklist", {}))
            return JSONResponse(_completion(tool_calls=calls))
        ids = _CHUNK_ID.findall(tool_text)
        content = f"Căn cứ quy định hiện hành, bạn cần xem điều khoản này. [cite:{ids[0]}]" if ids else "[[no_basis]]"
        return JSONResponse(_completion(content=content))


def _completion(*, content: str | None = None, tool_calls: list[tuple[str, dict]] | None = None) -> dict:
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [
            {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
            for i, (name, args) in enumerate(tool_calls)
        ]
    return {
        "id": "chatcmpl-fake",
        "object": "chat.completion",
        "created": 0,
        "model": "fake-model",
        "choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
