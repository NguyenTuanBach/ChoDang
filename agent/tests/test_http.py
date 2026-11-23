import pytest

from vin15_agent.runtime.http.app import create_app
from vin15_agent.shared.settings import Settings


def test_healthz_needs_no_token(client):
    assert client.get("/healthz").json() == {"status": "UP"}


def test_info_requires_token(client):
    assert client.get("/v1/info").status_code == 401
    assert client.get("/v1/info", headers={"Authorization": "Bearer sai"}).status_code == 401
    assert client.get("/v1/info", headers={"Authorization": "Basic tok"}).status_code == 401


def test_info_with_token(client):
    body = client.get("/v1/info", headers={"Authorization": "Bearer tok"}).json()
    assert body["service"] == "vin15-agent-api"
    assert body["agents"] == ["policy_assistant", "intake", "monitor", "pre_review", "journal_advice"]


def test_production_rejects_default_token():
    with pytest.raises(RuntimeError, match="AGENT_API_SERVICE_TOKEN"):
        create_app(Settings(_env_file=None, app_env="production"))
