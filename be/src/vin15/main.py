"""Backend VIN-15: ``uvicorn vin15.main:create_app --factory`` hoặc ``python -m vin15``."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import anyio.to_thread
import uvicorn
from fastapi import FastAPI

from .config import openapi_config
from .config.container import Container
from .config.cors_config import configure_cors
from .config.settings import Settings, get_settings
from .infrastructure.persistence.migrations import SqlMigrator
from .presentation.advice.global_exception_handler import register_exception_handlers
from .presentation.controller import (
    agent_controller,
    agent_tools_controller,
    assistant_controller,
    health_controller,
    policy_admin_controller,
)
from .presentation.rate_limit import RateLimitMiddleware, Rule

log = logging.getLogger("vin15")


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    issues = settings.validate_production()
    if issues:
        lines = "\n".join("- " + issue for issue in issues)
        raise RuntimeError(f"Kiểm tra cấu hình production thất bại. Đặt APP_ENV=development để bỏ qua, hoặc sửa:\n{lines}")

    container = container or Container(settings)
    if settings.database_url.strip() and not settings.has_database:
        log.warning("DATABASE_URL không phải Postgres: BE chạy không database")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        database = container.database
        if database is not None:
            await anyio.to_thread.run_sync(database.open)
            if settings.migrations_enabled:
                applied = await anyio.to_thread.run_sync(SqlMigrator(database).migrate)
                log.info("Migration đã áp dụng: %s", applied or "không có")
        yield
        if database is not None:
            await anyio.to_thread.run_sync(database.close)

    app = FastAPI(
        title=openapi_config.TITLE,
        description=openapi_config.DESCRIPTION,
        version=openapi_config.VERSION,
        openapi_tags=openapi_config.TAGS,
        lifespan=lifespan,
    )
    app.state.container = container
    configure_cors(app, settings)
    app.add_middleware(
        RateLimitMiddleware,
        rules=[
            Rule("/api/auth/", limit=30),
            Rule("/api/invitations", limit=30),
            # WebSocket không đi qua middleware này: giới hạn ask/kết nối nằm trong handler. Vé thì giới hạn ở đây.
            Rule("/api/assistant/ws-ticket", limit=30),
        ],
    )
    register_exception_handlers(app)
    app.include_router(health_controller.router)
    app.include_router(agent_controller.router)
    app.include_router(agent_tools_controller.router)
    app.include_router(assistant_controller.router)
    app.include_router(policy_admin_controller.router)
    return app


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    uvicorn.run("vin15.main:create_app", factory=True, host=settings.app_host, port=settings.app_port)
