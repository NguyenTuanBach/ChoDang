"""Google OAuth 2.0 (Authorization Code): tạo URL đăng nhập và đổi ``code`` lấy email đã xác minh.

Có tài khoản Google chưa đủ để vào hệ thống: email còn phải nằm trong danh sách đã mời (kiểm ở ``AccountActivationService``).
Vai trò do hệ thống gán, không lấy từ Google.
"""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from vin15.domain.exception import AuthenticationRequiredError

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, timeout: float = 10.0, transport: httpx.AsyncBaseTransport | None = None):
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._timeout = timeout
        self._transport = transport

    @property
    def enabled(self) -> bool:
        return bool(self._client_id and self._client_secret and self._redirect_uri)

    def authorization_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._client_id,
                "redirect_uri": self._redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"{AUTH_URL}?{query}"

    async def profile_for_code(self, code: str) -> tuple[str, str]:
        """Đổi ``code`` lấy ``(email, họ tên)``. Email phải được Google xác minh."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                token = await client.post(
                    TOKEN_URL,
                    data={
                        "code": code,
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "redirect_uri": self._redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )
                if token.status_code != 200:
                    raise AuthenticationRequiredError("Google từ chối mã đăng nhập")
                access_token = token.json().get("access_token", "")
                info = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        except httpx.HTTPError as error:
            raise AuthenticationRequiredError("Không kết nối được Google") from error
        if info.status_code != 200:
            raise AuthenticationRequiredError("Không lấy được thông tin tài khoản Google")
        body = info.json()
        if not body.get("email") or not body.get("email_verified"):
            raise AuthenticationRequiredError("Email Google chưa được xác minh")
        return str(body["email"]).lower(), str(body.get("name", ""))
