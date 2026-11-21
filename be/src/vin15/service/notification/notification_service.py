"""Thông báo trong ứng dụng + email (qua hộp thư đi, có thử lại). Email tổng hợp hằng ngày cho giảng viên (D15)."""

from __future__ import annotations

import logging

from vin15.domain.clock import Clock
from vin15.domain.ports import Mailer
from vin15.infrastructure.persistence.notification_repository import NotificationRepository

log = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, repository: NotificationRepository, mailer: Mailer, base_url: str, clock: Clock):
        self._repo = repository
        self._mailer = mailer
        self._base_url = base_url.rstrip("/")
        self._clock = clock

    def link(self, path: str) -> str:
        return f"{self._base_url}{path}"

    def notify(self, user_id: int, title: str, body: str = "", *, kind: str = "info", link: str = "", email: bool = False) -> None:
        """Gửi một thông báo. Không để lỗi thông báo làm hỏng nghiệp vụ chính."""
        try:
            self._repo.add(user_id, kind, title, body, link, email=email)
        except Exception:
            log.warning("Không ghi được thông báo cho người dùng %s", user_id, exc_info=True)

    def notify_many(self, user_ids: list[int], title: str, body: str = "", **kwargs) -> None:
        for user_id in dict.fromkeys(user_ids):
            self.notify(user_id, title, body, **kwargs)

    def send_email(self, to_email: str, subject: str, body: str) -> None:
        try:
            self._repo.enqueue_email(to_email, subject, body)
        except Exception:
            log.warning("Không xếp được email tới %s", to_email, exc_info=True)

    def list_for(self, user_id: int) -> list[dict]:
        return self._repo.list_for(user_id)

    def unread_count(self, user_id: int) -> int:
        return self._repo.unread_count(user_id)

    def mark_read(self, user_id: int, notification_id: int | None) -> None:
        self._repo.mark_read(user_id, notification_id)

    def flush_outbox(self) -> int:
        """Gửi các email đang chờ; trả về số email gửi được. Lỗi thì tăng số lần thử (tối đa 5)."""
        sent = 0
        for item in self._repo.claim_pending_emails():
            try:
                self._mailer.send(item["to_email"], item["subject"], item["body"])
            except Exception as error:
                self._repo.mark_email(item["id"], False, f"{type(error).__name__}: {error}")
            else:
                self._repo.mark_email(item["id"], True)
                sent += 1
        return sent
