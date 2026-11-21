import base64
import json

import pytest

from vin15.domain.exception import AuthenticationRequiredError
from vin15.infrastructure.security.actor_token import ActorTokenService


def service(**kw):
    return ActorTokenService("s" * 32, **kw)


def test_roundtrip():
    s = service()
    claims = s.decode(s.create(7, "lecturer"))
    assert claims["sub"] == 7 and claims["role"] == "lecturer"


def test_expired_token_is_rejected():
    s = service()
    with pytest.raises(AuthenticationRequiredError, match="hết hạn"):
        s.decode(s.create(1, "student", ttl_minutes=-1))


def test_tampered_payload_is_rejected():
    s = service()
    header, payload, sig = s.create(1, "student").split(".")
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    claims["role"] = "admin"
    forged = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    with pytest.raises(AuthenticationRequiredError, match="Chữ ký"):
        s.decode(f"{header}.{forged}.{sig}")


def test_other_secret_is_rejected():
    token = service().create(1, "student")
    with pytest.raises(AuthenticationRequiredError):
        ActorTokenService("khac" * 10).decode(token)


def test_alg_none_is_rejected():
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
    with pytest.raises(AuthenticationRequiredError, match="Thuật toán"):
        service().decode(f"{header}.e30.")


def test_revoked_token_is_rejected():
    s = service()
    token = s.create(1, "student")
    s.revoke(token)
    with pytest.raises(AuthenticationRequiredError, match="thu hồi"):
        s.decode(token)


def test_garbage_is_rejected():
    with pytest.raises(AuthenticationRequiredError):
        service().decode("khong-phai-token")


def test_agent_token_carries_scope_and_extra_claims():
    s = service()
    token = s.create(5, "student", 5, scope="agent_tools", extra={"conv": "c1", "turn": "t1", "sub": 999})
    claims = s.decode(token, scope="agent_tools")
    assert claims["scope"] == "agent_tools" and claims["conv"] == "c1" and claims["turn"] == "t1"
    assert claims["sub"] == 5  # claim phụ không ghi đè được chủ thể


def test_agent_token_is_rejected_by_regular_api():
    s = service()
    token = s.create(5, "student", 5, scope="agent_tools")
    with pytest.raises(AuthenticationRequiredError, match="không dùng được"):
        s.decode(token)


def test_session_token_is_rejected_for_agent_tools():
    s = service()
    with pytest.raises(AuthenticationRequiredError, match="không dùng được"):
        s.decode(s.create(5, "student"), scope="agent_tools")


def test_wrong_scope_is_rejected():
    s = service()
    with pytest.raises(AuthenticationRequiredError):
        s.decode(s.create(5, "student", scope="other"), scope="agent_tools")
