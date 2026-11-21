"""Đăng nhập dev: vào một tài khoản mẫu (``@example.test``) không cần Google. Chỉ được nối vào app khi không phải production.

Phát cùng loại token phiên như đăng nhập thật sẽ phát, nên phần còn lại của hệ thống không phân biệt. Tài khoản đang ở trạng thái
``invited`` được kích hoạt ở lần đăng nhập đầu (cùng luồng với đăng nhập thật); ``revoked`` bị từ chối.
"""

from __future__ import annotations

from vin15.domain.exception import AuthenticationRequiredError, PermissionDeniedError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import User, UserStatus
from vin15.infrastructure.persistence.audit_repository import AuditRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.infrastructure.security.actor_token import ActorTokenService
from vin15.service.auth.account_activation_service import AccountActivationService

DEV_EMAIL_SUFFIX = "@example.test"


class DevLoginService:
    def __init__(self, users: UserRepository, tokens: ActorTokenService, audit: AuditRepository, activation: AccountActivationService | None = None):
        self._users = users
        self._tokens = tokens
        self._audit = audit
        self._activation = activation or AccountActivationService(users)

    def list_accounts(self) -> list[User]:
        return [u for u in self._users.list_by_email_suffix(DEV_EMAIL_SUFFIX) if u.status != UserStatus.REVOKED]

    def login(self, email: str) -> tuple[User, str]:
        email = email.strip().lower()
        if not email.endswith(DEV_EMAIL_SUFFIX):
            raise PermissionDeniedError("Đăng nhập dev chỉ dành cho tài khoản mẫu")
        user = self._users.find_by_email(email)
        if user is None:
            raise AuthenticationRequiredError("Tài khoản mẫu không tồn tại (chạy make seed-dev hoặc mời email này trước)")
        user = self._activation.activate_by_email(email)
        self._audit.record(
            AuditEntry(
                actor_kind=ActorKind.HUMAN,
                actor_id=user.id,
                actor_role=user.role.value,
                entity="session",
                entity_id=user.id,
                action="dev_login",
                reason="Đăng nhập dev",
            )
        )
        return user, self._tokens.create(user.id, user.role.value)
