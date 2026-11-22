from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

#: Lời mời có hiệu lực trong khoảng này kể từ lúc mời (hoặc mời lại); quá hạn thì không đăng nhập được, phải mời lại.
INVITATION_TTL = timedelta(hours=3)


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
    #: Thời điểm mời (hoặc mời lại) gần nhất; tính hạn lời mời.
    invited_at: datetime | None = None

    def invitation_expired(self, now: datetime | None = None) -> bool:
        """Lời mời còn ở trạng thái ``invited`` nhưng đã quá ``INVITATION_TTL``."""
        if self.status != UserStatus.INVITED or self.invited_at is None:
            return False
        return (now or datetime.now(UTC)) - self.invited_at > INVITATION_TTL
