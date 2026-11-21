"""Xác định **chủ thể** của một lời gọi tool ``/api/agent-tools/*``. Do BE quyết, agent/LLM không truyền được.

Thứ tự:
1. Service token sai/thiếu -> 401.
2. Có ``X-On-Behalf-Of`` -> giải mã agent-token (``scope=agent_tools``, còn hạn); chủ thể = ``sub``; role lấy từ DB.
3. Không có, ``APP_ENV != production`` và đặt ``AGENT_DEV_DEFAULT_USER_EMAIL`` -> người dùng đó (audit ``dev-default-user``).
4. Còn lại -> 401.
"""

from __future__ import annotations

import hmac

from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.model.agent_tool import VIA_AGENT_TOKEN, VIA_DEV_DEFAULT, AgentToolSubject
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import UserStatus
from vin15.infrastructure.persistence.audit_repository import AuditRepository
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.infrastructure.security.actor_token import ActorTokenService

AGENT_TOOLS_SCOPE = "agent_tools"
#: Thời sống của agent-token cho một lượt hỏi.
AGENT_TOKEN_TTL_MINUTES = 5


class AgentSubjectResolver:
    def __init__(
        self,
        service_token: str,
        tokens: ActorTokenService,
        users: UserRepository,
        audit: AuditRepository,
        dev_default_email: str,
    ):
        self._service_token = service_token
        self._tokens = tokens
        self._users = users
        self._audit = audit
        self._dev_email = dev_default_email

    def resolve(self, authorization: str | None, on_behalf_of: str | None) -> AgentToolSubject:
        self._check_service_token(authorization)
        if on_behalf_of:
            return self._from_agent_token(on_behalf_of.strip())
        if self._dev_email:
            user = self._users.find_by_email(self._dev_email)
            if user is None or user.status == UserStatus.REVOKED:
                raise AuthenticationRequiredError("Người dùng mặc định (AGENT_DEV_DEFAULT_USER_EMAIL) không tồn tại hoặc đã bị khóa")
            return AgentToolSubject(user.id, user.role.value, VIA_DEV_DEFAULT)
        raise AuthenticationRequiredError("Thiếu X-On-Behalf-Of: agent chỉ hành động thay mặt một người dùng cụ thể")

    def _check_service_token(self, authorization: str | None) -> None:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token or not hmac.compare_digest(token.strip().encode(), self._service_token.encode()):
            raise AuthenticationRequiredError("Service token không hợp lệ")

    def _from_agent_token(self, token: str) -> AgentToolSubject:
        try:
            claims = self._tokens.decode(token, scope=AGENT_TOOLS_SCOPE)
            user = self._users.find_by_id(int(claims["sub"]))
            if user is None or user.status == UserStatus.REVOKED:
                raise AuthenticationRequiredError("Người dùng của agent-token không còn hiệu lực")
        except (AuthenticationRequiredError, KeyError, ValueError, TypeError) as error:
            self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.AGENT,
                    entity="agent_tool",
                    action="authenticate",
                    after={"outcome": "invalid_agent_token"},
                    reason=str(error)[:200],
                )
            )
            raise AuthenticationRequiredError("Agent-token hết hạn hoặc không hợp lệ") from error
        return AgentToolSubject(user.id, user.role.value, VIA_AGENT_TOKEN, str(claims.get("conv", "")), str(claims.get("turn", "")))
