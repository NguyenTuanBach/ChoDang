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
