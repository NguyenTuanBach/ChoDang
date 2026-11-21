import httpx

from tests.conftest import client_with_agent


def test_liveness(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"


def test_readiness_without_database_is_ready(client):
    body = client.get("/api/health/readiness").json()
    assert body == {"status": "UP", "components": {"database": "NOT_CONFIGURED"}}


def test_agent_disabled_by_default(client):
    response = client.get("/api/agent/health")
    assert response.status_code == 200
    assert response.json()["status"] == "DISABLED"


def test_agent_up():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/info":
            assert request.headers["authorization"] == "Bearer tok"
            return httpx.Response(200, json={"service": "vin15-agent-api"})
        return httpx.Response(200, json={"status": "UP"})

    with client_with_agent(handler) as client:
        body = client.get("/api/agent/health").json()
    assert body["status"] == "UP" and body["agent"]["service"] == "vin15-agent-api"


def test_agent_down_returns_503():
    def boom(request):
        raise httpx.ConnectError("refused")

    with client_with_agent(boom) as client:
        response = client.get("/api/agent/health")
    assert response.status_code == 503
    assert response.json()["status"] == "DOWN"
