class PermissionDeniedError(Exception):
    """Đã đăng nhập nhưng sai vai trò hoặc sai phạm vi dữ liệu. API trả 403."""
