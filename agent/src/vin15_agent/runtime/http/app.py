"""HTTP app của agent-api.

- ``GET /healthz``: không cần token, cho healthcheck của Docker.
- ``GET /v1/info``: cần service token, để BE xác nhận kết nối và token khớp.
Các endpoint của agent (giám sát, trợ lý, tiền thẩm) sẽ thêm ở ``/v1/...`` và đều đòi token.
"""

from __future__ import annotations

import hmac

from fastapi import Depends, FastAPI, Header, HTTPException

from vin15_agent import __version__
from vin15_agent.shared.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    issues = settings.validate_production()
    if issues:
        raise RuntimeError("Kiểm tra cấu hình production thất bại:\n" + "\n".join("- " + i for i in issues))

    def require_service_token(authorization: str = Header(default="")) -> None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(token.encode(), settings.agent_api_service_token.encode()):
            raise HTTPException(status_code=401, detail="Sai hoặc thiếu service token")

    app = FastAPI(title="VIN-15 Agent API", version=__version__)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "UP"}

    @app.get("/v1/info", dependencies=[Depends(require_service_token)])
    def info() -> dict:
        return {"service": "vin15-agent-api", "version": __version__, "agents": []}

    return app
