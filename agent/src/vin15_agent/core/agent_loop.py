"""Vòng lặp agent kiểu ReAct, dùng chung cho các agent: gọi LLM kèm tool → chạy ``tool_calls`` → nối kết quả → lặp.

- Giới hạn cứng: số vòng LLM, số lần gọi tool, tổng thời gian (P7). Vòng cuối (hoặc khi hết ngân sách tool) bị ép
  ``tool_choice="none"`` kèm một tin nhắn hệ thống, nên tổng số lời gọi LLM ≤ ``max_rounds``.
- Tool độc lập trong cùng một vòng chạy song song (``TaskGroup``); tool lỗi/quá hạn thành ``ToolResult(ok=False)`` cho LLM.
- Hủy (``task.cancel()``) lan xuống mọi lời gọi đang chạy; không phát sinh lời gọi mới (P12).
- Kết quả tool được che PII và bọc ``<tool_result>`` trước khi vào ``messages``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from vin15_agent.core.ai_client import AiClient, ChatResult, ToolCall
from vin15_agent.core.tools import ToolRegistry, ToolResult, TurnContext, tool_result_content

logger = logging.getLogger(__name__)

PLANNING_TEXT_LIMIT = 200


@dataclass(frozen=True)
class PlanningEvent:
    """Câu ngắn LLM nói trước khi gọi tool (hiển thị như tiến trình, không phải câu trả lời)."""

    text: str


@dataclass(frozen=True)
class ToolCallEvent:
    name: str
    label: str


@dataclass(frozen=True)
class ToolResultEvent:
    name: str
    ok: bool
    summary: str


LoopEvent = PlanningEvent | ToolCallEvent | ToolResultEvent
Emit = Callable[[LoopEvent], Awaitable[None]]


@dataclass(frozen=True)
class LoopConfig:
    max_rounds: int
    max_tool_calls: int
    turn_seconds: float
    tool_timeout_seconds: float
    temperature: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class LoopOutcome:
    text: str
    #: ``answer``: LLM trả câu cuối; ``limit``: hết vòng/ngân sách mà không có câu trả lời; ``timeout``: hết thời gian.
    finish: Literal["answer", "limit", "timeout"]
    rounds: int
    tool_calls_used: int


async def _execute_tool(call: ToolCall, registry: ToolRegistry, ctx: TurnContext, timeout: float) -> ToolResult:
    tool = registry.get(call.name)
    if tool is None:
        return ToolResult.failure("unknown_tool", f"Không có công cụ '{call.name}'")
    try:
        args = call.parsed_arguments()
    except ValueError as exc:
        return ToolResult.failure("invalid_arguments", str(exc))
    try:
        return await asyncio.wait_for(tool.run(args, ctx), timeout)
    except TimeoutError:
        return ToolResult.failure("tool_timeout", "Công cụ phản hồi quá chậm")
    except Exception as exc:  # không để một tool làm sập lượt; không đưa chi tiết lỗi nội bộ cho LLM
        logger.warning("Tool '%s' lỗi: %s", call.name, type(exc).__name__)
        return ToolResult.failure("tool_error", "Công cụ gặp lỗi, hãy thử cách khác hoặc nói rõ là chưa tra được")


async def _run_tools(
    calls: list[ToolCall], registry: ToolRegistry, ctx: TurnContext, timeout: float, emit: Emit | None
) -> list[ToolResult]:
    async def safe_emit(event: LoopEvent, errors: list[Exception]) -> None:
        if emit is None:
            return
        try:
            await emit(event)
        except Exception as exc:  # ví dụ client đã rớt: dừng lượt sau khi nhóm tool xong
            errors.append(exc)

    errors: list[Exception] = []
    for call in calls:
        tool = registry.get(call.name)
        label = call.name
        if tool is not None:
            try:
                label = tool.describe(call.parsed_arguments())
            except ValueError:
                label = getattr(tool, "label", call.name)
        await safe_emit(ToolCallEvent(call.name, label), errors)

    async def one(call: ToolCall) -> ToolResult:
        started = time.monotonic()
        result = await _execute_tool(call, registry, ctx, timeout)
        latency = int((time.monotonic() - started) * 1000)
        ctx.trace.add_tool(call.name, ok=result.ok, latency_ms=latency, summary=result.summary)
        if result.ok:
            ctx.tool_texts.append(json.dumps(result.data, ensure_ascii=False, default=str))
        await safe_emit(ToolResultEvent(call.name, result.ok, result.summary), errors)
        return result

    async with asyncio.TaskGroup() as group:
        tasks = [group.create_task(one(call)) for call in calls]
    if errors:
        raise errors[0]
    return [t.result() for t in tasks]


async def run_agent_loop(
    *,
    ai: AiClient,
    registry: ToolRegistry,
    messages: list[dict[str, Any]],
    ctx: TurnContext,
    config: LoopConfig,
    emit: Emit | None = None,
    limit_message: str = "",
    before_answer: Callable[[TurnContext], str | None] | None = None,
) -> LoopOutcome:
    """Chạy vòng lặp; ``messages`` được nối thêm tại chỗ. ``LlmUnavailableError`` và lỗi LLM khác được ném lên cho người gọi.

    ``before_answer(ctx)`` được hỏi khi LLM định trả câu cuối mà vẫn còn vòng và ngân sách tool: trả chuỗi thì chuỗi đó được thêm
    như một nhắc nhở (``system``) và LLM được gọi lại, nhưng chỉ một lần mỗi lượt (ví dụ nhắc tra quy định khi mới xem hồ sơ cá nhân).
    """
    deadline = time.monotonic() + config.turn_seconds
    specs = registry.to_openai_schema() or None
    used = 0
    nudged = False
    for round_no in range(1, config.max_rounds + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return LoopOutcome("", "timeout", round_no - 1, used)
        force_final = round_no == config.max_rounds or used >= config.max_tool_calls
        if force_final and used > 0 and limit_message:
            messages.append({"role": "system", "content": limit_message})
        ctx.trace.step("llm_round", f"vòng {round_no}")
        try:
            response: ChatResult = await asyncio.wait_for(
                ai.chat(
                    messages,
                    tools=specs,
                    tool_choice="none" if force_final else "auto",
                    temperature=config.temperature,
                    max_tokens=config.max_tokens,
                    reasoning_effort=config.reasoning_effort,
                ),
                remaining,
            )
        except TimeoutError:
            return LoopOutcome("", "timeout", round_no - 1, used)
        ctx.trace.add_llm(response)

        if not response.tool_calls:
            text = response.text.strip()
            if before_answer is not None and not nudged and not force_final and round_no < config.max_rounds:
                nudge = before_answer(ctx)
                if nudge:
                    nudged = True
                    messages.append({"role": "system", "content": nudge})
                    continue
            return LoopOutcome(text, "answer" if text else "limit", round_no, used)
        if force_final:  # LLM phớt lờ tool_choice="none": không còn lượt để chạy tool
            return LoopOutcome(response.text.strip(), "limit" if not response.text.strip() else "answer", round_no, used)

        messages.append(response.assistant_message())
        if response.text.strip() and emit is not None:
            await emit(PlanningEvent(ctx.redactor.redact_text(response.text.strip())[:PLANNING_TEXT_LIMIT]))
        budget = config.max_tool_calls - used
        runnable, skipped = list(response.tool_calls[:budget]), list(response.tool_calls[budget:])
        results = await _run_tools(runnable, registry, ctx, config.tool_timeout_seconds, emit)
        used += len(runnable)
        for call, result in zip(runnable, results, strict=True):
            messages.append({"role": "tool", "tool_call_id": call.id, "content": tool_result_content(call.name, result, ctx.redactor)})
        for call in skipped:
            skip = ToolResult.failure("tool_limit", "Đã hết số lần gọi công cụ cho lượt này")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": tool_result_content(call.name, skip, ctx.redactor)})
    return LoopOutcome("", "limit", config.max_rounds, used)
