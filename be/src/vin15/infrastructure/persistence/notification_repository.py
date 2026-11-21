"""Thông báo trong ứng dụng (``notification``), hộp thư email đi (``email_outbox``) và trạng thái job theo ngày (``job_state``)."""

from __future__ import annotations

from datetime import date

from psycopg import Connection

from .database import Database


def insert_notification(conn: Connection, user_id: int, kind: str, title: str, body: str = "", link: str = "") -> int:
    return conn.execute(
        "insert into notification (user_id, kind, title, body, link) values (%s, %s, %s, %s, %s) returning id",
        (user_id, kind, title, body, link),
    ).fetchone()["id"]


def insert_email(conn: Connection, to_email: str, subject: str, body: str) -> int:
    return conn.execute(
        "insert into email_outbox (to_email, subject, body) values (%s, %s, %s) returning id", (to_email, subject, body)
    ).fetchone()["id"]


class NotificationRepository:
    def __init__(self, database: Database):
        self._db = database

    def add(self, user_id: int, kind: str, title: str, body: str = "", link: str = "", *, email: bool = False) -> int:
        """Thêm thông báo trong ứng dụng; ``email=True`` thì xếp thêm một email tới địa chỉ của người nhận."""
        with self._db.connection() as conn:
            note_id = insert_notification(conn, user_id, kind, title, body, link)
            if email:
                row = conn.execute("select email from app_user where id = %s", (user_id,)).fetchone()
                if row:
                    insert_email(conn, row["email"], title, body or title)
        return note_id

    def enqueue_email(self, to_email: str, subject: str, body: str) -> int:
        with self._db.connection() as conn:
            return insert_email(conn, to_email, subject, body)

    def list_for(self, user_id: int, limit: int = 50) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, kind, title, body, link, created_at, read_at from notification "
                "where user_id = %s order by created_at desc, id desc limit %s",
                (user_id, limit),
            ).fetchall()

    def unread_count(self, user_id: int) -> int:
        with self._db.connection() as conn:
            return conn.execute("select count(*) as n from notification where user_id = %s and read_at is null", (user_id,)).fetchone()["n"]

    def mark_read(self, user_id: int, notification_id: int | None) -> None:
        with self._db.connection() as conn:
            if notification_id is None:
                conn.execute("update notification set read_at = now() where user_id = %s and read_at is null", (user_id,))
            else:
                conn.execute(
                    "update notification set read_at = now() where user_id = %s and id = %s and read_at is null", (user_id, notification_id)
                )

    # ---- Hộp thư email ----
    def claim_pending_emails(self, limit: int = 20) -> list[dict]:
        with self._db.connection() as conn:
            return conn.execute(
                "select id, to_email, subject, body, attempts from email_outbox where status = 'pending' and attempts < 5 "
                "order by id limit %s for update skip locked",
                (limit,),
            ).fetchall()

    def mark_email(self, email_id: int, sent: bool, error: str = "") -> None:
        with self._db.connection() as conn:
            if sent:
                conn.execute("update email_outbox set status = 'sent', sent_at = now(), attempts = attempts + 1 where id = %s", (email_id,))
            else:
                conn.execute(
                    "update email_outbox set attempts = attempts + 1, last_error = %s, "
                    "status = case when attempts + 1 >= 5 then 'failed' else 'pending' end where id = %s",
                    (error[:500], email_id),
                )

    # ---- Job theo ngày ----
    def last_run_on(self, name: str) -> date | None:
        with self._db.connection() as conn:
            row = conn.execute("select last_run_on from job_state where name = %s", (name,)).fetchone()
        return row["last_run_on"] if row else None

    def set_run_on(self, name: str, day: date, detail: str = "") -> None:
        with self._db.connection() as conn:
            conn.execute(
                "insert into job_state (name, last_run_on, detail) values (%s, %s, %s) "
                "on conflict (name) do update set last_run_on = excluded.last_run_on, detail = excluded.detail",
                (name, day, detail),
            )
