"""Mở rộng AiClient: tool, tham số theo lần gọi, model suy luận, streaming, embedding, khả năng theo đường (task 1.2–1.5)."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, AuthenticationError, BadRequestError

from vin15_agent.core.ai_client import AiClient, LlmEndpoint, LlmUnavailableError, ToolCall, is_reasoning_model
from vin15_agent.shared.settings import Settings

_REQUEST = httpx.Request("POST", "http://test/v1/chat/completions")
TOOLS = [{"type": "function", "function": {"name": "search_policy", "parameters": {"type": "object", "properties": {}}}}]
MSG = [{"role": "user", "content": "hi"}]


def _tc(id_, name, args):
    return SimpleNamespace(id=id_, function=SimpleNamespace(name=name, arguments=args))


class FakeClient:
    def __init__(self, *, content="ok", tool_calls=None, error=None, stream_chunks=None, embeddings=None):
        self.calls, self.embed_calls = [], []
        self._content, self._tool_calls, self._error = content, tool_calls, error
        self._stream_chunks, self._embeddings = stream_chunks, embeddings
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.embeddings = SimpleNamespace(create=self._embed)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        if kwargs.get("stream"):
            return self._stream()
        message = SimpleNamespace(content=self._content, tool_calls=self._tool_calls)
        return SimpleNamespace(
            model="m-x",
            choices=[SimpleNamespace(message=message, finish_reason="tool_calls" if self._tool_calls else "stop")],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=5),
        )

    async def _stream(self):
        for chunk in self._stream_chunks:
            yield chunk

    async def _embed(self, **kwargs):
        self.embed_calls.append(kwargs)
        if self._error:
            raise self._error
        return SimpleNamespace(data=[SimpleNamespace(index=i, embedding=v) for i, v in self._embeddings])


def _ep(name, fake, *, model="m", param="max_tokens", caps=frozenset({"tools", "stream", "embed"})):
    return LlmEndpoint(name=name, client=fake, model=model, max_tokens_param=param, capabilities=caps, embedding_model="emb-1")


def _client(*endpoints):
    return AiClient(endpoints, temperature=0.7, max_tokens=100)


# ---- 1.2 chat với tool ----


def test_chat_returns_tool_calls_and_finish_reason():
    fake = FakeClient(content=None, tool_calls=[_tc("c1", "search_policy", '{"query":"x"}')])
    result = asyncio.run(_client(_ep("openai", fake)).chat(MSG, tools=TOOLS))
    assert result.finish_reason == "tool_calls"
    assert result.tool_calls == (ToolCall("c1", "search_policy", '{"query":"x"}'),)
    assert result.tool_calls[0].parsed_arguments() == {"query": "x"}
    assert fake.calls[0]["tools"] == TOOLS and fake.calls[0]["tool_choice"] == "auto"
    msg = result.assistant_message()
    assert msg["role"] == "assistant" and msg["tool_calls"][0]["function"]["name"] == "search_policy"


def test_no_tools_means_no_tool_params():
    fake = FakeClient()
    asyncio.run(_client(_ep("openai", fake)).chat(MSG))
    assert "tools" not in fake.calls[0] and "tool_choice" not in fake.calls[0]


def test_per_call_parameters_override_defaults():
    fake = FakeClient()
    asyncio.run(_client(_ep("openai", fake)).chat(MSG, temperature=0.1, max_tokens=33, tool_choice="none", tools=TOOLS))
    call = fake.calls[0]
    assert (call["temperature"], call["max_tokens"], call["tool_choice"]) == (0.1, 33, "none")


def test_tool_call_with_bad_json_raises_value_error():
    with pytest.raises(ValueError):
        ToolCall("c", "t", "{không hợp lệ").parsed_arguments()
    with pytest.raises(ValueError):
        ToolCall("c", "t", "[1]").parsed_arguments()
    assert ToolCall("c", "t", "").parsed_arguments() == {}


@pytest.mark.parametrize("model,expected", [("o3-mini", True), ("gpt-5", True), ("gpt-5-mini", True), ("gpt-4o-mini", False), ("m", False)])
def test_is_reasoning_model(model, expected):
    assert is_reasoning_model(model) is expected


def test_reasoning_model_drops_temperature_and_raises_cap():
    fake = FakeClient()
    asyncio.run(_client(_ep("openai", fake, model="gpt-5-mini", param="max_completion_tokens")).chat(MSG, temperature=0.2, reasoning_effort="low"))
    call = fake.calls[0]
    assert "temperature" not in call
    assert call["max_completion_tokens"] >= 4096
    assert call["reasoning_effort"] == "low"


def test_non_reasoning_model_ignores_reasoning_effort():
    fake = FakeClient()
    asyncio.run(_client(_ep("openai", fake)).chat(MSG, reasoning_effort="low"))
    assert "reasoning_effort" not in fake.calls[0]


# ---- 1.3 streaming ----


def _chunk(content=None, tool_calls=None, finish=None, usage=None, choices=True):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    ch = [SimpleNamespace(delta=delta, finish_reason=finish)] if choices else []
    return SimpleNamespace(model="m-s", choices=ch, usage=usage)


def _collect(client, **kw):
    async def go():
        return [d async for d in client.chat_stream(MSG, **kw)]

    return asyncio.run(go())


def test_stream_yields_text_deltas_then_final_delta_with_usage():
    chunks = [
        _chunk("Xin "),
        _chunk("chào"),
        _chunk(finish="stop"),
        _chunk(choices=False, usage=SimpleNamespace(prompt_tokens=4, completion_tokens=2)),
    ]
    deltas = _collect(_client(_ep("openai", FakeClient(stream_chunks=chunks))))
    assert "".join(d.text for d in deltas) == "Xin chào"
    last = deltas[-1]
    assert (last.finish_reason, last.prompt_tokens, last.completion_tokens, last.provider) == ("stop", 4, 2, "openai")


def test_stream_assembles_tool_call_fragments():
    frag = lambda i, id_, name, args: SimpleNamespace(index=i, id=id_, function=SimpleNamespace(name=name, arguments=args))  # noqa: E731
    chunks = [
        _chunk(tool_calls=[frag(0, "c1", "search_policy", '{"que')]),
        _chunk(tool_calls=[frag(0, None, None, 'ry":"a"}')]),
        _chunk(tool_calls=[frag(1, "c2", "get_policy_clause", "{}")]),
        _chunk(finish="tool_calls"),
    ]
    last = _collect(_client(_ep("openai", FakeClient(stream_chunks=chunks))), tools=TOOLS)[-1]
    assert [(c.id, c.name, c.arguments) for c in last.tool_calls] == [("c1", "search_policy", '{"query":"a"}'), ("c2", "get_policy_clause", "{}")]


def test_stream_falls_back_before_first_delta_only():
    broken = FakeClient(error=APIConnectionError(request=_REQUEST))
    good = FakeClient(stream_chunks=[_chunk("ok"), _chunk(finish="stop")])
    deltas = _collect(_client(_ep("openai", broken), _ep("aiclient", good)))
    assert "".join(d.text for d in deltas) == "ok" and deltas[-1].provider == "aiclient"


def test_stream_error_after_first_delta_is_not_retried():
    class Flaky(FakeClient):
        async def _stream(self):
            yield _chunk("một phần")
            raise APIConnectionError(request=_REQUEST)

    backup = FakeClient(stream_chunks=[_chunk("khác")])
    with pytest.raises(LlmUnavailableError):
        _collect(_client(_ep("openai", Flaky()), _ep("aiclient", backup)))
    assert backup.calls == []


# ---- 1.4 embedding ----


def test_embed_returns_vectors_in_input_order():
    fake = FakeClient(embeddings=[(1, [0.3, 0.4]), (0, [0.1, 0.2])])
    vectors = asyncio.run(_client(_ep("openai", fake)).embed(["a", "b"]))
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert fake.embed_calls[0] == {"model": "emb-1", "input": ["a", "b"]}


def test_embed_empty_makes_no_call():
    fake = FakeClient()
    assert asyncio.run(_client(_ep("openai", fake)).embed([])) == []
    assert fake.embed_calls == []


def test_embed_unconfigured_raises_unavailable():
    with pytest.raises(LlmUnavailableError):
        asyncio.run(AiClient([], temperature=0.1, max_tokens=10).embed(["a"]))


# ---- 1.5 khả năng theo đường ----


def test_supports_reports_capabilities():
    client = _client(_ep("openai", FakeClient(), caps=frozenset({"embed"})), _ep("aiclient", FakeClient(), caps=frozenset()))
    assert client.supports("embed") and not client.supports("tools") and not client.supports("stream")


def test_fallback_skips_endpoint_without_tools_capability():
    primary = FakeClient(error=APIConnectionError(request=_REQUEST))
    chat_only = FakeClient()
    client = _client(_ep("openai", primary), _ep("aiclient", chat_only, caps=frozenset()))
    with pytest.raises(LlmUnavailableError):
        asyncio.run(client.chat(MSG, tools=TOOLS))
    assert chat_only.calls == []


def test_plain_chat_still_falls_back_to_chat_only_endpoint():
    primary = FakeClient(error=APIConnectionError(request=_REQUEST))
    client = _client(_ep("openai", primary), _ep("aiclient", FakeClient(content="dp"), caps=frozenset()))
    assert asyncio.run(client.chat(MSG)).text == "dp"


def test_no_endpoint_with_capability_raises_unavailable():
    client = _client(_ep("aiclient", FakeClient(), caps=frozenset()))
    with pytest.raises(LlmUnavailableError, match="embed"):
        asyncio.run(client.embed(["a"]))
    with pytest.raises(LlmUnavailableError, match="stream"):
        _collect(client)


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError("k", response=httpx.Response(401, request=_REQUEST), body=None),
        BadRequestError("b", response=httpx.Response(400, request=_REQUEST), body=None),
    ],
)
def test_400_401_not_masked_even_with_capable_backup(error):
    backup = FakeClient()
    client = _client(_ep("openai", FakeClient(error=error)), _ep("aiclient", backup))
    with pytest.raises(type(error)):
        asyncio.run(client.chat(MSG, tools=TOOLS))
    with pytest.raises(type(error)):
        asyncio.run(client.embed(["a"]))
    assert backup.calls == [] and backup.embed_calls == []


def test_from_settings_proxy_is_chat_only_by_default_and_configurable():
    s = Settings(_env_file=None, openai_api_key="sk-x", aiclient_base_url="http://proxy/v1")
    assert AiClient.from_settings(s).supports("tools")  # OpenAI chính đủ khả năng
    only_proxy = Settings(_env_file=None, aiclient_base_url="http://proxy/v1")
    assert not AiClient.from_settings(only_proxy).supports("tools")
    with_caps = Settings(_env_file=None, aiclient_base_url="http://proxy/v1", aiclient_capabilities="tools, stream")
    client = AiClient.from_settings(with_caps)
    assert client.supports("tools") and client.supports("stream") and not client.supports("embed")
