"""Mời tài khoản và quản lý vòng đời (A1, A2, D14): QTV mời GV, GV mời SV; thu hồi, mời lại, gán GV phụ trách, mã sinh viên."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from vin15.config.container import Container
from vin15.domain.model.user import Role, User
from vin15.presentation.dto.workflow import AdvisorBody, InviteBody, ReasonBody, StudentCodeBody
from vin15.service.user.account_service import InviteItem

from .dependencies import admin_user, container, staff_user

router = APIRouter(tags=["Tài khoản và lời mời"])


def _account(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role.value,
        "status": user.status.value,
        "student_code": user.student_code,
        "advisor_id": user.advisor_id,
        "invited_at": user.invited_at.isoformat() if user.invited_at else None,
        "invitation_expired": user.invitation_expired(),
    }


@router.post("/api/invitations", status_code=201, summary="Mời giảng viên (QTV) hoặc sinh viên (GV/QTV) qua email")
def invite(body: InviteBody, inviter: User = Depends(staff_user), app: Container = Depends(container)) -> dict:
    result = app.account_service.invite(
        inviter,
        Role(body.role),
        [InviteItem(i.email, i.full_name, i.student_code) for i in body.items],
        advisor_id=body.lecturer_id,
    )
    return {"invited": [_account(u) for u in result.invited], "errors": result.errors}


@router.get("/api/invitations", summary="Tài khoản trong phạm vi của tôi (kèm trạng thái lời mời)")
def list_accounts(viewer: User = Depends(staff_user), app: Container = Depends(container)) -> list[dict]:
    return [_account(u) for u in app.account_service.list_visible(viewer)]


@router.post("/api/invitations/{user_id}/revoke", summary="Thu hồi lời mời / khóa tài khoản")
def revoke(user_id: int, body: ReasonBody, actor: User = Depends(staff_user), app: Container = Depends(container)) -> dict:
    return _account(app.account_service.revoke(actor, user_id, body.reason))


@router.post("/api/invitations/{user_id}/reinvite", summary="Mời lại")
def reinvite(user_id: int, actor: User = Depends(staff_user), app: Container = Depends(container)) -> dict:
    return _account(app.account_service.reinvite(actor, user_id))


@router.get("/api/lecturers", summary="Danh sách giảng viên (để gán phụ trách)")
def lecturers(_viewer: User = Depends(staff_user), app: Container = Depends(container)) -> list[dict]:
    return [_account(u) for u in app.account_service.lecturers()]


@router.put("/api/students/{student_id}/advisor", summary="QTV gán giảng viên phụ trách")
def assign_advisor(student_id: int, body: AdvisorBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> dict:
    return _account(app.account_service.assign_advisor(admin, student_id, body.lecturer_id))


@router.put("/api/students/{student_id}/code", status_code=204, summary="Đặt mã sinh viên (khóa ánh xạ sang LMS)")
def set_student_code(student_id: int, body: StudentCodeBody, actor: User = Depends(staff_user), app: Container = Depends(container)) -> None:
    app.account_service.set_student_code(actor, student_id, body.student_code)
