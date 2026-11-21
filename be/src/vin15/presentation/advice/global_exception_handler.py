"""Đổi lỗi domain thành phản hồi HTTP thống nhất ``{"error": <mã>, "message": <nội dung>}``."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from vin15.domain.exception import (
    AgentUnavailableError,
    AuthenticationRequiredError,
    DatabaseUnavailableError,
    InvalidInputError,
    PermissionDeniedError,
    ResourceNotFoundError,
    StateConflictError,
)

log = logging.getLogger(__name__)

_STATUS: dict[type[Exception], tuple[int, str]] = {
    AuthenticationRequiredError: (401, "authentication_required"),
    PermissionDeniedError: (403, "permission_denied"),
    ResourceNotFoundError: (404, "not_found"),
    StateConflictError: (409, "conflict"),
    InvalidInputError: (422, "invalid_input"),
    AgentUnavailableError: (503, "agent_unavailable"),
    DatabaseUnavailableError: (503, "database_unavailable"),
}


def register_exception_handlers(app: FastAPI) -> None:
    def make(status: int, code: str):
        async def handler(_request: Request, error: Exception) -> JSONResponse:
            return JSONResponse(status_code=status, content={"error": code, "message": str(error)})

        return handler

    for exc_type, (status, code) in _STATUS.items():
        app.add_exception_handler(exc_type, make(status, code))

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, error: Exception) -> JSONResponse:
        # Không lộ chi tiết nội bộ cho client.
        log.error("Lỗi không lường trước: %s", type(error).__name__, exc_info=error)
        return JSONResponse(status_code=500, content={"error": "internal_error", "message": "Lỗi hệ thống"})
