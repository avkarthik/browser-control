from pydantic import BaseModel


class TaskResponse(BaseModel):
    status: str           # "started" | "busy" | "resumed" | "stopped" | "error"
    task: str = ""
    message: str = ""


class StatusResponse(BaseModel):
    active: bool
    task: str | None
    step: int
    paused: bool
    provider: str | None


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"