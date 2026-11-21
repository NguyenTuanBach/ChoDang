"""``AssistantOrchestrator`` với agent giả (WebSocket thật) và kho hội thoại giả."""

from __future__ import annotations

import asyncio
import json
import time

import pytest

from tests.fake_agent import FINAL, fake_agent, script
from tests.fakes import STUDENT_A, STUDENT_B, TODAY, FakeAudit, FakeChats
from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.pii import PiiRedactor
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.security.actor_token import ActorTokenService
from vin15.service.agent.assistant_orchestrator import AssistantOrchestrator

TOKENS = ActorTokenService("s" * 32)


class Sink:
    """Thu các khung gửi cho FE."""

    def __init__(self, fail_after: int | None = None):
        self.frames: list[dict] = []
        self._fail_after = fail_after

    async def __call__(self, frame):
        if self._fail_after is not None and len(self.frames) >= self._fail_after:
            raise ConnectionError("FE đã rớt")
        self.frames.append(frame)

    @property
    def types(self):
        return [f["type"] for f in self.frames]


def make(url, chats=None, audit=None, deadline=10.0, history_turns=2):
    chats = chats if chats is not None else FakeChats()
    audit = audit if audit is not None else FakeAudit()
    orchestrator = AssistantOrchestrator(
        AgentApiClient(url, "tok"),
        chats,
        audit,
        TOKENS,
        PiiRedactor(),
        lambda: TODAY,
        history_turns=history_turns,
        question_max_chars=200,
        deadline_seconds=deadline,
    )
    return orchestrator, chats, audit


FRAMES = [
    {"type": "ready"},
    {"type": "status", "step": "searching", "text": "Đang tra quy định liên hệ a@b.vn"},
    {"type": "tool_call", "name": "search_policy", "label": "Đang tra quy định…"},
    {"type": "tool_result", "name": "search_policy", "ok": True, "summary": "3 đoạn"},
    {"type": "token", "delta": "Thời lượng "},
    FINAL,
]


@pytest.mark.anyio
async def test_happy_path_forwards_frames_saves_and_audits():
    record = []
    async with fake_agent(script(*FRAMES, record=record)) as url:
        orchestrator, chats, audit = make(url)
        sink = Sink()
        await orchestrator.run_turn(STUDENT_A, None, "t1", "Thời lượng tối thiểu?", sink)
    assert sink.types == ["status", "tool_call", "tool_result", "token", "final"]  # agent `ready` không chuyển tiếp
    assert all(f["turn_id"] == "t1" and f["conversation_id"] == "1" for f in sink.frames)
    final = sink.frames[-1]
    assert final["message_id"] == "2" and final["trace_id"] == "tr-1" and final["citations"][0]["chunk_id"] == "QD-TT-01@v1/d3/k1"
    user_msg, assistant_msg = chats.messages
    assert (user_msg.role, user_msg.content, user_msg.turn_id) == ("user", "Thời lượng tối thiểu?", "t1")
    assert assistant_msg.role == "assistant" and "8 tuần" in assistant_msg.content and not assistant_msg.degraded
    assert assistant_msg.citations[0]["quote"].startswith("Thời lượng thực tập")
    trace = assistant_msg.trace
    assert trace["trace_id"] == "tr-1" and trace["verdict"] == "answered" and trace["usage"]["provider"] == "openai"
    assert [s["type"] for s in trace["steps"]] == ["status", "tool_call", "tool_result"]
    assert "a@b.vn" not in json.dumps(trace) and "[EMAIL_1]" in trace["steps"][0]["text"]  # trace đã che PII
    assert chats.conversations[1].title == "Thời lượng tối thiểu?"
    assert [(e.actor_kind.value, e.entity, e.action) for e in audit.entries] == [("agent", "assistant_turn", "answer")]
    assert audit.entries[0].after["trace_id"] == "tr-1" and audit.entries[0].reason == "conv=1 turn=t1"


@pytest.mark.anyio
async def test_start_frame_has_scoped_short_lived_agent_token_and_today():
    record = []
    async with fake_agent(script(FINAL, record=record)) as url:
        orchestrator, _chats, _audit = make(url)
        await orchestrator.run_turn(STUDENT_A, None, "t1", "  Xin chào  ", Sink())
    start = record[0]
    assert start["type"] == "start" and start["question"] == "Xin chào" and start["today"] == "2026-11-21"
    assert start["conversation_id"] == "1" and start["turn_id"] == "t1" and start["history"] == []
    assert start["actor"]["role"] == "student"
    claims = TOKENS.decode(start["actor"]["agent_token"], scope="agent_tools")
    assert claims["sub"] == STUDENT_A.id and claims["conv"] == "1" and claims["turn"] == "t1"
    assert claims["exp"] - time.time() <= 5 * 60 + 2
    with pytest.raises(AuthenticationRequiredError):
        TOKENS.decode(start["actor"]["agent_token"])  # không dùng được như token phiên thường


