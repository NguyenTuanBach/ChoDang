"""``/api/agent-tools/*`` qua HTTP với kho dữ liệu giả: xác thực hai lớp, chủ thể do BE quyết (P5), audit mỗi lời gọi (P8), lỗi theo hợp đồng."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from tests.fakes import (
    ADMIN,
    LECTURER,
    REVOKED,
    STUDENT_A,
    STUDENT_B,
    STUDENT_NO_RECORD,
    TODAY,
    FakeAudit,
    FakeInternships,
    FakePolicySearch,
    FakeUsers,
    chunk,
    internship_a,
    internship_b,
)
from vin15.config.container import Container
from vin15.main import create_app

SERVICE = {"Authorization": "Bearer svc-token"}
ME = ("internship", "milestones", "progress", "credit-checklist", "requests")


def build(**settings_overrides):
    settings = make_settings(agent_api_service_token="svc-token", jwt_secret="j" * 40, **settings_overrides)
    container = Container(settings)
    container.clock = lambda: TODAY
    container.user_repository = FakeUsers(ADMIN, LECTURER, STUDENT_A, STUDENT_B, STUDENT_NO_RECORD, REVOKED)
    container.audit_repository = FakeAudit()
    container.internship_repository = FakeInternships({STUDENT_A.id: internship_a(), STUDENT_B.id: internship_b()})
    container.policy_search_service = FakePolicySearch(
        [chunk(), chunk("QD-TT-01@v1/d4", article_no="4", clause_no=None, text="Nhật ký hằng tuần.")]
    )
    return container


@pytest.fixture
def container():
    return build()


@pytest.fixture
def app(container):
    return create_app(container.settings, container)


@pytest.fixture
def client(app):
    return TestClient(app)


def on_behalf(container, user, **kw) -> dict:
    token = container.token_service.create(user.id, user.role.value, 5, scope="agent_tools", extra=kw or None)
    return {**SERVICE, "X-On-Behalf-Of": token}


def error_of(response) -> dict:
    return response.json()["error"]


# ---- Xác thực ----
def test_missing_or_wrong_service_token_is_401(client, container):
    for headers in ({}, {"Authorization": "Bearer sai"}, {"Authorization": "Basic svc-token"}):
        response = client.get("/api/agent-tools/me/internship", headers=headers)
        assert response.status_code == 401 and error_of(response)["code"] == "authentication_required"


def test_no_agent_token_and_no_dev_user_is_401(client):
    response = client.get("/api/agent-tools/me/internship", headers=SERVICE)
    assert response.status_code == 401 and "X-On-Behalf-Of" in error_of(response)["message"]


def test_session_token_is_not_accepted_as_agent_token_and_is_audited(client, container):
    session_token = container.token_service.create(STUDENT_A.id, "student")  # token thường, không có scope
    response = client.get("/api/agent-tools/me/internship", headers={**SERVICE, "X-On-Behalf-Of": session_token})
    assert response.status_code == 401
    entry = container.audit_repository.entries[-1]
    assert entry.actor_kind.value == "agent" and entry.action == "authenticate" and entry.after == {"outcome": "invalid_agent_token"}


def test_expired_agent_token_is_401(client, container):
    token = container.token_service.create(STUDENT_A.id, "student", -1, scope="agent_tools")
    assert client.get("/api/agent-tools/me/internship", headers={**SERVICE, "X-On-Behalf-Of": token}).status_code == 401


def test_agent_token_is_not_accepted_by_regular_api(client, container):
    agent_token = container.token_service.create(STUDENT_A.id, "student", 5, scope="agent_tools")
    response = client.post("/api/assistant/ws-ticket", headers={"Authorization": f"Bearer {agent_token}"})
    assert response.status_code == 401


def test_revoked_user_token_is_401(client, container):
    assert client.get("/api/agent-tools/me/internship", headers=on_behalf(container, REVOKED)).status_code == 401


def test_dev_default_user_is_used_without_agent_token_and_audited():
    container = build(agent_dev_default_user_email="sv.b@example.test")
    client = TestClient(create_app(container.settings, container))
    response = client.get("/api/agent-tools/me/internship", headers=SERVICE)
    assert response.status_code == 200 and response.json()["internship"]["status"] == "pending_credit"
    entry = container.audit_repository.entries[-1]
    assert entry.actor_id == STUDENT_B.id and entry.reason == "dev-default-user"


def test_dev_default_user_still_needs_service_token():
    container = build(agent_dev_default_user_email="sv.b@example.test")
    client = TestClient(create_app(container.settings, container))
    assert client.get("/api/agent-tools/me/internship").status_code == 401


def test_dev_default_user_is_ignored_in_production_p11():
    container = build()
    # Mô phỏng cấu hình lọt qua kiểm tra: ở production người dùng mặc định không bao giờ hiệu lực.
    settings = make_settings(
        app_env="production", agent_api_service_token="svc-token", jwt_secret="j" * 40, agent_dev_default_user_email="sv.b@example.test"
    )
    assert settings.dev_default_user_email == ""
    prod = Container(settings)
    prod.user_repository, prod.audit_repository = container.user_repository, container.audit_repository
    resolved = prod.agent_subject_resolver
    from vin15.domain.exception import AuthenticationRequiredError

    with pytest.raises(AuthenticationRequiredError):
        resolved.resolve("Bearer svc-token", None)


def test_dev_default_user_missing_in_db_is_401():
    container = build(agent_dev_default_user_email="khong-co@example.test")
    client = TestClient(create_app(container.settings, container))
    assert client.get("/api/agent-tools/me/internship", headers=SERVICE).status_code == 401


# ---- Tool cá nhân: chủ thể do BE quyết (P5) ----
def test_me_endpoints_return_only_the_token_owner_data_p5(client, container):
    a, b = on_behalf(container, STUDENT_A), on_behalf(container, STUDENT_B)
    assert client.get("/api/agent-tools/me/internship", headers=a).json()["internship"]["status"] == "in_progress"
    assert client.get("/api/agent-tools/me/internship", headers=b).json()["internship"]["status"] == "pending_credit"
    repo: FakeInternships = container.internship_repository
    repo.queried_users.clear()
    for name in ME:
        assert client.get(f"/api/agent-tools/me/{name}", headers=a).status_code == 200
    assert set(repo.queried_users) == {STUDENT_A.id}  # không có đường nào chạm tới dữ liệu SV B


def test_subject_parameters_are_ignored_p5(client, container):
    headers = on_behalf(container, STUDENT_A)
    for path in ("internship", "milestones", "progress", "credit-checklist", "requests"):
        response = client.get(
            f"/api/agent-tools/me/{path}", params={"user_id": STUDENT_B.id, "student_id": 4, "email": STUDENT_B.email}, headers=headers
        )
        assert response.status_code == 200
    assert set(container.internship_repository.queried_users) == {STUDENT_A.id}
    body = client.get("/api/agent-tools/me/internship", params={"user_id": STUDENT_B.id}, headers=headers).json()
    assert body["internship"]["status"] == "in_progress"


def test_me_internship_shape_has_no_personal_contact_fields(client, container):
    body = client.get("/api/agent-tools/me/internship", headers=on_behalf(container, STUDENT_A)).json()
    assert body == {
        "available": True,
        "reason": None,
        "internship": {
            "cohort": "2026-K1",
            "status": "in_progress",
            "start_date": "2026-10-10",
            "end_date": "2027-01-01",
            "mode": "onsite",
            "lecturer_name": "Cô Lan",
        },
    }
    text = client.get("/api/agent-tools/me/internship", headers=on_behalf(container, STUDENT_A)).text.lower()
    assert "@" not in text and "email" not in text and "phone" not in text


def test_me_milestones_for_student_a_show_overdue_and_next_action(client, container):
    milestones = client.get("/api/agent-tools/me/milestones", headers=on_behalf(container, STUDENT_A)).json()["milestones"]
    by_code = {m["code"]: m for m in milestones}
    assert by_code["M3"]["status"] == "overdue" and by_code["M3"]["days_left"] == -5
    assert "quá hạn 5 ngày" in by_code["M3"]["next_action"] and "gia hạn" in by_code["M3"]["next_action"]
    assert by_code["M4"]["status"] == "pending" and by_code["M4"]["days_left"] == 34
    assert by_code["M1"]["status"] == "accepted" and by_code["M1"]["next_action"].startswith("Đã hoàn tất")
    assert [m["code"] for m in milestones] == ["M1", "M2", "M3", "M4", "M5"]


def test_me_progress_reports_missing_weeks(client, container):
    body = client.get("/api/agent-tools/me/progress", headers=on_behalf(container, STUDENT_A)).json()
    assert body["journal"] == {"submitted": 4, "expected": 6, "missing_weeks": ["2026-10-31", "2026-11-14"]}
    assert body["evidence"] == {"submitted": 0, "required": 3}


def test_me_credit_checklist_a_vs_b(client, container):
    a = client.get("/api/agent-tools/me/credit-checklist", headers=on_behalf(container, STUDENT_A)).json()
    assert a["all_met"] is False and [i["code"] for i in a["items"]] == ["T1", "T2", "T3", "T4", "T5", "T6"]
    by_code = {i["code"]: i for i in a["items"]}
    assert (by_code["T1"]["met"], by_code["T1"]["value"], by_code["T1"]["threshold"]) == (False, "6 tuần", "≥ 8 tuần")
    assert by_code["T2"]["met"] is True and by_code["T3"]["met"] is False
    assert (by_code["T4"]["met"], by_code["T4"]["value"]) == (False, "4/6 tuần (67%)")
    assert by_code["T5"]["met"] is False and by_code["T6"]["met"] is True
    b = {i["code"]: i for i in client.get("/api/agent-tools/me/credit-checklist", headers=on_behalf(container, STUDENT_B)).json()["items"]}
    assert b["T1"]["met"] and b["T4"]["met"] and not b["T3"]["met"] and not b["T5"]["met"]


def test_me_requests(client, container):
    body = client.get("/api/agent-tools/me/requests", headers=on_behalf(container, STUDENT_A)).json()
    assert [(r["kind"], r["status"]) for r in body["requests"]] == [("milestone_extension", "open")]


def test_student_without_record_gets_available_false(client, container):
    headers = on_behalf(container, STUDENT_NO_RECORD)
    for name in ME:
        body = client.get(f"/api/agent-tools/me/{name}", headers=headers).json()
        assert body["available"] is False and body["reason"] == "no_internship_record", name


@pytest.mark.parametrize("user", [LECTURER, ADMIN])
@pytest.mark.parametrize("name", ME)
def test_lecturer_and_admin_cannot_use_personal_tools(client, container, user, name):
    response = client.get(f"/api/agent-tools/me/{name}", headers=on_behalf(container, user))
    assert response.status_code == 403 and error_of(response)["code"] == "forbidden_role"
    assert container.internship_repository.queried_users == []


# ---- Tool tra quy định ----
def test_policy_search_returns_contract_shape_and_passes_args(client, container):
    response = client.post(
        "/api/agent-tools/policy/search",
        json={"query": "thời lượng tối thiểu", "query_vector": None, "top_k": 3},
        headers=on_behalf(container, LECTURER),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok" and body["mode"] == "keyword"
    assert set(body["chunks"][0]) == {
        "chunk_id",
        "doc_code",
        "doc_title",
        "version",
        "article_no",
        "clause_no",
        "heading",
        "text",
        "effective_from",
        "effective_to",
        "is_sample",
        "score",
    }
    assert body["chunks"][0]["effective_to"] is None and body["chunks"][0]["clause_no"] == "1"
    assert container.policy_search_service.calls == [("search", "thời lượng tối thiểu", None, 3)]


def test_policy_search_validates_body(client, container):
    headers = on_behalf(container, STUDENT_A)
    assert client.post("/api/agent-tools/policy/search", json={"query": "x", "top_k": 9}, headers=headers).status_code == 422
    assert client.post("/api/agent-tools/policy/search", json={"query": ""}, headers=headers).status_code == 422
    assert client.post("/api/agent-tools/policy/search", json={"query": "x"}, headers=headers).status_code == 200  # top_k mặc định 5
    assert container.policy_search_service.calls[-1][3] == 5


def test_policy_search_has_no_date_parameter(client, container):
    """Ngày hiệu lực do BE tính: gửi ``today`` cũng không có tác dụng."""
    client.post(
        "/api/agent-tools/policy/search",
        json={"query": "x", "today": "2020-01-01", "as_of": "2020-01-01"},
        headers=on_behalf(container, STUDENT_A),
    )
    assert container.policy_search_service.calls == [("search", "x", None, 5)]


def test_get_chunk_with_path_id_and_not_found(client, container):
    headers = on_behalf(container, STUDENT_A)
    ok = client.get("/api/agent-tools/policy/chunks/QD-TT-01@v1/d3/k1?with_neighbors=true", headers=headers)
    assert ok.status_code == 200 and ok.json()["chunk"]["chunk_id"] == "QD-TT-01@v1/d3/k1" and ok.json()["neighbors"] == []
    assert container.policy_search_service.calls[-1] == ("get_chunk", "QD-TT-01@v1/d3/k1", True)
    missing = client.get("/api/agent-tools/policy/chunks/QD-TT-01@v1/d9", headers=headers)
    assert missing.status_code == 404 and error_of(missing)["code"] == "not_found"


# ---- Audit (P8) và chỉ-đọc (P1) ----
def test_every_tool_call_writes_exactly_one_agent_audit_event_p8(client, container):
    headers = on_behalf(container, STUDENT_A, conv="c7", turn="t3")
    calls = [
        client.post("/api/agent-tools/policy/search", json={"query": "thời lượng"}, headers=headers),
        client.get("/api/agent-tools/policy/chunks/QD-TT-01@v1/d3/k1", headers=headers),
        *[client.get(f"/api/agent-tools/me/{name}", headers=headers) for name in ME],
    ]
    assert all(c.status_code == 200 for c in calls)
    entries = container.audit_repository.entries
    assert [e.action for e in entries] == [
        "search_policy",
        "get_policy_clause",
        "get_my_internship",
        "get_my_milestones",
        "get_my_progress",
        "get_my_credit_checklist",
        "get_my_requests",
    ]
    assert all(
        e.actor_kind.value == "agent" and e.entity == "agent_tool" and e.actor_id == STUDENT_A.id and e.actor_role == "student"
        for e in entries
    )
    assert all("conv=c7 turn=t3" in e.reason for e in entries)


def test_denied_call_is_audited_once_too(client, container):
    client.get("/api/agent-tools/me/progress", headers=on_behalf(container, LECTURER))
    entries = container.audit_repository.entries
    assert len(entries) == 1 and entries[0].after["outcome"] == "forbidden_role" and entries[0].actor_id == LECTURER.id


def test_audit_params_are_pii_redacted(client, container):
    client.post(
        "/api/agent-tools/policy/search",
        json={"query": "email em là sv.a@truong.edu.vn sdt 0912345678 hỏi thời lượng"},
        headers=on_behalf(container, STUDENT_A),
    )
    logged = container.audit_repository.entries[-1].after["params"]["query"]
    assert "sv.a@truong.edu.vn" not in logged and "0912345678" not in logged and "[EMAIL_1]" in logged and "[SDT_1]" in logged


def test_failed_service_auth_writes_no_tool_audit(client, container):
    client.get("/api/agent-tools/me/internship")
    assert container.audit_repository.entries == []


def test_agent_tools_are_read_only_p1(app):
    """Mọi route dưới /api/agent-tools chỉ là GET, trừ POST tìm kiếm (không đổi dữ liệu)."""
    paths = {p: item for p, item in app.openapi()["paths"].items() if p.startswith("/api/agent-tools")}
    assert len(paths) == 7
    for path, item in paths.items():
        for method in item:
            assert method == "get" or (method == "post" and path == "/api/agent-tools/policy/search"), (path, method)


def test_no_agent_tool_parameter_names_a_subject_p2(app):
    schema = app.openapi()
    forbidden = {"user_id", "student_id", "email", "owner_id", "subject", "on_behalf_of"}
    for path, item in schema["paths"].items():
        if not path.startswith("/api/agent-tools"):
            continue
        for operation in item.values():
            names = {p["name"].lower().replace("-", "_") for p in operation.get("parameters", [])}
            body = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
            ref = body.get("$ref", "").rsplit("/", 1)[-1]
            names |= set(schema["components"]["schemas"].get(ref, {}).get("properties", {}))
            assert not names & forbidden, (path, names & forbidden)


def test_db_not_configured_is_503_in_contract_shape():
    settings = make_settings(agent_api_service_token="svc-token")
    client = TestClient(create_app(settings, Container(settings)))
    response = client.get("/api/agent-tools/me/internship", headers=SERVICE)
    assert response.status_code == 503 and error_of(response)["code"] == "database_unavailable"
