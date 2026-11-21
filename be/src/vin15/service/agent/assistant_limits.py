"""Giới hạn WebSocket của trợ lý, tính trong handler vì ``RateLimitMiddleware`` không phủ WebSocket (trạng thái trong RAM)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock


class AskRateLimiter:
    """Cửa sổ trượt: tối đa ``per_minute`` câu hỏi mỗi người trong ``window_seconds``."""

    def __init__(self, per_minute: int, window_seconds: float = 60.0, clock: Callable[[], float] = time.monotonic):
        self._limit = per_minute
        self._window = window_seconds
        self._clock = clock
        self._events: dict[int, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def try_acquire(self, user_id: int) -> tuple[bool, int]:
        """``(được phép, số giây nên chờ)``. Chỉ tính khi được phép."""
        now = self._clock()
        with self._lock:
            events = self._events[user_id]
            while events and now - events[0] >= self._window:
                events.popleft()
            if len(events) >= self._limit:
                return False, max(1, int(self._window - (now - events[0])) + 1)
            events.append(now)
            return True, 0


class ConnectionLimiter:
    """Tối đa ``max_per_user`` kết nối WebSocket đồng thời mỗi người."""

    def __init__(self, max_per_user: int):
        self._max = max_per_user
        self._open: dict[int, int] = defaultdict(int)
        self._lock = Lock()

    def acquire(self, user_id: int) -> bool:
        with self._lock:
            if self._open[user_id] >= self._max:
                return False
            self._open[user_id] += 1
            return True

    def release(self, user_id: int) -> None:
        with self._lock:
            self._open[user_id] = max(0, self._open[user_id] - 1)
            if self._open[user_id] == 0:
                del self._open[user_id]
