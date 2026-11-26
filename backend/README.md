# TIA backend setup

Run the authenticated Tauri development workflow in PowerShell from the repository root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\dev.ps1
```

The authenticated development launcher is `scripts/dev.ps1`. It generates a
fresh 256-bit URL-safe token with Python's `secrets` module, starts FastAPI on
`127.0.0.1:8000`, waits for health, and starts Tauri/Vite. It stops the backend
when Tauri exits and refuses to start another backend if port 8000 is occupied.
The token stays in process environment/memory; it is not written to source,
configuration, command-line arguments, browser storage, or logs. Tauri retrieves
it through the minimal Rust command. Bare `npm run dev` can display the UI, but
API calls fail closed outside the authenticated desktop session.

Check the minimal health response:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The health response is `{"status":"healthy","app":"TIA","version":"0.1.0"}`.
`GET /health` is exempt from bearer authentication for startup checks; it
returns no user, model, or database data and still requires a loopback peer and
permitted host. All other paths, including `/docs` and `/openapi.json`, require
`Authorization: Bearer <token>`.

## Authentication and production lifecycle

Non-health routes check the loopback client address, exact `Host`, exact app
`Origin` when present, and a per-session bearer token using
`secrets.compare_digest`. Tokens must be at least 32 random bytes (43
URL-safe characters). CORS permits only `http://localhost:1420` and
`http://tauri.localhost`, and allows the `Authorization` header. CORS is not
authentication.

**Production bootstrap is not complete.** The Rust command can provide a token
already present in Tauri's process environment, and FastAPI requires the same
token, but the packaged app does not yet bundle, start, supervise, or stop a
Python backend. A packaged Python runtime and private per-launch handoff need a
separate implementation. Until then a packaged build without trusted external
bootstrap fails closed and cannot use the local API.

## Optional Bing text search

The backend searches Bing for result titles, public URLs, and snippets. It
uses Scrapling first and a shared headless Chromium browser through Playwright
if Scrapling times out, is blocked, or produces no valid results. The explicit
search endpoint returns metadata only; chat separately retrieves up to three
result pages for bounded evidence. Search is disabled by default. To enable it for the
current PowerShell session, set the environment variable before starting
Uvicorn:

```powershell
$env:TIA_WEB_SEARCH_ENABLED = "true"
Set-Location ..
.\scripts\dev.ps1
```

Optional settings (defaults shown):

| Environment variable | Default | Allowed values |
|---|---:|---|
| `TIA_WEB_SEARCH_ENABLED` | `false` | `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off` |
| `TIA_WEB_SEARCH_TIMEOUT` | `10` seconds | Integer from 1 to 120 |
| `TIA_WEB_SEARCH_MAX_RESULTS` | `5` | Integer from 1 to 20 |
| `TIA_WEB_SEARCH_SAFESEARCH` | `moderate` | `on`, `moderate`, `off` (mapped to Bing settings) |
| `TIA_WEB_SEARCH_REGION` | `us-en` | Language-region code such as `us-en` |
| `TIA_WEB_SEARCH_MAX_PAGES` | `3` | Integer from 1 to 5 |
| `TIA_WEB_SEARCH_PAGE_TIMEOUT` | `8` seconds | Integer from 1 to 30 |
| `TIA_WEB_SEARCH_TOTAL_CONTENT_TIMEOUT` | `25` seconds | At least page timeout, at most 120 |
| `TIA_WEB_SEARCH_MAX_PAGE_BYTES` | `2097152` | Integer from 65536 to 10485760 |
| `TIA_WEB_SEARCH_MAX_PAGE_CHARS` | `5000` | Integer from 1000 to 20000 |

Call the endpoint with a query and an optional result limit (bounded by the
configured maximum):

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/search `
  -Headers @{ Authorization = "Bearer $env:TIA_API_TOKEN" } `
  -ContentType "application/json" `
  -Body '{"query":"Python programming language","max_results":3}'
```

