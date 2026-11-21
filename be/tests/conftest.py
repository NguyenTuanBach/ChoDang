import httpx
import pytest
from fastapi.testclient import TestClient

from vin15.config.container import Container
from vin15.config.settings import Settings
from vin15.main import create_app


def make_settings(**overrides) -> Settings:
    """Settings không đọc `.env` thật, để test không phụ thuộc máy."""
    return Settings(_env_file=None, **overrides)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def agent_transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def client_with_agent(handler, **overrides) -> TestClient:
    """App có agent-api giả: ``handler(request) -> httpx.Response``."""
    settings = make_settings(agent_api_url="http://agent.test", agent_api_service_token="tok", **overrides)
    container = Container(settings)
    container.agent_client._transport = agent_transport(handler)
    return TestClient(create_app(settings, container))


@pytest.fixture
def anyio_backend() -> str:
    """Test async dùng plugin anyio, chỉ chạy với asyncio (không cài trio)."""
    return "asyncio"
