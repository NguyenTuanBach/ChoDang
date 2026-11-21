"""Cấu hình mới của trợ lý hỏi đáp (task 1.1)."""

from vin15_agent.shared.settings import Settings


def test_assistant_defaults():
    s = Settings(_env_file=None)
    assert s.openai_embedding_model == "text-embedding-3-small"
    assert s.assistant_temperature == 0.2
    assert (s.agent_max_rounds, s.agent_max_tool_calls, s.agent_turn_seconds) == (6, 8, 25.0)
    assert s.be_api_url == "http://localhost:8000"
    assert s.pii_student_id_pattern == ""
    assert s.school_name == "Trường"


def test_assistant_settings_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_MAX_ROUNDS", "3")
    monkeypatch.setenv("BE_API_URL", "http://be:9000")
    monkeypatch.setenv("PII_STUDENT_ID_PATTERN", r"SV\d{6}")
    s = Settings(_env_file=None)
    assert (s.agent_max_rounds, s.be_api_url, s.pii_student_id_pattern) == (3, "http://be:9000", r"SV\d{6}")
