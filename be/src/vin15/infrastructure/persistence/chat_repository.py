"""Hội thoại và tin nhắn của trợ lý hỏi đáp (``chat_conversation``, ``chat_message``)."""

from __future__ import annotations

from psycopg.types.json import Jsonb

from vin15.domain.model.chat import ChatMessage, Conversation

from .database import Database


def _conversation(row: dict) -> Conversation:
    return Conversation(row["id"], row["user_id"], row["title"], row["created_at"], row["updated_at"])


def _message(row: dict) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        conversation_id=row["conversation_id"],
        turn_id=row["turn_id"],
        role=row["role"],
        content=row["content"],
        created_at=row["created_at"],
        citations=row["citations"] or [],
        trace=row["trace"] or {},
        degraded=row["degraded"],
    )


class ChatRepository:
    def __init__(self, database: Database):
        self._db = database

    def create_conversation(self, user_id: int, title: str | None) -> Conversation:
        with self._db.connection() as conn:
            row = conn.execute("insert into chat_conversation (user_id, title) values (%s, %s) returning *", (user_id, title)).fetchone()
        return _conversation(row)

    def get_conversation(self, conversation_id: int) -> Conversation | None:
        with self._db.connection() as conn:
            row = conn.execute("select * from chat_conversation where id = %s", (conversation_id,)).fetchone()
        return _conversation(row) if row else None

    def list_conversations(self, user_id: int, limit: int = 100) -> list[Conversation]:
        with self._db.connection() as conn:
            rows = conn.execute(
                "select * from chat_conversation where user_id = %s order by updated_at desc, id desc limit %s", (user_id, limit)
            ).fetchall()
        return [_conversation(r) for r in rows]

    def list_messages(self, conversation_id: int) -> list[ChatMessage]:
        with self._db.connection() as conn:
            rows = conn.execute("select * from chat_message where conversation_id = %s order by id", (conversation_id,)).fetchall()
        return [_message(r) for r in rows]

    def recent_messages(self, conversation_id: int, limit: int) -> list[ChatMessage]:
        """``limit`` tin gần nhất, trả theo thứ tự thời gian tăng dần."""
        with self._db.connection() as conn:
            rows = conn.execute(
                "select * from (select * from chat_message where conversation_id = %s order by id desc limit %s) m order by id",
                (conversation_id, limit),
            ).fetchall()
        return [_message(r) for r in rows]

    def turn_exists(self, conversation_id: int, turn_id: str) -> bool:
        with self._db.connection() as conn:
            row = conn.execute(
                "select 1 from chat_message where conversation_id = %s and turn_id = %s limit 1", (conversation_id, turn_id)
            ).fetchone()
        return row is not None

    def add_message(
        self,
        conversation_id: int,
        turn_id: str,
        role: str,
        content: str,
        *,
        citations: list[dict] | None = None,
        trace: dict | None = None,
        degraded: bool = False,
    ) -> ChatMessage:
        with self._db.connection() as conn:
            row = conn.execute(
                "insert into chat_message (conversation_id, turn_id, role, content, citations, trace, degraded) "
                "values (%s, %s, %s, %s, %s, %s, %s) returning *",
                (conversation_id, turn_id, role, content, Jsonb(citations or []), Jsonb(trace or {}), degraded),
            ).fetchone()
            conn.execute("update chat_conversation set updated_at = now() where id = %s", (conversation_id,))
        return _message(row)

    def find_message_by_trace_id(self, trace_id: str) -> tuple[ChatMessage, Conversation] | None:
        with self._db.connection() as conn:
            row = conn.execute(
                "select * from chat_message where trace ->> 'trace_id' = %s order by id desc limit 1", (trace_id,)
            ).fetchone()
            if row is None:
                return None
            conv = conn.execute("select * from chat_conversation where id = %s", (row["conversation_id"],)).fetchone()
        return _message(row), _conversation(conv)
