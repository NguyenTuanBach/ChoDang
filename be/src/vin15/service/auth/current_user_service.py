"""Người dùng hiện tại của một request thường (không phải tool agent).

Token phiên (HS256, không có ``scope``) -> người dùng. Chưa có đăng nhập thật nên ở dev, không có token thì dùng người dùng mặc định
``AGENT_DEV_DEFAULT_USER_EMAIL`` (production không bao giờ). Agent-token không dùng được ở đây (decode kiểm scope).
"""

from __future__ import annotations

from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.model.user import User, UserStatus
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.infrastructure.security.actor_token import ActorTokenService


class CurrentUserService:
    def __init__(self, tokens: ActorTokenService, users: UserRepository, dev_default_email: str):
        self._tokens = tokens
        self._users = users
        self._dev_email = dev_default_email

    def resolve(self, authorization: str | None) -> User:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            claims = self._tokens.decode(token.strip())
            user = self._users.find_by_id(int(claims["sub"]))
        elif self._dev_email:
            user = self._users.find_by_email(self._dev_email)
        else:
            raise AuthenticationRequiredError("Cần đăng nhập")
        if user is None or user.status == UserStatus.REVOKED:
            raise AuthenticationRequiredError("Tài khoản không tồn tại hoặc đã bị khóa")
        return user
