# Deployment

The FastAPI `agent-service` is designed to run in Docker with a real Chromium and a virtual X display (Xvfb). This document covers the Dockerfile, `docker-compose.yml`, the critical `shm_size` setting, and how to point the service at Home Assistant.

## Quick start (Docker)

```powershell
cd agent-service
cp .env.example .env       # then edit: set GOOGLE_API_KEY, WAHA_URL, etc.
docker compose up --build -d
```

The service listens on `${PORT:-8765}`. Health check: `curl http://localhost:8765/health`.

## Dockerfile walkthrough

`agent-service/Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install Chromium, Xvfb, and Playwright system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium chromium-driver xvfb fonts-liberation libgbm1 libasound2 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxrandr2 libnss3 libnspr4 libu2f-udev \
    && rm -rf /var/lib/apt/lists/*

# Use system Chromium as the Playwright browser
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium
ENV DISPLAY=:99

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
COPY . .

# Start Xvfb + the FastAPI server
CMD Xvfb :99 -screen 0 1280x800x24 -ac +extension RANDR & \
    sleep 1 && \
    python agent_service.py
```

Key points:

- **System Chromium** is installed via apt and pointed to by `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`. This avoids downloading a second Chromium via `playwright install` (that step still runs but reuses the system binary's deps).
- **Xvfb** provides a virtual `:99` display so Chromium can run "headed" (which is what `browser_service.create_browser_profile()` expects — `headless=False` to avoid bot detection). The `CMD` starts Xvfb in the background, waits 1s, then launches the service.
- **`python:3.11-slim`** keeps the image small while still having apt available for Chromium.

## docker-compose.yml

`agent-service/docker-compose.yml`:

```yaml
services:
  agent-service:
    build: .
    container_name: agent-service
    ports:
      - "${PORT:-8765}:8765"
    env_file:
      - .env
    environment:
      - DISPLAY=:99
    volumes:
      - /tmp/.X11-unix:/tmp/.X11-unix
    shm_size: '2gb'          # ← CRITICAL — Chromium crashes without this
    extra_hosts:
      - "homeassistant.local:192.168.2.150"   # ← so agent can reach HA
    restart: unless-stopped
```

### `shm_size: '2gb'` — critical

Chromium uses shared memory for rendering. The default Docker `/dev/shm` is only 64 MB, which causes Chromium to crash with `session deleted because of page crash` or similar. Setting `shm_size: '2gb'` fixes this. **Do not remove it.**

### `extra_hosts`

The `extra_hosts` entry maps `homeassistant.local` to `192.168.2.150` inside the container. This is only needed if your tasks reference Home Assistant by hostname. Adjust or remove the IP/host to match your network.

### `volumes: /tmp/.X11-unix`

Mounts the host's X11 socket into the container. Combined with `DISPLAY=:99`, this lets Chromium talk to Xvfb. (Xvfb itself runs inside the container per the `CMD`, so this mount is belt-and-suspenders — useful if you ever run a second headed app in the same container.)

### `env_file: .env`

All secrets and tunables come from `agent-service/.env`. See [`environment.md`](./environment.md).

### `restart: unless-stopped`

The service auto-restarts on crash or host reboot, but stays stopped if you explicitly `docker compose stop` it.

## Running without Docker (local dev)

See [`agent-service.md`](./agent-service.md#run-locally) for the local PowerShell setup. On Windows/macOS you don't need Xvfb — Chromium opens a real window. The Docker setup is for headless Linux hosts.

## Environment variables

All runtime config is env-driven via `app/config.py` (pydantic-settings). See [`environment.md`](./environment.md) for the complete list. The minimum for a working deployment:

```
GOOGLE_API_KEY=...          # required for Gemini + fallback
WAHA_URL=http://...:3001    # required for WhatsApp notifications
WHATSAPP_CHAT_ID=...@g.us   # required for WhatsApp notifications
```

Other providers are optional — only set `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY` if you use them.

## Health check

```powershell
curl http://localhost:8765/health
# {"status":"ok","version":"1.0.0"}
```

## Status check

```powershell
curl http://localhost:8765/status
# {"active":false,"task":null,"step":0,"paused":false,"provider":null}
```

## Starting a task via HTTP

```powershell
curl -X POST http://localhost:8765/task `
  -H "Content-Type: application/json" `
  -d '{\"task\":\"find cheapest iPhone 16 Pro on bestbuy.ca\",\"max_steps\":15,\"provider\":\"gemini\"}'
```

(Use `Invoke-RestMethod` in PowerShell for cleaner JSON handling.)

## Common issues

| Symptom | Cause | Fix |
| --- | --- | --- |
| Chromium crashes with `page crash` | Missing `shm_size` | Set `shm_size: '2gb'` in compose. |
| `cannot open display :99` | Xvfb didn't start | Check container logs; the `CMD` starts Xvfb before Python. |
| `BROWSER_USE_NO_INTERACTIVE` not set | Old image | Rebuild: `docker compose up --build`. |
| WhatsApp messages not arriving | Wrong `WAHA_URL` / chat ID / session | Verify WAHA is up and the chat ID matches. |
| `net::ERR_...` errors in agent | Network/DNS inside container | Check `extra_hosts` and container networking. |
| Agent hangs at a pause forever | No `/resume` sent | POST `/resume` or send `continue` via WhatsApp. |

## Files

| File | Purpose |
| --- | --- |
| `agent-service/Dockerfile` | Image build: Python 3.11 + Chromium + Xvfb. |
| `agent-service/docker-compose.yml` | Orchestration: ports, env, shm_size, extra_hosts. |
| `agent-service/.env` | Runtime config (not committed). |
| `agent-service/.env.example` | Template — copy to `.env` and edit. |