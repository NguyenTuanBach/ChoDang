"""Người dùng hiện tại của một request thường (không phải tool agent).

Token phiên (HS256, không có ``scope``) -> người dùng. Token lấy từ header ``Authorization: Bearer`` hoặc cookie phiên
(do ``/api/auth/*`` đặt). Không có token thì 401. Agent-token không dùng được ở đây (decode kiểm scope).
"""

from __future__ import annotations

from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.model.user import User, UserStatus
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.infrastructure.security.actor_token import ActorTokenService


def bearer_token(authorization: str | None) -> str:
    scheme, _, token = (authorization or "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


class CurrentUserService:
    def __init__(self, tokens: ActorTokenService, users: UserRepository):
        self._tokens = tokens
        self._users = users

    def resolve(self, authorization: str | None, session_cookie: str | None = None) -> User:
        token = bearer_token(authorization) or (session_cookie or "").strip()
        if not token:
            raise AuthenticationRequiredError("Cần đăng nhập")
        claims = self._tokens.decode(token)
        user = self._users.find_by_id(int(claims["sub"]))
        if user is None or user.status == UserStatus.REVOKED:
            raise AuthenticationRequiredError("Tài khoản không tồn tại hoặc đã bị khóa")
        return user
