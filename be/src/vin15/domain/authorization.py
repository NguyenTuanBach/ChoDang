"""Kiểm phạm vi dữ liệu (X1): ai được xem/thao tác trên hồ sơ của ai.

SV chỉ thấy hồ sơ của mình; GV chỉ thấy hồ sơ sinh viên mình phụ trách; QTV thấy toàn bộ.
"""

from __future__ import annotations

from vin15.domain.exception import ForbiddenRoleError, ScopeDeniedError
from vin15.domain.model.audit import Actor, ActorKind
from vin15.domain.model.user import Role, User


def actor_of(user: User) -> Actor:
    return Actor(ActorKind.HUMAN, user.id, user.role.value)


def can_view_internship(user: User, owner_id: int, lecturer_id: int | None) -> bool:
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.LECTURER:
        return lecturer_id is not None and lecturer_id == user.id
    return user.id == owner_id


def require_view_internship(user: User, owner_id: int, lecturer_id: int | None) -> None:
    if not can_view_internship(user, owner_id, lecturer_id):
        raise ScopeDeniedError("Bạn không có quyền xem hồ sơ này")


def require_role(user: User, *roles: Role) -> None:
    if user.role not in roles:
        raise ForbiddenRoleError("Vai trò của bạn không được dùng chức năng này")
