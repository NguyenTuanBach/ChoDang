"""Client của agent-api (cổng riêng, mặc định 8100). Mọi lời gọi mang ``Authorization: Bearer <service token>``.

HTTP: ``/healthz``, ``/v1/info``, ``/v1/embeddings``. WebSocket: ``/v1/policy-assistant/ws`` (một kết nối cho mỗi lượt hỏi).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from vin15.domain.exception import AgentTimeoutError, AgentUnavailableError

log = logging.getLogger(__name__)


#: Khung agent gửi để kết thúc lượt; sau khung này không đọc thêm.
_TERMINAL_FRAMES = frozenset({"final", "error"})
#: Khung agent tối đa 256 KiB theo hợp đồng; chừa dư.
_MAX_FRAME_BYTES = 1 << 20
_EMBED_MIN_TIMEOUT = 30.0
_CLOSE_UNAUTHORIZED = 4401


@dataclass(frozen=True)
class EmbeddingResult:
    model: str
    vectors: list[list[float]]


class AgentApiClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None):
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout
        self._transport = transport
        self._ws_url = (("ws" + self._base[4:]) if self._base.startswith("http") else self._base) + "/v1/policy-assistant/ws"

    @property
    def enabled(self) -> bool:
        return bool(self._base)

    async def _get(self, path: str, *, authenticated: bool) -> dict[str, Any]:
        if not self.enabled:
            raise AgentUnavailableError("Chưa cấu hình AGENT_API_URL")
        headers = self._headers if authenticated else {}
        try:
            async with httpx.AsyncClient(base_url=self._base, headers=headers, timeout=self._timeout, transport=self._transport) as client:
                response = await client.get(path)
        except httpx.HTTPError as error:
            raise AgentUnavailableError(f"không nối được agent-api: {type(error).__name__}") from error
        if response.status_code != 200:
            raise AgentUnavailableError(f"agent-api trả mã {response.status_code}")
        body = response.json()
        return body if isinstance(body, dict) else {}

    async def health(self) -> dict[str, Any]:
        """``GET /healthz`` (không cần token): service còn sống."""
        return await self._get("/healthz", authenticated=False)

    async def info(self) -> dict[str, Any]:
        """``GET /v1/info`` (cần token): xác nhận token nội bộ khớp và cho biết phiên bản agent."""
        return await self._get("/v1/info", authenticated=True)

    async def embed(self, texts: list[str]) -> EmbeddingResult:
        """``POST /v1/embeddings``: embedding cho một lô văn bản (BE không giữ khóa LLM nên agent làm giúp)."""
        if not self.enabled:
            raise AgentUnavailableError("Chưa cấu hình AGENT_API_URL")
        try:
            async with httpx.AsyncClient(
                base_url=self._base, headers=self._headers, timeout=max(self._timeout, _EMBED_MIN_TIMEOUT), transport=self._transport
            ) as client:
                response = await client.post("/v1/embeddings", json={"texts": texts})
        except httpx.HTTPError as error:
            raise AgentUnavailableError(f"không nối được agent-api: {type(error).__name__}") from error
        if response.status_code != 200:
            raise AgentUnavailableError(f"agent-api trả mã {response.status_code} khi tạo embedding")
        body = response.json()
        vectors = body.get("vectors") if isinstance(body, dict) else None
        if not isinstance(vectors, list):
            raise AgentUnavailableError("agent-api trả embedding sai định dạng")
        return EmbeddingResult(model=str(body.get("model", "")), vectors=vectors)

    async def call(self, path: str, body: dict[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        """``POST <path>`` với thân JSON: cho các agent một-lượt có đầu ra cấu trúc (``/v1/intake/extract``, ``/v1/monitor/review``,
        ``/v1/pre-review``). Agent **không** có công cụ ghi: BE kiểm kết quả rồi tự ghi.
        """
        if not self.enabled:
            raise AgentUnavailableError("Chưa cấu hình AGENT_API_URL")
        try:
            async with httpx.AsyncClient(
                base_url=self._base, headers=self._headers, timeout=timeout or max(self._timeout, _EMBED_MIN_TIMEOUT), transport=self._transport
            ) as client:
                response = await client.post(path, json=body)
        except httpx.TimeoutException as error:
            raise AgentTimeoutError("agent không trả lời đúng hạn") from error
        except httpx.HTTPError as error:
            raise AgentUnavailableError(f"không nối được agent-api: {type(error).__name__}") from error
        if response.status_code != 200:
            raise AgentUnavailableError(f"agent-api trả mã {response.status_code} cho {path}")
        data = response.json()
        return data if isinstance(data, dict) else {}

    async def chat(
        self, start: dict[str, Any], *, cancel: asyncio.Event | None = None, deadline_seconds: float | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Mở WebSocket tới agent, gửi khung ``start``, phát từng khung agent gửi về cho tới ``final``/``error``.

        ``cancel`` được đặt thì gửi khung ``cancel`` cho agent (một lần) rồi tiếp tục đọc cho tới khi agent kết thúc lượt.
        Hết ``deadline_seconds`` ném ``AgentTimeoutError``. Không nối được, bị từ chối hoặc agent đóng giữa chừng: ``AgentUnavailableError``.
        Đóng generator sớm thì đóng kết nối, agent sẽ hủy lượt.
        """
        if not self.enabled:
            raise AgentUnavailableError("Chưa cấu hình AGENT_API_URL")
        loop = asyncio.get_running_loop()
        end = loop.time() + deadline_seconds if deadline_seconds else None
        try:
            async with connect(
                self._ws_url, additional_headers=self._headers, open_timeout=self._timeout, max_size=_MAX_FRAME_BYTES, ping_interval=20
            ) as ws:
                await ws.send(json.dumps(start, ensure_ascii=False))
                cancel_waiter = asyncio.ensure_future(cancel.wait()) if cancel is not None else None
                recv_task: asyncio.Future | None = None
                try:
                    while True:
                        if recv_task is None:
                            recv_task = asyncio.ensure_future(ws.recv())
                        waiting = {recv_task} | ({cancel_waiter} if cancel_waiter is not None else set())
                        remaining = None if end is None else end - loop.time()
                        if remaining is not None and remaining <= 0:
                            raise AgentTimeoutError("agent không kết thúc lượt đúng hạn")
                        done, _pending = await asyncio.wait(waiting, timeout=remaining, return_when=asyncio.FIRST_COMPLETED)
                        if not done:
                            raise AgentTimeoutError("agent không kết thúc lượt đúng hạn")
                        if cancel_waiter is not None and cancel_waiter in done:
                            cancel_waiter = None
                            await ws.send(json.dumps({"type": "cancel"}))
                        if recv_task in done:
                            raw, recv_task = recv_task.result(), None
                            frame = _parse_frame(raw)
                            if frame is None:
                                continue
                            yield frame
                            if frame.get("type") in _TERMINAL_FRAMES:
                                return
                finally:
                    for task in (recv_task, cancel_waiter):
                        if task is not None and not task.done():
                            task.cancel()
        except ConnectionClosed as error:
            code = error.rcvd.code if error.rcvd else None
            if code == _CLOSE_UNAUTHORIZED:  # agent thật chấp nhận kết nối rồi đóng 4401 khi service token sai
                raise AgentUnavailableError("agent từ chối service token (4401): kiểm tra AGENT_API_SERVICE_TOKEN hai bên") from error
            raise AgentUnavailableError(f"agent đóng kết nối trước khi kết thúc lượt (mã {code})") from error
        except (InvalidHandshake, OSError) as error:
            raise AgentUnavailableError(f"không mở được WebSocket tới agent: {type(error).__name__}") from error


def _parse_frame(raw: str | bytes) -> dict[str, Any] | None:
    try:
        frame = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        log.warning("Bỏ qua khung không phải JSON từ agent")
        return None
    return frame if isinstance(frame, dict) and isinstance(frame.get("type"), str) else None
