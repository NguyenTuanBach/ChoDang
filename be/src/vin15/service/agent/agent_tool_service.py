"""Các tool chỉ-đọc của agent. Mỗi lời gọi ghi **đúng một** ``audit_event`` (``actor_kind='agent'``), kể cả khi bị từ chối.

Chủ thể (``AgentToolSubject``) do BE quyết; tool không nhận tham số chủ thể nên không có đường lấy dữ liệu người khác.
Tool cá nhân (``me/*``) chỉ dành cho sinh viên; tool ``staff/*`` chỉ dành cho giảng viên/quản trị viên (phạm vi do BE quyết).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from vin15.domain.exception import ForbiddenRoleError
from vin15.domain.model.agent_tool import AgentToolSubject
from vin15.domain.model.audit import ActorKind, AuditEntry
from vin15.domain.model.policy import PolicyChunkLookup, PolicySearchResult
from vin15.domain.pii import PiiRedactor
from vin15.infrastructure.persistence.audit_repository import AuditRepository
from vin15.service.agent.agent_staff_reads import (
    AgentStaffReads,
    DashboardResult,
    FlagsResult,
    InternshipsResult,
    QueueResult,
)
from vin15.service.credit.credit_checklist_service import CreditChecklist, CreditChecklistService
from vin15.service.internship.internship_read_service import (
    InternshipReadService,
    InternshipResult,
    MilestonesResult,
    ProgressResult,
    RequestsResult,
)
from vin15.service.policy.policy_search_service import PolicySearchService

T = TypeVar("T")

#: Mã lỗi khi vai trò không được dùng tool cá nhân.
FORBIDDEN_ROLE = "forbidden_role"
_MAX_LOGGED_QUERY_CHARS = 200


class AgentToolService:
    def __init__(
        self,
        search: PolicySearchService,
        reads: InternshipReadService,
        credit: CreditChecklistService,
        audit: AuditRepository,
        redactor: PiiRedactor,
        staff: Callable[[], AgentStaffReads],
    ):
        self._search = search
        self._reads = reads
        self._credit = credit
        self._audit = audit
        self._redactor = redactor
        # Dựng muộn: tool tra quy định/cá nhân không cần ReportService/MonitoringService (và kết nối DB của chúng).
        self._staff_factory = staff

    # ---- Tra quy định (mọi vai trò) ----
    def policy_search(self, subject: AgentToolSubject, query: str, query_vector: list[float] | None, top_k: int) -> PolicySearchResult:
        params = {
            "query": self._redactor.redact_text(query)[:_MAX_LOGGED_QUERY_CHARS],
            "top_k": top_k,
            "has_vector": query_vector is not None,
        }
        return self._run(subject, "search_policy", params, lambda: self._search.search(query, query_vector, top_k))

    def policy_chunk(self, subject: AgentToolSubject, chunk_id: str, with_neighbors: bool) -> PolicyChunkLookup:
        params = {"chunk_id": self._redactor.redact_text(chunk_id)[:_MAX_LOGGED_QUERY_CHARS], "with_neighbors": with_neighbors}
        return self._run(subject, "get_policy_clause", params, lambda: self._search.get_chunk(chunk_id, with_neighbors))

    # ---- Ngữ cảnh cá nhân (chỉ sinh viên) ----
    def my_internship(self, subject: AgentToolSubject) -> InternshipResult:
        return self._run(subject, "get_my_internship", {}, lambda: self._reads.internship(subject.user_id), student_only=True)

    def my_milestones(self, subject: AgentToolSubject) -> MilestonesResult:
        return self._run(subject, "get_my_milestones", {}, lambda: self._reads.milestones(subject.user_id), student_only=True)

    def my_progress(self, subject: AgentToolSubject) -> ProgressResult:
        return self._run(subject, "get_my_progress", {}, lambda: self._reads.progress(subject.user_id), student_only=True)

    def my_credit_checklist(self, subject: AgentToolSubject) -> CreditChecklist:
        return self._run(subject, "get_my_credit_checklist", {}, lambda: self._credit.checklist(subject.user_id), student_only=True)

    def my_requests(self, subject: AgentToolSubject) -> RequestsResult:
        return self._run(subject, "get_my_requests", {}, lambda: self._reads.requests(subject.user_id), student_only=True)

    # ---- Dữ liệu cho giảng viên/quản trị viên (phạm vi do BE quyết từ chủ thể) ----
    def staff_queue(self, subject: AgentToolSubject) -> QueueResult:
        return self._run(subject, "get_staff_queue", {}, lambda: self._staff_factory().queue(subject), staff_only=True)

    def staff_flags(self, subject: AgentToolSubject, status: str | None) -> FlagsResult:
        return self._run(subject, "list_risk_flags", {"status": status}, lambda: self._staff_factory().flags(subject, status), staff_only=True)

    def staff_dashboard(self, subject: AgentToolSubject, cohort: str | None) -> DashboardResult:
        return self._run(subject, "get_dashboard_summary", {"cohort": cohort}, lambda: self._staff_factory().dashboard(subject, cohort), staff_only=True)

    def staff_internships(
        self, subject: AgentToolSubject, status: str | None, overdue_only: bool, cohort: str | None, student: str | None = None
    ) -> InternshipsResult:
        params = {"status": status, "overdue_only": overdue_only, "cohort": cohort, "student": student}
        return self._run(
            subject, "list_internships", params, lambda: self._staff_factory().internships(subject, status, overdue_only, cohort, student), staff_only=True
        )

    # ---- Chung ----
    def _run(
        self, subject: AgentToolSubject, tool: str, params: dict, call: Callable[[], T], *, student_only: bool = False, staff_only: bool = False
    ) -> T:
        outcome = "ok"
        try:
            if student_only and subject.role != "student":
                raise ForbiddenRoleError("Tool này chỉ dành cho sinh viên: giảng viên và quản trị viên dùng tool tra quy định và tool dữ liệu phạm vi phụ trách")
            if staff_only and subject.role not in ("lecturer", "admin"):
                raise ForbiddenRoleError("Tool này chỉ dành cho giảng viên và quản trị viên")
            return call()
        except ForbiddenRoleError:
            outcome = FORBIDDEN_ROLE
            raise
        except Exception as error:
            outcome = type(error).__name__
            raise
        finally:
            self._audit.record(
                AuditEntry(
                    actor_kind=ActorKind.AGENT,
                    actor_id=subject.user_id,
                    actor_role=subject.role,
                    entity="agent_tool",
                    action=tool,
                    after={"params": params, "outcome": outcome},
                    reason=subject.audit_reason,
                )
            )
