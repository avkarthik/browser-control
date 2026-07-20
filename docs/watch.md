# `watch.js` — Webpage Watcher

A Node.js script that periodically checks whether a webpage contains target content, using Playwright for browser automation and a local Ollama model for fuzzy matching. It's the simplest piece of the project — no FastAPI, no WhatsApp, no `browser-use`.

## Setup

```powershell
npm install        # installs playwright (see package.json)
npx playwright install chromium
```

Ensure a local Ollama is running at `http://localhost:11434` with the `gemma4` model pulled:

```powershell
ollama pull gemma4
```

## Run

```powershell
node watch.js
```

The script runs one check immediately on startup, then repeats every `CHECK_EVERY_MS` (default 60 seconds) via `setInterval`. It runs until you kill the process (Ctrl+C).

## Configuration

All configuration is hardcoded as constants at the top of `watch.js`. Edit the file to change behavior.

| Constant | Default | Purpose |
| --- | --- | --- |
| `URL` | `'https://example.com'` | The page to watch. |
| `CHECK_EVERY_MS` | `60_000` | Interval between checks (1 minute). |
| `SCREENSHOT_DIR` | `./shots` | Where screenshots are saved. Created if missing. |
| `MODEL` | `'gemma4'` | Ollama model used for fuzzy matching. |
| `TARGET_TEXT` | `'Example Domain'` | The text to look for on the page. |

## How a check works

`runCheck()` does the following:

1. Launches **headless** Chromium with a tall viewport (`1440×2200`) to capture full pages.
2. Navigates to `URL` with `waitUntil: 'networkidle'` and a 60s timeout, then waits an extra 2s.
3. Reads `page.locator('body').innerText()` as `bodyText`.
4. **Direct match** — if `bodyText.toLowerCase()` contains `TARGET_TEXT.toLowerCase()`, `matched = true`.
5. **Fuzzy match** — if no direct match, sends a prompt to the local Ollama (`http://localhost:11434/api/generate`) with the first 12,000 chars of `bodyText` and asks for a one-line reply:
   ```
   MATCH - reason
   ```
   or
   ```
   NO_MATCH - reason
   ```
   If the response starts with `MATCH`, `matched = true`.
6. Takes a full-page screenshot saved to `shots/`:
   - `match-<timestamp>.png` if matched.
   - `check-<timestamp>.png` if not matched.
   - The timestamp is `new Date().toISOString()` with `:` and `.` replaced by `-`.
7. Logs a JSON object to stdout:
   ```json
   {
     "url": "https://example.com",
     "matched": true,
     "reason": "Found direct text match: Example Domain",
     "screenshot": "shots/match-2026-05-23T23-44-33-200Z.png",
     "checkedAt": "2026-05-23T23:44:33.200Z"
   }
   ```
8. Closes the browser in a `finally` block. Errors are caught and logged to stderr; the interval keeps running.

## Output files

Screenshots are written to `shots/` (gitignored — see [`.gitignore`](../.gitignore)). Example:

```
shots/
├── match-2026-05-03T16-14-07-647Z.png
└── match-2026-05-23T23-44-33-200Z.png
```

## Limitations / notes

- **No alerting** — the script only logs to stdout and saves screenshots. It does not send notifications. To add notifications, extend `runCheck()` (e.g. call the WAHA API from `agent-service/`).
- **Single target** — one URL and one `TARGET_TEXT`. To watch multiple pages, refactor into a list and loop.
- **Ollama dependency** — if Ollama is down, the fuzzy-match branch will throw inside `askOllama()`, which is caught by the outer try/catch and logged. The direct-match branch still works.
- **Headless only** — unlike the Python agents, `watch.js` runs headless. It's a content check, not a bot-detection-sensitive automation.

## Related

- [`architecture.md`](./architecture.md) — where `watch.js` fits in the overall system.
- `package.json` — only declares `playwright` as a dependency.