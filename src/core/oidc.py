"""SSO/OIDC — authorization code flow cho confidential client (R1.2).

Luồng: /auth/oidc/login → IdP → /auth/oidc/callback?code&state → đổi code lấy access token
(có client_secret) → gọi userinfo → khớp tài khoản nội bộ theo email (hoặc username).
Vai trò lấy từ tài khoản nội bộ, không tin claim vai trò của IdP: nhà trường phân quyền
trong hệ thống này. Tài khoản chưa có trong hệ thống bị từ chối (không tự tạo).

`state` được ký HMAC + có hạn 10 phút nên không cần lưu phía server. Nếu IdP trả
`id_token`, chữ ký RSA và các claim issuer/audience/expiry/nonce được xác minh qua JWKS;
userinfo vẫn được gọi trực tiếp tới IdP qua TLS bằng access token vừa đổi.
"""

from __future__ import annotations

import base64
import hmac
import json
import secrets
import time
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from src.config import get_settings
from src.core.security import _b64, _sign, _unb64

_discovery_cache: dict[str, dict] = {}


class OIDCError(Exception):
    pass


def oidc_enabled() -> bool:
    s = get_settings()
    return bool(s.oidc_issuer and s.oidc_client_id and s.oidc_client_secret)


def http_client() -> httpx.AsyncClient:
    """Điểm thay thế cho test (MockTransport)."""
    return httpx.AsyncClient(timeout=10)


async def discovery() -> dict:
    issuer = get_settings().oidc_issuer.rstrip("/")
    if issuer not in _discovery_cache:
        async with http_client() as client:
            r = await client.get(f"{issuer}/.well-known/openid-configuration")
        if r.status_code != 200:
            raise OIDCError(f"Không đọc được cấu hình OIDC của {issuer} (HTTP {r.status_code})")
        _discovery_cache[issuer] = r.json()
    return _discovery_cache[issuer]


def make_state() -> str:
    payload = _b64(json.dumps({"n": secrets.token_urlsafe(12), "exp": int(time.time()) + 600}).encode())
    return f"{payload}.{_sign(('oidc:' + payload).encode())}"


def state_nonce(state: str) -> str:
    """Lấy nonce đã ký trong state để ràng buộc authorization response."""
    try:
        payload, _sig = state.split(".")
        return str(json.loads(_unb64(payload))["n"])
    except (ValueError, KeyError, UnicodeDecodeError, TypeError) as exc:
        raise OIDCError("state khÃ´ng há»£p lá»‡") from exc


def check_state(state: str) -> None:
    try:
        payload, sig = state.split(".")
        exp = json.loads(_unb64(payload))["exp"]
    except (ValueError, KeyError, UnicodeDecodeError) as exc:
        raise OIDCError("state không hợp lệ") from exc
    if not hmac.compare_digest(_sign(("oidc:" + payload).encode()), sig) or exp < time.time():
        raise OIDCError("state không hợp lệ hoặc đã hết hạn")


async def authorize_url() -> str:
    s = get_settings()
    meta = await discovery()
    query = {
        "response_type": "code", "client_id": s.oidc_client_id, "redirect_uri": s.oidc_redirect_uri,
        "scope": s.oidc_scopes, "state": make_state(),
    }
    query["nonce"] = state_nonce(query["state"])
    return f"{meta['authorization_endpoint']}?{urlencode(query)}"


def _b64int(value: str) -> int:
    return int.from_bytes(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)), "big")


async def _verify_id_token(raw: str, metadata: dict, expected_nonce: str | None) -> dict:
    """Verify RS256/RS384/RS512 ID tokens using the provider JWKS."""
    try:
        header_b64, payload_b64, sig_b64 = raw.split(".")
        header = json.loads(_unb64(header_b64))
        claims = json.loads(_unb64(payload_b64))
        if header.get("alg") not in {"RS256", "RS384", "RS512"}:
            raise OIDCError("id_token dùng thuật toán không được hỗ trợ")
        if claims.get("iss") != get_settings().oidc_issuer.rstrip("/"):
            raise OIDCError("id_token sai issuer")
        aud = claims.get("aud")
        if not (aud == get_settings().oidc_client_id or isinstance(aud, list) and get_settings().oidc_client_id in aud):
            raise OIDCError("id_token sai audience")
        if int(claims.get("exp", 0)) <= int(time.time()):
            raise OIDCError("id_token đã hết hạn")
        if expected_nonce and claims.get("nonce") != expected_nonce:
            raise OIDCError("id_token sai nonce")
        jwks_uri = metadata.get("jwks_uri")
        if not jwks_uri:
            raise OIDCError("IdP không công bố JWKS để xác minh id_token")
        async with http_client() as client:
            response = await client.get(jwks_uri)
        keys = response.json().get("keys", []) if response.status_code == 200 else []
        jwk = next((k for k in keys if k.get("kid") == header.get("kid") and k.get("kty") == "RSA"), None)
        if not jwk:
            raise OIDCError("Không tìm thấy khóa ký id_token")
        public_key = rsa.RSAPublicNumbers(_b64int(jwk["e"]), _b64int(jwk["n"])).public_key()
        digest = {"RS256": hashes.SHA256(), "RS384": hashes.SHA384(), "RS512": hashes.SHA512()}[header["alg"]]
        public_key.verify(base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4)),
                          f"{header_b64}.{payload_b64}".encode(), padding.PKCS1v15(), digest)
        return claims
    except OIDCError:
        raise
    except Exception as exc:
        raise OIDCError("id_token không hợp lệ") from exc


async def fetch_userinfo(code: str, expected_nonce: str | None = None) -> dict:
    s = get_settings()
    meta = await discovery()
    async with http_client() as client:
        token = await client.post(meta["token_endpoint"], data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": s.oidc_redirect_uri,
            "client_id": s.oidc_client_id, "client_secret": s.oidc_client_secret,
        })
        token_data = token.json()
        if token.status_code != 200 or "access_token" not in token_data:
            raise OIDCError("IdP từ chối mã đăng nhập")
        if token_data.get("id_token"):
            await _verify_id_token(token_data["id_token"], meta, expected_nonce)
        info = await client.get(meta["userinfo_endpoint"],
                                headers={"Authorization": f"Bearer {token_data['access_token']}"})
    if info.status_code != 200:
        raise OIDCError("Không lấy được thông tin người dùng từ IdP")
    return info.json()
