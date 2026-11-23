"""Đọc chữ từ tệp quy chế tải lên (.md/.txt/.docx/.pdf) và nút "Tạo embedding" (``PolicyIngestService.embed_version``)."""

from __future__ import annotations

import io
import unicodedata
import zipfile
from datetime import date

import anyio
import pytest

from vin15.domain.exception import InvalidInputError, ResourceNotFoundError
from vin15.domain.model.policy import PolicyVersion, VersionStatus
from vin15.infrastructure.agent_api.agent_client import EmbeddingResult
from vin15.service.policy.policy_chunker import PolicyChunker
from vin15.service.policy.policy_file_reader import MAX_TEXT_CHARS, read_policy_file
from vin15.service.policy.policy_ingest_service import EMBEDDING_DIMENSIONS, PolicyIngestService

_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_NUMBERING = f"""<w:numbering {_W}><w:abstractNum w:abstractNumId="0">
<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="Điều %1."/></w:lvl>
<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%2."/></w:lvl>
<w:lvl w:ilvl="2"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%3)"/></w:lvl>
</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>"""


def _p(text: str, level: int | None = None) -> str:
    pr = "" if level is None else f'<w:pPr><w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="1"/></w:numPr></w:pPr>'
    return f'<w:p>{pr}<w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'


def _docx(*paragraphs: str, numbering: bool = True) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", f"<w:document {_W}><w:body>{''.join(paragraphs)}</w:body></w:document>")
        if numbering:
            archive.writestr("word/numbering.xml", _NUMBERING)
    return buffer.getvalue()


def test_plain_text_utf8_bom_crlf_and_nfc():
    decomposed = unicodedata.normalize("NFD", "Điều 1. Phạm vi")
    assert read_policy_file("quy-che.MD", ("﻿" + decomposed + "\r\n\r\n\r\n\r\nnội dung  ").encode()) == "Điều 1. Phạm vi\n\nnội dung"


def test_plain_text_must_be_utf8():
    with pytest.raises(InvalidInputError, match="UTF-8"):
        read_policy_file("a.txt", "Điều".encode("utf-16-le"))


def test_docx_rebuilds_automatic_numbering_for_the_chunker():
    data = _docx(
        _p("QUY CHẾ THỰC TẬP"),
        _p("Phạm vi", 0), _p("Áp dụng cho sinh viên chính quy.", 1), _p("Không áp dụng cho học viên.", 1),
        _p("Thời gian", 0), _p("Tối thiểu 8 tuần.", 1), _p("trong học kỳ chính", 2), _p("trong học kỳ hè", 2),
    )  # fmt: skip
    text = read_policy_file("qc.docx", data)
    assert text.splitlines() == [
        "QUY CHẾ THỰC TẬP", "Điều 1. Phạm vi", "1. Áp dụng cho sinh viên chính quy.", "2. Không áp dụng cho học viên.",
        "Điều 2. Thời gian", "1. Tối thiểu 8 tuần.", "a) trong học kỳ chính", "b) trong học kỳ hè",
    ]  # fmt: skip
    assert [c.article_no for c in PolicyChunker().chunk(text)] == ["1", "2"]


def test_docx_without_numbering_keeps_typed_prefixes():
    assert read_policy_file("qc.docx", _docx(_p("Điều 3. A"), _p("1. x"), numbering=False)) == "Điều 3. A\n1. x"


@pytest.mark.parametrize(
    ("name", "data", "message"),
    [
        ("qc.doc", b"\xd0\xcf\x11\xe0", ".docx"),
        ("qc.exe", b"MZ", "Chỉ nhận"),
        ("qc.docx", b"not a zip", "docx"),
        ("qc.pdf", b"not a pdf", "PDF"),
        ("qc.txt", b"", "rỗng"),
        ("qc.txt", b"   \n  ", "Không đọc được chữ"),
    ],
)
def test_rejects_unsupported_or_broken_files(name, data, message):
    with pytest.raises(InvalidInputError, match=message):
        read_policy_file(name, data)


def test_pdf_without_text_layer_is_rejected():
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(InvalidInputError, match="OCR"):
        read_policy_file("scan.pdf", buffer.getvalue())


def test_text_too_long_is_rejected():
    with pytest.raises(InvalidInputError, match="dài quá"):
        read_policy_file("a.txt", b"a" * (MAX_TEXT_CHARS + 1))


# ---------------------------------------------------------------- PolicyIngestService ----
class FakeRepo:
    def __init__(self, missing: int):
        self.missing = [(i, f"Điều {i}", "nội dung") for i in range(1, missing + 1)]
        self.saved: list[int] = []

    def get_version(self, version_id):
        if version_id != 7:
            return None
        n = 3
        return PolicyVersion(7, 1, "QD", "Quy chế", "v1", date(2026, 1, 1), None, VersionStatus.DRAFT, False, n, n - len(self.missing) + len(self.saved))

    def chunks_missing_embedding(self, version_id):
        return [c for c in self.missing if c[0] not in self.saved]

    def set_embeddings(self, items, model):
        self.saved += [chunk_id for chunk_id, _v in items]


class FakeAgent:
    def __init__(self, enabled=True):
        self.enabled = enabled

    async def embed(self, texts):
        return EmbeddingResult("m", [[0.0] * EMBEDDING_DIMENSIONS for _ in texts])


def test_extract_counts_chunks_or_returns_warning():
    service = PolicyIngestService(FakeRepo(0), FakeAgent())
    ok = service.extract("a.md", "Điều 1. A\nnội dung".encode())
    assert ok.chunk_count == 1 and ok.warning is None
    unstructured = service.extract("a.md", "chỉ là một đoạn văn".encode())
    assert unstructured.chunk_count == 0 and unstructured.warning and unstructured.text == "chỉ là một đoạn văn"


def test_embed_version_fills_missing_embeddings():
    repo = FakeRepo(2)
    result = anyio.run(PolicyIngestService(repo, FakeAgent()).embed_version, 7)
    assert result.embedded_now == 2 and result.agent_enabled and result.version.embedded_count == 3 and repo.saved == [1, 2]


def test_embed_version_without_agent_and_unknown_version():
    result = anyio.run(PolicyIngestService(FakeRepo(2), FakeAgent(enabled=False)).embed_version, 7)
    assert result.embedded_now == 0 and result.agent_enabled is False
    with pytest.raises(ResourceNotFoundError):
        anyio.run(PolicyIngestService(FakeRepo(0), FakeAgent()).embed_version, 99)
