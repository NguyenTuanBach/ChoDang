"""Xác thực: phiên bằng cookie, /me, đăng xuất, và đăng nhập dev (chỉ ngoài production)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import make_settings
from tests.fakes import ADMIN, LECTURER, REVOKED, STUDENT_A, STUDENT_B, FakeAudit, FakeUsers, make_user
from vin15.config.container import Container
from vin15.domain.model.user import Role
from vin15.main import create_app

REAL_USER = make_user(9, "that@truong.edu.vn", Role.STUDENT)


def build(**overrides) -> Container:
    container = Container(make_settings(jwt_secret="j" * 40, **overrides))
    container.user_repository = FakeUsers(ADMIN, LECTURER, STUDENT_A, STUDENT_B, REVOKED, REAL_USER)
    container.audit_repository = FakeAudit()
    return container


def app_client(container: Container) -> TestClient:
    return TestClient(create_app(container.settings, container))


def production_container() -> Container:
    settings = make_settings(
        app_env="production",
        jwt_secret="j" * 40,
        database_url="postgresql://u:p@h:5432/db",
        migrations_enabled=False,
        cors_origins="https://truong.edu.vn",
        agent_api_url="http://agent:8100",
        agent_api_service_token="real-secret",
        app_admin_emails="qtv@truong.edu.vn",
    )
    container = Container(settings)
    container.database = None
    container.user_repository = FakeUsers(ADMIN, STUDENT_A)
    container.audit_repository = FakeAudit()
    return container


# ---- Đăng nhập dev ----
def test_dev_accounts_lists_active_sample_accounts_grouped_by_role():
    client = app_client(build())
    body = client.get("/api/auth/dev-accounts").json()
    assert [(u["email"], u["role"]) for u in body] == [
        ("qtv@example.test", "admin"),
        ("gv@example.test", "lecturer"),
        ("sv.a@example.test", "student"),
        ("sv.b@example.test", "student"),
    ]
    assert set(body[0]) == {"id", "email", "full_name", "role"}


def test_dev_login_sets_httponly_session_cookie_and_me_returns_that_user():
    container = build()
    client = app_client(container)
    assert client.get("/api/auth/me").status_code == 401
    response = client.post("/api/auth/dev-login", json={"email": "GV@example.test"})
    assert response.status_code == 200 and response.json()["role"] == "lecturer"
    cookie = response.headers["set-cookie"].lower()
    assert "session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    me = client.get("/api/auth/me").json()
    assert me["email"] == "gv@example.test" and me["role"] == "lecturer" and me["id"] == str(LECTURER.id)
    entry = container.audit_repository.entries[-1]
    assert (entry.entity, entry.action, entry.actor_id, entry.actor_role) == ("session", "dev_login", LECTURER.id, "lecturer")


def test_switching_account_replaces_the_session():
    client = app_client(build())
    client.post("/api/auth/dev-login", json={"email": "qtv@example.test"})
    assert client.get("/api/auth/me").json()["role"] == "admin"
    client.post("/api/auth/dev-login", json={"email": "sv.a@example.test"})
    assert client.get("/api/auth/me").json()["role"] == "student"


def test_dev_login_refuses_non_sample_unknown_and_revoked_accounts():
    container = build()
    client = app_client(container)
    assert client.post("/api/auth/dev-login", json={"email": REAL_USER.email}).status_code == 403
    assert client.post("/api/auth/dev-login", json={"email": "khong-co@example.test"}).status_code == 401
    assert client.post("/api/auth/dev-login", json={"email": REVOKED.email}).status_code == 401
    assert client.post("/api/auth/dev-login", json={}).status_code == 422
    assert container.audit_repository.entries == []  # từ chối thì không ghi đăng nhập
    assert "session" not in client.cookies


def test_bearer_token_still_works_and_beats_cookie():
    container = build()
    client = app_client(container)
    client.post("/api/auth/dev-login", json={"email": "sv.a@example.test"})
    token = container.token_service.create(ADMIN.id, "admin")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["role"] == "admin"


# ---- Đăng xuất và token hỏng ----
def test_logout_revokes_token_and_clears_cookie():
    container = build()
    client = app_client(container)
    client.post("/api/auth/dev-login", json={"email": "sv.a@example.test"})
    token = client.cookies["session"]
    assert client.post("/api/auth/logout").status_code == 204
    assert "session" not in client.cookies
    assert client.get("/api/auth/me").status_code == 401
    # Token đã thu hồi không dùng lại được dù bị giữ.
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_logout_without_session_or_with_garbage_token_is_204():
    client = app_client(build())
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("session", "rac")
    assert client.post("/api/auth/logout").status_code == 204


def test_garbage_or_revoked_user_session_is_401():
    container = build()
    client = app_client(container)
    client.cookies.set("session", "khong.phai.token")
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("session", container.token_service.create(REVOKED.id, "student"))
    assert client.get("/api/auth/me").status_code == 401


def test_agent_scoped_token_is_not_a_session():
    container = build()
    client = app_client(container)
    client.cookies.set("session", container.token_service.create(STUDENT_A.id, "student", scope="agent"))
    assert client.get("/api/auth/me").status_code == 401


# ---- Production: không có đường đăng nhập dev ----
def test_dev_login_routes_do_not_exist_in_production():
    container = production_container()
    client = app_client(container)
    assert client.get("/api/auth/dev-accounts").status_code == 404
    assert client.post("/api/auth/dev-login", json={"email": "qtv@example.test"}).status_code == 404
    # Đường chung vẫn có, và vẫn đòi đăng nhập.
    assert client.get("/api/auth/me").status_code == 401
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/auth/dev-login" not in paths and "/api/auth/me" in paths


def test_dev_login_enabled_only_outside_production():
    assert make_settings().dev_login_enabled is True
    assert make_settings(app_env="production").dev_login_enabled is False
