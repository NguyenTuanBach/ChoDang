from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from vin15.domain.model.policy import PolicyChunk, PolicyVersion


class PolicyIngestRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64, description="Mã văn bản, ví dụ QD-TT-01")
    title: str = Field(min_length=1, max_length=300)
    issuer: str = Field(default="", max_length=200)
    version_label: str = Field(min_length=1, max_length=32, description="Nhãn phiên bản, ví dụ v2")
    effective_from: date
    effective_to: date | None = None
    is_sample: bool = False
    text: str = Field(min_length=1, max_length=500_000, description='Markdown/văn bản thuần theo cấu trúc "Điều N." / "Khoản M."')


class PolicyVersionDto(BaseModel):
    id: str
    doc_code: str
    doc_title: str
    version_label: str
    effective_from: date
    effective_to: date | None
    status: str
    is_sample: bool
    chunk_count: int

    @classmethod
    def of(cls, version: PolicyVersion) -> PolicyVersionDto:
        return cls(
            id=str(version.id),
            doc_code=version.doc_code,
            doc_title=version.doc_title,
            version_label=version.version_label,
            effective_from=version.effective_from,
            effective_to=version.effective_to,
            status=version.status.value,
            is_sample=version.is_sample,
            chunk_count=version.chunk_count,
        )


class PolicyIngestResponse(BaseModel):
    version: PolicyVersionDto
    chunk_count: int
    #: Số đoạn đã có embedding (0 nếu agent không khả dụng: chỉ tìm được bằng từ khóa).
    embedded_count: int


class PolicyChunkPreview(BaseModel):
    chunk_id: str
    article_no: str
    clause_no: str | None
    heading: str
    text: str

    @classmethod
    def of(cls, chunk: PolicyChunk) -> PolicyChunkPreview:
        return cls(chunk_id=chunk.chunk_id, article_no=chunk.article_no, clause_no=chunk.clause_no, heading=chunk.heading, text=chunk.text)


class PolicyPreviewResponse(BaseModel):
    version: PolicyVersionDto
    chunks: list[PolicyChunkPreview]
