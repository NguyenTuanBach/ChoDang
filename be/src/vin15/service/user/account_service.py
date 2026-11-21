"""Mời tài khoản và quản lý vòng đời tài khoản (A1, A2, D14): QTV mời GV, GV mời SV; thu hồi, mời lại, gán GV phụ trách.

Email chưa được mời thì không đăng nhập được (Google OAuth và đăng nhập dev cùng kiểm). Vai trò do hệ thống gán.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from vin15.domain.exception import ForbiddenRoleError, InvalidInputError, ResourceNotFoundError, ScopeDeniedError
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.user import Role, User, UserStatus
from vin15.infrastructure.persistence.user_repository import UserRepository
from vin15.service.notification.notification_service import NotificationService

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class InviteItem:
    email: str
    full_name: str = ""
    student_code: str | None = None


@dataclass(frozen=True)
class InviteResult:
    invited: list[User]
    errors: list[dict]


class AccountService:
    def __init__(self, users: UserRepository, notifications: NotificationService):
        self._users = users
        self._notifications = notifications

    def invite(self, inviter: User, role: Role, items: list[InviteItem], advisor_id: int | None = None) -> InviteResult:
        if role == Role.LECTURER and inviter.role != Role.ADMIN:
            raise ForbiddenRoleError("Chỉ quản trị viên được mời giảng viên")
        if role == Role.STUDENT and inviter.role not in (Role.LECTURER, Role.ADMIN):
            raise ForbiddenRoleError("Chỉ giảng viên hoặc quản trị viên được mời sinh viên")
        if role == Role.ADMIN:
            raise ForbiddenRoleError("Quản trị viên được khai báo qua cấu hình APP_ADMIN_EMAILS")
        if role == Role.STUDENT:
            advisor_id = inviter.id if inviter.role == Role.LECTURER else advisor_id
            if advisor_id is not None:
                advisor = self._users.find_by_id(advisor_id)
                if advisor is None or advisor.role != Role.LECTURER:
                    raise InvalidInputError("Giảng viên phụ trách không hợp lệ")
        else:
            advisor_id = None
        invited: list[User] = []
        errors: list[dict] = []
        for item in items:
            email = item.email.strip().lower()
            if not _EMAIL.match(email):
                errors.append({"email": item.email, "error": "Email không hợp lệ"})
                continue
            audit = AuditEntry(
                actor_kind=ActorKind.HUMAN,
                actor_id=inviter.id,
                actor_role=inviter.role.value,
                entity="account",
                action="invite",
                after={"email": email, "role": role.value, "advisor_id": advisor_id},
                reason="Mời tài khoản",
            )
            try:
                user = self._users.insert_invited(
                    email, item.full_name or email.split("@")[0], role, inviter.id, audit, advisor_id=advisor_id, student_code=item.student_code or None
                )
            except Exception as error:
                errors.append({"email": email, "error": str(error)})
                continue
            invited.append(user)
            self._send_invitation(user, inviter)
        return InviteResult(invited, errors)

    def _send_invitation(self, user: User, inviter: User) -> None:
        role_label = {Role.LECTURER: "giảng viên", Role.STUDENT: "sinh viên"}.get(user.role, "người dùng")
        self._notifications.send_email(
            user.email,
            "Lời mời tham gia hệ thống hỗ trợ thực tập",
            f"{inviter.full_name} đã mời bạn tham gia hệ thống hỗ trợ thực tập với vai trò {role_label}.\n"
            f"Đăng nhập bằng đúng địa chỉ email này tại: {self._notifications.link('/login')}\n",
        )

    def list_visible(self, viewer: User) -> list[User]:
        """QTV: giảng viên và sinh viên; GV: sinh viên mình phụ trách."""
        if viewer.role == Role.ADMIN:
            return self._users.list_by_role(Role.LECTURER) + self._users.list_by_role(Role.STUDENT)
        if viewer.role == Role.LECTURER:
            return self._users.list_students_of(viewer.id)
        raise ForbiddenRoleError("Chỉ giảng viên hoặc quản trị viên xem được danh sách tài khoản")

    def lecturers(self) -> list[User]:
        return [u for u in self._users.list_by_role(Role.LECTURER) if u.status != UserStatus.REVOKED]

    def _managed(self, actor: User, user_id: int) -> User:
        target = self._users.find_by_id(user_id)
        if target is None:
            raise ResourceNotFoundError("Không tìm thấy tài khoản")
        if actor.role == Role.ADMIN:
            if target.role == Role.ADMIN:
                raise ForbiddenRoleError("Không thu hồi được tài khoản quản trị viên khởi tạo")
            return target
        if actor.role == Role.LECTURER and target.role == Role.STUDENT and target.advisor_id == actor.id:
            return target
        raise ScopeDeniedError("Bạn không quản lý tài khoản này")

    def revoke(self, actor: User, user_id: int, reason: str) -> User:
        """Thu hồi lời mời (chưa đăng nhập) hoặc khóa tài khoản (đã đăng nhập)."""
        target = self._managed(actor, user_id)
        audit = AuditEntry(
            actor_kind=ActorKind.HUMAN,
            actor_id=actor.id,
            actor_role=actor.role.value,
            entity="account",
            action="revoke",
            before={"status": target.status.value},
            after={"status": UserStatus.REVOKED.value},
            reason=reason or "Thu hồi / khóa tài khoản",
        )
        return self._users.set_status(user_id, UserStatus.REVOKED, audit)

    def reinvite(self, actor: User, user_id: int) -> User:
        target = self._managed(actor, user_id)
        audit = AuditEntry(
            actor_kind=ActorKind.HUMAN,
            actor_id=actor.id,
            actor_role=actor.role.value,
            entity="account",
            action="reinvite",
            before={"status": target.status.value},
            after={"status": UserStatus.INVITED.value},
            reason="Mời lại",
        )
        user = self._users.set_status(user_id, UserStatus.INVITED, audit, only_from=(UserStatus.REVOKED, UserStatus.INVITED))
        self._send_invitation(user, actor)
        return user

    def assign_advisor(self, actor: User, student_id: int, lecturer_id: int) -> User:
        if actor.role != Role.ADMIN:
            raise ForbiddenRoleError("Chỉ quản trị viên được đổi giảng viên phụ trách")
        lecturer = self._users.find_by_id(lecturer_id)
        if lecturer is None or lecturer.role != Role.LECTURER:
            raise InvalidInputError("Giảng viên không hợp lệ")
        audit = AuditEntry(
            actor_kind=ActorKind.HUMAN,
            actor_id=actor.id,
            actor_role=actor.role.value,
            entity="account",
            action="assign_advisor",
            after={"advisor_id": lecturer_id},
            reason="Gán giảng viên phụ trách",
        )
        student = self._users.set_advisor(student_id, lecturer_id, audit)
        self._notifications.notify(lecturer_id, "Bạn được phân công phụ trách một sinh viên", student.full_name, link="/lecturer/students")
        return student

    def visible_student(self, viewer: User, student_id: int) -> User:
        """Sinh viên mà người xem được phép xem (QTV: mọi sinh viên; GV: sinh viên mình phụ trách)."""
        target = self._managed(viewer, student_id)
        if target.role != Role.STUDENT:
            raise InvalidInputError("Không phải sinh viên")
        return target

    def set_student_code(self, actor: User, student_id: int, student_code: str) -> None:
        """Mã sinh viên là khóa ánh xạ sang LMS; QTV hoặc giảng viên phụ trách đặt."""
        target = self._managed(actor, student_id)
        if target.role != Role.STUDENT:
            raise InvalidInputError("Chỉ sinh viên có mã sinh viên")
        self._users.set_student_code(
            student_id,
            student_code.strip(),
            AuditEntry(
                actor_kind=ActorKind.HUMAN,
                actor_id=actor.id,
                actor_role=actor.role.value,
                entity="account",
                action="set_student_code",
                after={"student_code": student_code.strip()},
                reason="Cập nhật mã sinh viên",
            ),
        )

    def bootstrap_admins(self, emails: list[str]) -> int:
        return self._users.ensure_admins(emails) if emails else 0


