"""Token phiên HS256 chỉ dùng stdlib (hmac). Chỉ hỗ trợ HS256 + ``exp`` nên không có lỗi ``alg=none``.

Đăng nhập thật dùng Google OAuth; sau khi xác minh email đã mời, BE cấp token này cho trình duyệt.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from threading import Lock

from vin15.domain.exception import AuthenticationRequiredError


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


class ActorTokenService:
    def __init__(self, secret: str, ttl_minutes: int = 480):
        self._secret = secret.encode()
        self._ttl_minutes = ttl_minutes
        self._revoked: set[str] = set()
        self._lock = Lock()

    def _sign(self, message: bytes) -> str:
        return _b64(hmac.new(self._secret, message, hashlib.sha256).digest())

    def create(self, user_id: int, role: str, ttl_minutes: int | None = None) -> str:
        ttl = self._ttl_minutes if ttl_minutes is None else ttl_minutes
        header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        payload = _b64(json.dumps({"sub": user_id, "role": role, "jti": secrets.token_urlsafe(16), "exp": int(time.time()) + ttl * 60}).encode())
        return f"{header}.{payload}.{self._sign(f'{header}.{payload}'.encode())}"

    def decode(self, token: str) -> dict:
        try:
            header, payload, signature = token.split(".")
            alg = json.loads(_unb64(header)).get("alg")
        except (ValueError, UnicodeDecodeError, AttributeError) as exc:
            raise AuthenticationRequiredError("Token sai định dạng") from exc
        if alg != "HS256":
            raise AuthenticationRequiredError("Thuật toán không được hỗ trợ")
        if not hmac.compare_digest(self._sign(f"{header}.{payload}".encode()), signature):
            raise AuthenticationRequiredError("Chữ ký không hợp lệ")
        with self._lock:
            if signature in self._revoked:
                raise AuthenticationRequiredError("Token đã bị thu hồi")
        try:
            claims = json.loads(_unb64(payload))
        except (ValueError, UnicodeDecodeError) as exc:
            raise AuthenticationRequiredError("Token sai định dạng") from exc
        if claims.get("exp", 0) < time.time():
            raise AuthenticationRequiredError("Token đã hết hạn")
        return claims

    def revoke(self, token: str) -> None:
        """Thu hồi token (đăng xuất hoặc phát hiện phiên bị lộ). Trạng thái chỉ nằm trong RAM của tiến trình."""
        try:
            _header, _payload, signature = token.split(".")
        except ValueError as exc:
            raise AuthenticationRequiredError("Token sai định dạng") from exc
        with self._lock:
            self._revoked.add(signature)
