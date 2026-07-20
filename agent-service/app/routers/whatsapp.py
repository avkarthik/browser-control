"""Optional WAHA inbound webhook — receives messages directly from WAHA.

If WAHA is configured to POST messages here, this endpoint can handle
/continue, /stop, and new task commands without going through Home Assistant.
"""

from fastapi import APIRouter, Request
from app.models.responses import TaskResponse

router = APIRouter(prefix="/webhook", tags=["whatsapp"])


@router.post("")
async def waha_webhook(request: Request):
    """Receive inbound messages from WAHA.

    Expected payload: WAHA webhook format with 'event' = 'message'.
    Extracts text and routes to resume/stop/create-task logic.
    """
    try:
        data = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid json"}

    # Extract message text from WAHA webhook payload
    # WAHA sends: {"event": "message", "payload": {"body": "...", "from": "..."}}
    event = data.get("event", "")
    if event != "message":
        return {"status": "ignored", "reason": f"not a message event: {event}"}

    payload = data.get("payload", {})
    text = (payload.get("body") or payload.get("text") or "").strip().lower()
    sender = payload.get("from", "")

    print(f"[Webhook] Received from {sender}: {text}")

    # Route commands
    if text in ("continue", "go", "proceed"):
        from app.services import agent_service
        from app.models.requests import ResumeRequest
        return await agent_service.resume(ResumeRequest())

    if text in ("stop", "cancel", "end"):
        from app.services import agent_service
        from app.models.requests import StopRequest
        return await agent_service.stop(StopRequest())

    # Anything else: treat as new task instruction
    # Only start a new task if no agent is running
    from app.core.state import agent_state
    if agent_state.agent is not None:
        from app.services import agent_service
        from app.models.requests import ResumeRequest
        return await agent_service.resume(ResumeRequest(instruction=text))

    from app.services import agent_service
    from app.models.requests import TaskRequest
    import asyncio
    asyncio.create_task(agent_service.run(
        TaskRequest(task=text)
    ))
    return {"status": "started", "task": text}