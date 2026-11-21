"""Vòng lặp agent (task 5): gọi tool, giới hạn, song song, tool lỗi, hủy, trace. LLM giả, không mạng."""

import asyncio
import json
import time

import pytest

from vin15_agent.core.agent_loop import LoopConfig, PlanningEvent, ToolCallEvent, ToolResultEvent, run_agent_loop
from vin15_agent.core.ai_client import ChatResult, LlmUnavailableError, ToolCall
from vin15_agent.core.tools import ToolRegistry, ToolResult, TurnContext


def reply(text="", calls=()):
    return ChatResult(text=text, provider="fake", model="f-1", prompt_tokens=10, completion_tokens=5, tool_calls=tuple(calls))


def call(id_, name="echo", **args):
    return ToolCall(id_, name, json.dumps(args))


class FakeAi:
    """Phát lần lượt các phản hồi đã định; hết thì lặp lại phản hồi cuối. Ghi lại các lần gọi."""

    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    async def chat(self, messages, **kw):
        self.calls.append({"messages": [dict(m) for m in messages], **kw})
        r = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(r, Exception):
            raise r
        return r


class EchoTool:
    name, description, label, read_only = "echo", "echo", "Lặp lại", True
    parameters = {"type": "object", "properties": {"text": {"type": "string"}}}

    def __init__(self, delay=0.0, fail=None):
        self.delay, self.fail, self.runs, self.active, self.max_active = delay, fail, [], 0, 0

    async def run(self, args, ctx):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
            if self.fail:
                raise self.fail
            self.runs.append(args)
            return ToolResult.success({"echo": args.get("text")}, summary="đã lặp")
        finally:
            self.active -= 1

    def describe(self, args):
        return f"{self.label}: {args.get('text', '')}"


def run(ai, tool=None, *, config=None, messages=None, events=None):
    tool = tool or EchoTool()
    ctx = TurnContext(actor_role="student", today="2026-11-21")
    cfg = config or LoopConfig(max_rounds=6, max_tool_calls=8, turn_seconds=5, tool_timeout_seconds=1)
    events = events if events is not None else []

    async def emit(e):
        events.append(e)

    msgs = messages if messages is not None else [{"role": "user", "content": "hỏi"}]
    outcome = asyncio.run(run_agent_loop(ai=ai, registry=ToolRegistry([tool]), messages=msgs, ctx=ctx, config=cfg, emit=emit, limit_message="HẾT GIỚI HẠN"))
    return outcome, ctx, msgs, events


def test_no_tool_calls_returns_answer_immediately():
    out, ctx, _, events = run(FakeAi(reply("Xin chào")))
    assert (out.text, out.finish, out.rounds) == ("Xin chào", "answer", 1) and events == []
    assert ctx.trace.llm_calls == 1 and ctx.trace.prompt_tokens == 10


def test_tool_round_then_answer_and_messages_chain():
    ai = FakeAi(reply("Để mình tra.", [call("c1", text="a")]), reply("Kết quả."))
    out, ctx, msgs, events = run(ai)
    assert out.text == "Kết quả." and out.rounds == 2 and out.tool_calls_used == 1
    assistant, tool_msg = msgs[1], msgs[2]
    assert assistant["role"] == "assistant" and assistant["tool_calls"][0]["id"] == "c1"
    assert tool_msg["role"] == "tool" and tool_msg["tool_call_id"] == "c1"
    assert tool_msg["content"].startswith('<tool_result name="echo">') and '"echo": "a"' in tool_msg["content"]
    kinds = [type(e) for e in events]
    assert kinds == [PlanningEvent, ToolCallEvent, ToolResultEvent]
    assert events[1].label == "Lặp lại: a" and events[2].ok and events[2].summary == "đã lặp"
    assert [t["name"] for t in ctx.trace.tool_calls] == ["echo"] and ctx.trace.tool_calls[0]["ok"] is True
    assert ai.calls[0]["tool_choice"] == "auto" and ai.calls[0]["tools"][0]["function"]["name"] == "echo"


def test_tool_results_recorded_for_number_checking():
    _, ctx, _, _ = run(FakeAi(reply("", [call("c1", text="120")]), reply("ok")))
    assert any("120" in t for t in ctx.tool_texts)


def test_p7_loop_terminates_even_if_llm_always_asks_for_tools():
    ai = FakeAi(reply("", [call("x", text="1"), call("y", text="2"), call("z", text="3")]))
    tool = EchoTool()
    out, _, msgs, _ = run(ai, tool)
    assert len(ai.calls) <= 6 and out.rounds <= 6
    assert out.tool_calls_used <= 8 and len(tool.runs) <= 8
    assert out.finish == "limit"
    # mọi tool_call đều có tin nhắn phản hồi (API yêu cầu)
    ids = [c["id"] for m in msgs if m.get("tool_calls") for c in m["tool_calls"]]
    answered = {m["tool_call_id"] for m in msgs if m["role"] == "tool"}
    assert set(ids) == answered


def test_last_round_forces_no_tools_and_adds_limit_message():
    ai = FakeAi(reply("", [call("a", text="1")]), reply("Trả lời cuối."))
    cfg = LoopConfig(max_rounds=2, max_tool_calls=8, turn_seconds=5, tool_timeout_seconds=1)
    out, _, _, _ = run(ai, config=cfg)
    assert out.text == "Trả lời cuối." and out.finish == "answer"
    assert ai.calls[1]["tool_choice"] == "none"
    assert any(m["role"] == "system" and m["content"] == "HẾT GIỚI HẠN" for m in ai.calls[1]["messages"])


