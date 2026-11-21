"""Che PII (task 3): email, SĐT VN, MST, mã SV theo cấu hình; không khôi phục nhãn."""

import random

import pytest

from vin15_agent.core.pii import PiiRedactor


def test_masks_email_phone_tax_id():
    text, mapping = PiiRedactor().redact("Liên hệ an@congty.com.vn, 0912 345 678, +84 912345678, MST 0312345678-001 hoặc 1234567890.")
    assert "an@congty" not in text and "0912" not in text and "0312345678" not in text and "1234567890" not in text
    assert "[EMAIL_1]" in text and "[SDT_1]" in text and "[SDT_2]" in text and "[MST_1]" in text and "[MST_2]" in text
    assert mapping["[EMAIL_1]"] == "an@congty.com.vn"


def test_same_value_gets_same_label_across_calls():
    r = PiiRedactor()
    a, _ = r.redact("mail a@x.vn")
    b, _ = r.redact("lại a@x.vn và b@x.vn")
    assert a == "mail [EMAIL_1]" and b == "lại [EMAIL_1] và [EMAIL_2]"


def test_student_id_pattern_from_config():
    assert "[MSSV_1]" in PiiRedactor(r"SV\d{6}").redact("em là SV123456")[0]
    assert "SV123456" in PiiRedactor("").redact("em là SV123456")[0]  # trống = không che theo mã


def test_invalid_student_id_pattern_is_rejected():
    with pytest.raises(ValueError):
        PiiRedactor("(")


def test_does_not_touch_policy_numbers_or_citations():
    text = "Thực tập tối thiểu 120 giờ, nộp trước 5 ngày [cite:QC-01@v1/d5/k2] theo Điều 5 khoản 2 (2026-11-21)."
    assert PiiRedactor().redact(text)[0] == text


def test_masks_api_keys_and_bearer_tokens():
    out, _ = PiiRedactor().redact("khóa sk-abcdefghijklmnop1234 và Bearer abc.def-ghi_jkl1234567890")
    assert "sk-abcdef" not in out and "abc.def" not in out


def test_labels_not_restored_in_output():
    r = PiiRedactor()
    out, mapping = r.redact("a@x.vn")
    assert out == "[EMAIL_1]" and "a@x.vn" not in out
    assert "a@x.vn" not in r.redact_text("trả lời [EMAIL_1]")


def test_property_no_original_pii_remains():
    """P6: với PII sinh ngẫu nhiên, kết quả không còn giá trị gốc."""
    rng = random.Random(7)
    r = PiiRedactor(r"SV\d{6}")
    for _ in range(200):
        email = f"u{rng.randint(1, 10**6)}@mail{rng.randint(1, 99)}.com"
        phone = "0" + str(rng.choice([3, 5, 7, 8, 9])) + "".join(str(rng.randint(0, 9)) for _ in range(8))
        mst = "".join(str(rng.randint(1, 9)) for _ in range(10))
        sv = f"SV{rng.randint(100000, 999999)}"
        text = f"Tôi {sv}, mail {email}, gọi {phone}, MST {mst}."
        out, _ = r.redact(text)
        for secret in (email, phone, mst, sv):
            assert secret not in out, (secret, out)
