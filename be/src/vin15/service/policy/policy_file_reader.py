"""Đọc văn bản thuần từ tệp quy chế tải lên: ``.md``/``.txt`` (UTF-8), ``.docx``, ``.pdf`` (có lớp chữ).

Chỉ đọc chữ, không lưu tệp: văn bản trả về được điền vào ô "Nội dung" để quản trị viên xem/sửa rồi mới nạp như văn bản dán tay
(tách Điều/Khoản → bản nháp → xem trước → xuất bản). PDF scan (ảnh, không có lớp chữ) bị từ chối vì chưa có OCR.

DOCX: đọc ``word/document.xml`` theo thứ tự đoạn; đoạn đánh số tự động (``w:numPr``) được dựng lại số theo ``word/numbering.xml``
(ví dụ "Điều %1." → "Điều 3.", "%1." → "2.", "%1)" → "a)") vì bộ tách đoạn dựa vào các tiền tố đó.
"""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from xml.etree import ElementTree

from vin15.domain.exception import InvalidInputError

#: Kích thước tệp tải lên tối đa.
MAX_FILE_BYTES = 10 * 1024 * 1024
#: Giới hạn kích thước giải nén của một phần trong DOCX (chống zip bomb).
_MAX_DOCX_PART_BYTES = 30 * 1024 * 1024
_MAX_PDF_PAGES = 500
#: Khớp giới hạn ``text`` của yêu cầu nạp.
MAX_TEXT_CHARS = 500_000

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_EXTENSIONS = (".md", ".markdown", ".txt", ".docx", ".pdf")


