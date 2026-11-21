"""Thông báo trong ứng dụng (A13), hàng chờ duyệt (A12), cờ rủi ro (C4, C8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from vin15.config.container import Container
from vin15.domain.model.user import User
from vin15.presentation.dto.workflow import FlagChangeBody

from .dependencies import container, current_user, staff_user

router = APIRouter(tags=["Thông báo, hàng chờ, cờ rủi ro"])

_FLAG_TARGET = {"acknowledge": "acknowledged", "resolve": "resolved", "dismiss": "dismissed"}


@router.get("/api/notifications", summary="Thông báo của tôi")
def notifications(user: User = Depends(current_user), app: Container = Depends(container)) -> dict:
    return {"unread": app.notification_service.unread_count(user.id), "items": app.notification_service.list_for(user.id)}


@router.post("/api/notifications/read", status_code=204, summary="Đánh dấu đã đọc tất cả")
def read_all(user: User = Depends(current_user), app: Container = Depends(container)) -> None:
    app.notification_service.mark_read(user.id, None)


@router.post("/api/notifications/{notification_id}/read", status_code=204, summary="Đánh dấu đã đọc một thông báo")
def read_one(notification_id: int, user: User = Depends(current_user), app: Container = Depends(container)) -> None:
    app.notification_service.mark_read(user.id, notification_id)


@router.get("/api/queue", summary="Hàng chờ duyệt xếp theo ưu tiên")
def queue(user: User = Depends(staff_user), app: Container = Depends(container)) -> list[dict]:
    return app.report_service.queue(user)


@router.get("/api/flags", summary="Cờ rủi ro (GV: sinh viên mình phụ trách; QTV: toàn khóa)")
def flags(status: str | None = None, internship_id: int | None = None, user: User = Depends(staff_user), app: Container = Depends(container)) -> list[dict]:
    return app.monitoring_service.flags(user, status, internship_id)


@router.post("/api/flags/{flag_id}/decision", status_code=204, summary="Ghi nhận / giải quyết / bác bỏ cờ (bác bỏ cần lý do)")
def change_flag(flag_id: int, body: FlagChangeBody, user: User = Depends(staff_user), app: Container = Depends(container)) -> None:
    app.monitoring_service.change_flag(user, flag_id, _FLAG_TARGET[body.action], body.reason)
