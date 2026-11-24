"""Quản trị kho văn bản quy định: nạp (bản nháp), xem trước, xuất bản. **Chỉ vai trò quản trị viên** (HITL cho nội dung quy định)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from vin15.config.container import Container
from vin15.domain.exception import InvalidInputError, ResourceNotFoundError
from vin15.domain.model.user import User
from vin15.presentation.dto.policy_admin import (
    PolicyChunkPreview,
    PolicyEmbedResponse,
    PolicyExtractResponse,
    PolicyIngestRequest,
    PolicyIngestResponse,
    PolicyPreviewResponse,
    PolicyVersionDto,
)
from vin15.service.policy.policy_file_reader import MAX_FILE_BYTES

from .dependencies import admin_user, container

router = APIRouter(prefix="/api/admin/policies", tags=["Quy định (quản trị)"])


@router.get("", response_model=list[PolicyVersionDto], summary="Danh sách phiên bản văn bản quy định")
def list_versions(_admin: User = Depends(admin_user), app: Container = Depends(container)) -> list[PolicyVersionDto]:
    return [PolicyVersionDto.of(v) for v in app.policy_publish_service.list_versions()]


@router.post("", response_model=PolicyIngestResponse, status_code=201, summary="Nạp văn bản (tách Điều/Khoản, tạo bản nháp)")
async def ingest_policy(
    body: PolicyIngestRequest, _admin: User = Depends(admin_user), app: Container = Depends(container)
) -> PolicyIngestResponse:
    result = await app.policy_ingest_service.ingest(
        doc_code=body.code,
        doc_title=body.title,
        issuer=body.issuer,
        version_label=body.version_label,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        is_sample=body.is_sample,
        text=body.text,
    )
    return PolicyIngestResponse(
        version=PolicyVersionDto.of(result.version), chunk_count=result.chunk_count, embedded_count=result.embedded_count
    )


@router.post("/extract", response_model=PolicyExtractResponse, summary="Đọc chữ từ tệp quy chế (.md, .txt, .docx, .pdf), không lưu")
def extract_policy_file(
    file: UploadFile = File(...), _admin: User = Depends(admin_user), app: Container = Depends(container)
) -> PolicyExtractResponse:
    data = file.file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise InvalidInputError(f"Tệp vượt quá {MAX_FILE_BYTES // (1024 * 1024)} MB")
    filename = file.filename or ""
    result = app.policy_ingest_service.extract(filename, data)
    return PolicyExtractResponse(filename=filename, text=result.text, chunk_count=result.chunk_count, warning=result.warning)


@router.post("/versions/{version_id}/embed", response_model=PolicyEmbedResponse, summary="Tạo embedding cho các đoạn còn thiếu")
async def embed_version(version_id: int, _admin: User = Depends(admin_user), app: Container = Depends(container)) -> PolicyEmbedResponse:
    result = await app.policy_ingest_service.embed_version(version_id)
    return PolicyEmbedResponse(version=PolicyVersionDto.of(result.version), embedded_now=result.embedded_now, agent_enabled=result.agent_enabled)


@router.get("/versions/{version_id}", response_model=PolicyPreviewResponse, summary="Xem trước các đoạn đã tách")
def preview_version(version_id: int, _admin: User = Depends(admin_user), app: Container = Depends(container)) -> PolicyPreviewResponse:
    found = app.policy_publish_service.preview(version_id)
    if found is None:
        raise ResourceNotFoundError("Không tìm thấy phiên bản văn bản")
    version, chunks = found
    return PolicyPreviewResponse(version=PolicyVersionDto.of(version), chunks=[PolicyChunkPreview.of(c) for c in chunks])


@router.post("/versions/{version_id}/publish", response_model=PolicyVersionDto, summary="Xuất bản phiên bản (đóng hiệu lực bản cũ)")
def publish_version(version_id: int, admin: User = Depends(admin_user), app: Container = Depends(container)) -> PolicyVersionDto:
    return PolicyVersionDto.of(app.policy_publish_service.publish(version_id, admin.id, admin.role.value))