The response contains `success`, the validated query, normalized result
objects (`title`, `url`, `snippet`, and optional `published`), and
`result_count`. If both retrieval methods complete without valid results, the
endpoint returns an empty list. Disabled search returns HTTP 503; invalid
input returns HTTP 422; exhausted request timeouts return HTTP 504; provider
failures return a sanitized HTTP 502. Bing redirect links are unwrapped, and
only validated public HTTP(S) result URLs are returned. Local, private,
reserved, malformed, duplicate, and Bing navigation links are rejected.
Search snippets and extracted webpage text are untrusted external text. Page
requests are made only for validated Bing results. Each redirect is checked
again; DNS answers must be globally routable and are pinned to the validated IP
for Scrapling. Chromium uses an authenticated shared loopback HTTP proxy that
resolves and pins each connection, with Playwright request routing as an
additional check.
Local, private, reserved, link-local, unsupported-scheme, and nonstandard-port
destinations are blocked. Page bytes, extracted characters, pages per query,
concurrency, redirects, and total retrieval time are bounded.

The Scrapling request uses one attempt and a bounded timeout. One shared
Playwright browser is started and closed with the FastAPI application
lifespan; each fallback search gets an isolated browser context. Concurrent
searches are bounded to four at a time. Search-provider failures do not
expose internal exception details.

## Search-augmented chat

`POST /api/v1/chat/stream` uses a deterministic search-intent detector. It
searches only when the message contains current-time markers (such as â€œlatest,â€
â€œtoday,â€ or â€œrecentâ€) or asks about changing topics such as news, weather,
prices, scores, updates, versions, or releases. Ordinary educational and coding
questions continue directly to Ollama. It also recognizes common Roman Urdu
current-time wording such as â€œaaj,â€ â€œabhi,â€ and â€œkal ka/ki.â€ The detector is
intentionally conservative and can be extended later without adding a
classification model.

When search is enabled, chat fetches up to three validated result pages with
Scrapling and uses the shared Playwright browser when a page is unavailable,
empty, or JavaScript-heavy. Failed page fetches retain the validated search
snippet. FastAPI passes up to five sources as size-bounded, clearly labeled
untrusted JSON. Instructions tell Qwen not to follow page text as commands or
policy. The backend appends Markdown source links from validated URLs. Search results and snippets
are never sent to React as a separate data payload or rendered as raw HTML.

The streaming protocol still uses `start`, `delta`, `done`, and `error`. Search
starts after `start`; periodic SSE comment heartbeats keep the frontend's
inactivity timer alive and are ignored by its parser. If search is disabled,
times out, fails, or yields no usable results, FastAPI emits a clear `error`
event and does not ask Qwen to answer a current-information question from stale
training knowledge. Ordinary local questions do not call Bing and still
work when the provider is unavailable. `POST /api/v1/chat/test` remains
unchanged.

Live Bing search returned three pages, and Scrapling extracted readable text from all three. The Playwright page fallback was separately forced against Python.org through the safe shared proxy and extracted 1,395 characters. Provider availability depends on Bing, source sites, and network access.

## SQLite conversation foundation (Phase 5, Milestone 1)

The backend uses Python's built-in `sqlite3`; there are no database package
dependencies. On Windows, the default database is
`%LOCALAPPDATA%\TIA\tia.sqlite3` (normally under the current user's local app
data directory). `TIA_DATA_DIR` can override the directory. For deployments
that need a different filename or location, `TIA_DATABASE_PATH` overrides the
complete database path and takes precedence over `TIA_DATA_DIR`. The backend
creates the parent directory on startup. Database files and SQLite WAL/SHM
sidecars are ignored by Git.

FastAPI initializes the database during application startup. Migrations are
tracked with `PRAGMA user_version`; migrations run sequentially in individual
transactions and advance `user_version` only after success. Unknown future
versions fail safely. Version 1 creates:

- `conversations`: stable frontend UUID, title, millisecond creation/activity
  timestamps, and an archived flag.
