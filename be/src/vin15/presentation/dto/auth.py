"""Phản hồi và yêu cầu REST của xác thực."""

from __future__ import annotations

from pydantic import BaseModel, Field

from vin15.domain.model.user import User


class UserDto(BaseModel):
    id: str
    email: str
    full_name: str
    role: str

    @classmethod
    def of(cls, user: User) -> UserDto:
        return cls(id=str(user.id), email=user.email, full_name=user.full_name, role=user.role.value)


class DevLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
