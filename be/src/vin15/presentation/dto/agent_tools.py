"""Phản hồi của ``/api/agent-tools/*`` (hợp đồng: .kiro/specs/agent-hoi-dap/contract.md mục 5). Chỉ chứa trường tối thiểu."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from vin15.domain.model.policy import PolicyChunk, PolicyChunkLookup, PolicySearchResult
from vin15.service.credit.credit_checklist_service import CreditChecklist
from vin15.service.internship.internship_read_service import InternshipResult, MilestonesResult, ProgressResult, RequestsResult


class PolicySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    query_vector: list[float] | None = None
    top_k: int = Field(default=5, ge=1, le=8)


class ChunkDto(BaseModel):
    chunk_id: str
    doc_code: str
    doc_title: str
    version: str
    article_no: str
    clause_no: str | None
    heading: str
    text: str
    effective_from: date
    effective_to: date | None
    is_sample: bool
    score: float | None

    @classmethod
    def of(cls, chunk: PolicyChunk) -> ChunkDto:
        return cls(
            chunk_id=chunk.chunk_id,
            doc_code=chunk.doc_code,
            doc_title=chunk.doc_title,
            version=chunk.version,
            article_no=chunk.article_no,
            clause_no=chunk.clause_no,
            heading=chunk.heading,
            text=chunk.text,
            effective_from=chunk.effective_from,
            effective_to=chunk.effective_to,
            is_sample=chunk.is_sample,
            score=chunk.score,
        )


class PolicySearchResponse(BaseModel):
    status: str
    mode: str
    chunks: list[ChunkDto]

    @classmethod
    def of(cls, result: PolicySearchResult) -> PolicySearchResponse:
        return cls(status=result.status, mode=result.mode, chunks=[ChunkDto.of(c) for c in result.chunks])


class ChunkLookupResponse(BaseModel):
    chunk: ChunkDto
    neighbors: list[ChunkDto]

    @classmethod
    def of(cls, lookup: PolicyChunkLookup) -> ChunkLookupResponse:
        return cls(chunk=ChunkDto.of(lookup.chunk), neighbors=[ChunkDto.of(c) for c in lookup.neighbors])


class _Availability(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    available: bool
    reason: str | None = None


class InternshipDto(BaseModel):
    cohort: str
    status: str
    start_date: date | None
    end_date: date | None
    mode: str
    lecturer_name: str | None


class MeInternshipResponse(_Availability):
    internship: InternshipDto | None = None

    @classmethod
    def of(cls, result: InternshipResult) -> MeInternshipResponse:
        record = result.internship
        dto = (
            InternshipDto(
                cohort=record.cohort,
                status=record.status,
                start_date=record.start_date,
                end_date=record.end_date,
                mode=record.mode,
                lecturer_name=record.lecturer_name,
            )
            if record
            else None
        )
        return cls(available=result.available, reason=result.reason, internship=dto)


class MilestoneDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    due_date: date
    status: str
    days_left: int
    next_action: str


class MeMilestonesResponse(_Availability):
    milestones: list[MilestoneDto]

    @classmethod
    def of(cls, result: MilestonesResult) -> MeMilestonesResponse:
        return cls(available=result.available, reason=result.reason, milestones=[MilestoneDto.model_validate(m) for m in result.milestones])


class JournalDto(BaseModel):
    submitted: int
    expected: int
    missing_weeks: list[date]


class EvidenceDto(BaseModel):
    submitted: int
    required: int


class MeProgressResponse(_Availability):
    journal: JournalDto
    evidence: EvidenceDto

    @classmethod
    def of(cls, result: ProgressResult) -> MeProgressResponse:
        journal, evidence = result.journal, result.evidence
        return cls(
            available=result.available,
            reason=result.reason,
            journal=JournalDto(submitted=journal.submitted, expected=journal.expected, missing_weeks=journal.missing_weeks),
            evidence=EvidenceDto(submitted=evidence.submitted, required=evidence.required),
        )


class CreditItemDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    label: str
    met: bool
    value: str
    threshold: str


class MeCreditChecklistResponse(_Availability):
    items: list[CreditItemDto]
    all_met: bool

    @classmethod
    def of(cls, result: CreditChecklist) -> MeCreditChecklistResponse:
        return cls(
            available=result.available,
            reason=result.reason,
            items=[CreditItemDto.model_validate(i) for i in result.items],
            all_met=result.all_met,
        )


class RequestDto(BaseModel):
    kind: str
    status: str
    created_at: datetime


class MeRequestsResponse(_Availability):
    requests: list[RequestDto]

    @classmethod
    def of(cls, result: RequestsResult) -> MeRequestsResponse:
        return cls(
            available=result.available,
            reason=result.reason,
            requests=[RequestDto(kind=r.kind, status=r.status, created_at=r.created_at) for r in result.requests],
        )


# ---- Tool của giảng viên/quản trị viên (chỉ-đọc, trường tối thiểu: không email/SĐT/MST) ----
class _FromObject(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StaffQueueItemDto(_FromObject):
    kind: str
    internship_id: int
    student_name: str
    title: str
    since: date | None
    due_date: date | None
    severity: str | None
    priority: int


class StaffQueueResponse(_FromObject):
    total: int
    items: list[StaffQueueItemDto]


class StaffFlagDto(_FromObject):
    id: int
    internship_id: int
    student_name: str
    kind: str
    severity: str
    status: str
    reason: str
    created_at: date | None


class StaffFlagsResponse(_FromObject):
    total: int
    items: list[StaffFlagDto]


class StaffDashboardResponse(_FromObject):
    scope: str
    active_internships: int
    late_internships: int
    internships_by_status: dict[str, int]
    milestones_by_status: dict[str, int]
    open_flags_by_severity: dict[str, int]
    credit_outcomes: dict[str, int]


class StaffInternshipDto(_FromObject):
    id: int
    cohort: str
    status: str
    student_name: str
    company_name: str
    start_date: date | None
    end_date: date | None
    overdue_milestones: int
    submitted_milestones: int
    open_flags: int


class StaffInternshipsResponse(_FromObject):
    total: int
    items: list[StaffInternshipDto]
