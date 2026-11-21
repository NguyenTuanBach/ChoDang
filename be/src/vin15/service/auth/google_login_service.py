"""Đăng nhập Google (D9): chỉ email đã được mời và chưa bị thu hồi. Dùng chung ``AccountActivationService`` với đăng nhập dev."""

from __future__ import annotations

import secrets

from vin15.domain.exception import ResourceNotFoundError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import User
from vin15.infrastructure.oauth import GoogleOAuthClient
from vin15.infrastructure.persistence.audit_repository import AuditRepository
from vin15.infrastructure.security.actor_token import ActorTokenService
from vin15.service.auth.account_activation_service import AccountActivationService


class GoogleLoginService:
    def __init__(self, google: GoogleOAuthClient, activation: AccountActivationService, tokens: ActorTokenService, audit: AuditRepository):
        self._google = google
        self._activation = activation
        self._tokens = tokens
        self._audit = audit

    @property
    def enabled(self) -> bool:
        return self._google.enabled

    def start(self) -> tuple[str, str]:
        """Trả ``(url chuyển hướng tới Google, state)``; ``state`` được đặt vào cookie để đối chiếu ở callback."""
        if not self._google.enabled:
            raise ResourceNotFoundError("Đăng nhập Google chưa được cấu hình")
        state = secrets.token_urlsafe(24)
        return self._google.authorization_url(state), state

    async def finish(self, code: str) -> tuple[User, str]:
        email, _name = await self._google.profile_for_code(code)
        user = self._activation.activate_by_email(email)
        self._audit.record(
            AuditEntry(
                actor_kind=ActorKind.HUMAN,
                actor_id=user.id,
                actor_role=user.role.value,
                entity="session",
                entity_id=user.id,
                action="google_login",
                reason="Đăng nhập Google",
            )
        )
        return user, self._tokens.create(user.id, user.role.value)
