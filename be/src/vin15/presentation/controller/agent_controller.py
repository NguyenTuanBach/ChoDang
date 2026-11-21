from fastapi import APIRouter, Depends, Response

from vin15.config.container import Container
from vin15.domain.exception import AgentUnavailableError
from vin15.presentation.dto.agent_status_response import AgentStatusResponse

from .dependencies import container

router = APIRouter(prefix="/api/agent", tags=["Agent"])


@router.get("/health", response_model=AgentStatusResponse, summary="Trạng thái kết nối tới agent-api (cổng riêng)")
async def agent_health(response: Response, app: Container = Depends(container)) -> AgentStatusResponse:
    client = app.agent_client
    if not client.enabled:
        return AgentStatusResponse(status="DISABLED", detail="Chưa cấu hình AGENT_API_URL")
    try:
        await client.health()
        info = await client.info()
    except AgentUnavailableError as error:
        response.status_code = 503
        return AgentStatusResponse(status="DOWN", detail=str(error))
    return AgentStatusResponse(status="UP", agent=info)
