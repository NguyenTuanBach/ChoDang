from fastapi import Depends, Request
from starlette.requests import HTTPConnection

from vin15.config.container import Container
from vin15.domain.model.agent_tool import AgentToolSubject
from vin15.domain.model.user import User


def container(connection: HTTPConnection) -> Container:
    """Dùng được cho cả HTTP lẫn WebSocket."""
    return connection.app.state.container


def current_user(request: Request, app: Container = Depends(container)) -> User:
    """Người dùng của request: token phiên, hoặc người dùng mặc định ở dev (chưa có đăng nhập thật)."""
    return app.current_user_service.resolve(request.headers.get("authorization"))


def agent_subject(request: Request, app: Container = Depends(container)) -> AgentToolSubject:
    """Chủ thể của lời gọi tool agent: service token + agent-token (hoặc người dùng mặc định ở dev)."""
    return app.agent_subject_resolver.resolve(request.headers.get("authorization"), request.headers.get("x-on-behalf-of"))
