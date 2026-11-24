"""Sau khi nộp hồ sơ, sinh viên chỉ sửa được phần cá nhân (vị trí, mô tả công việc, hình thức); thông tin công ty khóa."""

from __future__ import annotations

import pytest

from tests.fakes import make_user
from vin15.domain.exception import InvalidInputError, ResourceNotFoundError, StateConflictError
from vin15.domain.model.user import Role
from vin15.service.internship.internship_service import InternshipService

STUDENT = make_user(3, "sv.a@example.test", Role.STUDENT)


class FakeCases:
    def __init__(self, status="in_progress"):
        self.row = {"id": 1, "status": status, "position": "Thực tập sinh", "job_description": "Viết mã", "mode": "onsite"}
        self.updates: list[tuple[int, dict, object]] = []

    def student_internship(self, user_id):
        return self.row

    def get_internship(self, internship_id):
        return self.row

    def update_personal(self, internship_id, fields, audit):
        self.updates.append((internship_id, fields, audit))


def service(cases) -> InternshipService:
    svc = object.__new__(InternshipService)  # chỉ cần _cases cho luồng này
    svc._cases = cases
    return svc


def test_personal_fields_are_saved_trimmed_with_audit():
    cases = FakeCases("in_progress")
    service(cases).update_personal(STUDENT, "  Backend intern ", " Làm API và kiểm thử ", "remote")
    _, fields, audit = cases.updates[0]
    assert fields == {"position": "Backend intern", "job_description": "Làm API và kiểm thử", "mode": "remote"}
    assert audit.action == "update_personal" and audit.entity == "internship"


def test_fields_not_sent_are_left_alone():
    cases = FakeCases("submitted")
    service(cases).update_personal(STUDENT, None, "Mô tả mới", None)
    assert cases.updates[0][1] == {"job_description": "Mô tả mới"}


@pytest.mark.parametrize("status", ["draft", "revision_requested"])
def test_draft_must_use_the_normal_save(status):
    cases = FakeCases(status)
    with pytest.raises(StateConflictError):
        service(cases).update_personal(STUDENT, "x", None, None)
    assert cases.updates == []


def test_empty_required_personal_field_is_rejected():
    cases = FakeCases()
    with pytest.raises(InvalidInputError):
        service(cases).update_personal(STUDENT, "   ", None, None)
    with pytest.raises(InvalidInputError):
        service(cases).update_personal(STUDENT, None, "", None)
    assert cases.updates == []


def test_invalid_mode_is_rejected():
    with pytest.raises(InvalidInputError):
        service(FakeCases()).update_personal(STUDENT, None, None, "nghi-ngoi")


def test_no_internship_is_not_found():
    cases = FakeCases()
    cases.student_internship = lambda user_id: None  # type: ignore[method-assign]
    with pytest.raises(ResourceNotFoundError):
        service(cases).update_personal(STUDENT, "x", None, None)