@pytest.mark.anyio
async def test_history_is_trimmed_and_pii_redacted():
    chats = FakeChats()
    record = []
    async with fake_agent(script(FINAL, record=record)) as url:
        orchestrator, chats, _audit = make(url, chats=chats, history_turns=2)
        for i in range(4):  # 4 lượt cũ, mỗi lượt có PII
            await orchestrator.run_turn(
                STUDENT_A, None if i == 0 else "1", f"t{i}", f"Câu {i}: email của em là sv{i}@truong.edu.vn, sđt 0912345678", Sink()
            )
        await orchestrator.run_turn(STUDENT_A, "1", "t9", "Câu cuối", Sink())
    history = record[-1]["history"]
    assert len(history) == 4  # chỉ 2 lượt gần nhất (câu hỏi + trả lời) -> 4 tin
    text = json.dumps(history, ensure_ascii=False)
    assert "truong.edu.vn" not in text and "0912345678" not in text and "[EMAIL_1]" in text and "[SDT_1]" in text
    assert "Câu 0" not in text and "Câu 3" in text
    assert [h["role"] for h in history] == ["user", "assistant", "user", "assistant"]


@pytest.mark.anyio
async def test_cancel_is_forwarded_to_agent_and_error_relayed():
    seen = []

    async def handler(ws):
        await ws.recv()
        await ws.send(json.dumps({"type": "status", "step": "searching", "text": "..."}))
        seen.append(json.loads(await ws.recv()))
        await ws.send(json.dumps({"type": "error", "code": "cancelled", "message": "Đã hủy"}))

    async with fake_agent(handler) as url:
        orchestrator, chats, audit = make(url)
        sink, cancel = Sink(), asyncio.Event()

        async def emit(frame):
            await sink(frame)
            if frame["type"] == "status":
                cancel.set()

        await orchestrator.run_turn(STUDENT_A, None, "t1", "hỏi", emit, cancel)
    assert seen == [{"type": "cancel"}]
    assert sink.types == ["status", "error"] and sink.frames[-1]["code"] == "cancelled"
    assert [m.role for m in chats.messages] == ["user"]  # không lưu câu trả lời
    assert audit.entries[0].action == "error" and audit.entries[0].after["code"] == "cancelled"


@pytest.mark.anyio
async def test_turn_completes_and_is_saved_even_if_frontend_drops():
    async with fake_agent(script(*FRAMES)) as url:
        orchestrator, chats, audit = make(url)
        sink = Sink(fail_after=1)  # FE chỉ nhận được 1 khung rồi rớt
        await orchestrator.run_turn(STUDENT_A, None, "t1", "hỏi", sink)
    assert sink.types == ["status"]
    assert [m.role for m in chats.messages] == ["user", "assistant"]
    assert chats.messages[1].trace["trace_id"] == "tr-1" and audit.entries[0].action == "answer"


@pytest.mark.anyio
async def test_agent_unavailable_reports_error_and_keeps_user_message():
    orchestrator, chats, audit = make("http://127.0.0.1:1")
    sink = Sink()
    await orchestrator.run_turn(STUDENT_A, None, "t1", "hỏi", sink)
    assert sink.types == ["error"] and sink.frames[0]["code"] == "llm_unavailable"
    assert sink.frames[0]["turn_id"] == "t1" and sink.frames[0]["conversation_id"] == "1"
    assert [m.role for m in chats.messages] == ["user"]
    assert audit.entries[0].action == "error" and audit.entries[0].after["code"] == "llm_unavailable"


@pytest.mark.anyio
async def test_agent_error_frame_is_forwarded():
    err = {"type": "error", "code": "busy", "message": "Agent bận"}
    async with fake_agent(script(err)) as url:
        orchestrator, _chats, audit = make(url)
        sink = Sink()
        await orchestrator.run_turn(STUDENT_A, None, "t1", "hỏi", sink)
    assert sink.frames == [{**err, "turn_id": "t1", "conversation_id": "1"}]
    assert audit.entries[0].after["code"] == "busy"


@pytest.mark.anyio
async def test_deadline_reports_timeout():
    async def handler(ws):
        await ws.recv()
        await asyncio.sleep(2)

    async with fake_agent(handler) as url:
        orchestrator, _chats, audit = make(url, deadline=0.3)
        sink = Sink()
        await orchestrator.run_turn(STUDENT_A, None, "t1", "hỏi", sink)
    assert sink.frames[-1]["code"] == "timeout" and audit.entries[0].after["code"] == "timeout"


