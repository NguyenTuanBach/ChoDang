"""Kiểm service token (``Authorization: Bearer ...``) dùng chung cho HTTP và WebSocket."""

from __future__ import annotations

import hmac

from vin15_agent.shared.settings import Settings


def service_token_matches(settings: Settings, authorization: str) -> bool:
    scheme, _, token = authorization.partition(" ")
    return scheme.lower() == "bearer" and hmac.compare_digest(token.encode(), settings.agent_api_service_token.encode())