- `messages`: stable UUID, conversation foreign key, `user`/`assistant` role,
  content, millisecond timestamp, and per-conversation insertion sequence.
- `memory_records` and `memory_sources`: schema foundation only. No memory
  extraction, retrieval, embeddings, Chroma, or RAG is implemented.
  Memory status values reserved by the schema are `proposed`, `approved`,
  `rejected`, `superseded`, and `deleted`.

Version 2 adds `conversation_turns`: one row per metadata-bearing chat turn,
keyed by the stable user-message UUID, with its conversation, expected
assistant-message ID, `used_web_search`, completion state, and timestamps. Turns
start incomplete. A turn is marked search-augmented when validated search
context is passed to Ollama. Assistant message persistence and successful turn
completion commit in one transaction. Failed and cancelled streams remain
incomplete. Existing version 1 messages are retained without guessed turn
records.

Foreign keys are enabled on each connection, conversation deletion cascades to
messages, the database uses WAL mode, and connections use a five-second busy
timeout. API operations use parameterized SQL and return sanitized storage
errors. API routes require the per-session bearer credential; localhost
binding and CORS are additional restrictions, not authentication.

Conversation endpoints under `/api/v1`:

| Method and path | Purpose |
|---|---|
| `PUT /conversations/{id}` | Create or update one conversation and its ordered messages |
| `GET /conversations?limit=200` | List recent non-archived conversations |
| `GET /conversations/{id}` | Read one conversation and ordered messages |
| `PATCH /conversations/{id}` | Update its title and activity timestamp |
| `DELETE /conversations/{id}` | Delete it and cascade-delete messages |
| `POST /conversations/{id}/messages` | Append one UUID-identified message idempotently |
| `POST /conversations/import` | Import a bounded array of localStorage-shaped conversations |

The import request uses the existing frontend format (`id`, `title`,
`createdAt`, and `messages` containing `id`, `role`, `content`, `createdAt`).
IDs and millisecond timestamps are preserved. Repeating an identical import
does not create duplicates; conflicting data under an existing ID is rejected.
The endpoint does not delete or alter browser localStorage. The React hook
imports localStorage records idempotently, then loads SQLite records on
startup. LocalStorage is retained if import or loading fails.

Run backend tests from `backend/` with its isolated interpreter:

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

No memory records are populated by chat, and the memory tables must not be
treated as an implemented memory feature.

## Conversation-aware chat (Phase 5, Milestone 2)

The streaming chat endpoint accepts the existing `{"message":"Hello"}` form
for backward compatibility. The React app also sends its stable conversation,
user-message, and assistant-message UUIDs and original millisecond timestamps.
The backend creates the conversation only if needed, then idempotently stores
the user message before local model generation. A successful Ollama `done`
marker causes the complete assistant answer to be stored with the supplied ID
and timestamp. Failed, interrupted, or cancelled generation leaves no completed
assistant record. Streamed deltas are never written as separate messages.

Before generation, the backend fetches recent SQLite messages, preserves user
and assistant roles and chronological order, excludes the current user message
by ID, and appends that current message once. The system prompt remains a
separate system role. Defaults are at most 12 prior messages and 12,000
characters of prior message content; the newest history is retained first and
the current user message is not included in that budget or truncated. Configure
these bounds with `TIA_CHAT_HISTORY_MAX_MESSAGES` (1-100) and
`TIA_CHAT_HISTORY_MAX_CHARS` (1,000-100,000). Character count is a conservative
memory bound, not an exact tokenizer count.

Search intent and the SSE `start`/`delta`/`done`/`error` protocol remain in
place, including heartbeat comments and answer-only `message.content` handling.
Web search remains opt-in and uses Scrapling for Bing result discovery with a Playwright fallback. DDGS remains in the dependency list temporarily for rollback.

Stop the server with `Ctrl+C` in the window running Uvicorn. To leave the
virtual environment afterward, run `deactivate`.

