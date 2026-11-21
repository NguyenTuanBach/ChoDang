from fastapi import FastAPI
from fastapi.testclient import TestClient

from vin15.presentation.rate_limit import RateLimitMiddleware, Rule


def make_client(now):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, rules=[Rule("/api/auth/", limit=2, window_seconds=60)], clock=lambda: now[0])

    @app.get("/api/auth/x")
    def limited():
        return {}

    @app.get("/api/other")
    def free():
        return {}

    return TestClient(app)


def test_blocks_after_limit_and_recovers_after_window():
    now = [0.0]
    client = make_client(now)
    assert client.get("/api/auth/x").status_code == 200
    assert client.get("/api/auth/x").status_code == 200
    blocked = client.get("/api/auth/x")
    assert blocked.status_code == 429 and int(blocked.headers["retry-after"]) >= 1
    now[0] = 61.0
    assert client.get("/api/auth/x").status_code == 200


def test_other_paths_are_not_limited():
    client = make_client([0.0])
    assert all(client.get("/api/other").status_code == 200 for _ in range(10))
