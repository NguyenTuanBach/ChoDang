"""Xác thực: người dùng hiện tại, đăng xuất, và (chỉ khi không phải production) đăng nhập dev.

Phiên là token HS256 đặt trong cookie HttpOnly nên FE (cùng origin qua Next rewrites) không phải tự giữ token.
``dev_router`` chỉ được ``include_router`` khi ``Settings.dev_login_enabled``; ở production route không tồn tại (404).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from vin15.config.container import Container
from vin15.domain.exception import AuthenticationRequiredError
from vin15.domain.model.user import User
from vin15.presentation.dto.auth import DevLoginRequest, UserDto
from vin15.service.auth.current_user_service import bearer_token

from .dependencies import SESSION_COOKIE, container, current_user

router = APIRouter(prefix="/api/auth", tags=["Xác thực"])
dev_router = APIRouter(prefix="/api/auth", tags=["Xác thực"])


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
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=app.settings.jwt_ttl_minutes * 60,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return UserDto.of(user)
