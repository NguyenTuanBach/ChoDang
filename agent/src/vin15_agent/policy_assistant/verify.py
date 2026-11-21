"""Hậu kiểm câu trả lời bằng code tất định (không tin LLM): trích dẫn, số liệu, cụm cam kết, cảnh báo văn bản mẫu.

Tất cả thao tác theo từng câu: câu hỏng bị thay bằng mẫu cố định lấy từ ``prompts/refusals.md``.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any

from vin15_agent.policy_assistant.protocol import Citation

MAX_CITATIONS = 5
QUOTE_LIMIT = 1200

CITE_RE = re.compile(r"\[cite:([^\]\s]+)\]")
# Tách câu sau dấu kết câu + khoảng trắng, nhưng KHÔNG tách ngay trước thẻ [cite:...] (thẻ thuộc về câu đứng trước).
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?!\[cite:)")


_LEADING_MARKER = re.compile(r"^\s*(?:[-*+]\s*)?(?:\*\*)?\d+[.)]\s+")


def _segments(text: str) -> list[list[str]]:
    """Văn bản → các dòng, mỗi dòng là danh sách câu (số thứ tự đầu dòng "1." không tách thành một câu riêng)."""
    lines: list[list[str]] = []
    for line in text.split("\n"):
        marker = _LEADING_MARKER.match(line)
        prefix = marker.group(0) if marker else ""
        parts = _SENTENCE_SPLIT.split(line[len(prefix) :])
        parts[0] = prefix + parts[0]
        lines.append(parts)
    return lines


def _join(lines: list[list[str]]) -> str:
    out = "\n".join(" ".join(s for s in sentences if s) for sentences in lines)
    return re.sub(r"[ \t]+([,.;:!?])", r"\1", re.sub(r"[ \t]{2,}", " ", out)).strip()


def _replace_segments(text: str, decide) -> str:
    """Duyệt từng câu; ``decide(seg)`` trả chuỗi thay thế hoặc ``None`` để giữ. Các câu thay thế liền nhau (kể cả ở các dòng/mục liền kề) gộp thành một."""
    lines = _segments(text)
    previous_replacement: str | None = None
    for sentences in lines:
        for i, seg in enumerate(sentences):
            new = decide(seg)
            if new is None:
                if seg.strip():
                    previous_replacement = None
                continue
            sentences[i] = "" if new == previous_replacement else new
            previous_replacement = new if new else previous_replacement
    return re.sub(r"\n{3,}", "\n\n", _join(lines))


# ---------------------------------------------------------------- 6.1 trích dẫn


@dataclass
class CitationCheck:
    text: str
    cited_ids: list[str]
    dropped_ids: list[str] = field(default_factory=list)
    #: số câu bị thay vì mất hết trích dẫn hợp lệ
    stripped: int = 0


def verify_citations(text: str, seen_ids: Collection[str], *, limit: int = MAX_CITATIONS, no_basis_partial: str) -> CitationCheck:
    """Giữ ``[cite:id]`` với id ∈ ``seen_ids`` (tối đa ``limit`` id khác nhau); bỏ id lạ.

    Câu có trích dẫn nhưng không còn id hợp lệ nào bị thay bằng ``no_basis_partial``.
    """
    seen = set(seen_ids)
    cited: list[str] = []
    dropped: list[str] = []
    stripped = 0

    def decide(seg: str) -> str | None:
        nonlocal stripped
        ids = CITE_RE.findall(seg)
        if not ids:
            return None
        valid = [i for i in ids if i in seen]
        if not valid:
            dropped.extend(i for i in ids if i not in dropped)
            stripped += 1
            return no_basis_partial

        def keep(match: re.Match[str]) -> str:
            cid = match.group(1)
            if cid not in seen:
                if cid not in dropped:
                    dropped.append(cid)
                return ""
            if cid not in cited:
                if len(cited) >= limit:
                    return ""
                cited.append(cid)
            return match.group(0)

        return CITE_RE.sub(keep, seg)

    return CitationCheck(_replace_segments(text, decide), cited, dropped, stripped)


def build_citations(seen_chunks: dict[str, dict[str, Any]], cited_ids: Iterable[str]) -> list[Citation]:
    """Dựng ``citations`` của khung ``final`` từ kết quả tool (không từ chữ do LLM viết)."""
    out: list[Citation] = []
    for cid in cited_ids:
        c = seen_chunks.get(cid)
        if c is None:
            continue
        quote = str(c.get("text", ""))
        if len(quote) > QUOTE_LIMIT:
            quote = quote[: QUOTE_LIMIT - 1].rstrip() + "…"
        clause = c.get("clause_no")
        out.append(
            Citation(
                chunk_id=cid,
                doc_code=str(c.get("doc_code", "")),
                doc_title=str(c.get("doc_title", "")),
                version=str(c.get("version", "")),
                article=str(c.get("article_no", "")),
                clause=None if clause in (None, "") else str(clause),
                effective_from=str(c.get("effective_from", "")),
                is_sample=bool(c.get("is_sample", False)),
                quote=quote,
            )
        )
    return out


def sample_warning_needed(seen_chunks: dict[str, dict[str, Any]], cited_ids: Iterable[str]) -> bool:
    return any(bool(seen_chunks.get(cid, {}).get("is_sample")) for cid in cited_ids)


# ---------------------------------------------------------------- 6.2 số liệu

# Số trong câu trả lời: không dính chữ/mã (T1, M3, QC-01) ở trước. Nguồn lấy lỏng hơn (mọi dãy chữ số).
_ANSWER_NUMBER = re.compile(r"(?<![\w/@.\-])\d+(?:[.,]\d+)*")
_SOURCE_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]\s*)?(?:\*\*)?\d+[.)]\s")
_THOUSANDS = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


def _normalize_number(token: str) -> str:
    token = token.rstrip(".,")
    if _THOUSANDS.match(token):
        return token.replace(".", "")
    if "," in token and "." not in token:
        token = token.replace(",", ".")
    if token.isdigit():
        return str(int(token))
    return token


def extract_numbers(text: str, *, strict: bool = True) -> list[str]:
    text = CITE_RE.sub(" ", text)
    if strict:
        text = "\n".join(_LIST_MARKER.sub("", line) for line in text.split("\n"))
    pattern = _ANSWER_NUMBER if strict else _SOURCE_NUMBER
    return [_normalize_number(m) for m in pattern.findall(text)]


@dataclass
class NumberCheck:
    text: str
    blocked: int = 0
    bad_numbers: list[str] = field(default_factory=list)


def check_numbers(text: str, sources: Iterable[str], mismatch_notice: str) -> NumberCheck:
    """Mọi số/thời hạn trong câu trả lời phải có trong nguồn (chunk, kết quả tool, câu hỏi, hôm nay); câu lệch bị thay bằng thông báo."""
    allowed: set[str] = set()
    for source in sources:
        allowed.update(extract_numbers(source, strict=False))
    result = NumberCheck(text)

    def decide(seg: str) -> str | None:
        bad = [n for n in extract_numbers(seg) if n not in allowed]
        if not bad:
            return None
        result.blocked += 1
        result.bad_numbers.extend(n for n in bad if n not in result.bad_numbers)
        return mismatch_notice

    result.text = _replace_segments(text, decide)
    return result


def number_sources(seen_chunks: dict[str, dict[str, Any]], tool_texts: Iterable[str], extra: Iterable[str] = ()) -> list[str]:
    return [json.dumps(c, ensure_ascii=False, default=str) for c in seen_chunks.values()] + list(tool_texts) + list(extra)


# ---------------------------------------------------------------- 6.3 cam kết

_COMMITMENT_PATTERNS = [
    r"(?<!không )(?<!chưa )chắc chắn (?:sẽ |là )?(?:được |đã )?(?:duyệt|công nhận|chấp nhận|phê duyệt|đạt|đậu)",
    r"(?<!chưa )(?<!không )đã được (?:duyệt|công nhận|chấp nhận|phê duyệt|xác nhận|ghi nhận)",
    r"(?<!chưa )(?<!không )sẽ được (?:duyệt|công nhận|chấp nhận|phê duyệt)",
    r"(?:em|bạn|anh|chị) đã được\b",
    r"(?:đảm bảo|cam kết|hứa)(?: chắc chắn)?(?: sẽ| là| rằng)? (?:được |bạn |em )?(?:duyệt|công nhận|chấp nhận|phê duyệt|đạt)",
    r"(?:mình|tôi|trợ lý|tớ) (?:đã|sẽ) (?:nộp|duyệt|công nhận|ghi|gửi|tạo|chấp nhận|phê duyệt|cập nhật)",
]
_COMMITMENT_RE = re.compile("|".join(f"(?:{p})" for p in _COMMITMENT_PATTERNS), re.IGNORECASE)


def contains_commitment(text: str) -> bool:
    return _COMMITMENT_RE.search(text) is not None


@dataclass
class GuardResult:
    text: str
    count: int = 0


def guard_commitments(text: str, replacement: str) -> GuardResult:
    """Câu chứa cụm cam kết kết quả ("chắc chắn được duyệt", "đã được công nhận"...) bị viết lại theo mẫu không cam kết."""
    result = GuardResult(text)

    def decide(seg: str) -> str | None:
        if not contains_commitment(seg):
            return None
        result.count += 1
        return replacement

    result.text = _replace_segments(text, decide)
    return result
