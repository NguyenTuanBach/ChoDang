"""``vin15-agent-api``: chạy agent-api bằng uvicorn."""

from __future__ import annotations

import logging

import uvicorn

from vin15_agent.shared.settings import get_settings


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run("vin15_agent.runtime.http.app:create_app", factory=True, host=settings.agent_api_host, port=settings.agent_api_port)
