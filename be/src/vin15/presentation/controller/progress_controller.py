"""Đề cương, mốc, nhật ký tuần, minh chứng (A7-A10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile

from vin15.config.container import Container
from vin15.domain.model.user import User
from vin15.presentation.dto.workflow import (
    CommentBody,
    EvidenceFieldsBody,
    JournalAdviceBody,
    JournalBody,
    JournalItemsBody,
    OutlineBody,
    OutlineDecisionBody,
    ReasonBody,
)

from .dependencies import container, current_user, lecturer_user, student_user
from .internship_controller import file_response, read_upload

router = APIRouter(tags=["Đề cương, mốc, nhật ký, minh chứng"])


# ---- Đề cương ----
@router.post("/api/student/outlines/extract", summary="Tải tệp đề cương: AI đọc và gợi ý bốn phần để điền form (không lưu, SV kiểm tra rồi mới nộp)")
async def extract_outline_file(file: UploadFile = File(...), student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return await app.outline_review_service.extract_file(student, file.filename or "dec-cuong", read_upload(file, app.settings.upload_max_bytes))


@router.post("/api/student/outlines/{outline_id}/file", status_code=201, summary="Đính kèm tệp đề cương đã nộp (lưu bản gốc cho giảng viên mở)")
async def attach_outline_file(outline_id: int, file: UploadFile = File(...), student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return app.outline_review_service.attach_file(student, outline_id, file.filename or "dec-cuong", read_upload(file, app.settings.upload_max_bytes))


@router.get("/api/outlines/{outline_id}/file", summary="Tải tệp đề cương (kiểm quyền: chủ hồ sơ, GV phụ trách, QTV)")
def download_outline_file(outline_id: int, user: User = Depends(current_user), app: Container = Depends(container)) -> Response:
    return file_response(*app.outline_review_service.file_bytes(user, outline_id))


@router.post("/api/student/outlines", status_code=201, summary="Nộp đề cương (phiên bản mới)")
async def submit_outline(body: OutlineBody, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    # Có lỗi chắc chắn thì saved=false (không lưu) kèm chỗ sai và nhận xét AI; chuẩn đầu ra do AI nhận diện, không còn tích tay.
    return await app.outline_review_service.submit(student, body.content)


@router.post("/api/outlines/{outline_id}/decision", status_code=204, summary="GV duyệt / yêu cầu sửa / từ chối đề cương (HITL)")
def decide_outline(outline_id: int, body: OutlineDecisionBody, lecturer: User = Depends(lecturer_user), app: Container = Depends(container)) -> None:
    app.outline_service.decide(lecturer, outline_id, body.action, body.reason)


# ---- Mốc ----
@router.post("/api/student/milestones/{code}/submit", status_code=204, summary="Nộp mốc (cần có minh chứng với M3-M5)")
def submit_milestone(code: str, student: User = Depends(student_user), app: Container = Depends(container)) -> None:
    app.milestone_service.submit(student, code)


@router.post("/api/student/milestones/{code}/evidence", status_code=201, summary="Tải minh chứng cho mốc (PDF/PNG/JPG/DOCX)")
def upload_evidence(
    code: str,
    file: UploadFile = File(...),
    title: str = Form(default=""),
    student: User = Depends(student_user),
    app: Container = Depends(container),
) -> dict:
    return {"id": app.milestone_service.upload_evidence(student, code, file.filename or "tep", read_upload(file, app.settings.upload_max_bytes), title)}


@router.post("/api/student/evidence/{evidence_id}/extract", summary="AI gợi ý các trường từ giấy xác nhận / phiếu đánh giá (SV xác nhận từng trường)")
async def extract_evidence(evidence_id: int, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return await app.intake_service.extract_evidence(student, evidence_id)


@router.put("/api/student/evidence/{evidence_id}/fields", summary="SV xác nhận thông tin trên giấy; BE đối chiếu với hồ sơ")
def confirm_evidence_fields(evidence_id: int, body: EvidenceFieldsBody, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return app.milestone_service.confirm_evidence_fields(student, evidence_id, body.fields, body.confirmations)


@router.post("/api/student/evidence/{evidence_id}/withdraw", status_code=204, summary="SV thu hồi (xóa) minh chứng đang chờ duyệt của mốc chưa nộp")
def withdraw_evidence(evidence_id: int, student: User = Depends(student_user), app: Container = Depends(container)) -> None:
    app.milestone_service.withdraw_evidence(student, evidence_id)


@router.post("/api/student/intake/auto", summary="Đính kèm giấy trong Trợ lý: AI nhận loại giấy, lưu vào đúng chỗ, trả gợi ý trường")
async def auto_intake(file: UploadFile = File(...), student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return await app.intake_service.auto_intake(student, file.filename or "tep", read_upload(file, app.settings.upload_max_bytes))


@router.post("/api/milestones/{milestone_id}/accept", status_code=204, summary="GV chấp nhận mốc (HITL)")
def accept_milestone(milestone_id: int, lecturer: User = Depends(lecturer_user), app: Container = Depends(container)) -> None:
    app.milestone_service.review(lecturer, milestone_id, True)


@router.post("/api/milestones/{milestone_id}/reject", status_code=204, summary="GV trả lại mốc, bắt buộc có lý do (HITL)")
def reject_milestone(milestone_id: int, body: ReasonBody, lecturer: User = Depends(lecturer_user), app: Container = Depends(container)) -> None:
    app.milestone_service.review(lecturer, milestone_id, False, body.reason)


@router.get("/api/evidence/{evidence_id}/download", summary="Tải minh chứng (kiểm quyền)")
def download_evidence(evidence_id: int, user: User = Depends(current_user), app: Container = Depends(container)) -> Response:
    return file_response(*app.milestone_service.evidence_bytes(user, evidence_id))


# ---- Nhật ký ----
@router.post("/api/student/journal", status_code=201, summary="Nộp nhật ký tuần")
def submit_journal(body: JournalBody, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    items = [i.model_dump() for i in body.plan_items]
    return {"id": app.milestone_service.submit_journal(student, body.week_start, body.content, items, body.blockers, body.ai_advice)}


@router.put("/api/student/journal/{journal_id}/items", status_code=204, summary="Sinh viên tích việc đã hoàn thành trong nhật ký")
def update_journal_items(journal_id: int, body: JournalItemsBody, student: User = Depends(student_user), app: Container = Depends(container)) -> None:
    app.milestone_service.update_journal_items(student, journal_id, [i.model_dump() for i in body.plan_items])


@router.post("/api/student/journal/ai-advice", summary="Hỏi AI xem lịch tuần tới đã ổn chưa (gợi ý, không thay quyết định)")
async def journal_ai_advice(body: JournalAdviceBody, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return await app.journal_advice_service.advise(student, body.content, [i.model_dump() for i in body.plan_items], body.blockers)


@router.post("/api/journal/{journal_id}/comment", status_code=204, summary="GV nhận xét nhật ký")
def comment_journal(journal_id: int, body: CommentBody, lecturer: User = Depends(lecturer_user), app: Container = Depends(container)) -> None:
    app.milestone_service.comment_journal(lecturer, journal_id, body.comment)
