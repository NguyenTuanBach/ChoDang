"""Cấu hình của QTV (mẫu mốc, chuẩn đầu ra), dashboard + xuất báo cáo (D7, D8), audit, và LMS mini (học phần, điểm, sổ tín chỉ, đồng bộ)."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, File, Response, UploadFile

from vin15.config.container import Container
from vin15.domain.authorization import actor_of
from vin15.domain.exception import ForbiddenRoleError
from vin15.domain.model.user import Role, User
from vin15.presentation.dto.workflow import CourseBody, GradeBody, LmsStudentBody, MilestoneTemplateBody, OutcomeBody, PrerequisiteBody

from .dependencies import admin_user, container, current_user, staff_user, student_user

router = APIRouter(tags=["Cấu hình, dashboard, LMS"])


# ---- Cấu hình ----
@router.get("/api/config/milestone-templates", summary="Mẫu mốc (hạn tính theo ngày bắt đầu/giữa/kết thúc)")
def milestone_templates(_user: User = Depends(current_user), app: Container = Depends(container)) -> list[dict]:
    return app.config_service.milestone_templates()


@router.put("/api/admin/milestone-templates/{code}", status_code=204, summary="QTV sửa mẫu mốc (áp cho hồ sơ xác nhận từ sau đó)")
def update_template(code: str, body: MilestoneTemplateBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.config_service.update_milestone_template(admin, code, body.name, body.anchor, body.offset_days)


@router.get("/api/config/outcomes", summary="Chuẩn đầu ra theo khóa")
def outcomes(cohort: str | None = None, _user: User = Depends(current_user), app: Container = Depends(container)) -> list[dict]:
    return app.config_service.outcomes(cohort or app.settings.current_cohort)


@router.put("/api/admin/outcomes", status_code=204, summary="QTV thêm/sửa chuẩn đầu ra của một khóa")
def upsert_outcome(body: OutcomeBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.config_service.upsert_outcome(admin, body.cohort, body.code, body.description)


@router.delete("/api/admin/outcomes/{outcome_id}", status_code=204, summary="QTV xóa chuẩn đầu ra")
def delete_outcome(outcome_id: int, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.config_service.delete_outcome(admin, outcome_id)


# ---- Dashboard ----
@router.get("/api/dashboard", summary="Dashboard (QTV: toàn khóa; GV: phạm vi mình)")
def dashboard(cohort: str | None = None, user: User = Depends(staff_user), app: Container = Depends(container)) -> dict:
    return app.report_service.dashboard(user, cohort)


@router.get("/api/dashboard/export.csv", summary="Xuất số liệu dashboard (CSV)")
def dashboard_export(cohort: str | None = None, user: User = Depends(staff_user), app: Container = Depends(container)) -> Response:
    return Response(
        content=app.report_service.dashboard_csv(user, cohort),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=dashboard.csv"},
    )


@router.get("/api/admin/audit", summary="Nhật ký kiểm toán (chỉ QTV)")
def audit(limit: int = 200, entity: str | None = None, actor_id: int | None = None, user: User = Depends(admin_user), app: Container = Depends(container)) -> list[dict]:
    return app.report_service.audit(user, limit, entity, actor_id)


# ---- LMS mini: giao diện quản trị ----
@router.get("/api/lms/courses", summary="Học phần trong LMS mini")
def courses(_user: User = Depends(current_user), app: Container = Depends(container)) -> list[dict]:
    return app.lms_admin_service.courses()


@router.put("/api/admin/lms/courses", status_code=204, summary="QTV thêm/sửa học phần")
def upsert_course(body: CourseBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.lms_admin_service.upsert_course(actor_of(admin), body.code, body.name, body.credits, body.kind)


@router.get("/api/admin/lms/courses/{course_code}/prerequisites", summary="Học phần tiên quyết")
def prerequisites(course_code: str, _admin: User = Depends(admin_user), app: Container = Depends(container)) -> list[dict]:
    return app.lms_admin_service.prerequisites(course_code.upper())


@router.put("/api/admin/lms/courses/{course_code}/prerequisites", status_code=204, summary="QTV đặt học phần tiên quyết")
def set_prerequisite(course_code: str, body: PrerequisiteBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.lms_admin_service.set_prerequisite(actor_of(admin), course_code, body.required_course_code, body.min_score)


@router.delete("/api/admin/lms/courses/{course_code}/prerequisites/{required_code}", status_code=204, summary="Bỏ học phần tiên quyết")
def remove_prerequisite(course_code: str, required_code: str, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.lms_admin_service.remove_prerequisite(actor_of(admin), course_code, required_code)


@router.get("/api/admin/lms/students", summary="Sinh viên trong LMS mini (kèm tín chỉ tích lũy)")
def lms_students(_admin: User = Depends(admin_user), app: Container = Depends(container)) -> list[dict]:
    return app.lms_admin_service.students()


@router.put("/api/admin/lms/students", status_code=204, summary="QTV thêm/sửa sinh viên trong LMS")
def upsert_lms_student(body: LmsStudentBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.lms_admin_service.upsert_student(actor_of(admin), body.student_code, body.full_name)


@router.put("/api/admin/lms/grades", status_code=204, summary="QTV nhập/sửa điểm")
def upsert_grade(body: GradeBody, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.lms_admin_service.upsert_grade(actor_of(admin), body.student_code, body.course_code, body.score, body.term)


@router.delete("/api/admin/lms/grades/{student_code}/{course_code}", status_code=204, summary="Xóa điểm")
def delete_grade(student_code: str, course_code: str, admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.lms_admin_service.delete_grade(actor_of(admin), student_code, course_code)


@router.post("/api/admin/lms/grades/import", summary="Nhập điểm từ CSV (student_code,course_code,score,term)")
def import_grades(file: UploadFile = File(...), admin: User = Depends(admin_user), app: Container = Depends(container)) -> dict:
    content = file.file.read(2 * 1024 * 1024).decode("utf-8-sig", errors="replace")
    return app.lms_admin_service.import_grades_csv(actor_of(admin), content)


@router.get("/api/admin/lms/sync-jobs", summary="Việc đồng bộ kết quả sang LMS")
def sync_jobs(status: str | None = None, _admin: User = Depends(admin_user), app: Container = Depends(container)) -> list[dict]:
    return app.lms_sync_service.jobs(status)


@router.post("/api/admin/lms/sync-jobs/{job_id}/retry", status_code=204, summary="Thử lại việc đồng bộ đã thất bại")
def retry_sync(job_id: int, _admin: User = Depends(admin_user), app: Container = Depends(container)) -> None:
    app.lms_sync_service.retry(job_id)


# ---- LMS: xem điểm và tín chỉ ----
def _record_dict(record) -> dict | None:
    if record is None:
        return None
    return {
        "student_code": record.student_code,
        "full_name": record.full_name,
        "total_credits": record.total_credits,
        "grades": [asdict(g) for g in record.grades],
        "credits": [asdict(c) for c in record.credits],
    }


@router.get("/api/lms/me", summary="Bảng điểm và tín chỉ tích lũy của tôi (sinh viên)")
def my_record(student: User = Depends(student_user), app: Container = Depends(container)) -> dict:
    return {
        "student_code": student.student_code,
        "record": _record_dict(app.lms.student_record(student.student_code)),
        "prerequisites": asdict(app.lms.prerequisite_status(student.student_code)),
    }


@router.get("/api/lms/students/{student_id}/record", summary="Bảng điểm của một sinh viên (GV phụ trách hoặc QTV)")
def student_record(student_id: int, viewer: User = Depends(staff_user), app: Container = Depends(container)) -> dict:
    if viewer.role not in (Role.LECTURER, Role.ADMIN):
        raise ForbiddenRoleError("Không có quyền xem")
    student = app.account_service.visible_student(viewer, student_id)
    return {
        "student_code": student.student_code,
        "record": _record_dict(app.lms.student_record(student.student_code)),
        "prerequisites": asdict(app.lms.prerequisite_status(student.student_code)),
    }
