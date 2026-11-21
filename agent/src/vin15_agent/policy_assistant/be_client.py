"""Client HTTP gọi ``/api/agent-tools/*`` của BE (chỉ-đọc).

Xác thực: ``Authorization: Bearer <service token>``; thêm ``X-On-Behalf-Of: <agent_token>`` nếu có (rỗng ở dev:
BE dùng người dùng mặc định). Tool KHÔNG có tham số chủ thể: BE quyết định chủ thể từ token. Token không bao giờ vào log.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

PERSONAL_ENDPOINTS = frozenset({"internship", "milestones", "progress", "credit-checklist", "requests"})
_CHUNK_ID = re.compile(r"^[\w@.:/\-]{1,200}$")

_DEFAULT_ERRORS = {
    401: ("unauthorized", "Phiên làm việc của trợ lý không hợp lệ hoặc đã hết hạn"),
    403: ("forbidden", "Không có quyền dùng chức năng này"),
    404: ("not_found", "Không tìm thấy"),
    429: ("rate_limited", "Hệ thống đang bận, thử lại sau"),
}


class BeToolError(Exception):
    """Lỗi từ BE hoặc đường truyền, đã chuẩn hóa ``code``/``message`` (tiếng Việt, không lộ chi tiết nội bộ)."""

    def __init__(self, code: str, message: str, status: int | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.status = code, message, status


def is_valid_chunk_id(chunk_id: str) -> bool:
    return bool(_CHUNK_ID.match(chunk_id)) and ".." not in chunk_id.split("/") and not chunk_id.startswith("/")


class BeToolsClient:
    def __init__(
        self,
        base_url: str,
        service_token: str,
        agent_token: str = "",
        *,
        timeout: float = 8.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {service_token}"}
        if agent_token:
            headers["X-On-Behalf-Of"] = agent_token
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport)

    def __repr__(self) -> str:  # không lộ token
        return f"BeToolsClient(base_url={str(self._http.base_url)!r})"

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.TimeoutException as exc:
            raise BeToolError("be_timeout", "Hệ thống phản hồi quá chậm") from exc
        except httpx.HTTPError as exc:
            logger.warning("Gọi BE lỗi: %s", type(exc).__name__)
            raise BeToolError("be_unavailable", "Không kết nối được tới hệ thống") from exc
        if response.status_code >= 400:
            raise self._error(response)
        try:
            body = response.json()
        except ValueError as exc:
            raise BeToolError("be_bad_response", "Hệ thống trả dữ liệu không hợp lệ", response.status_code) from exc
        if not isinstance(body, dict):
            raise BeToolError("be_bad_response", "Hệ thống trả dữ liệu không hợp lệ", response.status_code)
        return body

    @staticmethod
    def _error(response: httpx.Response) -> BeToolError:
        status = response.status_code
        code, message = _DEFAULT_ERRORS.get(status, ("be_error", "Hệ thống gặp lỗi, thử lại sau") if status >= 500 else ("bad_request", "Yêu cầu không hợp lệ"))
        try:
            err = response.json().get("error")
            if isinstance(err, dict):
                code = str(err.get("code") or code)
                if status < 500 and err.get("message"):
                    message = str(err["message"])[:300]
        except (ValueError, AttributeError):
            pass
        return BeToolError(code, message, status)

    async def search(self, query: str, query_vector: list[float] | None, top_k: int = 5) -> dict[str, Any]:
        return await self._request("POST", "/api/agent-tools/policy/search", json={"query": query, "query_vector": query_vector, "top_k": top_k})

    async def get_chunk(self, chunk_id: str, with_neighbors: bool = False) -> dict[str, Any]:
        if not is_valid_chunk_id(chunk_id):
            raise BeToolError("not_found", "Mã đoạn quy định không hợp lệ", 404)
        path = f"/api/agent-tools/policy/chunks/{quote(chunk_id, safe='/@:')}"
        return await self._request("GET", path, params={"with_neighbors": "true" if with_neighbors else "false"})

    async def me(self, endpoint: str) -> dict[str, Any]:
        if endpoint not in PERSONAL_ENDPOINTS:
            raise ValueError(f"endpoint cá nhân không hợp lệ: {endpoint}")
        return await self._request("GET", f"/api/agent-tools/me/{endpoint}")


BeClientFactory = Callable[[str], BeToolsClient]
