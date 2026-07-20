# WhatsApp Integration (via WAHA)

The FastAPI service communicates with WhatsApp through [WAHA](https://waha.devlike.pro/) (WhatsApp HTTP API). WAHA runs as a separate service and exposes a REST API for sending messages and receiving inbound webhooks. This document covers the outbound message format, the inbound webhook contract, and the command routing logic.

## Architecture

```
┌──────────┐   message    ┌──────────┐  POST /webhook   ┌─────────────────┐
│  WhatsApp │ ──────────▶ │   WAHA   │ ───────────────▶ │  agent-service  │
│  (phone)  │ ◀────────── │          │ ◀─────────────── │  (FastAPI)      │
└──────────┘  sendText    └──────────┘  POST /api/sendText └─────────────────┘
```

- **Outbound** (service → user): the service POSTs to WAHA's `/api/sendText` endpoint.
- **Inbound** (user → service): WAHA POSTs the user's message to the service's `/webhook` endpoint.

## Configuration (`app/config.py`)

| Setting | Default | Purpose |
| --- | --- | --- |
| `waha_url` | `http://192.168.2.152:3001` | Base URL of the WAHA instance. |
| `waha_api_key` | `""` | Value of the `X-Api-Key` header. Leave empty if WAHA auth is disabled. |
| `whatsapp_chat_id` | `120363407334128082@g.us` | The chat to send messages to. `@g.us` = group, `@c.us` = direct chat. |
| `whatsapp_session` | `default` | WAHA session name. |

All overridable via environment variables — see [`environment.md`](./environment.md).

## Outbound: `send_message` (`services/whatsapp_service.py`)

```python
async def send_message(message: str) -> None:
```

POSTs to `{waha_url}/api/sendText` with:

```json
{
  "chatId": "<whatsapp_chat_id>",
  "text": "<message>",
  "session": "<whatsapp_session>",
  "linkPreview": false
}
```

Headers: `X-Api-Key: <waha_api_key>`, `Content-Type: application/json`.

- Timeout: 10s total.
- Non-2xx responses and exceptions are logged to stdout but **do not raise** — WhatsApp is best-effort; the agent should keep running even if messaging fails.

### Higher-level helpers

| Function | When it's called | Message shape |
| --- | --- | --- |
| `send_consolidated_pause(step, max_steps, current_url, current_thought, steps_log)` | Every `pause_every_n_steps` from the `on_step_end` hook | `⏸️ Paused at step X/Y` + progress summary + steps log + reply instructions |
| `send_error(error)` | From `agent_service.run()`'s `except` block | Categorized: timeout / network / browser / generic |

The pause message includes the reply instructions:

```
Reply with:
• continue — keep going
• stop — end the task
• Any instruction — redirect the agent
```

### Error categorization (`send_error`)

| Condition | Prefix |
| --- | --- |
| `TimeoutError` or `"timeout"` in message | `⏱️ Page timed out. The site may be slow or blocking bots.` |
| `net::ERR_` in message | `🌐 Network error reaching the site.` |
| `"Executable path"` or `Browser` in exception type | `🔧 Browser configuration error.` |
| otherwise | `❌ Error: <first 300 chars>` |

## Inbound: `POST /webhook` (`routers/whatsapp.py`)

WAHA is configured to POST inbound messages here. The expected payload shape:

```json
{
  "event": "message",
  "payload": {
    "body": "continue",
    "from": "1234567890@c.us"
  }
}
```

The handler:

1. Parses JSON (returns `{"status":"ignored","reason":"invalid json"}` on parse failure).
2. Checks `event == "message"`; otherwise ignores.
3. Extracts `text = (payload.body or payload.text or "").strip().lower()`.
4. Routes by text content (see table below).

### Command routing

| Inbound text | Action | Response |
| --- | --- | --- |
| `continue`, `go`, `proceed` | `agent_service.resume(ResumeRequest())` | `TaskResponse(status="resumed", ...)` |
| `stop`, `cancel`, `end` | `agent_service.stop(StopRequest())` | `TaskResponse(status="stopped", ...)` |
| anything else, **agent running** | `agent_service.resume(ResumeRequest(instruction=text))` — injects the text as a new task instruction | `TaskResponse(status="resumed", ...)` |
| anything else, **no agent running** | `asyncio.create_task(agent_service.run(TaskRequest(task=text)))` — starts a new task | `{"status":"started","task":text}` |

So a user can:

- Send `find me the cheapest RTX 4070 on bestbuy.ca` to start a task (when idle).
- Send `continue` to resume a paused task.
- Send `stop` to end it.
- Send `also check amazon.ca` while a task is running to redirect it (injected via `agent.add_new_task`).

## Configuring WAHA (external)

WAHA itself is not part of this repo. To set it up:

1. Run WAHA (e.g. via its Docker image) and scan the WhatsApp QR code to attach a session.
2. Note the WAHA base URL and API key (if you enabled auth).
3. Configure the webhook in WAHA to POST to `http://<agent-service-host>:8765/webhook`.
4. Set `WAHA_URL`, `WAHA_API_KEY`, `WHATSAPP_CHAT_ID`, `WHATSAPP_SESSION` in `agent-service/.env`.

See the [WAHA docs](https://waha.devlike.pro/) for full setup details.

## Files

| File | Responsibility |
| --- | --- |
| `app/services/whatsapp_service.py` | `send_message`, `send_consolidated_pause`, `send_error`, `_action_label` |
| `app/routers/whatsapp.py` | `POST /webhook` handler + command routing |
| `app/config.py` | WAHA URL / API key / chat ID / session settings |

## Gotchas

- **`linkPreview: false`** is set on every send to avoid WhatsApp's link-preview bars cluttering messages with URLs.
- **Lowercasing** — inbound text is lowercased before routing, so `Continue`, `CONTINUE`, and `continue` all match.
- **No authentication on the webhook** — anyone who can reach `/webhook` can start/stop tasks. If you expose the service publicly, put it behind a reverse proxy with auth, or add a shared secret check.
- **Best-effort sends** — `send_message` swallows errors. Don't rely on WhatsApp delivery for control flow; the HTTP endpoints (`/task`, `/resume`, `/stop`) are the source of truth.