def read_policy_file(filename: str, data: bytes) -> str:
    """Trả văn bản đã chuẩn hóa (NFC, xuống dòng ``\\n``). ``InvalidInputError`` nếu định dạng không hỗ trợ hoặc không đọc được."""
    name = (filename or "").lower().strip()
    if not data:
        raise InvalidInputError("Tệp rỗng")
    if name.endswith(".docx"):
        text = _read_docx(data)
    elif name.endswith(".pdf"):
        text = _read_pdf(data)
    elif name.endswith((".md", ".markdown", ".txt")):
        text = _read_plain(data)
    else:
        raise InvalidInputError(f"Chỉ nhận tệp {', '.join(_EXTENSIONS)} (tệp .doc cũ: mở bằng Word rồi lưu lại thành .docx)")
    text = _normalize(text)
    if not text:
        raise InvalidInputError("Không đọc được chữ nào trong tệp")
    if len(text) > MAX_TEXT_CHARS:
        raise InvalidInputError(f"Văn bản dài quá {MAX_TEXT_CHARS:,} ký tự; hãy tách thành nhiều văn bản")
    return text


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", ""))
    lines = [line.rstrip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _read_plain(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise InvalidInputError("Tệp văn bản phải mã hóa UTF-8") from error


# ------------------------------------------------------------------ PDF ----
def _read_pdf(data: bytes) -> str:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise InvalidInputError("PDF có mật khẩu; hãy bỏ mật khẩu rồi tải lại")
        if len(reader.pages) > _MAX_PDF_PAGES:
            raise InvalidInputError(f"PDF quá {_MAX_PDF_PAGES} trang")
        pages = [page.extract_text() or "" for page in reader.pages]
    except InvalidInputError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as error:
        raise InvalidInputError("Không đọc được tệp PDF (hỏng hoặc không đúng định dạng)") from error
    text = "\n".join(pages)
    if not text.strip():
        raise InvalidInputError("PDF không có lớp chữ (bản scan); hệ thống chưa hỗ trợ OCR, hãy dùng bản Word/PDF gốc")
    return text


# ------------------------------------------------------------------ DOCX ----
def _read_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            document = _part(archive, "word/document.xml")
            if document is None:
                raise InvalidInputError("Tệp .docx thiếu nội dung (word/document.xml)")
            numbering = _Numbering(_part(archive, "word/numbering.xml"))
            root = ElementTree.fromstring(document)
    except zipfile.BadZipFile as error:
        raise InvalidInputError("Không đọc được tệp .docx (hỏng hoặc không đúng định dạng)") from error
    except ElementTree.ParseError as error:
        raise InvalidInputError("Tệp .docx có nội dung XML lỗi") from error
    body = root.find(f"{_W}body")
    if body is None:
        return ""
    lines: list[str] = []
    for paragraph in body.iter(f"{_W}p"):
        text = _paragraph_text(paragraph)
        prefix = numbering.next_label(paragraph)
        if prefix and text.strip():
            text = f"{prefix} {text.lstrip()}"
        lines.append(text)
    return "\n".join(lines)


def _part(archive: zipfile.ZipFile, name: str) -> bytes | None:
    try:
        info = archive.getinfo(name)
    except KeyError:
        return None
    if info.file_size > _MAX_DOCX_PART_BYTES:
        raise InvalidInputError("Tệp .docx quá lớn sau khi giải nén")
    return archive.read(info)


def _paragraph_text(paragraph: ElementTree.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter():
        if node.tag == f"{_W}t" and node.text:
            parts.append(node.text)
        elif node.tag == f"{_W}tab":
            parts.append("\t")
        elif node.tag in (f"{_W}br", f"{_W}cr"):
            parts.append("\n")
    return "".join(parts)


def _format_number(value: int, fmt: str) -> str:
    if fmt in ("lowerLetter", "upperLetter"):
        letters, n = "", value
        while n > 0:
            n, rem = divmod(n - 1, 26)
            letters = chr(ord("a") + rem) + letters
        return letters.upper() if fmt == "upperLetter" else letters
    if fmt in ("lowerRoman", "upperRoman"):
        roman = _roman(value)
        return roman if fmt == "upperRoman" else roman.lower()
    return str(value)  # decimal và các kiểu khác


def _roman(value: int) -> str:
    out = ""
    for number, symbol in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")):
        while value >= number:
            out += symbol
            value -= number
    return out


class _Numbering:
    """Dựng lại nhãn số của đoạn đánh số tự động: đếm theo (numId, ilvl), cấp sâu hơn đặt lại khi cấp trên tăng."""

    def __init__(self, xml: bytes | None):
        #: numId -> {ilvl: (numFmt, lvlText, start)}
        self._levels: dict[str, dict[int, tuple[str, str, int]]] = {}
        self._counters: dict[str, dict[int, int]] = {}
        if not xml:
            return
        try:
            root = ElementTree.fromstring(xml)
        except ElementTree.ParseError:
            return
        abstract: dict[str, dict[int, tuple[str, str, int]]] = {}
        for node in root.findall(f"{_W}abstractNum"):
            levels: dict[int, tuple[str, str, int]] = {}
            for lvl in node.findall(f"{_W}lvl"):
                ilvl = int(lvl.get(f"{_W}ilvl", "0"))
                levels[ilvl] = (_val(lvl, "numFmt") or "decimal", _val(lvl, "lvlText") or "", int(_val(lvl, "start") or "1"))
            abstract[node.get(f"{_W}abstractNumId", "")] = levels
        for num in root.findall(f"{_W}num"):
            ref = _val(num, "abstractNumId")
            if ref in abstract:
                self._levels[num.get(f"{_W}numId", "")] = abstract[ref]

    def next_label(self, paragraph: ElementTree.Element) -> str | None:
        num_pr = paragraph.find(f"{_W}pPr/{_W}numPr")
        if num_pr is None:
            return None
        num_id = _val(num_pr, "numId")
        ilvl = int(_val(num_pr, "ilvl") or "0")
        levels = self._levels.get(num_id or "")
        if not levels or ilvl not in levels:
            return None
        fmt, template, start = levels[ilvl]
        if fmt in ("bullet", "none") or not template:
            return "-" if fmt == "bullet" else None
        counters = self._counters.setdefault(num_id or "", {})
        counters[ilvl] = counters.get(ilvl, start - 1) + 1
        for deeper in [k for k in counters if k > ilvl]:
            del counters[deeper]

        def level_value(match: re.Match[str]) -> str:
            level = int(match.group(1)) - 1
            level_fmt, _t, level_start = levels.get(level, ("decimal", "", 1))
            return _format_number(counters.get(level, level_start), level_fmt)

        return re.sub(r"%(\d)", level_value, template)


def _val(node: ElementTree.Element, child: str) -> str | None:
    found = node.find(f"{_W}{child}")
    return None if found is None else found.get(f"{_W}val")
