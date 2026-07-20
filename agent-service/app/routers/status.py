from fastapi import APIRouter
from app.models.responses import StatusResponse, HealthResponse
from app.core.state import agent_state

router = APIRouter(tags=["status"])


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@router.get("/status", response_model=StatusResponse)
async def status():
    return StatusResponse(
        active=agent_state.agent is not None,
        task=agent_state.task,
        step=agent_state.step,
        paused=agent_state.paused,
        provider=agent_state.provider,
    )