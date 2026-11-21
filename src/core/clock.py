"""Giờ nghiệp vụ theo múi giờ của trường (OQ-9).

Máy chủ/container chạy UTC: `date.today()` lệch 1 ngày từ 0h–7h sáng giờ VN, job "07:00" thành 14:00.
Mọi chỗ cần "hôm nay" hay giờ chạy job dùng module này. Timestamp trong DB vẫn là UTC naive
(`orm.utcnow`) — chỉ quy đổi khi so với một mốc ngày nghiệp vụ (`local_midnight_utc`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from functools import lru_cache
from zoneinfo import ZoneInfo

from src.config import get_settings


@lru_cache
def _zone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def tz() -> ZoneInfo:
    return _zone(get_settings().app_timezone)


def now() -> datetime:
    """Giờ hiện tại (có tzinfo) theo múi giờ của trường."""
    return datetime.now(tz())


def today() -> date:
    return now().date()


def local_midnight_utc(day: date) -> datetime:
    """00:00 ngày `day` theo giờ trường, đổi sang UTC naive để so với cột DateTime trong DB."""
    return datetime.combine(day, time.min, tz()).astimezone(UTC).replace(tzinfo=None)
