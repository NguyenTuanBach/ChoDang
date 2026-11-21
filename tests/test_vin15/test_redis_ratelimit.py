import pytest
from fastapi import HTTPException

from src.core import ratelimit


class FakePipeline:
    def __init__(self, count):
        self.count = count

    def zremrangebyscore(self, *args):
        return self

    def zadd(self, *args):
        return self

    def zcard(self, *args):
        return self

    def expire(self, *args):
        return self

    def execute(self):
        return [0, 1, self.count, True]


class FakeRedis:
    def __init__(self, count):
        self.count = count

    def pipeline(self):
        return FakePipeline(self.count)


def test_shared_redis_rate_limit_rejects_after_limit(monkeypatch):
    monkeypatch.setattr(ratelimit, "_redis", FakeRedis(3))
    monkeypatch.setattr(ratelimit, "_redis_checked", True)
    ratelimit.reset_all()
    with pytest.raises(HTTPException) as exc:
        ratelimit.enforce_usage(user_id=3, bucket="assistant", per_minute=2)
    assert exc.value.status_code == 429


def test_shared_redis_rate_limit_allows_under_limit(monkeypatch):
    monkeypatch.setattr(ratelimit, "_redis", FakeRedis(1))
    monkeypatch.setattr(ratelimit, "_redis_checked", True)
    ratelimit.reset_all()
    ratelimit.enforce_usage(user_id=3, bucket="assistant", per_minute=2)
