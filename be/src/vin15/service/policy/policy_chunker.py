"""Tách văn bản quy định (Markdown hoặc văn bản thuần) theo cấu trúc "Điều N." / "Khoản M." thành các đoạn (chunk).

Quy ước đầu vào:
- Dòng bắt đầu một điều: ``Điều 5. Tiêu đề`` (cho phép tiền tố ``#``, ``**``; dấu sau số là ``.`` hoặc ``:``).
- Khoản: dòng bắt đầu bằng ``1.`` hoặc ``1)`` (hoặc ``Khoản 1.``). Dòng khác (điểm ``a)``, đoạn nối) thuộc khoản/điều đang mở.
- Phần trước điều đầu tiên (tiêu đề, lời mở đầu) bị bỏ qua.

Một chunk = một khoản; điều không có khoản, hoặc điều ngắn (tổng ≤ ``short_article_chars`` ký tự), là một chunk nguyên điều.
Phần dẫn của điều (trước khoản 1) thành chunk riêng không có số khoản. Mỗi chunk mang tiêu đề điều để đứng riêng vẫn rõ nghĩa.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vin15.domain.exception import InvalidInputError
from vin15.domain.model.policy import ChunkDraft

_ARTICLE = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*Điều\s+(\d+[A-Za-z]?)\s*[.:]\s*(.*?)\s*(?:\*\*)?\s*$", re.IGNORECASE)
_CLAUSE = re.compile(r"^\s*(?:Khoản\s+)?(\d+)\s*[.)]\s+(.*\S)\s*$", re.IGNORECASE)

DEFAULT_SHORT_ARTICLE_CHARS = 300


@dataclass
class _Article:
    number: str
    title: str
    intro: list[str] = field(default_factory=list)
    clauses: list[tuple[str, list[str]]] = field(default_factory=list)

    @property
    def heading(self) -> str:
        return f"Điều {self.number}. {self.title}" if self.title else f"Điều {self.number}"


def _join(lines: list[str]) -> str:
    return "\n".join(line.strip() for line in lines if line.strip()).strip()


class PolicyChunker:
    def __init__(self, short_article_chars: int = DEFAULT_SHORT_ARTICLE_CHARS):
        self._short = short_article_chars

    def chunk(self, text: str) -> list[ChunkDraft]:
        articles = self._parse(text)
        if not articles:
            raise InvalidInputError('Không tìm thấy "Điều N." nào trong văn bản: cần đúng cấu trúc Điều/Khoản')
        seen: set[str] = set()
        drafts: list[ChunkDraft] = []
        for article in articles:
            if article.number in seen:
                raise InvalidInputError(f"Điều {article.number} bị trùng trong văn bản")
            seen.add(article.number)
            drafts.extend(self._chunks_of(article, start=len(drafts)))
        return drafts

    def _parse(self, text: str) -> list[_Article]:
        articles: list[_Article] = []
        current: _Article | None = None
        for raw in text.splitlines():
            line = raw.rstrip()
            match = _ARTICLE.match(line)
            if match:
                current = _Article(number=match.group(1), title=match.group(2).strip("*# ").strip())
                articles.append(current)
                continue
            if current is None:
                continue  # trước điều đầu tiên
            clause = _CLAUSE.match(line)
            if clause:
                current.clauses.append((clause.group(1), [clause.group(2)]))
            elif current.clauses:
                current.clauses[-1][1].append(line)
            else:
                current.intro.append(line)
        return articles

    def _chunks_of(self, article: _Article, start: int) -> list[ChunkDraft]:
        heading = article.heading
        intro = _join(article.intro)
        clauses = [(number, _join(lines)) for number, lines in article.clauses]
        if not intro and not any(body for _n, body in clauses):
            raise InvalidInputError(f"Điều {article.number} không có nội dung")
        total = len(intro) + sum(len(body) for _n, body in clauses)
        if not clauses or total <= self._short:
            parts = [intro] + [f"{number}. {body}" for number, body in clauses]
            return [ChunkDraft(start, article.number, None, heading, "\n".join(p for p in parts if p))]
        numbers = [number for number, _body in clauses]
        if len(set(numbers)) != len(numbers):
            raise InvalidInputError(f"Điều {article.number} có khoản bị trùng số")
        drafts: list[ChunkDraft] = []
        if intro:
            drafts.append(ChunkDraft(start, article.number, None, heading, intro))
        for number, body in clauses:
            if not body:
                raise InvalidInputError(f"Khoản {number} của Điều {article.number} không có nội dung")
            drafts.append(ChunkDraft(start + len(drafts), article.number, number, heading, body))
        return drafts
