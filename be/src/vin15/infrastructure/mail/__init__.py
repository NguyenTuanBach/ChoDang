"""Gửi email: Gmail SMTP khi có ``SMTP_USER``/``SMTP_PASSWORD``, ngược lại chỉ ghi log (dev)."""

from .smtp_mailer import LogMailer, SmtpMailer

__all__ = ["LogMailer", "SmtpMailer"]
