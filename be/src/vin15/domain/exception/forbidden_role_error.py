from .permission_denied_error import PermissionDeniedError


class ForbiddenRoleError(PermissionDeniedError):
    """Vai trò của chủ thể không được dùng chức năng này (ví dụ giảng viên gọi tool cá nhân của sinh viên). API trả 403."""
