import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, AuthenticationError, RateLimitError

from vin15_agent.core.ai_client import AiClient, LlmEndpoint, LlmUnavailableError
from vin15_agent.shared.settings import Settings

_REQUEST = httpx.Request("POST", "http://test/v1/chat/completions")


class FakeClient:
    def __init__(self, result=None, error=None):
        self.calls = []
        self._result, self._error = result, error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(
            model="m-x",
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._result))],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
        )


def _client(*endpoints):
    return AiClient(endpoints, temperature=0.1, max_tokens=50)


def _ep(name, fake, param="max_tokens"):
    return LlmEndpoint(name=name, client=fake, model="m", max_tokens_param=param)


MSG = [{"role": "user", "content": "hi"}]


def test_primary_used_when_healthy():
    primary, backup = FakeClient(result="ok"), FakeClient(result="backup")
    result = asyncio.run(_client(_ep("openai", primary, "max_completion_tokens"), _ep("aiclient", backup)).complete(MSG))
    assert (result.text, result.provider, result.prompt_tokens) == ("ok", "openai", 3)
    assert primary.calls[0]["max_completion_tokens"] == 50 and "max_tokens" not in primary.calls[0]
    assert backup.calls == []


@pytest.mark.parametrize(
    "error",
    [
        APIConnectionError(request=_REQUEST),
        RateLimitError("slow down", response=httpx.Response(429, request=_REQUEST), body=None),
    ],
)
def test_falls_back_on_transient_error(error):
    primary, backup = FakeClient(error=error), FakeClient(result="backup")
    result = asyncio.run(_client(_ep("openai", primary), _ep("aiclient", backup)).complete(MSG))
    assert (result.text, result.provider) == ("backup", "aiclient")


def test_auth_error_is_not_masked_by_fallback():
    error = AuthenticationError("bad key", response=httpx.Response(401, request=_REQUEST), body=None)
    primary, backup = FakeClient(error=error), FakeClient(result="backup")
    with pytest.raises(AuthenticationError):
        asyncio.run(_client(_ep("openai", primary), _ep("aiclient", backup)).complete(MSG))
    assert backup.calls == []


def test_all_transient_failures_raise_unavailable():
    errors = [FakeClient(error=APIConnectionError(request=_REQUEST)) for _ in range(2)]
    with pytest.raises(LlmUnavailableError):
        asyncio.run(_client(_ep("openai", errors[0]), _ep("aiclient", errors[1])).complete(MSG))


def test_unconfigured_raises_unavailable():
    client = AiClient.from_settings(Settings(_env_file=None))
    assert client.providers == []
    with pytest.raises(LlmUnavailableError, match="OPENAI_API_KEY"):
        asyncio.run(client.complete(MSG))


def test_from_settings_builds_primary_then_fallback():
    settings = Settings(_env_file=None, openai_api_key="sk-test", aiclient_base_url="http://proxy/v1")
    assert AiClient.from_settings(settings).providers == ["openai", "aiclient"]
    assert AiClient.from_settings(Settings(_env_file=None, openai_api_key="sk-test")).providers == ["openai"]


def test_api_key_not_leaked_in_settings_repr():
    assert "sk-secret" not in repr(Settings(_env_file=None, openai_api_key="sk-secret"))
