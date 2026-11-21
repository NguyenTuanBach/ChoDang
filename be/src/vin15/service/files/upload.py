"""Kiểm tệp tải lên bằng chữ ký byte đầu (không tin đuôi tệp hay Content-Type do client gửi), rồi lưu qua ``FileStorage``.

Tên tệp gốc chỉ để hiển thị; khóa lưu là chuỗi ngẫu nhiên nên không lộ nội dung/định danh.
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass

from vin15.domain.exception import InvalidInputError
from vin15.domain.ports import FileStorage

PDF, PNG, JPEG, DOCX = "application/pdf", "image/png", "image/jpeg", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
RECEIPT_TYPES = frozenset({PDF, PNG, JPEG})
EVIDENCE_TYPES = frozenset({PDF, PNG, JPEG, DOCX})


@dataclass(frozen=True)
class StoredFile:
    key: str
    filename: str
    mime: str
    size: int
    sha256: str


def sniff_mime(data: bytes, filename: str) -> str | None:
    """Loại tệp thật theo chữ ký byte; ``None`` nếu không nhận ra."""
    if data.startswith(b"%PDF-"):
        return PDF
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if data.startswith(b"\xff\xd8\xff"):
        return JPEG
    if data.startswith(b"PK\x03\x04") and filename.lower().endswith(".docx") and b"word/" in data[:200_000]:
        return DOCX
    return None


def safe_filename(name: str) -> str:
    base = os.path.basename(name or "").strip()
    base = re.sub(r"[^\w.\- ()]", "_", base, flags=re.UNICODE)
    return (base or "tep")[:120]


def store_upload(storage: FileStorage, prefix: str, filename: str, data: bytes, allowed: frozenset[str], max_bytes: int) -> StoredFile:
    if not data:
        raise InvalidInputError("Tệp rỗng")
    if len(data) > max_bytes:
        raise InvalidInputError(f"Tệp vượt quá {max_bytes // (1024 * 1024)} MB")
    mime = sniff_mime(data, filename)
    if mime is None or mime not in allowed:
        raise InvalidInputError("Loại tệp không được chấp nhận (chỉ PDF, PNG, JPG" + (", DOCX" if DOCX in allowed else "") + ")")
    key = f"{prefix}/{uuid.uuid4().hex}"
    storage.put(key, data, mime)
    return StoredFile(key, safe_filename(filename), mime, len(data), hashlib.sha256(data).hexdigest())