def test_tool_budget_exhausted_skips_extra_calls_and_forces_final():
    ai = FakeAi(reply("", [call("a", text="1"), call("b", text="2"), call("c", text="3")]), reply("Xong."))
    cfg = LoopConfig(max_rounds=6, max_tool_calls=2, turn_seconds=5, tool_timeout_seconds=1)
    tool = EchoTool()
    out, _, msgs, _ = run(ai, tool, config=cfg)
    assert len(tool.runs) == 2 and out.tool_calls_used == 2 and out.text == "Xong."
    skipped = next(m for m in msgs if m.get("tool_call_id") == "c")
    assert "tool_limit" in skipped["content"]
    assert ai.calls[1]["tool_choice"] == "none"


def test_independent_tool_calls_run_in_parallel():
    tool = EchoTool(delay=0.2)
    ai = FakeAi(reply("", [call("a", text="1"), call("b", text="2"), call("c", text="3")]), reply("ok"))
    t0 = time.monotonic()
    run(ai, tool)
    assert time.monotonic() - t0 < 0.5 and tool.max_active == 3


def test_failing_slow_unknown_and_bad_args_become_tool_results():
    slow, bad_tool = EchoTool(delay=2), EchoTool(fail=RuntimeError("secret internals"))
    cfg = LoopConfig(max_rounds=6, max_tool_calls=8, turn_seconds=5, tool_timeout_seconds=0.05)
    out, _, msgs, events = run(FakeAi(reply("", [call("a", text="1")]), reply("ok")), slow, config=cfg)
    assert out.text == "ok" and "tool_timeout" in msgs[2]["content"]
    out, _, msgs, _ = run(FakeAi(reply("", [call("a", text="1")]), reply("ok")), bad_tool)
    assert "tool_error" in msgs[2]["content"] and "secret internals" not in msgs[2]["content"]
    out, _, msgs, events = run(FakeAi(reply("", [ToolCall("u", "khong_co", "{}"), ToolCall("v", "echo", "{hỏng")]), reply("ok")))
    assert "unknown_tool" in msgs[2]["content"] and "invalid_arguments" in msgs[3]["content"]
    assert [e.ok for e in events if isinstance(e, ToolResultEvent)] == [False, False]


def test_timeout_during_llm_call_ends_with_timeout_outcome():
    class SlowAi(FakeAi):
        async def chat(self, messages, **kw):
            await asyncio.sleep(2)

    cfg = LoopConfig(max_rounds=6, max_tool_calls=8, turn_seconds=0.1, tool_timeout_seconds=1)
    out, *_ = run(SlowAi(), config=cfg)
    assert out.finish == "timeout" and out.text == ""


def test_llm_unavailable_propagates():
    with pytest.raises(LlmUnavailableError):
        run(FakeAi(LlmUnavailableError("sập")))


def test_cancel_stops_llm_and_tool_calls_p12():
    """Hủy task đang chạy: tool đang chạy bị hủy, không có lời gọi LLM/tool mới."""

    async def scenario():
        tool = EchoTool(delay=10)
        ai = FakeAi(reply("", [call("a", text="1")]), reply("không bao giờ tới"))
        ctx = TurnContext(actor_role="student", today="2026-11-21")
        task = asyncio.create_task(
            run_agent_loop(
                ai=ai, registry=ToolRegistry([tool]), messages=[{"role": "user", "content": "x"}], ctx=ctx,
                config=LoopConfig(6, 8, 30, 20), emit=None, limit_message="",
            )
        )  # fmt: skip
        await asyncio.sleep(0.1)
        assert tool.active == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.05)
        return tool, ai

    tool, ai = asyncio.run(scenario())
    assert tool.active == 0 and len(ai.calls) == 1 and tool.runs == []


# ---- before_answer: nhắc tra quy định một lần ----
def run_with_nudge(ai, nudge, tool=None, config=None):
    tool = tool or EchoTool()
    registry = ToolRegistry([tool])
    messages = [{"role": "user", "content": "hỏi"}]
    ctx = TurnContext(actor_role="student", agent_token="", today="2026-11-21")
    cfg = config or LoopConfig(max_rounds=4, max_tool_calls=6, turn_seconds=5, tool_timeout_seconds=2, temperature=0.2, max_tokens=500)
    outcome = asyncio.run(run_agent_loop(ai=ai, registry=registry, messages=messages, ctx=ctx, config=cfg, before_answer=nudge))
    return outcome, messages


def test_before_answer_nudges_once_then_lets_llm_call_tool_and_answer():
    ai = FakeAi(reply("trả lời sớm"), reply(calls=[call("c1", text="x")]), reply("trả lời đủ"))
    outcome, messages = run_with_nudge(ai, lambda ctx: None if ctx.trace.tool_calls else "HÃY TRA QUY ĐỊNH")
    assert outcome.text == "trả lời đủ" and outcome.tool_calls_used == 1 and len(ai.calls) == 3
    assert {"role": "system", "content": "HÃY TRA QUY ĐỊNH"} in messages


def test_before_answer_is_asked_to_nudge_at_most_once():
    ai = FakeAi(reply("lần 1"), reply("lần 2"))
    outcome, _ = run_with_nudge(ai, lambda ctx: "NHẮC")
    assert outcome.text == "lần 2" and len(ai.calls) == 2
