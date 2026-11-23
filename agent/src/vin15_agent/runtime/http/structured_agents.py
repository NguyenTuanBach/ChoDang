"""Endpoint các agent một-lượt có đầu ra cấu trúc: chuẩn hóa hồ sơ, giám sát (đánh giá nội dung), tiền thẩm, gợi ý lịch nhật ký. Tất cả cần service token.

Các agent này **không có công cụ ghi** và không gọi ngược BE: BE gửi dữ liệu đã che PII, nhận kết luận có cấu trúc rồi tự kiểm và ghi.
"""

from __future__ import annotations

import base64
import binascii
import logging
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from vin15_agent.core.ai_client import AiClient, LlmUnavailableError
from vin15_agent.core.prompts import PromptLoader
from vin15_agent.core.structured import StructuredOutputError
from vin15_agent.intake import IntakeExtractor
from vin15_agent.journal_advice import JournalAdvisor
from vin15_agent.monitor import MonitorReviewer
from vin15_agent.outline_review import OutlineReviewer
from vin15_agent.pre_review import PreReviewer
from vin15_agent.shared.settings import Settings

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 12 * 1024 * 1024


class IntakeRequest(BaseModel):
    filename: str = Field(max_length=200)
    mime: str = Field(max_length=100)
    content_b64: str
    fields: list[str] = Field(default_factory=list, max_length=30)
    kind: Literal["receipt_letter", "completion_letter", "auto"] = "receipt_letter"


def register_structured_agents(app: FastAPI, *, settings: Settings, ai: AiClient, require_service_token, prompts: PromptLoader | None = None) -> None:
    loader = prompts or PromptLoader(settings.agent_prompts_dir or None)
    intake = IntakeExtractor(ai, loader, settings)
    monitor = MonitorReviewer(ai, loader)
    pre_review = PreReviewer(ai, loader)
    journal_advice = JournalAdvisor(ai, loader)
    outline_review = OutlineReviewer(ai, loader)

    async def guarded(coro) -> dict[str, Any]:
        try:
            return await coro
        except LlmUnavailableError as exc:
            raise HTTPException(status_code=503, detail="LLM không khả dụng") from exc
        except StructuredOutputError as exc:
            raise HTTPException(status_code=502, detail="AI không trả kết quả hợp lệ") from exc

    @app.post("/v1/intake/extract", dependencies=[Depends(require_service_token)])
    async def intake_extract(body: IntakeRequest) -> dict:
        try:
            data = base64.b64decode(body.content_b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=422, detail="content_b64 không hợp lệ") from exc
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="Tệp quá lớn")
        return await guarded(intake.extract(body.mime, data, body.fields, body.kind))

    @app.post("/v1/monitor/review", dependencies=[Depends(require_service_token)])
    async def monitor_review(body: dict[str, Any]) -> dict:
        return await guarded(monitor.review(body))

    @app.post("/v1/outline/review", dependencies=[Depends(require_service_token)])
    async def outline_review_endpoint(body: dict[str, Any]) -> dict:
        return await guarded(outline_review.review(body))

    @app.post("/v1/journal/advice", dependencies=[Depends(require_service_token)])
    async def journal_advice_endpoint(body: dict[str, Any]) -> dict:
        return await guarded(journal_advice.advise(body))

    @app.post("/v1/pre-review", dependencies=[Depends(require_service_token)])
    async def pre_review_endpoint(body: dict[str, Any]) -> dict:
        return await guarded(pre_review.review(body))
