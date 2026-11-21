"""Vé dùng một lần để mở WebSocket (trình duyệt không đặt được header ``Authorization`` cho WebSocket).

Trạng thái nằm trong RAM của một tiến trình BE (MVP). Vé sống ``ttl_seconds`` (~30 s), dùng xong là xóa.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from threading import Lock

DEFAULT_TTL_SECONDS = 30
#: Trần số vé đang chờ để vé không dùng không làm đầy RAM.
_MAX_PENDING = 10_000


class WsTicketStore:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS, clock: Callable[[], float] = time.monotonic):
        self._ttl = ttl_seconds
        self._clock = clock
        self._tickets: dict[str, tuple[int, float]] = {}
        self._lock = Lock()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl

    def issue(self, user_id: int) -> str:
        ticket = secrets.token_urlsafe(24)
        now = self._clock()
        with self._lock:
            self._purge(now)
            if len(self._tickets) >= _MAX_PENDING:
                self._tickets.pop(next(iter(self._tickets)))
            self._tickets[ticket] = (user_id, now + self._ttl)
        return ticket

    def consume(self, ticket: str) -> int | None:
        """Trả ``user_id`` nếu vé hợp lệ và còn hạn rồi xóa vé; ngược lại ``None``."""
        with self._lock:
            entry = self._tickets.pop(ticket, None)
        if entry is None or entry[1] < self._clock():
            return None
        return entry[0]

    def _purge(self, now: float) -> None:
        for key in [k for k, (_u, exp) in self._tickets.items() if exp < now]:
            del self._tickets[key]
