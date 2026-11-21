import pytest

from vin15.domain.exception import InvalidInputError
from vin15.service.policy.policy_chunker import PolicyChunker

SAMPLE = """# Quy chế thực tập (mẫu)

Lời nói đầu không thuộc điều nào.

## Điều 1. Phạm vi áp dụng
Quy chế này áp dụng cho sinh viên đi thực tập.

## Điều 5. Thời lượng và nhật ký
Sinh viên phải thực tập đủ thời lượng quy định tại các khoản dưới đây và nộp nhật ký đúng hạn để được xét công nhận.
1. Thời lượng thực tập tối thiểu là 8 tuần liên tục, tính từ ngày bắt đầu ghi trong hồ sơ được xác nhận.
2. Tỷ lệ tuần có nhật ký phải đạt từ 80% trở lên.
a) Nhật ký nộp muộn quá 7 ngày không được tính là đã nộp.
3. Trường hợp đặc biệt do giảng viên xem xét.

**Điều 6: Hồ sơ**
Hồ sơ gồm giấy tiếp nhận.
"""


def chunks(text=SAMPLE, **kw):
    return PolicyChunker(**kw).chunk(text)


def test_short_article_without_clauses_is_one_chunk_keeping_heading():
    first = chunks()[0]
    assert (first.article_no, first.clause_no, first.ordinal) == ("1", None, 0)
    assert first.heading == "Điều 1. Phạm vi áp dụng"
    assert first.text == "Quy chế này áp dụng cho sinh viên đi thực tập."


def test_article_with_clauses_splits_per_clause_and_keeps_intro():
    result = chunks()
    ids = [(c.article_no, c.clause_no) for c in result]
    assert ids == [("1", None), ("5", None), ("5", "1"), ("5", "2"), ("5", "3"), ("6", None)]
    assert [c.ordinal for c in result] == list(range(6))
    clause2 = next(c for c in result if c.clause_no == "2")
    assert clause2.heading == "Điều 5. Thời lượng và nhật ký"
    assert "80%" in clause2.text and "Nhật ký nộp muộn" in clause2.text  # điểm a) thuộc khoản 2
    assert not clause2.text.startswith("2.")


def test_preamble_before_first_article_is_ignored_and_markdown_noise_stripped():
    result = chunks()
    assert all("Lời nói đầu" not in c.text for c in result)
    assert result[-1].heading == "Điều 6. Hồ sơ" and result[-1].text == "Hồ sơ gồm giấy tiếp nhận."


def test_short_article_with_clauses_is_merged_when_below_limit():
    text = "Điều 2. Ngắn\n1. Một.\n2. Hai.\n"
    merged = PolicyChunker(short_article_chars=100).chunk(text)
    assert len(merged) == 1 and merged[0].clause_no is None and "1. Một." in merged[0].text
    split = PolicyChunker(short_article_chars=0).chunk(text)
    assert [c.clause_no for c in split] == ["1", "2"]


def test_chunking_is_deterministic():
    assert chunks() == chunks()


def test_no_article_is_rejected():
    with pytest.raises(InvalidInputError, match="Điều"):
        chunks("Chỉ có văn bản thường, không có điều nào.")


def test_duplicate_article_or_clause_is_rejected():
    with pytest.raises(InvalidInputError, match="trùng"):
        chunks("Điều 1. A\nnội dung\nĐiều 1. B\nnội dung")
    with pytest.raises(InvalidInputError, match="trùng"):
        chunks("Điều 1. A\n" + "x" * 400 + "\n1. a\n1. b", short_article_chars=10)


def test_empty_article_is_rejected():
    with pytest.raises(InvalidInputError, match="không có nội dung"):
        chunks("Điều 1. Rỗng\nĐiều 2. Có\nnội dung")
