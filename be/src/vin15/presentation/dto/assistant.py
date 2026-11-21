"""Phản hồi REST của trợ lý hỏi đáp. Mã số đi ra ngoài dạng chuỗi (khớp ``fe/src/lib/assistant-protocol.ts``)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from vin15.domain.model.chat import ChatMessage, Conversation


class WsTicketResponse(BaseModel):
    ticket: str
    expires_in: int


class ConversationSummaryDto(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, conversation: Conversation) -> ConversationSummaryDto:
        return cls(
            id=str(conversation.id), title=conversation.title, created_at=conversation.created_at, updated_at=conversation.updated_at
        )


class StoredMessageDto(BaseModel):
    id: str
    turn_id: str
    role: str
    content: str
    citations: list[dict]
    degraded: bool
    created_at: datetime

    @classmethod
    def of(cls, message: ChatMessage) -> StoredMessageDto:
        return cls(
            id=str(message.id),
            turn_id=message.turn_id,
            role=message.role,
            content=message.content,
            citations=message.citations,
            degraded=message.degraded,
            created_at=message.created_at,
        )


class ConversationDetailDto(BaseModel):
    id: str
    title: str | None
    messages: list[StoredMessageDto]


class TraceDto(BaseModel):
    trace_id: str
    conversation_id: str
    turn_id: str
    message_id: str
    trace: dict
