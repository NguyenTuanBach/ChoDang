"""Tìm kiếm quy định cho agent: lọc hiệu lực theo ngày nghiệp vụ, từ khóa + vector, trộn RRF, ngưỡng ``no_match``.

Ngày hiệu lực do BE tự tính (``Clock``), không nhận từ agent hay LLM, nên LLM không thể bị lừa tra văn bản cũ.
Từ khóa dùng ``simple`` + bỏ dấu (Postgres không có cấu hình tiếng Việt). Câu hỏi tự nhiên dài nên không dùng AND tất cả từ như
``websearch_to_tsquery``: tách từ, bỏ từ dừng, chấm điểm theo độ hiếm của từ (xem ``PolicyRepository``).
"""

from __future__ import annotations

import re
import unicodedata

from vin15.domain.clock import Clock
from vin15.domain.exception import InvalidInputError, ResourceNotFoundError
from vin15.domain.model.policy import PolicyChunkLookup, PolicySearchResult
from vin15.infrastructure.persistence.policy_repository import PolicyRepository

MAX_TOP_K = 8
MAX_QUERY_CHARS = 500
EMBEDDING_DIMENSIONS = 1536
_MAX_TOKENS = 12

#: Từ dừng tiếng Việt (đã bỏ dấu, chữ thường) thường gặp trong câu hỏi, không mang nghĩa tìm kiếm.
_STOPWORDS = frozenset(
    "la va cua co cho thi duoc khong nhung cac mot nhu the nao gi em toi minh ban bao nhieu voi trong khi de neu bi se da dang "
    "can phai nen hay hoac ma o tai tu den vao ra len xuong sao roi nua cung rat lam nay do day kia nhe a oi vay".split()
)


def normalize(text: str) -> str:
    """Chữ thường, bỏ dấu tiếng Việt (kể cả đ)."""
    decomposed = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def tokenize(query: str) -> list[str]:
    tokens: list[str] = []
    for word in re.findall(r"[a-z0-9]+", normalize(query)):
        if word in _STOPWORDS or (len(word) < 2 and not word.isdigit()) or word in tokens:
            continue
        tokens.append(word)
    return tokens[:_MAX_TOKENS]


def min_match(token_count: int) -> int:
    """Số từ tối thiểu một đoạn phải chứa để tính là khớp từ khóa: câu càng dài càng đòi nhiều, để một từ chung chung không đủ."""
    if token_count <= 2:
        return 1
    return 2 if token_count <= 6 else 3


class PolicySearchService:
    def __init__(self, repository: PolicyRepository, clock: Clock, no_match_threshold: float):
        self._repo = repository
        self._clock = clock
        self._tau = no_match_threshold

    def search(self, query: str, query_vector: list[float] | None = None, top_k: int = 5) -> PolicySearchResult:
        query = query.strip()
        if not query:
            raise InvalidInputError("Câu tìm kiếm không được rỗng")
        if query_vector is not None and len(query_vector) != EMBEDDING_DIMENSIONS:
            raise InvalidInputError(f"query_vector phải có {EMBEDDING_DIMENSIONS} chiều")
        top_k = max(1, min(top_k, MAX_TOP_K))
        tokens = tokenize(query[:MAX_QUERY_CHARS])
        chunks = self._repo.search(
            today=self._clock(),
            tokens=tokens,
            min_match=min_match(len(tokens)),
            query_vector=query_vector,
            threshold=self._tau,
            top_k=top_k,
        )
        return PolicySearchResult("ok" if chunks else "no_match", "hybrid" if query_vector is not None else "keyword", chunks)

    def get_chunk(self, chunk_id: str, with_neighbors: bool = False) -> PolicyChunkLookup:
        found = self._repo.find_chunk(chunk_id, self._clock(), with_neighbors)
        if found is None:
            raise ResourceNotFoundError("Không tìm thấy đoạn quy định đang có hiệu lực với mã này")
        return PolicyChunkLookup(found[0], found[1])
