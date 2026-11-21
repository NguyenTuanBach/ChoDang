"""Khung WebSocket của trợ lý hỏi đáp. Nguồn sự thật: ``.kiro/specs/agent-hoi-dap/contract.md`` (đổi ở đây phải đổi cả ``fe/src/lib/assistant-protocol.ts``)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

Role = Literal["student", "lecturer", "admin"]
Step = Literal["planning", "searching", "reading", "answering", "verifying"]
ErrorCode = Literal["busy", "rate_limited", "timeout", "cancelled", "llm_unavailable", "internal"]
Verdict = Literal["answered", "no_match", "refused", "needs_human", "degraded", "error_fallback"]


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Actor(BaseModel):
    role: Role
    #: Rỗng ở dev: BE dùng người dùng mặc định. Agent chỉ chuyển tiếp, không giải mã.
    agent_token: str = ""


class StartFrame(BaseModel):
    type: Literal["start"] = "start"
    conversation_id: str
    turn_id: str
    question: str
    history: list[HistoryItem] = Field(default_factory=list)
    actor: Actor
    today: str  # YYYY-MM-DD, theo múi giờ nghiệp vụ


class CancelFrame(BaseModel):
    type: Literal["cancel"] = "cancel"


class PingFrame(BaseModel):
    type: Literal["ping"] = "ping"


class PongFrame(BaseModel):
    type: Literal["pong"] = "pong"


class ReadyFrame(BaseModel):
    type: Literal["ready"] = "ready"


class StatusFrame(BaseModel):
    type: Literal["status"] = "status"
    step: Step
    text: str


class ToolCallFrame(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    name: str
    label: str


class ToolResultFrame(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    name: str
    ok: bool
    summary: str


class TokenFrame(BaseModel):
    type: Literal["token"] = "token"
    delta: str


class Citation(BaseModel):
    chunk_id: str
    doc_code: str
    doc_title: str
    version: str
    article: str
    clause: str | None = None
    effective_from: str
    is_sample: bool = False
    quote: str


class Usage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    provider: str | None = None
    model: str | None = None


class Action(BaseModel):
    """Hành động giao diện trợ lý đề nghị (hiện chỉ điều hướng). ``page`` là khóa trang trong ``pages.json``; FE tự đổi sang URL."""

    type: Literal["navigate"] = "navigate"
    page: str
    label: str


class FinalFrame(BaseModel):
    type: Literal["final"] = "final"
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    verdict: Verdict
    degraded: bool = False
    usage: Usage = Field(default_factory=Usage)
    trace_id: str
    actions: list[Action] = Field(default_factory=list)


class ErrorFrame(BaseModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    message: str


#: Khung agent nhận (sau ``start``): chỉ ``cancel`` và ``ping``.
InboundFrame = Annotated[StartFrame | CancelFrame | PingFrame, Field(discriminator="type")]
OutboundFrame = Annotated[
    ReadyFrame | StatusFrame | ToolCallFrame | ToolResultFrame | TokenFrame | FinalFrame | ErrorFrame | PongFrame,
    Field(discriminator="type"),
]

inbound_adapter: TypeAdapter[InboundFrame] = TypeAdapter(InboundFrame)
outbound_adapter: TypeAdapter[OutboundFrame] = TypeAdapter(OutboundFrame)

#: Mã đóng WebSocket.
CLOSE_OK = 1000
CLOSE_UNSUPPORTED = 1003
CLOSE_TOO_BIG = 1009
CLOSE_UNAUTHORIZED = 4401
CLOSE_TIMEOUT = 4408
CLOSE_RATE_LIMITED = 4429
MAX_FRAME_BYTES = 256 * 1024
