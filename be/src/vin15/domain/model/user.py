from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    STUDENT = "student"
    LECTURER = "lecturer"
    ADMIN = "admin"


class UserStatus(StrEnum):
    #: Đã được mời nhưng chưa đăng nhập lần đầu.
    INVITED = "invited"
    ACTIVE = "active"
    #: Lời mời bị thu hồi hoặc tài khoản bị khóa: đăng nhập không còn hiệu lực.
    REVOKED = "revoked"


@dataclass(frozen=True)
class User:
    id: int
    email: str
    full_name: str
    role: Role
    status: UserStatus
    invited_by: int | None = None
    #: Mã sinh viên: khóa ánh xạ sang LMS (chỉ sinh viên).
    student_code: str | None = None
    #: Giảng viên phụ trách (chỉ sinh viên).
    advisor_id: int | None = None
