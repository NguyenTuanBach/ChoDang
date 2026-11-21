"""Xác thực: người dùng hiện tại, đăng xuất, và (chỉ khi không phải production) đăng nhập dev.

Phiên là token HS256 đặt trong cookie HttpOnly nên FE (cùng origin qua Next rewrites) không phải tự giữ token.
``dev_router`` chỉ được ``include_router`` khi ``Settings.dev_login_enabled``; ở production route không tồn tại (404).
"""

from __future__ import annotations

import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from vin15.config.container import Container
from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.model.user import User
from vin15.presentation.dto.auth import DevLoginRequest, UserDto
from vin15.service.auth.current_user_service import bearer_token

from .dependencies import SESSION_COOKIE, container, current_user

router = APIRouter(prefix="/api/auth", tags=["Xác thực"])
dev_router = APIRouter(prefix="/api/auth", tags=["Xác thực"])


OAUTH_STATE_COOKIE = "oauth_state"


def _set_session_cookie(response: Response, app: Container, request: Request, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=app.settings.jwt_ttl_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


@router.get("/providers", summary="Các cách đăng nhập đang bật")
def providers(app: Container = Depends(container)) -> dict:
    return {"google": app.google_client.enabled, "dev": app.settings.dev_login_enabled}


@router.get("/google/login", summary="Chuyển tới Google để đăng nhập (chỉ email đã được mời)")
def google_login(request: Request, app: Container = Depends(container)) -> RedirectResponse:
    url, state = app.google_login_service.start()
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(OAUTH_STATE_COOKIE, state, max_age=600, httponly=True, samesite="lax", secure=request.url.scheme == "https", path="/")
    return response


@router.get("/google/callback", summary="Google chuyển về đây sau khi người dùng đồng ý")
async def google_callback(
    request: Request, code: str = "", state: str = "", error: str = "", app: Container = Depends(container)
) -> RedirectResponse:
    base = app.settings.app_base_url.rstrip("/")
    expected = request.cookies.get(OAUTH_STATE_COOKIE, "")

    def failure(message: str) -> RedirectResponse:
        redirect = RedirectResponse(f"{base}/login?error={quote(message)}", status_code=302)
        redirect.delete_cookie(OAUTH_STATE_COOKIE, path="/")
        return redirect

    if error or not code:
        return failure("Đăng nhập Google bị hủy hoặc thất bại")
    if not expected or not secrets.compare_digest(expected, state):
        return failure("Phiên đăng nhập Google không hợp lệ, hãy thử lại")
    try:
        _user, token = await app.google_login_service.finish(code)
    except AuthenticationRequiredError as exc:
        return failure(str(exc))
    response = RedirectResponse(f"{base}/", status_code=302)
    response.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    _set_session_cookie(response, app, request, token)
    return response


@router.get("/me", response_model=UserDto, summary="Người dùng đang đăng nhập")
def me(user: User = Depends(current_user)) -> UserDto:
    return UserDto.of(user)


@router.post("/logout", status_code=204, summary="Đăng xuất: thu hồi token và xóa cookie phiên")
def logout(request: Request, app: Container = Depends(container)) -> Response:
    token = bearer_token(request.headers.get("authorization")) or request.cookies.get(SESSION_COOKIE, "")
    if token:
        try:
            app.token_service.revoke(token)
        except AuthenticationRequiredError:
            pass  # token hỏng: vẫn xóa cookie
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@dev_router.get("/dev-accounts", response_model=list[UserDto], summary="[Dev] Các tài khoản mẫu có thể đăng nhập")
def dev_accounts(app: Container = Depends(container)) -> list[UserDto]:
    return [UserDto.of(u) for u in app.dev_login_service.list_accounts()]


@dev_router.post("/dev-login", response_model=UserDto, summary="[Dev] Đăng nhập vào một tài khoản mẫu")
def dev_login(
    body: DevLoginRequest, request: Request, response: Response, app: Container = Depends(container)
) -> UserDto:
    user, token = app.dev_login_service.login(body.email)
    _set_session_cookie(response, app, request, token)
    return UserDto.of(user)
