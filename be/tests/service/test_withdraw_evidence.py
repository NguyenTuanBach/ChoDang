"""Thu hồi minh chứng: chỉ chủ minh chứng, chỉ khi còn chờ duyệt và mốc chưa nộp / chưa chấp nhận; tệp bị xóa, dấu vết ghi audit."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.fakes import make_user
from vin15.domain.exception import ResourceNotFoundError, StateConflictError
from vin15.domain.model.user import Role
from vin15.service.milestone.milestone_service import MilestoneService

STUDENT = make_user(3, "sv.a@example.test", Role.STUDENT)
OTHER = make_user(4, "sv.b@example.test", Role.STUDENT)


class FakeCases:
    def __init__(self, *, evidence_status="submitted", milestone_status="pending", internship_status="in_progress", owner_id=3):
        self.evidence = {
            "id": 7, "owner_id": owner_id, "status": evidence_status, "internship_id": 1, "milestone_code": "M3",
            "filename": "bao-cao.pdf", "storage_key": "evidence/1/abc",
        }
        self.milestone_status = milestone_status
        self.internship_status = internship_status
        self.deleted: list[tuple[int, object]] = []

    def get_evidence(self, evidence_id):
        return self.evidence if evidence_id == 7 else None

    def get_internship(self, internship_id):
        return {"id": internship_id, "status": self.internship_status}

    def milestone_by_code(self, internship_id, code):
        return {"id": 5, "status": self.milestone_status}

    def delete_evidence(self, evidence_id, audit):
        self.deleted.append((evidence_id, audit))


class FakeStorage:
    def __init__(self, fail=False):
        self.removed: list[str] = []
        self._fail = fail

    def delete(self, key):
        if self._fail:
            raise OSError("kho lỗi")
        self.removed.append(key)


def service(cases, storage):
    return MilestoneService(cases, SimpleNamespace(), storage, lambda: None, 10 * 1024 * 1024)


def test_owner_withdraws_pending_evidence_and_file_is_removed():
    cases, storage = FakeCases(), FakeStorage()
    service(cases, storage).withdraw_evidence(STUDENT, 7)
    assert [d[0] for d in cases.deleted] == [7]
    assert cases.deleted[0][1].action == "withdraw" and cases.deleted[0][1].entity == "evidence"
    assert storage.removed == ["evidence/1/abc"]


def test_storage_failure_does_not_undo_the_withdrawal():
    cases = FakeCases()
    service(cases, FakeStorage(fail=True)).withdraw_evidence(STUDENT, 7)
    assert [d[0] for d in cases.deleted] == [7]


def test_other_student_cannot_withdraw():
    cases = FakeCases()
    with pytest.raises(ResourceNotFoundError):
        service(cases, FakeStorage()).withdraw_evidence(OTHER, 7)
    assert cases.deleted == []


def test_unknown_evidence_is_not_found():
    with pytest.raises(ResourceNotFoundError):
        service(FakeCases(), FakeStorage()).withdraw_evidence(STUDENT, 999)


@pytest.mark.parametrize("evidence_status", ["accepted", "rejected"])
def test_only_pending_evidence_can_be_withdrawn(evidence_status):
    cases = FakeCases(evidence_status=evidence_status)
    with pytest.raises(StateConflictError):
        service(cases, FakeStorage()).withdraw_evidence(STUDENT, 7)
    assert cases.deleted == []


@pytest.mark.parametrize("milestone_status", ["submitted", "accepted"])
def test_locked_milestone_blocks_withdrawal(milestone_status):
    cases = FakeCases(milestone_status=milestone_status)
    with pytest.raises(StateConflictError):
        service(cases, FakeStorage()).withdraw_evidence(STUDENT, 7)
    assert cases.deleted == []


def test_internship_must_be_in_working_state():
    cases = FakeCases(internship_status="completed")
    with pytest.raises(StateConflictError):
        service(cases, FakeStorage()).withdraw_evidence(STUDENT, 7)
