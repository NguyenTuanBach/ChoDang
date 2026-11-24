"""Tệp đề cương sinh viên đính kèm khi nộp: chỉ chủ hồ sơ gắn được, mỗi phiên bản một tệp, người có quyền xem mới tải được."""

from __future__ import annotations

import pytest

from tests.fakes import make_user
from vin15.domain.exception import InvalidInputError, ResourceNotFoundError, ScopeDeniedError, StateConflictError
from vin15.domain.model.user import Role
from vin15.service.outline.outline_review_service import OutlineReviewService

OWNER = make_user(3, "sv.a@example.test", Role.STUDENT)
OTHER = make_user(4, "sv.b@example.test", Role.STUDENT)
LECTURER = make_user(2, "gv@example.test", Role.LECTURER)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class FakeCases:
    def __init__(self, file_key=None):
        self.row = {"id": 5, "internship_id": 1, "owner_id": 3, "lecturer_id": 2, "file_key": file_key, "file_mime": "image/png", "file_name": "de-cuong.png"}
        self.attached: list[tuple] = []

    def get_outline(self, outline_id):
        return self.row if outline_id == 5 else None

    def attach_outline_file(self, outline_id, filename, mime, size, key):
        if self.row["file_key"]:
            return False
        self.attached.append((outline_id, filename, key))
        self.row["file_key"] = key
        return True


class FakeStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def put(self, key, data, content_type):
        self.files[key] = data

    def get(self, key):
        return self.files[key]

    def delete(self, key):
        self.files.pop(key, None)


def service(cases, storage) -> OutlineReviewService:
    svc = object.__new__(OutlineReviewService)
    svc._cases, svc._storage, svc._max_bytes = cases, storage, 10 * 1024 * 1024
    return svc


def test_owner_attaches_file_and_it_is_stored():
    cases, storage = FakeCases(), FakeStorage()
    result = service(cases, storage).attach_file(OWNER, 5, "de-cuong.png", PNG)
    assert result["file_name"] == "de-cuong.png" and len(cases.attached) == 1
    assert list(storage.files.values()) == [PNG]


def test_other_student_cannot_attach():
    with pytest.raises(ResourceNotFoundError):
        service(FakeCases(), FakeStorage()).attach_file(OTHER, 5, "x.png", PNG)


def test_second_file_for_same_version_is_rejected_and_not_kept():
    cases, storage = FakeCases(file_key="outline/1/da-co"), FakeStorage()
    with pytest.raises(StateConflictError):
        service(cases, storage).attach_file(OWNER, 5, "x.png", PNG)
    assert storage.files == {}


def test_unsupported_type_is_rejected():
    with pytest.raises(InvalidInputError):
        service(FakeCases(), FakeStorage()).attach_file(OWNER, 5, "ghi-chu.txt", b"chi la chu")


def test_unknown_outline_is_not_found():
    with pytest.raises(ResourceNotFoundError):
        service(FakeCases(), FakeStorage()).attach_file(OWNER, 99, "x.png", PNG)


def test_owner_and_lecturer_can_download_but_a_stranger_cannot():
    cases, storage = FakeCases(), FakeStorage()
    svc = service(cases, storage)
    svc.attach_file(OWNER, 5, "de-cuong.png", PNG)
    assert svc.file_bytes(OWNER, 5) == (PNG, "image/png", "de-cuong.png")
    assert svc.file_bytes(LECTURER, 5)[0] == PNG
    with pytest.raises(ScopeDeniedError):
        svc.file_bytes(OTHER, 5)


def test_download_without_file_is_not_found():
    with pytest.raises(ResourceNotFoundError):
        service(FakeCases(), FakeStorage()).file_bytes(OWNER, 5)
