"""Hội thoại của trợ lý hỏi đáp."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Conversation:
    id: int
    user_id: int
    title: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ChatMessage:
    id: int
    conversation_id: int
    turn_id: str
    role: str
    content: str
    created_at: datetime
    citations: list[dict] = field(default_factory=list)
    trace: dict = field(default_factory=dict)
    degraded: bool = False
