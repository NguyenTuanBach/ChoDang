"""Đọc lại hội thoại và vết (trace) của trợ lý. Hội thoại chỉ chủ sở hữu đọc được; vết thì chủ sở hữu hoặc quản trị viên."""

from __future__ import annotations

from vin15.domain.exception import ResourceNotFoundError
from vin15.domain.model.chat import ChatMessage, Conversation
from vin15.domain.model.user import Role, User
from vin15.infrastructure.persistence.chat_repository import ChatRepository


class ConversationService:
    def __init__(self, chats: ChatRepository):
        self._chats = chats

    def list_conversations(self, user: User) -> list[Conversation]:
        return self._chats.list_conversations(user.id)

    def get_conversation(self, user: User, conversation_id: int) -> tuple[Conversation, list[ChatMessage]]:
        conversation = self._chats.get_conversation(conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise ResourceNotFoundError("Không tìm thấy hội thoại")  # 404 cả khi của người khác: không lộ sự tồn tại
        return conversation, self._chats.list_messages(conversation_id)

    def get_trace(self, user: User, trace_id: str) -> tuple[ChatMessage, Conversation]:
        found = self._chats.find_message_by_trace_id(trace_id)
        if found is None:
            raise ResourceNotFoundError("Không tìm thấy vết của lượt hỏi")
        message, conversation = found
        if conversation.user_id != user.id and user.role != Role.ADMIN:
            raise ResourceNotFoundError("Không tìm thấy vết của lượt hỏi")
        return message, conversation
