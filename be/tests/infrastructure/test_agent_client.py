import asyncio

import httpx
import pytest

from vin15.domain.exception import AgentUnavailableError
from vin15.infrastructure.agent_api import AgentApiClient


def client(handler, url="http://agent.test") -> AgentApiClient:
    return AgentApiClient(url, "tok", transport=httpx.MockTransport(handler))


def test_disabled_without_url():
    c = client(lambda r: httpx.Response(200, json={}), url="")
    assert c.enabled is False
    with pytest.raises(AgentUnavailableError, match="AGENT_API_URL"):
        asyncio.run(c.health())


def test_info_sends_bearer_but_health_does_not():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen[request.url.path] = request.headers.get("authorization")
        return httpx.Response(200, json={"ok": True})

    c = client(handler)
    asyncio.run(c.health())
    asyncio.run(c.info())
    assert seen["/healthz"] is None
    assert seen["/v1/info"] == "Bearer tok"


def test_non_200_is_unavailable():
    with pytest.raises(AgentUnavailableError, match="401"):
        asyncio.run(client(lambda r: httpx.Response(401)).info())


def test_network_error_is_unavailable():
    def boom(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(AgentUnavailableError, match="ConnectError"):
        asyncio.run(client(boom).health())
