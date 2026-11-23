"""Điều phối một lượt hỏi của trợ lý: kiểm hội thoại, nạp + che PII lịch sử, cấp agent-token, mở WebSocket tới agent,
chuyển tiếp khung cho FE, lưu ``final``/trace/audit.

Nếu FE rớt giữa lượt (``emit`` lỗi), lượt vẫn chạy hết và ``final`` vẫn được lưu để FE lấy lại qua REST (R9.7).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

import anyio.to_thread

from vin15.domain.clock import Clock
from vin15.domain.exception import AgentTimeoutError, AgentUnavailableError, InvalidInputError, ResourceNotFoundError, StateConflictError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.chat import Conversation
from vin15.domain.model.user import User
from vin15.domain.pii import PiiRedactor
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.audit_repository import AuditRepository
from vin15.infrastructure.persistence.chat_repository import ChatRepository
from vin15.infrastructure.security.actor_token import ActorTokenService

from .agent_subject_resolver import AGENT_TOKEN_TTL_MINUTES, AGENT_TOOLS_SCOPE

log = logging.getLogger(__name__)

_PAGE_KEY = re.compile(r"^[a-z_]{1,40}$")
_FILTER_KEY = re.compile(r"^[a-z_]{1,40}$")
_FILTER_VALUE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
_MAX_ACTION_LABEL = 80
_MAX_FILTERS = 4


def _positive_id(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _valid_filters(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    items = [(k, v) for k, v in raw.items() if isinstance(k, str) and _FILTER_KEY.match(k) and isinstance(v, str) and _FILTER_VALUE.match(v)]
    return dict(items[:_MAX_FILTERS])


def valid_actions(raw: Any) -> list[dict[str, Any]]:
    """Hành động giao diện agent đề nghị trong ``final``: chỉ giữ điều hướng hợp lệ (khóa trang chữ thường/gạch dưới, nhãn ngắn), tối đa một.

    ``internship_id`` (số nguyên dương) và ``filters`` (tối đa 4 cặp khóa/giá trị ngắn) là tùy chọn: trường sai định dạng thì bỏ trường đó.
    FE vẫn tự kiểm khóa theo vai trò, khóa lọc theo trang và tự đổi sang URL; quyền xem hồ sơ do BE kiểm khi trang tải. Đây là lớp lọc
    để BE không chuyển tiếp dữ liệu lạ từ agent tới trình duyệt. Không lưu DB: tải lại lịch sử không có hành động nên không tự điều hướng lại.
    """
    if not isinstance(raw, list):
        return []
    for item in raw:
        if not isinstance(item, dict) or item.get("type") != "navigate":
            continue
        page, label = item.get("page"), item.get("label")
        if isinstance(page, str) and _PAGE_KEY.match(page) and isinstance(label, str) and 0 < len(label) <= _MAX_ACTION_LABEL:
            action: dict[str, Any] = {"type": "navigate", "page": page, "label": label}
            internship_id = _positive_id(item.get("internship_id"))
            if internship_id is not None:
                action["internship_id"] = internship_id
            filters = _valid_filters(item.get("filters"))
            if filters:
                action["filters"] = filters
            return [action]
    return []


def valid_current_page(raw: Any) -> dict[str, Any] | None:
    """Trang người dùng đang mở (FE gửi kèm ``ask``): ``{"key", "internship_id"?}``; sai định dạng thì ``None`` (chỉ là ngữ cảnh, không báo lỗi)."""
    if not isinstance(raw, dict):
        return None
    key = raw.get("key")
    if not isinstance(key, str) or not _PAGE_KEY.match(key):
        return None
    page: dict[str, Any] = {"key": key}
    internship_id = _positive_id(raw.get("internship_id"))
    if internship_id is not None:
        page["internship_id"] = internship_id
    return page

Emit = Callable[[dict[str, Any]], Awaitable[None]]

_PROGRESS_FRAMES = ("status", "tool_call", "tool_result")
_TERMINAL = ("final", "error")
_MAX_TRACE_STEPS = 60
_TITLE_CHARS = 60


class _SafeEmitter:
    """Gửi khung cho FE; lỗi (FE đã rớt) thì bỏ qua các khung sau thay vì làm hỏng lượt."""

    def __init__(self, emit: Emit):
        self._emit = emit
        self.alive = True

    async def __call__(self, frame: dict[str, Any]) -> None:
        if not self.alive:
            return
        try:
            await self._emit(frame)
        except Exception:
            self.alive = False
            log.info("FE đã rớt kết nối giữa lượt: lượt vẫn chạy hết và sẽ được lưu")


class AssistantOrchestrator:
    def __init__(
        self,
        agent: AgentApiClient,
        chats: ChatRepository,
        audit: AuditRepository,
        tokens: ActorTokenService,
        redactor: PiiRedactor,
        clock: Clock,
        *,
        history_turns: int,
        question_max_chars: int,
        deadline_seconds: float,
    ):
        self._agent = agent
        self._chats = chats
        self._audit = audit
        self._tokens = tokens
        self._redactor = redactor
        self._clock = clock
        self._history_turns = history_turns
        self._question_max = question_max_chars
        self._deadline = deadline_seconds

    async def run_turn(
        self,
        user: User,
        conversation_id: str | None,
        turn_id: str,
        question: str,
        emit: Emit,
        cancel: asyncio.Event | None = None,
        current_page: Any = None,
    ) -> None:
        send = _SafeEmitter(emit)
        started = time.monotonic()
        try:
            conversation, history = await anyio.to_thread.run_sync(lambda: self._prepare(user, conversation_id, turn_id, question))
        except (InvalidInputError, ResourceNotFoundError, StateConflictError) as error:
            await send(_error_frame("invalid_frame", str(error), turn_id, conversation_id))
            return
        conv_id = str(conversation.id)
        start = {
            "type": "start",
            "conversation_id": conv_id,
            "turn_id": turn_id,
            "question": question.strip(),
            "history": history,
            "actor": {"role": user.role.value, "agent_token": self._agent_token(user, conv_id, turn_id)},
            "today": self._clock().isoformat(),
        }
        page = valid_current_page(current_page)
        if page is not None:
            start["current_page"] = page
        steps: list[dict[str, Any]] = []
        outcome: dict[str, Any] = {"result": "error", "code": "internal"}
        #: Khung kết thúc (final/error) giữ lại tới sau khi ghi audit: FE nhận nó rồi hỏi tiếp ngay thì lượt này đã xong, không bị ``busy``.
        terminal: dict[str, Any] | None = None
        try:
            async for frame in self._agent.chat(start, cancel=cancel, deadline_seconds=self._deadline):
                kind = frame.get("type")
                if kind in ("ready", "ping", "pong"):
                    continue  # ``ready`` của FE do handler gửi một lần sau ``auth``
                if kind in _PROGRESS_FRAMES and len(steps) < _MAX_TRACE_STEPS:
                    steps.append(self._trace_step(frame))
                if kind == "final":
                    frame, outcome = await self._save_final(conversation, turn_id, frame, steps, started)
                    if frame is None:
                        terminal = _error_frame("internal", "Không lưu được câu trả lời. Vui lòng thử lại.", turn_id, conv_id)
                        break
                elif kind == "error":
                    outcome = {"result": "error", "code": str(frame.get("code", "internal"))}
                framed = {**frame, "turn_id": turn_id, "conversation_id": conv_id}
                if kind in _TERMINAL:
                    terminal = framed
                else:
                    await send(framed)
        except AgentTimeoutError:
            outcome = {"result": "error", "code": "timeout"}
            terminal = _error_frame("timeout", "Trợ lý xử lý quá lâu, vui lòng thử lại.", turn_id, conv_id)
        except AgentUnavailableError as error:
            log.warning("Agent không khả dụng: %s", error)
            outcome = {"result": "error", "code": "llm_unavailable"}
            terminal = _error_frame(
                "llm_unavailable", "Trợ lý AI tạm không khả dụng. Vui lòng thử lại sau hoặc liên hệ giảng viên.", turn_id, conv_id
            )
        except Exception:
            log.exception("Lỗi không lường trước khi điều phối lượt hỏi")
            outcome = {"result": "error", "code": "internal"}
            terminal = _error_frame("internal", "Lỗi hệ thống khi xử lý câu hỏi.", turn_id, conv_id)
        await self._record_audit(user, conversation, turn_id, outcome, int((time.monotonic() - started) * 1000))
        if terminal is not None:
            await send(terminal)

    # ---- Chuẩn bị ----
    def _prepare(self, user: User, conversation_id: str | None, turn_id: str, question: str) -> tuple[Conversation, list[dict[str, str]]]:
        question = question.strip()
        if not question:
            raise InvalidInputError("Câu hỏi không được rỗng")
        if len(question) > self._question_max:
            raise InvalidInputError(f"Câu hỏi quá dài (tối đa {self._question_max} ký tự)")
        if conversation_id is None:
            conversation = self._chats.create_conversation(user.id, self._redactor.redact_text(question)[:_TITLE_CHARS])
            history: list[dict[str, str]] = []
        else:
            conversation = self._owned_conversation(user, conversation_id)
            if self._chats.turn_exists(conversation.id, turn_id):
                raise StateConflictError("turn_id đã được dùng trong hội thoại này")
            recent = self._chats.recent_messages(conversation.id, self._history_turns * 2)
            history = [{"role": m.role, "content": self._redactor.redact_text(m.content)} for m in recent]
        self._chats.add_message(conversation.id, turn_id, "user", question)
        return conversation, history

    def _owned_conversation(self, user: User, conversation_id: str) -> Conversation:
        try:
            conversation = self._chats.get_conversation(int(conversation_id))
        except ValueError:
            conversation = None
        if conversation is None or conversation.user_id != user.id:
            raise ResourceNotFoundError("Không tìm thấy hội thoại")  # không tiết lộ hội thoại của người khác có tồn tại
        return conversation

    def _agent_token(self, user: User, conv_id: str, turn_id: str) -> str:
        return self._tokens.create(
            user.id, user.role.value, AGENT_TOKEN_TTL_MINUTES, scope=AGENT_TOOLS_SCOPE, extra={"conv": conv_id, "turn": turn_id}
        )

    # ---- Lưu kết quả ----
    async def _save_final(
        self, conversation: Conversation, turn_id: str, frame: dict[str, Any], steps: list[dict[str, Any]], started: float
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        citations = [c for c in frame.get("citations", []) if isinstance(c, dict)]
        degraded = bool(frame.get("degraded", False))
        trace = {
            "trace_id": str(frame.get("trace_id", "")),
            "verdict": frame.get("verdict"),
            "degraded": degraded,
            "usage": frame.get("usage") if isinstance(frame.get("usage"), dict) else {},
            "latency_ms": int((time.monotonic() - started) * 1000),
            "citation_ids": [c.get("chunk_id") for c in citations],
            "steps": list(steps),
        }
        outcome = {"result": "final", "verdict": frame.get("verdict"), "degraded": degraded, "trace_id": trace["trace_id"]}
        try:
            message = await anyio.to_thread.run_sync(
                lambda: self._chats.add_message(
                    conversation.id,
                    turn_id,
                    "assistant",
                    str(frame.get("answer", "")),
                    citations=citations,
                    trace=trace,
                    degraded=degraded,
                )
            )
        except Exception:
            log.exception("Không lưu được câu trả lời của trợ lý")
            return None, {"result": "error", "code": "internal"}
        return {**frame, "message_id": str(message.id), "actions": valid_actions(frame.get("actions"))}, outcome

    def _trace_step(self, frame: dict[str, Any]) -> dict[str, Any]:
        """Bước tiến trình đã che PII (mọi chuỗi) và chỉ giữ trường cần."""
        keep = {"type", "step", "text", "name", "label", "ok", "summary"}
        return {k: (self._redactor.redact_text(v) if isinstance(v, str) else v) for k, v in frame.items() if k in keep}

    async def _record_audit(self, user: User, conversation: Conversation, turn_id: str, outcome: dict[str, Any], latency_ms: int) -> None:
        entry = AuditEntry(
            actor_kind=ActorKind.AGENT,
            actor_id=user.id,
            actor_role=user.role.value,
            entity="assistant_turn",
            entity_id=conversation.id,
            action="answer" if outcome.get("result") == "final" else "error",
            after={**outcome, "latency_ms": latency_ms},
            reason=f"conv={conversation.id} turn={turn_id}",
        )
        try:
            await anyio.to_thread.run_sync(lambda: self._audit.record(entry))
        except Exception:
            log.exception("Không ghi được audit cho lượt hỏi")


def _error_frame(code: str, message: str, turn_id: str, conversation_id: str | None) -> dict[str, Any]:
    frame: dict[str, Any] = {"type": "error", "code": code, "message": message, "turn_id": turn_id}
    if conversation_id is not None:
        frame["conversation_id"] = conversation_id
    return frame
