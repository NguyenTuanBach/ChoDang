from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from vin15.config.container import Container
from vin15.domain.exception import ForbiddenRoleError
from vin15.domain.model.agent_tool import AgentToolSubject
from vin15.domain.model.user import Role, User


#: Cookie phiên do ``/api/auth/*`` đặt (HttpOnly).
SESSION_COOKIE = "session"


def container(connection: HTTPConnection) -> Container:
    """Dùng được cho cả HTTP lẫn WebSocket."""
    return connection.app.state.container


def current_user(request: Request, app: Container = Depends(container)) -> User:
    """Người dùng của request: token phiên trong header Bearer hoặc cookie phiên; không có thì 401."""
    return app.current_user_service.resolve(request.headers.get("authorization"), request.cookies.get(SESSION_COOKIE))


def agent_subject(request: Request, app: Container = Depends(container)) -> AgentToolSubject:
    """Chủ thể của lời gọi tool agent: service token + agent-token (hoặc người dùng mặc định ở dev)."""
    return app.agent_subject_resolver.resolve(request.headers.get("authorization"), request.headers.get("x-on-behalf-of"))


def require_role(*roles: Role):
    """Dependency: người dùng hiện tại phải có một trong các vai trò; ngược lại 403. Phạm vi dữ liệu do service kiểm (``domain.authorization``)."""

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenRoleError("Vai trò của bạn không được dùng chức năng này")
        return user

    return dependency


student_user = require_role(Role.STUDENT)
lecturer_user = require_role(Role.LECTURER)
admin_user = require_role(Role.ADMIN)
staff_user = require_role(Role.LECTURER, Role.ADMIN)
