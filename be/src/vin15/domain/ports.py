"""Cổng ra ngoài mà tầng service dùng; adapter nằm ở ``infrastructure`` (R2/đĩa cục bộ, SMTP/log)."""

from __future__ import annotations

from typing import Protocol


class FileStorage(Protocol):
    """Lưu tệp riêng tư theo khóa; không có URL công khai, mọi lần tải đi qua endpoint kiểm quyền."""

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None:
        """Gửi một email văn bản thuần. Lỗi thì ném ngoại lệ để hộp thư đi (outbox) thử lại."""
        ...
