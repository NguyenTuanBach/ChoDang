import pytest

from src.config import Settings
from src.core import security


def test_revoked_token_is_rejected(monkeypatch):
    settings = __import__("src.config", fromlist=["get_settings"]).get_settings()
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    security.clear_revoked_tokens()
    token = security.create_token(7, "student")
    assert security.decode_token(token)["sub"] == 7
    security.revoke_token(token)
    with pytest.raises(security.TokenError, match="thu hồi"):
        security.decode_token(token)
    security.clear_revoked_tokens()


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError, match="JWT_SECRET production"):
        Settings(_env_file=None, app_env="production", jwt_secret="dev-only-change-me")


def test_production_accepts_long_random_jwt_secret():
    settings = Settings(_env_file=None, app_env="production", jwt_secret="x" * 48)
    assert settings.app_env == "production"
