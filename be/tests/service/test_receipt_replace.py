"""Mỗi hồ sơ chỉ giữ MỘT giấy tiếp nhận: tải giấy mới thì giấy cũ (dòng DB và tệp) bị thay thế."""

from __future__ import annotations

from tests.fakes import make_user
from vin15.domain.model.user import Role
from vin15.service.internship.internship_service import InternshipService

STUDENT = make_user(3, "sv.a@example.test", Role.STUDENT)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


class FakeCases:
    def __init__(self, old_keys):
        self.old_keys = old_keys
        self.replaced: list[tuple] = []

    def student_internship(self, user_id):
        return {"id": 1, "status": "draft"}

    def replace_document(self, internship_id, filename, mime, size, sha256, key, uploaded_by):
        self.replaced.append((internship_id, filename, key))
        return 9, list(self.old_keys)


class FakeStorage:
    def __init__(self, fail_delete=False):
        self.put_keys, self.deleted, self._fail = [], [], fail_delete

    def put(self, key, data, content_type):
        self.put_keys.append(key)

    def delete(self, key):
        if self._fail:
            raise OSError("kho lỗi")
        self.deleted.append(key)


def service(cases, storage) -> InternshipService:
    svc = object.__new__(InternshipService)
    svc._cases, svc._storage, svc._max_bytes = cases, storage, 10 * 1024 * 1024
    return svc


def test_new_document_replaces_old_ones_and_old_files_are_removed():
    cases, storage = FakeCases(["internship/1/old-a", "internship/1/old-b"]), FakeStorage()
    result = service(cases, storage).upload_document(STUDENT, "giay-moi.png", PNG)
    assert result["id"] == 9 and len(cases.replaced) == 1
    assert storage.deleted == ["internship/1/old-a", "internship/1/old-b"]
    assert storage.put_keys and storage.put_keys[0] not in storage.deleted  # tệp mới không bị xóa nhầm


def test_failure_deleting_old_file_does_not_break_the_upload():
    cases, storage = FakeCases(["internship/1/old"]), FakeStorage(fail_delete=True)
    assert service(cases, storage).upload_document(STUDENT, "giay-moi.png", PNG)["id"] == 9


def test_first_upload_has_nothing_to_remove():
    cases, storage = FakeCases([]), FakeStorage()
    service(cases, storage).upload_document(STUDENT, "giay.png", PNG)
    assert storage.deleted == []
