"""Hậu kiểm câu trả lời (task 6): trích dẫn (P3), số liệu (P10), cụm cam kết, cảnh báo văn bản mẫu."""

import random

from vin15_agent.policy_assistant.verify import (
    build_citations,
    check_numbers,
    contains_commitment,
    guard_commitments,
    sample_warning_needed,
    verify_citations,
)

PARTIAL = "(chưa có căn cứ)"
MISMATCH = "(số liệu chưa khớp)"
COMMIT = "(không cam kết)"


def chunk(cid, text="Thực tập tối thiểu 8 tuần.", **kw):
    base = {
        "chunk_id": cid, "doc_code": "QC-TT", "doc_title": "Quy chế thực tập", "version": "v1", "article_no": "5", "clause_no": "2",
        "heading": "Thời lượng", "text": text, "effective_from": "2026-01-01", "is_sample": False,
    }  # fmt: skip
    return {**base, **kw}


SEEN = {"QC-TT@v1/d5/k2": chunk("QC-TT@v1/d5/k2"), "QC-TT@v1/d6": chunk("QC-TT@v1/d6", "Nộp báo cáo trong 5 ngày làm việc.")}


# ---- 6.1 CitationVerifier ----


def test_valid_cites_kept_and_collected_in_order():
    text = "Cần 8 tuần [cite:QC-TT@v1/d5/k2]. Báo cáo nộp sau đó [cite:QC-TT@v1/d6]."
    r = verify_citations(text, SEEN.keys(), no_basis_partial=PARTIAL)
    assert r.text == text and r.cited_ids == ["QC-TT@v1/d5/k2", "QC-TT@v1/d6"] and r.stripped == 0


def test_unknown_id_dropped_and_unsupported_claim_replaced():
    text = "Cần 8 tuần [cite:QC-TT@v1/d5/k2]. Được miễn hoàn toàn [cite:BIA-DAT/d9]. Đúng hạn là tốt."
    r = verify_citations(text, SEEN.keys(), no_basis_partial=PARTIAL)
    assert "BIA-DAT" not in r.text and PARTIAL in r.text and "miễn" not in r.text
    assert r.cited_ids == ["QC-TT@v1/d5/k2"] and r.dropped_ids == ["BIA-DAT/d9"] and r.stripped == 1
    assert "Đúng hạn là tốt." in r.text


def test_mixed_valid_and_invalid_in_one_sentence_keeps_valid():
    r = verify_citations("Cần 8 tuần [cite:QC-TT@v1/d5/k2][cite:ma-bia].", SEEN.keys(), no_basis_partial=PARTIAL)
    assert r.text == "Cần 8 tuần [cite:QC-TT@v1/d5/k2]." and r.dropped_ids == ["ma-bia"] and r.stripped == 0


def test_cite_after_period_stays_with_its_claim():
    r = verify_citations("Cần 8 tuần. [cite:QC-TT@v1/d5/k2]", SEEN.keys(), no_basis_partial=PARTIAL)
    assert r.cited_ids == ["QC-TT@v1/d5/k2"] and PARTIAL not in r.text


def test_at_most_five_distinct_citations():
    seen = {f"c{i}": chunk(f"c{i}") for i in range(8)}
    text = " ".join(f"Ý {i} [cite:c{i}]." for i in range(8))
    r = verify_citations(text, seen.keys(), limit=5, no_basis_partial=PARTIAL)
    assert r.cited_ids == [f"c{i}" for i in range(5)]
    assert "c5" not in r.text and "c7" not in r.text


def test_consecutive_stripped_segments_collapse_to_one_notice():
    r = verify_citations("A [cite:x]. B [cite:y]. C [cite:z].", SEEN.keys(), no_basis_partial=PARTIAL)
    assert r.text.count(PARTIAL) == 1 and r.stripped == 3 and r.cited_ids == []


def test_stripped_list_items_on_separate_lines_collapse_to_one_notice():
    text = "Bạn còn thiếu:\n- Một [cite:x].\n- Hai [cite:y].\n\n- Ba [cite:z].\nCòn lại do giảng viên quyết định."
    r = verify_citations(text, SEEN.keys(), no_basis_partial=PARTIAL)
    assert r.text.count(PARTIAL) == 1 and r.stripped == 3
    assert "Bạn còn thiếu:" in r.text and "Còn lại do giảng viên quyết định." in r.text and "\n\n\n" not in r.text


def test_text_without_any_cite_is_untouched():
    r = verify_citations("Theo hồ sơ của bạn, bạn còn 3 ngày.", SEEN.keys(), no_basis_partial=PARTIAL)
    assert r.text == "Theo hồ sơ của bạn, bạn còn 3 ngày." and r.cited_ids == []


def test_p3_property_cited_ids_subset_of_seen_and_at_most_five():
    rng = random.Random(3)
    pool = ["QC-TT@v1/d5/k2", "QC-TT@v1/d6", "x1", "x2", "x3", "bịa-1", "bịa-2", "bịa-3"]
    for _ in range(300):
        text = " ".join(f"Câu {i} " + "".join(f"[cite:{rng.choice(pool)}]" for _ in range(rng.randint(0, 3))) + "." for i in range(rng.randint(1, 9)))
        r = verify_citations(text, SEEN.keys(), no_basis_partial=PARTIAL)
        assert set(r.cited_ids) <= set(SEEN) and len(r.cited_ids) <= 5
        for cid in ("bịa-1", "bịa-2", "bịa-3", "x1"):
            assert f"[cite:{cid}]" not in r.text


