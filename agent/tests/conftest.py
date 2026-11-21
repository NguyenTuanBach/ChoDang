import pytest
from fastapi.testclient import TestClient

from vin15_agent.runtime.http.app import create_app
from vin15_agent.shared.settings import Settings


@pytest.fixture
def client() -> TestClient:
    settings = Settings(_env_file=None, agent_api_service_token="tok")
    return TestClient(create_app(settings))
