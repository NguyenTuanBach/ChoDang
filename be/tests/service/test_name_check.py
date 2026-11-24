"""Đối chiếu tên sinh viên trên giấy với tài khoản: tên rút gọn / đầy đủ vẫn khớp, tên khác người thì báo lệch."""

from __future__ import annotations

import pytest

from tests.fakes import make_user
from vin15.domain.model.user import Role
from vin15.service.internship.intake_service import IntakeService
from vin15.service.milestone.evidence_check import names_differ, normalize


@pytest.mark.parametrize(
    ("paper", "account", "differ"),
    [
        ("Sinh viên H", "Sinh viên H (test giấy tiếp nhận)", False),  # AI đọc rút gọn
        ("Sinh viên H (test giấy tiếp nhận)", "Sinh viên H", False),
        ("NGUYỄN VĂN AN", "Nguyễn Văn An", False),  # hoa/thường và dấu
        ("Nguyen Van An", "Nguyễn Văn An", False),
        ("Nguyễn Văn Bình", "Nguyễn Văn An", True),  # người khác
        ("", "Nguyễn Văn An", False),  # giấy không có tên: không xét
        ("Nguyễn Văn An", "", False),
    ],
)
def test_names_differ(paper, account, differ):
    assert names_differ(normalize(paper), normalize(account)) is differ


def test_shortened_name_on_paper_gives_no_identity_warning():
    student = make_user(8, "sv.h@example.test", Role.STUDENT, name="Sinh viên H (test giấy tiếp nhận)")
    assert IntakeService._identity_warnings(student, {"student_name": {"value": "Sinh viên H"}}) == []


def test_other_person_name_on_paper_still_warns():
    student = make_user(8, "sv.h@example.test", Role.STUDENT, name="Nguyễn Văn An")
    warnings = IntakeService._identity_warnings(student, {"student_name": {"value": "Trần Thị Bình"}})
    assert len(warnings) == 1 and "khác tên tài khoản" in warnings[0]
