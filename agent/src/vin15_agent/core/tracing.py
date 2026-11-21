"""Ghi vết một lượt hỏi: các bước, tool đã gọi, độ trễ, token, nhà cung cấp LLM. Chỉ nhận văn bản đã che PII."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vin15_agent.core.ai_client import ChatResult
    from vin15_agent.core.pii import PiiRedactor


@dataclass
class TurnTrace:
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    redactor: PiiRedactor | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    provider: str | None = None
    model: str | None = None
    degraded: bool = False
    _started: float = field(default_factory=time.monotonic, repr=False)

    def _clean(self, text: str) -> str:
        text = text[:300]
        return self.redactor.redact_text(text) if self.redactor else text

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)

    def step(self, name: str, text: str = "") -> None:
        self.steps.append({"name": name, "t_ms": self.elapsed_ms(), **({"text": self._clean(text)} if text else {})})

    def add_tool(self, name: str, *, ok: bool, latency_ms: int, summary: str) -> None:
        self.tool_calls.append({"name": name, "ok": ok, "latency_ms": latency_ms, "summary": self._clean(summary)})

    def add_llm(self, result: ChatResult) -> None:
        self.llm_calls += 1
        self.prompt_tokens += result.prompt_tokens or 0
        self.completion_tokens += result.completion_tokens or 0
        self.provider, self.model = result.provider, result.model

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "llm_calls": self.llm_calls,
            "usage": {"prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens},
            "provider": self.provider,
            "model": self.model,
            "degraded": self.degraded,
            "total_ms": self.elapsed_ms(),
        }
