"""Cổng tới LMS (đọc điều kiện tiên quyết). Bản thật nối LMS của trường; bản giả trả dữ liệu cố định để dev/test."""

from __future__ import annotations

from typing import Protocol


class LmsPort(Protocol):
    def prerequisites_met(self, user_id: int) -> bool:
        """Sinh viên đã đủ điều kiện tiên quyết học phần thực tập (T6) chưa."""
        ...


class FakeLmsAdapter:
    """Dữ liệu cố định, không gọi mạng: luôn đủ điều kiện tiên quyết. Thay bằng adapter LMS thật khi có."""

    def prerequisites_met(self, user_id: int) -> bool:
        return True
