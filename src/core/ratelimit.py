"""Giới hạn tần suất — Redis dùng chung khi cấu hình, memory cho local/test.

- Đăng nhập: khóa tài khoản sau LOGIN_MAX_FAILURES lần sai trong LOGIN_LOCK_MINUTES phút
  (khóa cả khi sau đó nhập đúng), và giới hạn số lần thử mỗi IP mỗi phút.
- Trợ lý / intake: giới hạn số lời gọi mỗi người dùng mỗi phút → chặn đốt chi phí LLM.
Khi không cấu hình Redis, trạng thái mất khi khởi động lại và không chia sẻ giữa nhiều worker.
"""

from __future__ import annotations

import logging
import secrets
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException

from src.config import get_settings

logger = logging.getLogger("vin15.ratelimit")

Clock = Callable[[], float]


class SlidingWindow:
    def __init__(self, clock: Clock = time.monotonic):
        self.clock = clock
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, key: str, window: float) -> deque[float]:
        q = self.events[key]
        now = self.clock()
        while q and now - q[0] >= window:
            q.popleft()
        return q

    def count(self, key: str, window: float) -> int:
        return len(self._trim(key, window))

    def add(self, key: str) -> None:
        self.events[key].append(self.clock())

    def retry_after(self, key: str, window: float) -> int:
        q = self._trim(key, window)
        return max(1, int(window - (self.clock() - q[0]))) if q else 0

    def clear(self, key: str) -> None:
        self.events.pop(key, None)

    def reset(self) -> None:
        self.events.clear()


login_failures = SlidingWindow()
login_attempts_by_ip = SlidingWindow()
usage = SlidingWindow()
_redis = None
_redis_checked = False


def _redis_client():
    global _redis, _redis_checked
    if _redis_checked:
        return _redis
    _redis_checked = True
    url = get_settings().redis_url.strip()
    if not url:
        return None
    try:
        import redis
        client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=0.5)
        client.ping()
        _redis = client
        logger.info("Rate limit dùng Redis store chia sẻ")
    except Exception as exc:
        logger.warning("Không kết nối được Redis, dùng in-memory rate limit: %s", type(exc).__name__)
    return _redis


def _redis_count_add(key: str, window: int) -> int | None:
    client = _redis_client()
    if client is None:
        return None
    now = time.time()
    member = f"{now}:{secrets.token_hex(6)}"
    redis_key = f"vin15:ratelimit:{key}"
    pipe = client.pipeline()
    pipe.zremrangebyscore(redis_key, 0, now - window)
    pipe.zadd(redis_key, {member: now})
    pipe.zcard(redis_key)
    pipe.expire(redis_key, window + 2)
    return int(pipe.execute()[2])


def reset_all() -> None:
    for w in (login_failures, login_attempts_by_ip, usage):
        w.reset()


def check_login_allowed(username: str, ip: str) -> None:
    s = get_settings()
    login_attempts_by_ip.add(ip)
    if login_attempts_by_ip.count(ip, 60) > s.login_ip_per_minute:
        raise HTTPException(status_code=429, detail="Quá nhiều lần thử đăng nhập từ địa chỉ này, hãy thử lại sau 1 phút",
                            headers={"Retry-After": "60"})
    window = s.login_lock_minutes * 60
    if login_failures.count(username, window) >= s.login_max_failures:
        wait = login_failures.retry_after(username, window)
        raise HTTPException(status_code=429, detail=f"Tài khoản tạm khóa do đăng nhập sai nhiều lần, thử lại sau {wait // 60 + 1} phút",
                            headers={"Retry-After": str(wait)})


def record_login_failure(username: str) -> None:
    login_failures.add(username)


def record_login_success(username: str) -> None:
    login_failures.clear(username)


def enforce_usage(user_id: int, bucket: str, per_minute: int) -> None:
    key = f"{bucket}:{user_id}"
    shared_count = _redis_count_add(key, 60)
    if shared_count is not None:
        if shared_count > per_minute:
            raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"})
        return
    if usage.count(key, 60) >= per_minute:
        raise HTTPException(status_code=429, detail="Bạn gửi quá nhiều yêu cầu, hãy thử lại sau ít phút",
                            headers={"Retry-After": str(usage.retry_after(key, 60))})
    usage.add(key)
