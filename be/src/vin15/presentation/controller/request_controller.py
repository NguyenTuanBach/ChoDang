"""Gia hạn mốc, ngoại lệ (D1-D3) và công nhận tín chỉ (D4)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Response, UploadFile

from vin15.config.container import Container
from vin15.domain.model.user import User
from vin15.presentation.dto.workflow import AssessBody, CreditDecisionBody, ExceptionBody, ExceptionTypeBody, ExtensionBody, RequestDecisionBody

from .dependencies import admin_user, container, current_user, lecturer_user, staff_user, student_user
from .internship_controller import file_response, read_upload

router = APIRouter(tags=["Gia hạn, ngoại lệ, tín chỉ"])


@router.get("/api/exception-types", summary="Danh mục loại ngoại lệ")
def exception_types(user: User = Depends(current_user), app: Container = Depends(container)) -> list[dict]:
    return app.request_service.exception_types(active_only=user.role.value != "admin")


@router.put("/api/admin/exception-types", status_code=204, summary="QTV thêm/sửa loại ngoại lệ (đánh dấu ảnh hưởng tín chỉ)")
def upsert_exception_type(body: ExceptionTypeBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.request_service.upsert_exception_type(admin, body.code, body.name, body.affects_credit, body.active)


# ---- Sinh viên ----
@router.get("/api/student/requests", summary="Yêu cầu của tôi")
def my_requests(student: User = Depends(student_user), app: Container = Depends(container)) -> list[dict]:
    return app.request_service.mine(student)


@router.post("/api/student/requests/extension", status_code=201, summary="Yêu cầu gia hạn mốc")
def create_extension(body: ExtensionBody, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return {"id": app.request_service.create_extension(student, body.milestone_code, body.new_due_date, body.reason)}


@router.post("/api/student/requests/exception", status_code=201, summary="Yêu cầu ngoại lệ")
def create_exception(body: ExceptionBody, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return {"id": app.request_service.create_exception(student, body.type_code, body.reason)}


@router.post("/api/student/requests/{request_id}/attachments", status_code=201, summary="Đính kèm minh chứng vào yêu cầu")
def attach(request_id: int, file: UploadFile = File(...), student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return {"id": app.request_service.attach(student, request_id, file.filename or "tep", read_upload(file, app.settings.upload_max_bytes))}


@router.post("/api/student/requests/{request_id}/cancel", status_code=204, summary="Hủy yêu cầu đang chờ")
def cancel(request_id: int, student: User = Depends(student_user), app: Container = Depends(container)) -> None:
    app.request_service.cancel(student, request_id)


@router.get("/api/request-attachments/{attachment_id}/download", summary="Tải tệp đính kèm yêu cầu (kiểm quyền)")
def download_attachment(attachment_id: int, user: User = Depends(current_user), app: Container = Depends(container)) -> Response:
    return file_response(*app.request_service.attachment_bytes(user, attachment_id))


# ---- Người duyệt ----
@router.get("/api/requests/pending", summary="Yêu cầu đang chờ tôi duyệt (GV: loại thường; QTV: ảnh hưởng tín chỉ)")
def pending_requests(user: User = Depends(staff_user), app: Container = Depends(container)) -> list[dict]:
    return app.request_service.pending_for(user)


@router.get("/api/internships/{internship_id}/requests", summary="Yêu cầu của một hồ sơ")
def internship_requests(internship_id: int, user: User = Depends(current_user), app: Container = Depends(container)) -> list[dict]:
    return app.request_service.for_internship(user, internship_id)


@router.post("/api/requests/{request_id}/decision", status_code=204, summary="Duyệt / từ chối yêu cầu (HITL; người duyệt theo loại)")
def decide_request(request_id: int, body: RequestDecisionBody, user: User = Depends(staff_user), app: Container = Depends(container)) -> None:
    app.request_service.decide(user, request_id, body.approve, body.reason)


# ---- Công nhận tín chỉ ----
@router.get("/api/internships/{internship_id}/credit", summary="Bảng điều kiện T1-T6 và thẩm định của hồ sơ")
def credit_view(internship_id: int, user: User = Depends(current_user), app: Container = Depends(container)) -> dict:
    return app.credit_decision_service.view(user, internship_id)


@router.post("/api/internships/{internship_id}/credit/assess", status_code=204, summary="GV thẩm định điều kiện công nhận (đạt → QTV; chưa đạt → trả lại)")
def assess_credit(internship_id: int, body: AssessBody, lecturer: User = Depends(lecturer_user), app: Container = Depends(container)) -> None:
    app.credit_decision_service.assess(lecturer, internship_id, body.passed, body.note)


@router.post("/api/internships/{internship_id}/credit/decision", status_code=204, summary="QTV phê duyệt cuối công nhận tín chỉ (HITL) → ghi LMS")
def decide_credit(internship_id: int, body: CreditDecisionBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.credit_decision_service.decide(admin, internship_id, body.approve, body.reason)
