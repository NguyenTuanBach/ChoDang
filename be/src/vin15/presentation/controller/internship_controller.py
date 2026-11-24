"""Hồ sơ thực tập: phía sinh viên (khai báo, tải giấy tiếp nhận, AI gợi ý, nộp) và phía GV/QTV (danh sách, chi tiết, quyết định, tiền thẩm)."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile

from vin15.config.container import Container
from vin15.domain.exception import InvalidInputError
from vin15.domain.model.user import Role, User
from vin15.presentation.dto.workflow import DecisionBody, InternshipDraftBody, InternshipPersonalBody, PreReviewBody

from .dependencies import container, current_user, lecturer_user, staff_user, student_user

router = APIRouter(tags=["Hồ sơ thực tập"])


def read_upload(file: UploadFile, max_bytes: int) -> bytes:
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise InvalidInputError(f"Tệp vượt quá {max_bytes // (1024 * 1024)} MB")
    return data


def file_response(data: bytes, mime: str, filename: str) -> Response:
    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}", "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


# ------------------------------------------------------------------ sinh viên ----
@router.get("/api/student/internship", summary="Hồ sơ thực tập của tôi kèm mốc, đề cương, nhật ký, yêu cầu và kết quả kiểm")
def my_internship(student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    row = app.internship_service.mine(student)
    outcomes = app.outline_service.outcomes_for(row["cohort"] if row else app.settings.current_cohort)
    if row is None:
        # Chưa có hồ sơ: vẫn trả đủ các danh sách (rỗng) để trang không phải xử lý khóa thiếu.
        return {
            "internship": None,
            "documents": [],
            "outlines": [],
            "milestones": [],
            "journals": [],
            "evidence": [],
            "requests": [],
            "flags": [],
            "suggestions": [],
            "outcomes": outcomes,
            "checks": [],
        }
    detail = app.report_service.detail(student, row["id"])
    detail["outcomes"] = outcomes
    detail["checks"] = app.internship_service.validate(row) if row["status"] in ("draft", "revision_requested") else []
    return detail


@router.put("/api/student/internship", summary="Lưu bản nháp hồ sơ (tạo mới nếu chưa có)")
def save_internship(body: InternshipDraftBody, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    data = body.model_dump(exclude_unset=True)
    confirmations = data.pop("confirmations", {})
    row = app.internship_service.save_draft(student, data, confirmations)
    return {"internship": row, "checks": app.internship_service.validate(row)}


@router.put("/api/student/internship/personal", summary="Sau khi nộp hồ sơ: chỉ sửa phần cá nhân (vị trí, mô tả công việc, hình thức)")
def update_personal(body: InternshipPersonalBody, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    row = app.internship_service.update_personal(student, body.position, body.job_description, body.mode)
    return {"internship": row}


@router.post("/api/student/internship/documents", status_code=201, summary="Tải giấy tiếp nhận (PDF/PNG/JPG)")
def upload_document(file: UploadFile = File(...), student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return app.internship_service.upload_document(student, file.filename or "tep", read_upload(file, app.settings.upload_max_bytes))


@router.post("/api/student/internship/documents/{document_id}/extract", summary="AI gợi ý các trường từ giấy tiếp nhận (SV xác nhận từng trường)")
async def extract_document(document_id: int, student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return await app.intake_service.extract(student, document_id)


@router.post("/api/student/internship/submit", summary="Nộp hồ sơ cho giảng viên xác nhận")
def submit_internship(student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return {"internship": app.internship_service.submit(student)}


@router.post("/api/student/internship/submit-for-credit", status_code=204, summary="Nộp kết thúc thực tập để thẩm định công nhận tín chỉ")
def submit_for_credit(student: User = Depends(student_user), app: Container = Depends(container)) -> None:
    app.credit_decision_service.submit_for_credit(student)


@router.get("/api/documents/{document_id}/download", summary="Tải giấy tiếp nhận (kiểm quyền)")
def download_document(document_id: int, user: User = Depends(current_user), app: Container = Depends(container)) -> Response:
    return file_response(*app.internship_service.document_bytes(user, document_id))


# ------------------------------------------------------------------ giảng viên / QTV ----
@router.get("/api/internships", summary="Danh sách hồ sơ có lọc (GV: sinh viên mình phụ trách; QTV: toàn khóa)")
def list_internships(
    status: str | None = None,
    milestone_code: str | None = Query(default=None, pattern="^M[1-5]$"),
    milestone_status: str | None = None,
    flagged: bool = False,
    cohort: str | None = None,
    user: User = Depends(staff_user),
    app: Container = Depends(container),
) -> list[dict]:
    return app.report_service.list_internships(
        user, status=status, milestone_code=milestone_code, milestone_status=milestone_status, flagged=flagged, cohort=cohort
    )


@router.get("/api/internships/export.csv", summary="Xuất danh sách hồ sơ (CSV)")
def export_internships(
    status: str | None = None,
    milestone_code: str | None = Query(default=None, pattern="^M[1-5]$"),
    milestone_status: str | None = None,
    flagged: bool = False,
    cohort: str | None = None,
    user: User = Depends(staff_user),
    app: Container = Depends(container),
) -> Response:
    content = app.report_service.export_csv(
        user, status=status, milestone_code=milestone_code, milestone_status=milestone_status, flagged=flagged, cohort=cohort
    )
    return Response(content=content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=ho-so-thuc-tap.csv"})


@router.get("/api/internships/{internship_id}", summary="Chi tiết một hồ sơ (kiểm phạm vi)")
def internship_detail(internship_id: int, user: User = Depends(current_user), app: Container = Depends(container)) -> dict:
    return app.report_service.detail(user, internship_id)


@router.post("/api/internships/{internship_id}/decision", summary="GV xác nhận / yêu cầu sửa / từ chối hồ sơ (HITL)")
def decide_internship(internship_id: int, body: DecisionBody, lecturer: User = Depends(lecturer_user), app: Container = Depends(container)) -> dict:
    return {"internship": app.internship_service.decide(lecturer, internship_id, body.action, body.reason)}


@router.post("/api/internships/{internship_id}/pre-review", summary="Tiền thẩm bằng AI (gợi ý, không thay GV quyết định)")
async def pre_review(internship_id: int, body: PreReviewBody, user: User = Depends(staff_user), app: Container = Depends(container)) -> dict:
    assert user.role in (Role.LECTURER, Role.ADMIN)
    return await app.pre_review_service.review(user, internship_id, body.subject_kind, body.subject_id)
