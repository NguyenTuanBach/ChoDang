"""Gọi LLM: OpenAI trực tiếp là đường chính, proxy ``AiClient`` (tương thích OpenAI) là đường dự phòng.

Chỉ chuyển sang dự phòng khi lỗi tạm thời (mất kết nối, hết thời gian chờ, bị giới hạn tốc độ, 5xx).
Lỗi do yêu cầu hoặc khóa sai (400, 401, 403...) được ném lại nguyên vẹn, không đổi đường để khỏi che lỗi cấu hình.

Mỗi đường khai báo khả năng (``tools``, ``stream``, ``embed``, ``vision`` = nhận ảnh trong tin nhắn). Khi cần một khả năng, chỉ thử các đường có khả năng đó;
không đường nào đủ thì ném ``LlmUnavailableError`` (agent sẽ chuyển sang chế độ suy giảm).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from vin15_agent.shared.settings import Settings

logger = logging.getLogger(__name__)

Message = dict[str, Any]
Capability = Literal["tools", "stream", "embed", "vision"]
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
ALL_CAPABILITIES: frozenset[str] = frozenset({"tools", "stream", "embed", "vision"})
T = TypeVar("T")

#: Model suy luận không nhận ``temperature`` và tính token suy luận vào trần đầu ra.
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5")
_REASONING_MIN_TOKENS = 4096
_REASONING_TOKEN_FACTOR = 4


def is_reasoning_model(model: str) -> bool:
    name = model.lower().rsplit("/", 1)[-1]
    return name.startswith(_REASONING_PREFIXES)


class LlmUnavailableError(RuntimeError):
    """Không đường LLM nào dùng được (chưa cấu hình, không đủ khả năng, hoặc tất cả đều lỗi tạm thời)."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    #: Chuỗi JSON thô do LLM sinh; người gọi tự phân tích (có thể không hợp lệ).
    arguments: str

    def parsed_arguments(self) -> dict[str, Any]:
        """Trả ``dict`` đối số; ném ``ValueError`` nếu không phải JSON object."""
        raw = self.arguments.strip() or "{}"
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("đối số tool không phải JSON hợp lệ") from exc
        if not isinstance(value, dict):
            raise ValueError("đối số tool phải là một JSON object")
        return value


@dataclass(frozen=True)
class ChatResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    finish_reason: str | None = None

    def assistant_message(self) -> Message:
        """Tin nhắn ``assistant`` để nối lại vào hội thoại (kèm ``tool_calls`` nếu có)."""
        message: Message = {"role": "assistant", "content": self.text or None}
        if self.tool_calls:
            message["tool_calls"] = [
                {"id": c.id, "type": "function", "function": {"name": c.name, "arguments": c.arguments}} for c in self.tool_calls
            ]
        return message


@dataclass(frozen=True)
class Delta:
    """Một mảnh của lượt trả lời streaming. Mảnh cuối có ``finish_reason`` và gộp ``tool_calls``, token."""

    text: str = ""
    finish_reason: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    provider: str = ""
    model: str = ""


@dataclass(frozen=True)
class LlmEndpoint:
    name: str
    client: Any  # AsyncOpenAI (hoặc đối tượng giả trong test)
    model: str
    #: OpenAI trực tiếp dùng ``max_completion_tokens``; proxy tương thích thường chỉ hiểu ``max_tokens``.
    max_tokens_param: str
    capabilities: frozenset[str] = ALL_CAPABILITIES
    embedding_model: str = "text-embedding-3-small"
    #: ``None`` = đoán theo tên model.
    reasoning: bool | None = None

    @property
    def is_reasoning(self) -> bool:
        return is_reasoning_model(self.model) if self.reasoning is None else self.reasoning


def _is_transient(exc: Exception) -> bool:
    if isinstance(exc, APIConnectionError | RateLimitError):  # APITimeoutError là con của APIConnectionError
        return True
    return isinstance(exc, APIStatusError) and exc.status_code >= 500


def _parse_capabilities(raw: str) -> frozenset[str]:
    return frozenset(p.strip().lower() for p in raw.split(",") if p.strip()) & ALL_CAPABILITIES


def _tool_calls_from_message(message: Any) -> tuple[ToolCall, ...]:
    calls = getattr(message, "tool_calls", None) or []
    return tuple(ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments or "") for c in calls)


