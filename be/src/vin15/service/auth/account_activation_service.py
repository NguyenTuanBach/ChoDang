"""Kích hoạt tài khoản ở lần đăng nhập đầu tiên (``invited`` → ``active``). Đăng nhập dev và Google OAuth cùng dùng.

Email chưa được mời (không có tài khoản), đã bị thu hồi hoặc lời mời quá hạn 3 giờ thì không có hiệu lực (D9); mời lại để đặt lại hạn.
"""

from __future__ import annotations

from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import User, UserStatus
from vin15.infrastructure.persistence.user_repository import UserRepository


class AccountActivationService:
    def __init__(self, users: UserRepository):
        self._users = users

    def activate_by_email(self, email: str) -> User:
        user = self._users.find_by_email(email)
        if user is None:
            raise AuthenticationRequiredError("Email này chưa được mời vào hệ thống")
        if user.status == UserStatus.REVOKED:
            raise AuthenticationRequiredError("Lời mời đã bị thu hồi hoặc tài khoản đã bị khóa")
        if user.invitation_expired():
            raise AuthenticationRequiredError("Lời mời đã hết hạn (quá 3 giờ), hãy nhờ người mời gửi lại lời mời")
        if user.status == UserStatus.INVITED:
            user = self._users.set_status(
                user.id,
                UserStatus.ACTIVE,
                AuditEntry(
                    actor_kind=ActorKind.HUMAN,
                    actor_id=user.id,
                    actor_role=user.role.value,
                    entity="account",
                    action="activate",
                    before={"status": "invited"},
                    after={"status": "active"},
                    reason="Đăng nhập lần đầu",
                ),
                only_from=(UserStatus.INVITED, UserStatus.ACTIVE),
            )
        return user
