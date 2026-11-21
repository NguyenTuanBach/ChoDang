"""Ngày nghiệp vụ theo múi giờ cấu hình (mặc định ``Asia/Ho_Chi_Minh``). Hiệu lực quy định và hạn mốc tính theo ngày này."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

#: Hàm trả "hôm nay" theo múi giờ nghiệp vụ; test thay bằng giá trị cố định.
Clock = Callable[[], date]


def business_clock(timezone: str = "Asia/Ho_Chi_Minh") -> Clock:
    zone = ZoneInfo(timezone)
    return lambda: datetime.now(zone).date()
