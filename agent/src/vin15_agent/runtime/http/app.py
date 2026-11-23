"""HTTP app của agent-api.

- ``GET /healthz``: không cần token, cho healthcheck của Docker.
- ``GET /v1/info``: cần service token, để BE xác nhận kết nối và token khớp.
- ``POST /v1/embeddings`` và ``WS /v1/policy-assistant/ws``: trợ lý hỏi đáp chính sách (``runtime/http/policy_assistant.py``).
- ``POST /v1/intake/extract``, ``/v1/monitor/review``, ``/v1/pre-review``: agent một-lượt có đầu ra cấu trúc, không công cụ ghi
  (``runtime/http/structured_agents.py``). Tất cả đòi service token.
"""

from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException

from vin15_agent import __version__
from vin15_agent.core.ai_client import AiClient
from vin15_agent.runtime.http.policy_assistant import register_policy_assistant
from vin15_agent.runtime.http.security import service_token_matches
from vin15_agent.runtime.http.structured_agents import register_structured_agents
from vin15_agent.shared.settings import Settings, get_settings


def create_app(
    settings: Settings | None = None,
    *,
    ai_client: AiClient | None = None,
    be_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """``ai_client`` và ``be_transport`` chỉ để test thay LLM giả / BE giả; production để mặc định."""
    settings = settings or get_settings()
    issues = settings.validate_production()
    if issues:
        raise RuntimeError("Kiểm tra cấu hình production thất bại:\n" + "\n".join("- " + i for i in issues))

    def require_service_token(authorization: str = Header(default="")) -> None:
        if not service_token_matches(settings, authorization):
            raise HTTPException(status_code=401, detail="Sai hoặc thiếu service token")

    ai_client = ai_client or AiClient.from_settings(settings)
    app = FastAPI(title="VIN-15 Agent API", version=__version__)
    app.state.ai_client = ai_client
    agents = ["policy_assistant", "intake", "monitor", "pre_review", "journal_advice", "outline_review"]
    app.state.policy_assistant = register_policy_assistant(
        app, settings=settings, ai=ai_client, require_service_token=require_service_token, be_transport=be_transport
    )
    register_structured_agents(app, settings=settings, ai=ai_client, require_service_token=require_service_token)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "UP"}

    @app.get("/v1/info", dependencies=[Depends(require_service_token)])
    def info() -> dict:
        return {"service": "vin15-agent-api", "version": __version__, "agents": agents, "llm_providers": ai_client.providers}

    return app