def test_build_citations_from_tool_results_only():
    seen = {"QC-TT@v1/d5/k2": chunk("QC-TT@v1/d5/k2", "x" * 2000, is_sample=True)}
    cites = build_citations(seen, ["QC-TT@v1/d5/k2", "khong-co"])
    assert len(cites) == 1
    c = cites[0]
    assert (c.chunk_id, c.doc_code, c.doc_title, c.version, c.article, c.clause) == ("QC-TT@v1/d5/k2", "QC-TT", "Quy chế thực tập", "v1", "5", "2")
    assert c.is_sample is True and c.effective_from == "2026-01-01" and len(c.quote) <= 1200


# ---- 6.2 NumberChecker ----


def test_numbers_present_in_sources_pass():
    text = "Tối thiểu 8 tuần [cite:a] và nộp trong 5 ngày làm việc."
    r = check_numbers(text, ["Thực tập tối thiểu 8 tuần.", "Nộp trong 5 ngày làm việc."], MISMATCH)
    assert r.text == text and r.blocked == 0


def test_invented_number_blocks_the_sentence():
    r = check_numbers("Cần tối thiểu 12 tuần. Hạn nộp là cuối kỳ.", ["Thực tập tối thiểu 8 tuần."], MISMATCH)
    assert "12" not in r.text and MISMATCH in r.text and "Hạn nộp là cuối kỳ." in r.text
    assert r.blocked == 1 and r.bad_numbers == ["12"]


def test_number_formats_are_normalized():
    srcs = ["Ngưỡng 80% và hạn 2026-12-01, 1.000 đồng, 2,5 điểm."]
    ok = "Đạt 80% trước 01/12/2026, phí 1000 đồng, điểm 2.5."
    assert check_numbers(ok, srcs, MISMATCH).blocked == 0


def test_codes_citations_and_list_markers_are_not_numbers():
    text = "1. Điều kiện T1 và mốc M3 [cite:QC-TT@v1/d5/k2].\n2) Việc tiếp theo là liên hệ giảng viên."
    assert check_numbers(text, ["không có số"], MISMATCH).blocked == 0


def test_user_numbers_and_today_can_be_sources():
    r = check_numbers("Bạn nói đã làm 6 tuần; hôm nay 2026-11-21.", ["Em đã làm 6 tuần", "2026-11-21"], MISMATCH)
    assert r.blocked == 0


def test_p10_property_all_numbers_in_output_come_from_sources():
    rng = random.Random(11)
    sources = ["Thực tập tối thiểu 8 tuần, 120 giờ, nộp trong 5 ngày làm việc."]
    for _ in range(200):
        nums = [str(rng.choice([8, 120, 5, 7, 99, 1000])) for _ in range(rng.randint(1, 4))]
        text = ". ".join(f"Ý số {n} nói về {n} đơn vị" for n in nums)
        out = check_numbers(text, sources, MISMATCH).text
        for tok in out.replace(".", " ").split():
            if tok.isdigit():
                assert tok in {"8", "120", "5"}, (text, out)


# ---- 6.3 CommitmentGuard ----


def test_commitment_phrases_detected():
    for phrase in (
        "Em chắc chắn được công nhận.", "Hồ sơ của bạn đã được duyệt rồi.", "Bạn sẽ được công nhận tín chỉ.",
        "Tôi đảm bảo được duyệt.", "Mình đã nộp giúp bạn.", "Tín chỉ đã được công nhận cho em.", "Em đã được chấp nhận.",
    ):  # fmt: skip
        assert contains_commitment(phrase), phrase


def test_non_commitment_phrases_not_flagged():
    for phrase in (
        "Điều kiện công nhận gồm ba mục.", "Bạn chưa được công nhận cho tới khi giảng viên duyệt.",
        "Mình không chắc chắn được duyệt; kết quả do giảng viên quyết định.", "Bạn có thể gửi yêu cầu để được xét duyệt.",
    ):  # fmt: skip
        assert not contains_commitment(phrase), phrase


def test_guard_rewrites_commitment_sentence_with_template():
    r = guard_commitments("Theo quy định cần 8 tuần. Em chắc chắn được công nhận tín chỉ. Hãy liên hệ giảng viên.", COMMIT)
    assert COMMIT in r.text and "chắc chắn" not in r.text and r.count == 1
    assert "Theo quy định cần 8 tuần." in r.text and "Hãy liên hệ giảng viên." in r.text
    assert not contains_commitment(r.text)


# ---- 6.4 văn bản mẫu ----


def test_sample_warning_only_when_cited_chunk_is_sample():
    seen = {"a": chunk("a", is_sample=True), "b": chunk("b")}
    assert sample_warning_needed(seen, ["a"]) and sample_warning_needed(seen, ["a", "b"])
    assert not sample_warning_needed(seen, ["b"]) and not sample_warning_needed(seen, [])
