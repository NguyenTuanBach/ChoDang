from fastapi import APIRouter, Depends, Response

from vin15.config.container import Container
from vin15.presentation.dto.health_response import HealthResponse

from .dependencies import container

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("", response_model=HealthResponse, summary="Liveness: tiến trình còn sống")
def health(app: Container = Depends(container)) -> HealthResponse:
    return HealthResponse.of(app.health_service.get_health())


@router.get("/readiness", response_model=HealthResponse, summary="Readiness: kiểm tra cả DB. Chưa sẵn sàng thì trả 503")
def readiness(response: Response, app: Container = Depends(container)) -> HealthResponse:
    result = app.health_service.get_readiness()
    if result.status != "UP":
        response.status_code = 503
    return HealthResponse.of(result)
