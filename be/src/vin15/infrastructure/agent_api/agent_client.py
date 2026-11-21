"""Client HTTP của agent-api (cổng riêng, mặc định 8100). Mọi lời gọi mang ``Authorization: Bearer <service token>``."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from vin15.domain.exception import AgentUnavailableError

log = logging.getLogger(__name__)


class AgentApiClient:
    def __init__(self, base_url: str, token: str, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None):
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = timeout
        self._transport = transport

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
