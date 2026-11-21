import base64
import json
import time

import httpx
import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from src.config import get_settings
from src.core import oidc


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _token(key, claims, kid="test-key"):
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT", "kid": kid}, separators=(",", ":")).encode())
    payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = key.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64(signature)}"


@pytest.mark.asyncio
async def test_verify_id_token_checks_signature_claims_and_nonce(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = key.public_key().public_numbers()
    settings = get_settings()
    monkeypatch.setattr(settings, "oidc_issuer", "https://idp.example")
    monkeypatch.setattr(settings, "oidc_client_id", "vin15")
    now = int(time.time())
    claims = {"iss": "https://idp.example", "aud": "vin15", "exp": now + 300, "nonce": "nonce-1", "sub": "u1"}
    raw = _token(key, claims)

    async def fake_client():
        def handler(request: httpx.Request):
            return httpx.Response(200, json={
                "keys": [{"kty": "RSA", "kid": "test-key", "n": _b64(public.n.to_bytes((public.n.bit_length() + 7) // 8, "big")),
                          "e": _b64(public.e.to_bytes((public.e.bit_length() + 7) // 8, "big"))}]
            })
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    # _verify_id_token uses async context manager; provide the same protocol.
    class ClientContext:
        async def __aenter__(self):
            return await fake_client()
        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(oidc, "http_client", lambda: ClientContext())
    result = await oidc._verify_id_token(raw, {"jwks_uri": "https://idp.example/jwks"}, "nonce-1")
    assert result["sub"] == "u1"

    with pytest.raises(oidc.OIDCError, match="nonce"):
        await oidc._verify_id_token(raw, {"jwks_uri": "https://idp.example/jwks"}, "wrong")
