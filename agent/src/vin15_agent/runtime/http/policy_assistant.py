"""Endpoint của trợ lý chính sách: ``WS /v1/policy-assistant/ws`` và ``POST /v1/embeddings`` (BE nạp chunk).

WebSocket (xem ``.kiro/specs/agent-hoi-dap/contract.md`` mục 3): bắt tay kiểm service token (sai → đóng 4401); khung đầu phải là
``start``; sau đó chỉ nhận ``cancel``/``ping``. Một lượt mỗi kết nối: agent phát ``final`` hoặc ``error`` rồi đóng 1000.
Khung quá ``MAX_FRAME_BYTES`` → 1009; JSON/``type`` sai → 1003. ``cancel`` hoặc đóng kết nối hủy lượt đang chạy (TaskGroup).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

import httpx
from fastapi import Depends, FastAPI, WebSocket
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator

from vin15_agent.core.ai_client import AiClient, LlmUnavailableError
from vin15_agent.policy_assistant.agent import PolicyAssistant
from vin15_agent.policy_assistant.be_client import BeToolsClient
from vin15_agent.policy_assistant.protocol import (
    CLOSE_OK,
    CLOSE_TIMEOUT,
    CLOSE_TOO_BIG,
    CLOSE_UNAUTHORIZED,
    CLOSE_UNSUPPORTED,
    MAX_FRAME_BYTES,
    CancelFrame,
    ErrorFrame,
    OutboundFrame,
    PingFrame,
    PongFrame,
    ReadyFrame,
    StartFrame,
    inbound_adapter,
)
from vin15_agent.runtime.http.security import service_token_matches
from vin15_agent.shared.settings import Settings

logger = logging.getLogger(__name__)

WS_PATH = "/v1/policy-assistant/ws"
#: Thời gian tối đa chờ khung ``start`` sau khi bắt tay.
START_TIMEOUT_SECONDS = 10.0
MAX_EMBED_TEXTS = 256
MAX_EMBED_TEXT_CHARS = 8000


class _Disconnected(Exception):
    pass


class _BadFrame(Exception):
    pass


class _TooBig(Exception):
    pass


class EmbeddingsRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=MAX_EMBED_TEXTS)

    @field_validator("texts")
    @classmethod
    def _limit_length(cls, texts: list[str]) -> list[str]:
        if any(len(t) > MAX_EMBED_TEXT_CHARS for t in texts):
            raise ValueError(f"mỗi văn bản tối đa {MAX_EMBED_TEXT_CHARS} ký tự")
        return texts


async def _recv_text(websocket: WebSocket) -> str:
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise _Disconnected
    text = message.get("text")
    if text is None:
        raise _BadFrame("khung nhị phân không được hỗ trợ")
    if len(text.encode("utf-8")) > MAX_FRAME_BYTES:
        raise _TooBig
    return text


async def _close(websocket: WebSocket, code: int, reason: str = "") -> None:
    with contextlib.suppress(Exception):
        await websocket.close(code=code, reason=reason)


def register_policy_assistant(
    app: FastAPI,
    *,
    settings: Settings,
    ai: AiClient,
    require_service_token,
    be_transport: httpx.AsyncBaseTransport | None = None,
) -> PolicyAssistant:
    def make_be(agent_token: str) -> BeToolsClient:
        return BeToolsClient(
            settings.be_api_url,
            settings.agent_api_service_token,
            agent_token,
            timeout=settings.agent_tool_timeout_seconds,
            transport=be_transport,
        )

    assistant = PolicyAssistant(ai, make_be, settings)
    active_turns = 0

    @app.post("/v1/embeddings", dependencies=[Depends(require_service_token)])
    async def embeddings(body: EmbeddingsRequest):
        try:
            vectors = await ai.embed(body.texts)
        except LlmUnavailableError as exc:
            logger.warning("Embedding không khả dụng: %s", exc)
            return JSONResponse(status_code=503, content={"error": {"code": "llm_unavailable", "message": "Dịch vụ AI tạm không khả dụng"}})
        except Exception as exc:  # lỗi khóa/yêu cầu: không che thành "tạm không khả dụng"
            logger.error("Embedding lỗi: %s", type(exc).__name__)
            return JSONResponse(status_code=500, content={"error": {"code": "internal", "message": "Không tạo được embedding"}})
        return {"model": ai.embedding_model, "dimensions": len(vectors[0]) if vectors else 0, "vectors": vectors}

    async def serve_turn(websocket: WebSocket, start: StartFrame) -> int:
        """Chạy lượt song song với việc nghe ``cancel``/``ping``; trả mã đóng (hoặc ``-1`` nếu client đã rớt)."""
        state = {"code": CLOSE_OK, "cancelled": False, "disconnected": False}

        async def emit(frame: OutboundFrame) -> None:
            await websocket.send_text(frame.model_dump_json())

        tasks: dict[str, asyncio.Task[None]] = {}

        async def run_turn() -> None:
            try:
                await assistant.run(start, emit)
            except Exception as exc:
                logger.error("Lượt hỏi gặp lỗi không xử lý được: %s", type(exc).__name__)
                with contextlib.suppress(Exception):
                    await emit(ErrorFrame(code="internal", message="Trợ lý gặp sự cố, vui lòng thử lại sau."))
            finally:
                tasks["watch"].cancel()  # lượt xong (hoặc bị hủy): thôi nghe khung từ BE

        async def watch() -> None:
            try:
                while True:
                    try:
                        frame = inbound_adapter.validate_json(await _recv_text(websocket))
                    except _Disconnected:
                        state["disconnected"] = True
                        return
                    except _TooBig:
                        state["code"] = CLOSE_TOO_BIG
                        return
                    except (_BadFrame, ValidationError):
                        state["code"] = CLOSE_UNSUPPORTED
                        return
                    if isinstance(frame, PingFrame):
                        try:
                            await emit(PongFrame())
                        except Exception:  # client đã rớt
                            state["disconnected"] = True
                            return
                    elif isinstance(frame, CancelFrame):
                        state["cancelled"] = True
                        return
                    else:  # ``start`` lần hai
                        state["code"] = CLOSE_UNSUPPORTED
                        return
            finally:
                tasks["turn"].cancel()  # cancel/rớt kết nối/khung lỗi: hủy lượt đang chạy (no-op nếu lượt đã xong)

        # Hai task trong một TaskGroup: task nào xong trước thì hủy task kia; hủy tràn xuống mọi await (LLM, tool).
        async with asyncio.TaskGroup() as group:
            tasks["turn"] = group.create_task(run_turn())
            tasks["watch"] = group.create_task(watch())
        if state["disconnected"]:
            return -1
        if state["cancelled"]:
            with contextlib.suppress(Exception):
                await emit(ErrorFrame(code="cancelled", message="Đã dừng theo yêu cầu."))
        return state["code"]

    @app.websocket(WS_PATH)
    async def policy_assistant_ws(websocket: WebSocket) -> None:
        nonlocal active_turns
        await websocket.accept()
        if not service_token_matches(settings, websocket.headers.get("authorization", "")):
            await _close(websocket, CLOSE_UNAUTHORIZED, "Sai hoặc thiếu service token")
            return
        try:
            raw = await asyncio.wait_for(_recv_text(websocket), START_TIMEOUT_SECONDS)
            first = inbound_adapter.validate_json(raw)
            if not isinstance(first, StartFrame):
                raise _BadFrame("khung đầu tiên phải là start")
        except _Disconnected:
            return
        except _TooBig:
            await _close(websocket, CLOSE_TOO_BIG, "Khung quá lớn")
            return
        except TimeoutError:
            await _close(websocket, CLOSE_TIMEOUT, "Không nhận được khung start")
            return
        except (_BadFrame, ValidationError):
            await _close(websocket, CLOSE_UNSUPPORTED, "Khung không hợp lệ")
            return

        if active_turns >= settings.assistant_max_concurrent_turns:
            await websocket.send_text(ErrorFrame(code="busy", message="Hệ thống đang bận, vui lòng thử lại sau.").model_dump_json())
            await _close(websocket, CLOSE_OK)
            return
        active_turns += 1
        try:
            await websocket.send_text(ReadyFrame().model_dump_json())
            code = await serve_turn(websocket, first)
        except Exception as exc:  # gửi ``ready`` thất bại: client đã rớt
            logger.info("Kết nối đóng trước khi chạy lượt: %s", type(exc).__name__)
            return
        finally:
            active_turns -= 1
        if code != -1:
            await _close(websocket, code)

    return assistant


