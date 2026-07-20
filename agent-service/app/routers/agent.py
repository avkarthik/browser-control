from fastapi import APIRouter
from app.models.requests import TaskRequest, ResumeRequest, StopRequest
from app.models.responses import TaskResponse
from app.services import agent_service
from app.core.state import agent_state
import asyncio

router = APIRouter(tags=["agent"])


@router.post("/task", response_model=TaskResponse)
async def start_task(req: TaskRequest):
    if agent_state.agent is not None:
        return TaskResponse(status="busy", message="Agent already running")
    asyncio.create_task(agent_service.run(req))
    return TaskResponse(status="started", task=req.task)


@router.post("/resume", response_model=TaskResponse)
async def resume_task(req: ResumeRequest):
    return await agent_service.resume(req)


@router.post("/stop", response_model=TaskResponse)
async def stop_task(req: StopRequest):
    return await agent_service.stop(req)