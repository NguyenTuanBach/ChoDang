"""Thân yêu cầu REST của nghiệp vụ thực tập. Phản hồi trả về dict (FastAPI tự mã hóa ngày giờ)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class InviteItemBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(default="", max_length=200)
    student_code: str | None = Field(default=None, max_length=40)


class InviteBody(BaseModel):
    role: Literal["lecturer", "student"]
    items: list[InviteItemBody] = Field(min_length=1, max_length=200)
    #: Chỉ QTV khi mời sinh viên: giảng viên phụ trách. GV mời thì mặc định là chính GV.
    lecturer_id: int | None = None


class ReasonBody(BaseModel):
    reason: str = Field(default="", max_length=2000)


class AdvisorBody(BaseModel):
    lecturer_id: int


class StudentCodeBody(BaseModel):
    student_code: str = Field(min_length=1, max_length=40)


class InternshipDraftBody(BaseModel):
    company_name: str | None = Field(default=None, max_length=300)
    company_tax_code: str | None = Field(default=None, max_length=20)
    company_address: str | None = Field(default=None, max_length=500)
    position: str | None = Field(default=None, max_length=200)
    mentor_name: str | None = Field(default=None, max_length=200)
    mentor_email: str | None = Field(default=None, max_length=254)
    mentor_phone: str | None = Field(default=None, max_length=30)
    job_description: str | None = Field(default=None, max_length=5000)
    start_date: date | None = None
    end_date: date | None = None
    mode: Literal["onsite", "remote", "hybrid"] | None = None
    #: Từng trường do AI gợi ý đã được SV xác nhận: ``{"company_name": "ai_confirmed"}``.
    confirmations: dict[str, Literal["ai_confirmed", "manual"]] = Field(default_factory=dict)


class DecisionBody(BaseModel):
    action: Literal["confirm", "request_revision", "reject"]
    reason: str = Field(default="", max_length=2000)


class OutlineBody(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    outcome_codes: list[str] = Field(default_factory=list, max_length=50)


class OutlineDecisionBody(BaseModel):
    action: Literal["approve", "request_revision", "reject"]
    reason: str = Field(default="", max_length=2000)


class PlanItemBody(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    done: bool = False


class JournalBody(BaseModel):
    week_start: date
    content: str = Field(min_length=1, max_length=10000)
    plan_items: list[PlanItemBody] = Field(default_factory=list, max_length=20)
    blockers: str = Field(default="", max_length=2000)
    #: Gợi ý lịch do AI (lấy từ ``/api/student/journal/ai-advice``); để trống nếu sinh viên không hỏi.
    ai_advice: str = Field(default="", max_length=3000)


class JournalItemsBody(BaseModel):
    plan_items: list[PlanItemBody] = Field(max_length=20)


class JournalAdviceBody(BaseModel):
    content: str = Field(default="", max_length=10000)
    plan_items: list[PlanItemBody] = Field(default_factory=list, max_length=20)
    blockers: str = Field(default="", max_length=2000)


class CommentBody(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)


class ExtensionBody(BaseModel):
    milestone_code: Literal["M1", "M2", "M3", "M4", "M5"]
    new_due_date: date
    reason: str = Field(min_length=1, max_length=2000)


class ExceptionBody(BaseModel):
    type_code: str = Field(min_length=1, max_length=60)
    reason: str = Field(min_length=1, max_length=2000)


class RequestDecisionBody(BaseModel):
    approve: bool
    reason: str = Field(default="", max_length=2000)


class AssessBody(BaseModel):
    passed: bool
    note: str = Field(default="", max_length=2000)


class CreditDecisionBody(BaseModel):
    approve: bool
    reason: str = Field(default="", max_length=2000)


class ExceptionTypeBody(BaseModel):
    code: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    affects_credit: bool = False
    active: bool = True


class MilestoneTemplateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    anchor: Literal["start", "mid", "end"]
    offset_days: int = Field(ge=-365, le=365)


class OutcomeBody(BaseModel):
    cohort: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1, max_length=1000)


class FlagChangeBody(BaseModel):
    action: Literal["acknowledge", "resolve", "dismiss"]
    reason: str = Field(default="", max_length=2000)


class PreReviewBody(BaseModel):
    subject_kind: Literal["outline", "milestone"]
    subject_id: int


class CourseBody(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    credits: int = Field(ge=1, le=30)
    kind: Literal["regular", "internship"] = "regular"


class PrerequisiteBody(BaseModel):
    required_course_code: str = Field(min_length=1, max_length=20)
    min_score: float = Field(default=5.0, ge=0, le=10)


class LmsStudentBody(BaseModel):
    student_code: str = Field(min_length=1, max_length=40)
    full_name: str = Field(default="", max_length=200)


class GradeBody(BaseModel):
    student_code: str = Field(min_length=1, max_length=40)
    course_code: str = Field(min_length=1, max_length=20)
    score: float = Field(ge=0, le=10)
    term: str = Field(default="", max_length=40)
