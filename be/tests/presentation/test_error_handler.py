import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_settings
from vin15.domain.exception import (
    AuthenticationRequiredError,
    PermissionDeniedError,
    ResourceNotFoundError,
    StateConflictError,
)
from vin15.main import create_app


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (AuthenticationRequiredError("a"), 401, "authentication_required"),
        (PermissionDeniedError("b"), 403, "permission_denied"),
        (ResourceNotFoundError("c"), 404, "not_found"),
        (StateConflictError("d"), 409, "conflict"),
    ],
)
def test_domain_errors_map_to_http(error, status, code):
    app = create_app(make_settings())

    @app.get("/boom")
    def boom():
        raise error

    response = TestClient(app).get("/boom")
    assert response.status_code == status
    assert response.json() == {"error": code, "message": str(error)}


def test_unexpected_error_hides_details():
    app = create_app(make_settings())

    @app.get("/boom")
    def boom():
        raise RuntimeError("mật khẩu db là hunter2")

    response = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert "hunter2" not in response.text
