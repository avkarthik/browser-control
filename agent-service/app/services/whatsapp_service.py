"""WhatsApp messaging via WAHA (WhatsApp HTTP API)."""

import aiohttp
from app.config import settings


# ---------------------------------------------------------------------------
# Core send — all other helpers delegate to this
# ---------------------------------------------------------------------------
async def send_message(message: str) -> None:
    """Send a text message to the configured WhatsApp chat via WAHA."""
    waha_url = settings.waha_url.rstrip("/")
    payload = {
        "chatId": settings.whatsapp_chat_id,
        "text": message,
        "session": settings.whatsapp_session,
        "linkPreview": False,  # disable WhatsApp link preview bars
    }
    headers = {
        "X-Api-Key": settings.waha_api_key,
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{waha_url}/api/sendText",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    print(f"[WhatsApp] WAHA returned {resp.status}: {body[:300]}")
    except Exception as e:
        print(f"[WhatsApp] Failed to send: {e}")


# ---------------------------------------------------------------------------
# Extracts a human-readable label from a browser-use action dict
# ---------------------------------------------------------------------------
def _action_label(action) -> str:
    """Convert a browser-use action dict like {'click': {...}} to 'click (index 561)'."""
    try:
        if isinstance(action, dict):
            for key, val in action.items():
                if key == "interacted_element":
                    continue
                if isinstance(val, dict):
                    # Pick the most useful sub-field
                    for sub in ("text", "selector", "seconds", "url"):
                        if sub in val:
                            label = str(val[sub])[:50]
                            return f"{key}: {label}"
                    return key
                return f"{key}: {str(val)[:50]}"
        return str(action)[:80]
    except Exception:
        return str(action)[:80]


# ---------------------------------------------------------------------------
# Consolidated pause notification — one message with full progress summary
# ---------------------------------------------------------------------------
async def send_consolidated_pause(
    step: int,
    max_steps: int,
    current_url: str,
    current_thought: str,
    steps_log: list[str],
) -> None:
    """Send ONE consolidated message with all steps since last pause."""
    log_lines = "\n".join(steps_log) if steps_log else "(no steps recorded)"

    # Truncate thought: take first line or first 200 chars
    thought_text = current_thought.split("\n")[0][:250] if current_thought else "processing..."

    message = (
        f"⏸️ *Paused at step {step}/{max_steps}*\n\n"
        f"📊 *Progress Summary*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{log_lines}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💭 {thought_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Reply with:\n"
        f"• *continue* — keep going\n"
        f"• *stop* — end the task\n"
        f"• Any instruction — redirect the agent"
    )
    await send_message(message)


# ---------------------------------------------------------------------------
# Error messages — categorized for user-friendliness
# ---------------------------------------------------------------------------
async def send_error(error: Exception) -> None:
    """Send a categorized error message based on the exception type/content."""
    msg = str(error)

    if isinstance(error, TimeoutError) or "TimeoutError" in msg or "timeout" in msg.lower():
        prefix = "⏱️ Page timed out. The site may be slow or blocking bots."
    elif "net::ERR_" in msg:
        prefix = "🌐 Network error reaching the site."
    elif "Executable path" in msg or "Browser" in type(error).__name__:
        prefix = "🔧 Browser configuration error."
    else:
        short = msg[:300] + ("..." if len(msg) > 300 else "")
        prefix = f"❌ Error: {short}"

    await send_message(prefix)