"""``/api/agent-tools/*``: công cụ **chỉ-đọc** cho agent (hợp đồng: .kiro/specs/agent-hoi-dap/contract.md mục 5).

Xác thực: service token + ``X-On-Behalf-Of`` (agent-token), hoặc người dùng mặc định ở dev. Không endpoint nào nhận tham số chủ thể.
Chỉ GET, ngoại trừ POST tìm kiếm quy định (không có tác dụng phụ ngoài audit). Lỗi trả ``{"error": {"code", "message"}}`` đúng hợp đồng.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from vin15.config.container import Container
from vin15.domain.exception import (
    AuthenticationRequiredError,
    DatabaseUnavailableError,
    ForbiddenRoleError,
    InvalidInputError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from vin15.domain.model.agent_tool import AgentToolSubject
from vin15.presentation.dto.agent_tools import (
    ChunkLookupResponse,
    MeCreditChecklistResponse,
    MeInternshipResponse,
    MeMilestonesResponse,
    MeProgressResponse,
    MeRequestsResponse,
    PolicySearchRequest,
    PolicySearchResponse,
)

from .dependencies import agent_subject, container

#: Thứ tự quan trọng: lớp con trước lớp cha.
_ERRORS: tuple[tuple[type[Exception], int, str], ...] = (
    (AuthenticationRequiredError, 401, "authentication_required"),
    (ForbiddenRoleError, 403, "forbidden_role"),
    (PermissionDeniedError, 403, "permission_denied"),
    (ResourceNotFoundError, 404, "not_found"),
    (InvalidInputError, 422, "invalid_input"),
    (DatabaseUnavailableError, 503, "database_unavailable"),
)


class AgentToolsRoute(APIRoute):
    """Trả lỗi domain theo hợp đồng của agent: ``{"error": {"code", "message"}}`` (khác định dạng phẳng của các API thường)."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except Exception as error:
                for exc_type, status, code in _ERRORS:
                    if isinstance(error, exc_type):
                        return JSONResponse(status_code=status, content={"error": {"code": code, "message": str(error)}})
                raise

        return handler


router = APIRouter(prefix="/api/agent-tools", tags=["Agent tools"], route_class=AgentToolsRoute)


@router.post("/policy/search", response_model=PolicySearchResponse, summary="Tìm quy định đang hiệu lực (từ khóa + vector)")
def search_policy(
    body: PolicySearchRequest, subject: AgentToolSubject = Depends(agent_subject), app: Container = Depends(container)
) -> PolicySearchResponse:
    return PolicySearchResponse.of(app.agent_tool_service.policy_search(subject, body.query, body.query_vector, body.top_k))


@router.get("/policy/chunks/{chunk_id:path}", response_model=ChunkLookupResponse, summary="Nguyên văn một đoạn quy định đang hiệu lực")
def get_policy_chunk(
    chunk_id: str, with_neighbors: bool = False, subject: AgentToolSubject = Depends(agent_subject), app: Container = Depends(container)
) -> ChunkLookupResponse:
    return ChunkLookupResponse.of(app.agent_tool_service.policy_chunk(subject, chunk_id, with_neighbors))


@router.get("/me/internship", response_model=MeInternshipResponse, summary="Hồ sơ thực tập của người hỏi")
def my_internship(subject: AgentToolSubject = Depends(agent_subject), app: Container = Depends(container)) -> MeInternshipResponse:
    return MeInternshipResponse.of(app.agent_tool_service.my_internship(subject))


@router.get("/me/milestones", response_model=MeMilestonesResponse, summary="Các mốc của người hỏi")
def my_milestones(subject: AgentToolSubject = Depends(agent_subject), app: Container = Depends(container)) -> MeMilestonesResponse:
    return MeMilestonesResponse.of(app.agent_tool_service.my_milestones(subject))


@router.get("/me/progress", response_model=MeProgressResponse, summary="Tiến độ nhật ký và minh chứng của người hỏi")
def my_progress(subject: AgentToolSubject = Depends(agent_subject), app: Container = Depends(container)) -> MeProgressResponse:
    return MeProgressResponse.of(app.agent_tool_service.my_progress(subject))


@router.get("/me/credit-checklist", response_model=MeCreditChecklistResponse, summary="Bảng điều kiện tín chỉ T1-T6 do BE tính")
def my_credit_checklist(
    subject: AgentToolSubject = Depends(agent_subject), app: Container = Depends(container)
) -> MeCreditChecklistResponse:
    return MeCreditChecklistResponse.of(app.agent_tool_service.my_credit_checklist(subject))


@router.get("/me/requests", response_model=MeRequestsResponse, summary="Yêu cầu gia hạn/ngoại lệ của người hỏi")
def my_requests(subject: AgentToolSubject = Depends(agent_subject), app: Container = Depends(container)) -> MeRequestsResponse:
    return MeRequestsResponse.of(app.agent_tool_service.my_requests(subject))
