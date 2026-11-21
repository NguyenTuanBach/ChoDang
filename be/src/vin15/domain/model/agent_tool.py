"""Chủ thể của một lời gọi tool agent: do BE quyết, agent và LLM không truyền được."""

from __future__ import annotations

from dataclasses import dataclass

#: Giá trị ``AgentToolSubject.via``.
VIA_AGENT_TOKEN = "agent-token"
VIA_DEV_DEFAULT = "dev-default-user"


@dataclass(frozen=True)
class AgentToolSubject:
    user_id: int
    role: str
    via: str
    conversation_id: str = ""
    turn_id: str = ""

    @property
    def audit_reason(self) -> str:
        """Lý do ghi vào audit: nguồn chủ thể + hội thoại/lượt (nếu có)."""
        parts = [self.via] if self.via == VIA_DEV_DEFAULT else []
        if self.conversation_id or self.turn_id:
            parts.append(f"conv={self.conversation_id} turn={self.turn_id}")
        return "; ".join(parts)