@pytest.mark.anyio
async def test_other_users_conversation_is_rejected_without_calling_agent():
    record = []
    async with fake_agent(script(FINAL, record=record)) as url:
        orchestrator, chats, _audit = make(url)
        await orchestrator.run_turn(STUDENT_A, None, "t1", "hỏi của A", Sink())
        sink = Sink()
        await orchestrator.run_turn(STUDENT_B, "1", "t2", "tôi đọc hội thoại của A", sink)
    assert sink.types == ["error"] and sink.frames[0]["code"] == "invalid_frame" and "Không tìm thấy hội thoại" in sink.frames[0]["message"]
    assert len(record) == 1  # agent chỉ được gọi cho lượt của A
    assert all(m.conversation_id == 1 and m.content != "tôi đọc hội thoại của A" for m in chats.messages)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("conversation_id", "turn_id", "question", "message"),
    [
        (None, "t1", "   ", "không được rỗng"),
        (None, "t1", "x" * 201, "quá dài"),
        ("abc", "t1", "hỏi", "Không tìm thấy hội thoại"),
        ("99", "t1", "hỏi", "Không tìm thấy hội thoại"),
    ],
)
async def test_invalid_requests_never_reach_agent(conversation_id, turn_id, question, message):
    orchestrator, chats, audit = make("http://127.0.0.1:1")
    sink = Sink()
    await orchestrator.run_turn(STUDENT_A, conversation_id, turn_id, question, sink)
    assert sink.frames[0]["code"] == "invalid_frame" and message in sink.frames[0]["message"]
    assert chats.messages == [] and audit.entries == []


@pytest.mark.anyio
async def test_duplicate_turn_id_is_rejected():
    async with fake_agent(script(FINAL)) as url:
        orchestrator, chats, _audit = make(url)
        await orchestrator.run_turn(STUDENT_A, None, "t1", "hỏi", Sink())
        sink = Sink()
        await orchestrator.run_turn(STUDENT_A, "1", "t1", "hỏi lại", sink)
    assert sink.frames[0]["code"] == "invalid_frame" and "turn_id" in sink.frames[0]["message"]
    assert len(chats.messages) == 2


# ---- hành động giao diện (điều hướng) trong `final` ----
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, []),
        ("navigate", []),
        ([], []),
        ([{"type": "navigate", "page": "outline", "label": "Đề cương"}], [{"type": "navigate", "page": "outline", "label": "Đề cương"}]),
        ([{"type": "navigate", "page": "outline", "label": "Đề cương", "href": "https://evil.example"}], [{"type": "navigate", "page": "outline", "label": "Đề cương"}]),
        ([{"type": "open_url", "page": "outline", "label": "x"}], []),
        ([{"type": "navigate", "page": "../admin", "label": "x"}], []),
        ([{"type": "navigate", "page": "Outline", "label": "x"}], []),
        ([{"type": "navigate", "page": "a" * 41, "label": "x"}], []),
        ([{"type": "navigate", "page": "outline", "label": "x" * 81}], []),
        ([{"type": "navigate", "page": "outline", "label": ""}], []),
        ([{"type": "navigate", "page": 3, "label": "x"}], []),
        (
            [{"type": "navigate", "page": "../x", "label": "bad"}, {"type": "navigate", "page": "journal", "label": "Nhật ký"}, {"type": "navigate", "page": "grades", "label": "Bảng điểm"}],
            [{"type": "navigate", "page": "journal", "label": "Nhật ký"}],
        ),
    ],
)
def test_valid_actions_filters_and_limits_to_one(raw, expected):
    from vin15.service.agent.assistant_orchestrator import valid_actions

    assert valid_actions(raw) == expected


@pytest.mark.anyio
async def test_final_forwards_only_valid_navigate_action_and_does_not_store_it():
    final = {**FINAL, "actions": [{"type": "navigate", "page": "outline", "label": "Đề cương", "x": 1}, {"type": "navigate", "page": "bad/key", "label": "y"}]}
    async with fake_agent(script({"type": "ready"}, final)) as url:
        orchestrator, chats, _ = make(url)
        sink = Sink()
        await orchestrator.run_turn(STUDENT_A, None, "t1", "mở trang đề cương", sink)
    assert sink.frames[-1]["actions"] == [{"type": "navigate", "page": "outline", "label": "Đề cương"}]
    assert "actions" not in chats.messages[-1].trace and "outline" not in json.dumps(chats.messages[-1].trace)


@pytest.mark.anyio
async def test_final_without_actions_gets_empty_list():
    async with fake_agent(script({"type": "ready"}, FINAL)) as url:
        orchestrator, _, _ = make(url)
        sink = Sink()
        await orchestrator.run_turn(STUDENT_A, None, "t1", "hỏi", sink)
    assert sink.frames[-1]["actions"] == []