class AiClient:
    def __init__(
        self,
        endpoints: Sequence[LlmEndpoint],
        *,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self._endpoints = list(endpoints)
        self._temperature = temperature
        self._max_tokens = max_tokens

    @classmethod
    def from_settings(cls, settings: Settings) -> AiClient:
        endpoints: list[LlmEndpoint] = []
        openai_key = settings.openai_api_key.get_secret_value()
        if openai_key:
            endpoints.append(
                LlmEndpoint(
                    name="openai",
                    client=AsyncOpenAI(
                        api_key=openai_key,
                        # Phải đặt tường minh: SDK đọc OPENAI_BASE_URL từ môi trường khi base_url=None,
                        # mà chuỗi rỗng (start.sh export cả biến trống trong .env) làm mọi lời gọi lỗi kết nối.
                        base_url=settings.openai_base_url or OPENAI_DEFAULT_BASE_URL,
                        timeout=settings.openai_timeout_seconds,
                        max_retries=1,  # ít thử lại để còn kịp chuyển sang dự phòng
                    ),
                    model=settings.openai_model,
                    max_tokens_param="max_completion_tokens",
                    capabilities=ALL_CAPABILITIES,
                    embedding_model=settings.openai_embedding_model,
                )
            )
        if settings.aiclient_base_url:
            endpoints.append(
                LlmEndpoint(
                    name="aiclient",
                    client=AsyncOpenAI(
                        api_key=settings.aiclient_api_key.get_secret_value() or "unused",
                        base_url=settings.aiclient_base_url,
                        timeout=settings.openai_timeout_seconds,
                        max_retries=1,
                    ),
                    model=settings.aiclient_model or settings.openai_model,
                    max_tokens_param="max_tokens",
                    capabilities=_parse_capabilities(settings.aiclient_capabilities),
                    embedding_model=settings.openai_embedding_model,
                )
            )
        return cls(endpoints, temperature=settings.openai_temperature, max_tokens=settings.openai_max_tokens)

    @property
    def providers(self) -> list[str]:
        return [e.name for e in self._endpoints]

    def supports(self, capability: Capability) -> bool:
        """Có ít nhất một đường hỗ trợ khả năng này không."""
        return any(capability in e.capabilities for e in self._endpoints)

    @property
    def embedding_model(self) -> str:
        """Model embedding của đường đầu tiên hỗ trợ ``embed`` (rỗng nếu không có)."""
        return next((e.embedding_model for e in self._endpoints if "embed" in e.capabilities), "")

    # ------------------------------------------------------------------ chat

    async def complete(self, messages: Sequence[Message]) -> ChatResult:
        """Chat thường một lượt (không tool, không stream)."""
        return await self.chat(messages)

    async def chat(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] = "auto",
        temperature: float | None = None,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
        capability: Capability | None = None,
    ) -> ChatResult:
        """``capability`` đòi thêm một khả năng (vd. ``vision`` khi tin nhắn có ảnh); có ``tools`` thì luôn đòi ``tools``."""
        return await self._with_fallback(
            "tools" if tools else None,
            lambda ep: self._chat_once(ep, messages, tools, tool_choice, temperature, max_tokens, reasoning_effort),
            also=(capability,) if capability else (),
        )

    async def chat_stream(
        self,
        messages: Sequence[Message],
        *,
        tools: Sequence[Mapping[str, Any]] | None = None,
        tool_choice: str | Mapping[str, Any] = "auto",
        temperature: float | None = None,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> AsyncIterator[Delta]:
        """Streaming: phát ``Delta`` theo từng mảnh. Chỉ chuyển đường dự phòng khi lỗi xảy ra *trước* mảnh đầu tiên."""
        endpoints = self._eligible("stream", also=("tools",) if tools else ())
        last_error: Exception | None = None
        for endpoint in endpoints:
            started = False
            try:
                async for delta in self._stream_once(endpoint, messages, tools, tool_choice, temperature, max_tokens, reasoning_effort):
                    started = True
                    yield delta
                return
            except Exception as exc:
                if not _is_transient(exc):
                    raise
                if started:
                    raise LlmUnavailableError("Luồng LLM bị ngắt giữa chừng") from exc
                logger.warning("LLM '%s' lỗi tạm thời khi stream (%s), thử đường kế tiếp", endpoint.name, type(exc).__name__)
                last_error = exc
        raise LlmUnavailableError("Mọi đường LLM đều lỗi tạm thời") from last_error

    # ------------------------------------------------------------------ embedding

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        async def call(endpoint: LlmEndpoint) -> list[list[float]]:
            response = await endpoint.client.embeddings.create(model=endpoint.embedding_model, input=list(texts))
            items = sorted(response.data, key=lambda d: getattr(d, "index", 0))
            return [list(d.embedding) for d in items]

        return await self._with_fallback("embed", call)

    # ------------------------------------------------------------------ nội bộ

    def _eligible(self, capability: str | None, also: Sequence[str] = ()) -> list[LlmEndpoint]:
        if not self._endpoints:
            raise LlmUnavailableError("Chưa cấu hình LLM: đặt OPENAI_API_KEY (hoặc AICLIENT_BASE_URL cho đường dự phòng)")
        needed = {c for c in (capability, *also) if c}
        eligible = [e for e in self._endpoints if needed <= e.capabilities]
        if not eligible:
            raise LlmUnavailableError(f"Không có đường LLM nào hỗ trợ: {', '.join(sorted(needed))}")
        return eligible

    async def _with_fallback(self, capability: str | None, call: Callable[[LlmEndpoint], Awaitable[T]], also: Sequence[str] = ()) -> T:
        last_error: Exception | None = None
        for endpoint in self._eligible(capability, also):
            try:
                return await call(endpoint)
            except Exception as exc:
                if not _is_transient(exc):
                    raise
                logger.warning("LLM '%s' lỗi tạm thời (%s), thử đường kế tiếp", endpoint.name, type(exc).__name__)
                last_error = exc
        raise LlmUnavailableError("Mọi đường LLM đều lỗi tạm thời") from last_error

    def _request_kwargs(
        self,
        endpoint: LlmEndpoint,
        messages: Sequence[Message],
        tools: Sequence[Mapping[str, Any]] | None,
        tool_choice: str | Mapping[str, Any],
        temperature: float | None,
        max_tokens: int | None,
        reasoning_effort: str | None,
    ) -> dict[str, Any]:
        limit = max_tokens or self._max_tokens
        kwargs: dict[str, Any] = {"model": endpoint.model, "messages": list(messages)}
        if endpoint.is_reasoning:
            # Model suy luận: bỏ temperature, nới trần để còn chỗ cho token suy luận.
            limit = max(limit * _REASONING_TOKEN_FACTOR, _REASONING_MIN_TOKENS)
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort
        else:
            kwargs["temperature"] = self._temperature if temperature is None else temperature
        kwargs[endpoint.max_tokens_param] = limit
        if tools:
            kwargs["tools"] = list(tools)
            kwargs["tool_choice"] = tool_choice
        return kwargs

    async def _chat_once(self, endpoint: LlmEndpoint, messages, tools, tool_choice, temperature, max_tokens, reasoning_effort) -> ChatResult:
        kwargs = self._request_kwargs(endpoint, messages, tools, tool_choice, temperature, max_tokens, reasoning_effort)
        response = await endpoint.client.chat.completions.create(**kwargs)
        usage = response.usage
        choice = response.choices[0]
        return ChatResult(
            text=choice.message.content or "",
            provider=endpoint.name,
            model=response.model or endpoint.model,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            tool_calls=_tool_calls_from_message(choice.message),
            finish_reason=getattr(choice, "finish_reason", None),
        )

    async def _stream_once(
        self, endpoint: LlmEndpoint, messages, tools, tool_choice, temperature, max_tokens, reasoning_effort
    ) -> AsyncIterator[Delta]:
        kwargs = self._request_kwargs(endpoint, messages, tools, tool_choice, temperature, max_tokens, reasoning_effort)
        stream = await endpoint.client.chat.completions.create(stream=True, stream_options={"include_usage": True}, **kwargs)
        pending: dict[int, dict[str, str]] = {}
        finish_reason: str | None = None
        usage: Any = None
        model = endpoint.model
        async for chunk in stream:
            model = getattr(chunk, "model", None) or model
            usage = getattr(chunk, "usage", None) or usage
            for choice in getattr(chunk, "choices", None) or []:
                delta = choice.delta
                if getattr(delta, "content", None):
                    yield Delta(text=delta.content)
                for tc in getattr(delta, "tool_calls", None) or []:
                    slot = pending.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
                    slot["id"] = tc.id or slot["id"]
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        slot["name"] += getattr(fn, "name", None) or ""
                        slot["arguments"] += getattr(fn, "arguments", None) or ""
                finish_reason = getattr(choice, "finish_reason", None) or finish_reason
        calls = tuple(ToolCall(id=s["id"], name=s["name"], arguments=s["arguments"]) for _, s in sorted(pending.items()))
        yield Delta(
            finish_reason=finish_reason,
            tool_calls=calls,
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            provider=endpoint.name,
            model=model,
        )


__all__ = [
    "ALL_CAPABILITIES",
    "AiClient",
    "Capability",
    "ChatResult",
    "Delta",
    "LlmEndpoint",
    "LlmUnavailableError",
    "Message",
    "ToolCall",
    "is_reasoning_model",
]
