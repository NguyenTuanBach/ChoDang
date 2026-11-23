"""Nạp văn bản quy định (Markdown/văn bản thuần): tách Điều/Khoản -> lưu bản nháp -> embedding qua agent."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import anyio.to_thread

from vin15.domain.exception import AgentUnavailableError, InvalidInputError, ResourceNotFoundError, StateConflictError
from vin15.domain.model.policy import PolicyVersion
from vin15.infrastructure.agent_api import AgentApiClient
from vin15.infrastructure.persistence.policy_repository import PolicyRepository

from .policy_chunker import PolicyChunker
from .policy_file_reader import read_policy_file

log = logging.getLogger(__name__)

#: Số đoạn gửi agent mỗi lần xin embedding.
EMBED_BATCH = 64
EMBEDDING_DIMENSIONS = 1536


@dataclass(frozen=True)
class IngestResult:
    version: PolicyVersion
    chunk_count: int
    embedded_count: int
    #: ``True`` nếu đã tạo phiên bản mới; ``False`` nếu phiên bản đã có (chạy lại, không ghi đè).
    created: bool


@dataclass(frozen=True)
class ExtractResult:
    """Văn bản đọc từ tệp tải lên (chưa lưu gì). ``chunk_count`` = số đoạn tách thử; 0 kèm ``warning`` nếu chưa đúng cấu trúc."""

    text: str
    chunk_count: int
    warning: str | None


@dataclass(frozen=True)
class EmbedResult:
    version: PolicyVersion
    #: Số đoạn vừa được tạo embedding ở lần gọi này.
    embedded_now: int
    #: ``False`` nếu BE không cấu hình agent (không tạo được embedding).
    agent_enabled: bool


class PolicyIngestService:
    def __init__(self, repository: PolicyRepository, agent: AgentApiClient, chunker: PolicyChunker | None = None):
        self._repo = repository
        self._agent = agent
        self._chunker = chunker or PolicyChunker()

    async def ingest(
        self,
        *,
        doc_code: str,
        doc_title: str,
        issuer: str = "",
        version_label: str,
        effective_from: date,
        effective_to: date | None = None,
        is_sample: bool = False,
        text: str,
    ) -> IngestResult:
        """Tạo bản ``draft`` (chưa tìm được cho tới khi xuất bản). Không có agent/embedding thì vẫn nạp, chỉ tìm bằng từ khóa."""
        drafts = self._chunker.chunk(text)  # InvalidInputError nếu sai cấu trúc
        version = await anyio.to_thread.run_sync(
            lambda: self._repo.create_draft(
                doc_code=doc_code.strip(),
                doc_title=doc_title.strip(),
                issuer=issuer.strip(),
                version_label=version_label.strip(),
                effective_from=effective_from,
                effective_to=effective_to,
                is_sample=is_sample,
                chunks=drafts,
            )
        )
        embedded = await self.embed_missing(version.id)
        return IngestResult(version, len(drafts), embedded, created=True)

    def extract(self, filename: str, data: bytes) -> ExtractResult:
        """Đọc chữ từ tệp quy chế và tách thử Điều/Khoản (không lưu). Sai cấu trúc vẫn trả văn bản để quản trị viên sửa tay."""
        text = read_policy_file(filename, data)
        try:
            return ExtractResult(text, len(self._chunker.chunk(text)), None)
        except InvalidInputError as error:
            return ExtractResult(text, 0, str(error))

    async def embed_version(self, version_id: int) -> EmbedResult:
        """Bù embedding còn thiếu của một phiên bản (nút "Tạo embedding" ở trang quản trị; cũng dùng sau khi agent hết lỗi)."""
        if await anyio.to_thread.run_sync(lambda: self._repo.get_version(version_id)) is None:
            raise ResourceNotFoundError("Không tìm thấy phiên bản văn bản")
        embedded = await self.embed_missing(version_id)
        version = await anyio.to_thread.run_sync(lambda: self._repo.get_version(version_id))
        assert version is not None
        return EmbedResult(version, embedded, self._agent.enabled)

    async def ensure(self, **kwargs) -> IngestResult:
        """Như :meth:`ingest` nhưng chạy lại được: phiên bản đã có thì không tạo lại, chỉ bù embedding còn thiếu."""
        existing = await anyio.to_thread.run_sync(lambda: self._repo.find_version(kwargs["doc_code"], kwargs["version_label"]))
        if existing is None:
            return await self.ingest(**kwargs)
        embedded = await self.embed_missing(existing.id)
        return IngestResult(existing, existing.chunk_count, embedded, created=False)

    async def embed_missing(self, version_id: int) -> int:
        """Xin agent embedding cho các đoạn chưa có. Trả số đoạn đã embed (0 nếu không có agent hoặc agent lỗi)."""
        if not self._agent.enabled:
            return 0
        pending = await anyio.to_thread.run_sync(lambda: self._repo.chunks_missing_embedding(version_id))
        done = 0
        for start in range(0, len(pending), EMBED_BATCH):
            batch = pending[start : start + EMBED_BATCH]
            try:
                result = await self._agent.embed([f"{heading}\n{text}" for _id, heading, text in batch])
            except AgentUnavailableError as error:
                log.warning("Không tạo được embedding (%s): các đoạn còn lại chỉ tìm bằng từ khóa", error)
                break
            if len(result.vectors) != len(batch) or any(len(v) != EMBEDDING_DIMENSIONS for v in result.vectors):
                raise StateConflictError(f"Agent trả embedding sai số lượng hoặc sai số chiều (cần {EMBEDDING_DIMENSIONS})")
            items = [(chunk_id, vector) for (chunk_id, _h, _t), vector in zip(batch, result.vectors, strict=True)]
            await anyio.to_thread.run_sync(lambda items=items, model=result.model: self._repo.set_embeddings(items, model))
            done += len(batch)
        return done
