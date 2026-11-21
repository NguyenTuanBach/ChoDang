import pytest

from tests.conftest import make_settings


def test_defaults_run_without_database_and_agent():
    s = make_settings()
    assert s.has_database is False
    assert s.agent_api_url == ""
    assert s.app_port == 8000
    assert s.validate_production() == []


def test_has_database_only_for_postgres_urls():
    assert make_settings(database_url="postgresql://u:p@h:5432/db").has_database
    assert make_settings(database_url="postgres://u:p@h/db").has_database
    assert not make_settings(database_url="sqlite:///./data/app.db").has_database


def test_lists_are_trimmed_and_lowercased():
    s = make_settings(cors_origins=" http://a.test , http://b.test ,", app_admin_emails="Admin@X.vn, ,qtv@x.vn")
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]
    assert s.admin_email_list == ["admin@x.vn", "qtv@x.vn"]


def test_production_rejects_unsafe_defaults():
    issues = make_settings(app_env="production", agent_api_url="http://agent:8100").validate_production()
    text = " ".join(issues)
    assert "JWT_SECRET" in text
    assert "DATABASE_URL" in text
    assert "CORS_ORIGINS" in text
    assert "AGENT_API_SERVICE_TOKEN" in text
    assert "APP_ADMIN_EMAILS" in text


def test_production_accepts_safe_config():
    s = make_settings(
        app_env="production",
        jwt_secret="x" * 40,
        database_url="postgresql://u:p@h:5432/db",
        cors_origins="https://truong.edu.vn",
        agent_api_url="http://agent:8100",
        agent_api_service_token="a-real-secret",
        app_admin_emails="qtv@truong.edu.vn",
    )
    assert s.validate_production() == []


def test_dev_default_user_is_rejected_in_production():
    safe = dict(
        app_env="production",
        jwt_secret="x" * 40,
        database_url="postgresql://u:p@h:5432/db",
        cors_origins="https://truong.edu.vn",
        agent_api_url="http://agent:8100",
        agent_api_service_token="a-real-secret",
        app_admin_emails="qtv@truong.edu.vn",
    )
    assert make_settings(**safe).validate_production() == []
    issues = make_settings(**safe, agent_dev_default_user_email="sv.a@example.test").validate_production()
    assert any("AGENT_DEV_DEFAULT_USER_EMAIL" in issue for issue in issues)
    # Dù lọt cấu hình, ở production không bao giờ có người dùng mặc định.
    assert make_settings(**safe, agent_dev_default_user_email="sv.a@example.test").dev_default_user_email == ""


def test_dev_default_user_in_development_is_normalized():
    assert make_settings(agent_dev_default_user_email=" SV.A@Example.test ").dev_default_user_email == "sv.a@example.test"
    assert make_settings().dev_default_user_email == ""


def test_app_refuses_to_start_with_dev_default_user_in_production():
    from vin15.main import create_app

    with pytest.raises(RuntimeError, match="AGENT_DEV_DEFAULT_USER_EMAIL"):
        create_app(make_settings(app_env="production", agent_dev_default_user_email="sv.a@example.test"))


def test_agent_ws_url_derives_from_http_url():
    assert make_settings(agent_api_url="http://localhost:8100/").agent_ws_url == "ws://localhost:8100/v1/policy-assistant/ws"
    assert make_settings(agent_api_url="https://agent.x").agent_ws_url == "wss://agent.x/v1/policy-assistant/ws"
    assert make_settings().agent_ws_url == ""


def test_assistant_defaults_match_env_example():
    s = make_settings()
    assert (s.policy_no_match_threshold, s.assistant_ask_per_minute, s.assistant_max_connections_per_user) == (0.25, 10, 3)
    assert (s.assistant_max_frame_bytes, s.assistant_history_turns, s.assistant_ws_auth_seconds) == (65536, 6, 5.0)
