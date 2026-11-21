"""Đăng nhập Google OAuth, chỉ nhận email đã được mời; cấu hình ``GOOGLE_*`` trong settings."""

from .google_oauth import GoogleOAuthClient

__all__ = ["GoogleOAuthClient"]
