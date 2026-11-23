"""``/api/admin/policies``: chỉ quản trị viên (nạp, xem trước, xuất bản). Dịch vụ giả, không cần database."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from tests.fakes import ADMIN, LECTURER, STUDENT_A, FakeUsers, chunk
from vin15.config.container import Container
from vin15.domain.exception import InvalidInputError
from vin15.domain.model.policy import PolicyVersion, VersionStatus
from vin15.main import create_app
from vin15.service.policy.policy_ingest_service import EmbedResult, ExtractResult, IngestResult

VERSION = PolicyVersion(7, 1, "QD-TT-01", "Quy chế", "v1", date(2026, 1, 1), None, VersionStatus.DRAFT, True, 4)
BODY = {
    "code": "QD-TT-01",
    "title": "Quy chế",
    "version_label": "v1",
    "effective_from": "2026-01-01",
    "is_sample": True,
    "text": "Điều 1. A\nnội dung",
}


class FakeIngest:
    def __init__(self):
        self.calls = []

    async def ingest(self, **kwargs):
        self.calls.append(kwargs)
        if "LỖI" in kwargs["text"]:
            raise InvalidInputError('Không tìm thấy "Điều N."')
        return IngestResult(VERSION, 4, 4, True)

    def extract(self, filename, data):
        self.calls.append({"extract": filename, "size": len(data)})
        if filename.endswith(".exe"):
            raise InvalidInputError("Chỉ nhận tệp .md, .txt, .docx, .pdf")
        return ExtractResult(data.decode(), 1, None)

    async def embed_version(self, version_id):
        self.calls.append({"embed": version_id})
        return EmbedResult(PolicyVersion(7, 1, "QD-TT-01", "Quy chế", "v1", date(2026, 1, 1), None, VersionStatus.DRAFT, True, 4, 4), 3, True)


class FakePublish:
    def __init__(self):
        self.published = []

    def publish(self, version_id, actor_id, actor_role="admin"):
        self.published.append((version_id, actor_id, actor_role))
        return PolicyVersion(7, 1, "QD-TT-01", "Quy chế", "v1", date(2026, 1, 1), None, VersionStatus.PUBLISHED, True, 4)

    def preview(self, version_id):
        return (VERSION, [chunk()]) if version_id == 7 else None

    def list_versions(self):
        return [VERSION]


@pytest.fixture
def container():
    c = Container(make_settings(jwt_secret="j" * 40))
    c.user_repository = FakeUsers(ADMIN, LECTURER, STUDENT_A)
    c.policy_ingest_service = FakeIngest()
    c.policy_publish_service = FakePublish()
    return c


@pytest.fixture
def client(container):
    return TestClient(create_app(container.settings, container))


def as_user(container, user):
    return {"Authorization": f"Bearer {container.token_service.create(user.id, user.role.value)}"}


@pytest.mark.parametrize("user", [LECTURER, STUDENT_A])
def test_only_admin_may_manage_policies(client, container, user):
    headers = as_user(container, user)
    assert client.get("/api/admin/policies", headers=headers).status_code == 403
    assert client.post("/api/admin/policies", json=BODY, headers=headers).status_code == 403
    assert client.get("/api/admin/policies/versions/7", headers=headers).status_code == 403
    assert client.post("/api/admin/policies/versions/7/publish", headers=headers).status_code == 403
    assert client.post("/api/admin/policies/extract", files={"file": ("q.md", b"x")}, headers=headers).status_code == 403
    assert client.post("/api/admin/policies/versions/7/embed", headers=headers).status_code == 403
    assert container.policy_ingest_service.calls == [] and container.policy_publish_service.published == []


def test_anonymous_is_401(client):
    assert client.get("/api/admin/policies").status_code == 401


def test_admin_ingest_preview_publish(client, container):
    headers = as_user(container, ADMIN)
    created = client.post("/api/admin/policies", json=BODY, headers=headers)
    assert created.status_code == 201
    assert created.json()["chunk_count"] == 4 and created.json()["embedded_count"] == 4 and created.json()["version"]["status"] == "draft"
    sent = container.policy_ingest_service.calls[0]
    assert sent["doc_code"] == "QD-TT-01" and sent["effective_from"] == date(2026, 1, 1) and sent["is_sample"] is True
    preview = client.get("/api/admin/policies/versions/7", headers=headers).json()
    assert preview["chunks"][0]["chunk_id"] == "QD-TT-01@v1/d3/k1" and preview["version"]["id"] == "7"
    assert client.get("/api/admin/policies/versions/8", headers=headers).status_code == 404
    published = client.post("/api/admin/policies/versions/7/publish", headers=headers)
    assert published.status_code == 200 and published.json()["status"] == "published"
    assert container.policy_publish_service.published == [(7, ADMIN.id, "admin")]
    assert [v["id"] for v in client.get("/api/admin/policies", headers=headers).json()] == ["7"]


def test_bad_document_format_is_422(client, container):
    response = client.post("/api/admin/policies", json={**BODY, "text": "LỖI"}, headers=as_user(container, ADMIN))
    assert response.status_code == 422 and response.json()["error"] == "invalid_input"


def test_body_validation(client, container):
    headers = as_user(container, ADMIN)
    assert client.post("/api/admin/policies", json={**BODY, "code": ""}, headers=headers).status_code == 422
    assert (
        client.post("/api/admin/policies", json={k: v for k, v in BODY.items() if k != "effective_from"}, headers=headers).status_code
        == 422
    )


def test_extract_returns_text_without_saving(client, container):
    headers = as_user(container, ADMIN)
    response = client.post("/api/admin/policies/extract", files={"file": ("quy-che.md", "Điều 1. A\nnội dung".encode())}, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"filename": "quy-che.md", "text": "Điều 1. A\nnội dung", "chunk_count": 1, "warning": None}
    bad = client.post("/api/admin/policies/extract", files={"file": ("x.exe", b"MZ")}, headers=headers)
    assert bad.status_code == 422 and bad.json()["error"] == "invalid_input"


def test_extract_rejects_oversized_file(client, container):
    from vin15.service.policy.policy_file_reader import MAX_FILE_BYTES

    big = b"a" * (MAX_FILE_BYTES + 1)
    response = client.post("/api/admin/policies/extract", files={"file": ("q.txt", big)}, headers=as_user(container, ADMIN))
    assert response.status_code == 422 and not any("extract" in c for c in container.policy_ingest_service.calls)


def test_embed_version(client, container):
    response = client.post("/api/admin/policies/versions/7/embed", headers=as_user(container, ADMIN))
    assert response.status_code == 200
    body = response.json()
    assert body["embedded_now"] == 3 and body["agent_enabled"] is True and body["version"]["embedded_count"] == 4
    assert {"embed": 7} in container.policy_ingest_service.calls
