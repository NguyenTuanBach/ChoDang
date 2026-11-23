"""Mô hình kho văn bản quy định: văn bản -> phiên bản -> đoạn (chunk)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class VersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class ChunkDraft:
    """Đoạn mới tách từ văn bản, chưa lưu."""

    ordinal: int
    article_no: str
    clause_no: str | None
    heading: str
    text: str


@dataclass(frozen=True)
class PolicyVersion:
    id: int
    document_id: int
    doc_code: str
    doc_title: str
    version_label: str
    effective_from: date
    effective_to: date | None
    status: VersionStatus
    is_sample: bool
    chunk_count: int = 0
    #: Số đoạn đã có embedding (còn thiếu thì đoạn đó chỉ tìm được bằng từ khóa).
    embedded_count: int = 0


@dataclass(frozen=True)
class PolicyChunk:
    """Đoạn quy định trả cho agent. ``chunk_id`` ổn định, đọc được: ``<mã>@<nhãn bản>/d<điều>[/k<khoản>]``."""

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
    score: float | None = None


@dataclass(frozen=True)
class PolicySearchResult:
    #: ``ok`` hoặc ``no_match``.
    status: str
    #: ``hybrid`` (có vector truy vấn) hoặc ``keyword``.
    mode: str
    chunks: list[PolicyChunk] = field(default_factory=list)


@dataclass(frozen=True)
class PolicyChunkLookup:
    chunk: PolicyChunk
    neighbors: list[PolicyChunk] = field(default_factory=list)


def make_chunk_id(doc_code: str, version_label: str, article_no: str, clause_no: str | None) -> str:
    base = f"{doc_code}@{version_label}/d{article_no}"
    return f"{base}/k{clause_no}" if clause_no else base
