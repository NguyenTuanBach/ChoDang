from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

log = logging.getLogger(__name__)


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str, timeout: float = 15.0):
        self._host, self._port, self._user, self._password = host, port, user, password
        self._sender = sender or user
        self._timeout = timeout

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self._user, self._password)
            smtp.send_message(message)


class LogMailer:
    """Không gửi thật: chỉ ghi log (dev, test, hoặc khi chưa cấu hình SMTP). Không ghi nội dung thư ra log."""

    def send(self, to: str, subject: str, body: str) -> None:
        log.info("[email giả] tới=%s chủ đề=%s (%d ký tự)", to, subject, len(body))
