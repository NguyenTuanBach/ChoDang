"""Giới hạn tần suất theo IP cho các đường dẫn nhạy cảm (đăng nhập, lời mời). Trạng thái nằm trong RAM của một tiến trình."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


@dataclass(frozen=True)
class Rule:
    prefix: str
    limit: int
    window_seconds: float = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, rules: list[Rule], clock: Callable[[], float] = time.monotonic):
        super().__init__(app)
        self._rules = rules
        self._clock = clock
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rule = next((r for r in self._rules if request.url.path.startswith(r.prefix)), None)
        if rule is not None:
            client = request.client.host if request.client else "unknown"
            events = self._events[(rule.prefix, client)]
            now = self._clock()
            while events and now - events[0] >= rule.window_seconds:
                events.popleft()
            if len(events) >= rule.limit:
                retry = max(1, int(rule.window_seconds - (now - events[0])))
                return JSONResponse(
                    status_code=429,
                    content={"error": "rate_limited", "message": "Quá nhiều yêu cầu, thử lại sau"},
                    headers={"Retry-After": str(retry)},
                )
            events.append(now)
        return await call_next(request)
