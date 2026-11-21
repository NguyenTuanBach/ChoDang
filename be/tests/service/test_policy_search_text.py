from vin15.service.policy.policy_search_service import min_match, normalize, tokenize


def test_normalize_strips_vietnamese_accents_including_d():
    assert normalize("Đề cương Thực tập, Điều 5") == "de cuong thuc tap, dieu 5"


def test_tokenize_drops_stopwords_duplicates_and_keeps_digits():
    assert tokenize("Em thực tập bao nhiêu tuần thì tuần 8 là đủ?") == ["thuc", "tap", "tuan", "8", "du"]


def test_tokenize_caps_token_count():
    assert len(tokenize(" ".join(f"tu{i}x" for i in range(40)))) == 12


def test_min_match_grows_with_query_length():
    assert [min_match(n) for n in (0, 1, 2, 3, 6, 7, 12)] == [1, 1, 1, 2, 2, 3, 3]
