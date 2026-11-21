from .permission_denied_error import PermissionDeniedError


class ScopeDeniedError(PermissionDeniedError):
    """Đúng vai trò nhưng sai phạm vi dữ liệu (ví dụ giảng viên xem hồ sơ của sinh viên mình không phụ trách). API trả 403."""
