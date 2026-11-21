from __future__ import annotations

from pydantic import BaseModel


class AgentStatusResponse(BaseModel):
    #: UP | DOWN | DISABLED
    status: str
    detail: str = ""
    agent: dict = {}
