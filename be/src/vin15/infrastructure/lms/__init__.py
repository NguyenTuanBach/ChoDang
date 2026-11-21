"""LMS mini: nơi **duy nhất** được truy cập các bảng ``lms_*``. Phần còn lại của hệ thống đi qua ``LmsPort``."""

from .mini_lms_adapter import MiniLmsAdapter
from .mini_lms_admin import MiniLmsAdmin

__all__ = ["MiniLmsAdapter", "MiniLmsAdmin"]
