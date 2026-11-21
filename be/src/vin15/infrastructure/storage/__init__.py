"""Lưu tệp minh chứng: Cloudflare R2 (S3) khi cấu hình đủ ``R2_*``, ngược lại thư mục cục bộ riêng tư."""

from .local_storage import LocalFileStorage
from .r2_storage import R2FileStorage

__all__ = ["LocalFileStorage", "R2FileStorage"]
