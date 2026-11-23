"""Trợ lý hỏi đáp cho FE: cấp vé WebSocket, đọc lại hội thoại, vết, và ``WS /api/assistant/ws``.

Hợp đồng khung: .kiro/specs/agent-hoi-dap/contract.md mục 4. ``RateLimitMiddleware`` không phủ WebSocket nên giới hạn
``ask``/phút và số kết nối/người được tính ngay trong handler.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import anyio.to_thread
from fastapi import APIRouter, Depends, WebSocket
from starlette.websockets import WebSocketDisconnect

from vin15.config.container import Container
from vin15.domain.exception import DatabaseUnavailableError, ResourceNotFoundError
from vin15.domain.model.user import User
from vin15.presentation.dto.assistant import (
    ConversationDetailDto,
    ConversationSummaryDto,
    StoredMessageDto,
    TraceDto,
    WsTicketResponse,
)

from .dependencies import container, current_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assistant", tags=["Trợ lý hỏi đáp"])

# Mã đóng WebSocket theo hợp đồng.
CLOSE_OK = 1000
CLOSE_POLICY = 1008
CLOSE_TOO_BIG = 1009
CLOSE_INTERNAL = 1011
CLOSE_UNAUTHORIZED = 4401
CLOSE_IDLE = 4408
CLOSE_RATE_LIMITED = 4429

#: BE chủ động ping mỗi ~25 giây; im lặng quá ~60 giây thì đóng.
PING_SECONDS = 25.0
IDLE_SECONDS = 60.0
_TURN_ID = re.compile(r"^[\w.-]{1,64}$")

#: Giữ tham chiếu tới task lượt hỏi để lượt vẫn chạy hết (và được lưu) kể cả khi FE đã rớt.
_background_turns: set[asyncio.Task] = set()


# ---------------------------------------------------------------- REST ----


@router.post("/ws-ticket", response_model=WsTicketResponse, summary="Cấp vé dùng một lần (~30 giây) để mở WebSocket")
def issue_ws_ticket(user: User = Depends(current_user), app: Container = Depends(container)) -> WsTicketResponse:
    store = app.ws_ticket_store
    return WsTicketResponse(ticket=store.issue(user.id), expires_in=store.ttl_seconds)


@router.get("/conversations", response_model=list[ConversationSummaryDto], summary="Hội thoại của tôi")
def list_conversations(user: User = Depends(current_user), app: Container = Depends(container)) -> list[ConversationSummaryDto]:
    return [ConversationSummaryDto.of(c) for c in app.conversation_service.list_conversations(user)]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailDto, summary="Một hội thoại của tôi (kèm tin nhắn)")
def get_conversation(
    conversation_id: str, user: User = Depends(current_user), app: Container = Depends(container)
) -> ConversationDetailDto:
    if not conversation_id.isdigit():
        raise ResourceNotFoundError("Không tìm thấy hội thoại")
    conversation, messages = app.conversation_service.get_conversation(user, int(conversation_id))
    return ConversationDetailDto(id=str(conversation.id), title=conversation.title, messages=[StoredMessageDto.of(m) for m in messages])


@router.get("/traces/{trace_id}", response_model=TraceDto, summary="Vết một lượt hỏi (chủ sở hữu hoặc quản trị viên)")
def get_trace(trace_id: str, user: User = Depends(current_user), app: Container = Depends(container)) -> TraceDto:
    message, conversation = app.conversation_service.get_trace(user, trace_id)
    return TraceDto(
        trace_id=trace_id,
        conversation_id=str(conversation.id),
        turn_id=message.turn_id,
        message_id=str(message.id),
        trace=message.trace,
    )


# ----------------------------------------------------------- WebSocket ----


class _FrameTooBig(Exception):
    pass


class _BadFrame(Exception):
    pass


def _origin_allowed(websocket: WebSocket, app: Container) -> bool:
    """Chống tấn công cross-site WebSocket hijacking: trình duyệt luôn gửi ``Origin``. Thiếu ``Origin`` (client không phải
    trình duyệt) chỉ được chấp nhận ngoài production; vẫn phải có vé hợp lệ."""
    origin = websocket.headers.get("origin")
    allowed = app.settings.cors_origin_list
    if origin is None:
        return not app.settings.is_production
    return "*" in allowed or origin in allowed


async def _read_frame(websocket: WebSocket, max_bytes: int) -> dict[str, Any]:
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    raw = message.get("text")
    if raw is None:
        raw = (message.get("bytes") or b"").decode("utf-8", errors="replace")
    if len(raw.encode("utf-8")) > max_bytes:
        raise _FrameTooBig
    try:
        frame = json.loads(raw)
    except ValueError as error:
        raise _BadFrame("Khung không phải JSON hợp lệ") from error
    if not isinstance(frame, dict) or not isinstance(frame.get("type"), str):
        raise _BadFrame('Khung phải là đối tượng JSON có trường "type"')
    return frame


async def _authenticate(websocket: WebSocket, app: Container) -> User | None:
    """Khung đầu tiên phải là ``auth{ticket}`` trong ``ASSISTANT_WS_AUTH_SECONDS`` giây. Sai/quá hạn: đóng 4401."""
    try:
        frame = await asyncio.wait_for(
            _read_frame(websocket, app.settings.assistant_max_frame_bytes), app.settings.assistant_ws_auth_seconds
        )
    except (TimeoutError, _BadFrame, WebSocketDisconnect):
        await _close(websocket, CLOSE_UNAUTHORIZED, "Cần khung auth trong thời gian quy định")
        return None
    except _FrameTooBig:
        await _close(websocket, CLOSE_TOO_BIG, "Khung quá lớn")
        return None
    ticket = frame.get("ticket")
    user_id = app.ws_ticket_store.consume(ticket) if frame.get("type") == "auth" and isinstance(ticket, str) else None
    user = await anyio.to_thread.run_sync(lambda: app.user_repository.find_by_id(user_id)) if user_id is not None else None
    if user is None or user.status.value == "revoked":
        await _close(websocket, CLOSE_UNAUTHORIZED, "Vé không hợp lệ hoặc đã hết hạn")
        return None
    return user


async def _close(websocket: WebSocket, code: int, reason: str = "") -> None:
    try:
        await websocket.close(code=code, reason=reason)
    except Exception:  # đã đóng
        pass


@router.websocket("/ws")
async def assistant_ws(websocket: WebSocket) -> None:
    app: Container = websocket.app.state.container
    if not _origin_allowed(websocket, app):
        await websocket.close(code=CLOSE_POLICY)  # trước accept: client nhận HTTP 403
        return
    await websocket.accept()
    try:
        user = await _authenticate(websocket, app)
        if user is None:
            return
        if not app.connection_limiter.acquire(user.id):
            await _send_quiet(
                websocket, {"type": "error", "code": "rate_limited", "message": "Quá nhiều kết nối đồng thời, hãy đóng bớt tab."}
            )
            await _close(websocket, CLOSE_RATE_LIMITED, "Quá nhiều kết nối")
            return
    except DatabaseUnavailableError:
        await _close(websocket, CLOSE_INTERNAL, "Chưa cấu hình database")
        return
    try:
        await _serve(websocket, app, user)
    except WebSocketDisconnect:
        pass
    finally:
        app.connection_limiter.release(user.id)


async def _send_quiet(websocket: WebSocket, frame: dict[str, Any]) -> None:
    try:
        await websocket.send_json(frame)
    except Exception:
        pass


async def _serve(websocket: WebSocket, app: Container, user: User) -> None:
    settings = app.settings
    send_lock = asyncio.Lock()

    async def send(frame: dict[str, Any]) -> None:
        async with send_lock:
            await websocket.send_json(frame)

    await send({"type": "ready"})
    turn: asyncio.Task | None = None
    turn_cancel: asyncio.Event | None = None
    turn_id: str | None = None
    last_activity = time.monotonic()

    while True:
        try:
            frame = await asyncio.wait_for(_read_frame(websocket, settings.assistant_max_frame_bytes), PING_SECONDS)
        except TimeoutError:
            if time.monotonic() - last_activity > IDLE_SECONDS:
                await _close(websocket, CLOSE_IDLE, "Im lặng quá lâu")
                return
            await send({"type": "ping"})
            continue
        except _FrameTooBig:
            await _close(websocket, CLOSE_TOO_BIG, "Khung quá lớn")
            return
        except _BadFrame as error:
            await send({"type": "error", "code": "invalid_frame", "message": str(error)})
            continue
        last_activity = time.monotonic()

        kind = frame["type"]
        if kind == "ping":
            await send({"type": "pong"})
        elif kind == "pong":
            continue
        elif kind == "cancel":
            if turn is not None and not turn.done() and turn_cancel is not None and frame.get("turn_id") == turn_id:
                turn_cancel.set()
        elif kind == "ask":
            error = _validate_ask(frame, settings.assistant_question_max_chars)
            if error is not None:
                await send({"type": "error", "code": "invalid_frame", "message": error, **_turn_ref(frame)})
            elif turn is not None and not turn.done():
                await send(
                    {
                        "type": "error",
                        "code": "busy",
                        "message": "Đang xử lý câu hỏi trước, vui lòng chờ hoặc bấm dừng.",
                        **_turn_ref(frame),
                    }
                )
            else:
                allowed, wait = app.ask_rate_limiter.try_acquire(user.id)
                if not allowed:
                    await send(
                        {
                            "type": "error",
                            "code": "rate_limited",
                            "message": f"Bạn hỏi quá nhanh, vui lòng thử lại sau {wait} giây.",
                            "retry_after": wait,
                            **_turn_ref(frame),
                        }
                    )
                    continue
                turn_id = frame["turn_id"]
                turn_cancel = asyncio.Event()
                conversation_id = frame.get("conversation_id")
                turn = asyncio.create_task(
                    app.assistant_orchestrator.run_turn(
                        user,
                        None if conversation_id is None else str(conversation_id),
                        turn_id,
                        frame["question"],
                        send,
                        turn_cancel,
                        current_page=frame.get("page"),  # ngữ cảnh tùy chọn; orchestrator tự lọc định dạng
                    )
                )
                _background_turns.add(turn)
                turn.add_done_callback(_background_turns.discard)
        else:
            await send({"type": "error", "code": "invalid_frame", "message": f"Loại khung không hỗ trợ: {kind}"})


def _turn_ref(frame: dict[str, Any]) -> dict[str, Any]:
    turn_id = frame.get("turn_id")
    return {"turn_id": turn_id} if isinstance(turn_id, str) else {}


def _validate_ask(frame: dict[str, Any], max_chars: int) -> str | None:
    turn_id, question, conversation_id = frame.get("turn_id"), frame.get("question"), frame.get("conversation_id")
    if not isinstance(turn_id, str) or not _TURN_ID.match(turn_id):
        return "turn_id phải là chuỗi 1-64 ký tự (chữ, số, gạch)"
    if conversation_id is not None and not isinstance(conversation_id, str | int):
        return "conversation_id phải là chuỗi hoặc null"
    if not isinstance(question, str) or not question.strip():
        return "Câu hỏi không được rỗng"
    if len(question) > max_chars:
        return f"Câu hỏi quá dài (tối đa {max_chars} ký tự)"
    return None
