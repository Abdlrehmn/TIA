# TIA Project Status

## Project overview

TIA is a local-first Windows desktop assistant. Its long-term goal is to
support English and Roman Urdu, answer through voice, and carry out approved
computer tasks. The current application has a chat interface connected to a
local model; voice and computer task features remain unimplemented.

## Current phase

- **Phase 1: COMPLETE** — React, TypeScript, Tailwind CSS, Vite, and Tauri
  desktop foundation.
- **Phase 2: COMPLETE** — Python 3.14.3 FastAPI backend foundation with a
  localhost-only health endpoint. See [backend setup](../backend/README.md).
- **Phase 3: COMPLETE** — frontend health monitoring and chat communication
  with the backend.
- **Phase 4: COMPLETE** — Milestone 1 connects chat to local Ollama;
  Milestone 2A adds the backend-only response prompt and configurable 10-minute
  keep-alive; Milestone 2B adds safe Markdown rendering; Milestone 2C streams
  answer content through FastAPI SSE; Milestone 3A adds an opt-in backend
  DuckDuckGo text-search endpoint; Milestone 3B adds deterministic search
  selection and bounded search context for current-information chat requests.
  Search is disabled by default. Live DuckDuckGo availability remains unverified
  because observed requests returned HTTP 202 or timed out.
- **Phase 5: IN PROGRESS** — Milestone 1 SQLite conversation schema/API and
  Milestone 2 conversation-aware Qwen context, completed response persistence,
  and frontend synchronization are implemented. Milestone 3.1 adds fail-closed
  local API authentication, exact app origins, sequential schema version 2
  migrations, and conversation turn provenance. Production Python backend
  bundling and supervised private token bootstrap remain incomplete.

## Completed and verified in Phase 1

- Tauri 2 Windows desktop shell with TIA branding and NSIS packaging.
- React 19, strict TypeScript, Tailwind CSS 4, and Vite frontend.
- Single chat screen, sidebar, conversation history, welcome state, and
  settings dialog.
- Text submission with an explicitly identified fixed placeholder response.
- Conversation persistence in browser `localStorage`.
- Disabled microphone control shown as a visual placeholder.
- The installed Windows application was launched and manually exercised.

The project owner reports these checks passed: `tsc --noEmit`, `npm run
build`, `cargo check`, `npm run tauri dev`, manual desktop interface testing,
`npm run tauri build`, and launch/manual testing of the installed
application. The installer was generated at
`frontend/src-tauri/target/release/bundle/nsis/TIA_0.1.0_x64-setup.exe`.
These are owner-reported results; this review did not rerun them.

## Technology stack

| Area | Current or selected technology | State |
|---|---|---|
| Desktop shell | Tauri 2 and Rust | Implemented and tested |
| UI | React 19, TypeScript, Tailwind CSS 4, Vite | Implemented and tested |
| Conversation storage | Backend SQLite source of truth + browser `localStorage` copy | Startup import/load and chat persistence implemented |
| Backend | Python 3.14.3, FastAPI, Uvicorn, Pydantic | Implemented in `backend/` with isolated `backend/.venv/` |
| AI | Ollama + `qwen3:4b` | Connected through the FastAPI chat endpoint; local generation only |
| Speech | faster-whisper, SoundDevice, Piper/Kokoro evaluation | Planned |
| Memory | SQLite schema foundation | Tables exist; extraction, retrieval, embeddings, and RAG are not implemented |
| Automation | Playwright and reviewed desktop tools | Planned |

## Current limitations

- Ollama must be running locally with the configured model available. Defaults
  are `http://127.0.0.1:11434`, `qwen3:4b`, and a 120-second request timeout;
  backend settings use `TIA_OLLAMA_BASE_URL`, `TIA_OLLAMA_MODEL`, and
  `TIA_OLLAMA_TIMEOUT`. The configured Ollama URL is restricted to loopback.
  System instructions can be overridden only in the backend with
  `TIA_OLLAMA_SYSTEM_PROMPT`; model residency defaults to 10 minutes and can
  be configured with `TIA_OLLAMA_KEEP_ALIVE`.
- Multi-turn chat context is retrieved from SQLite and bounded to 12 recent
  messages and 12,000 characters by default. Ollama health reporting is not
  implemented.
- `POST /api/v1/search` performs an explicit DuckDuckGo text search only when
  `TIA_WEB_SEARCH_ENABLED=true`. It returns normalized titles, URLs, snippets,
  and optional publication dates. The chat stream uses deterministic wording
  rules to invoke this service for likely current-information questions. It
  passes at most five bounded results to Ollama as untrusted context and adds
  validated source links to the streamed answer. It does not fetch result pages.
  The service rejects private/reserved IP literals and common local host names,
  and reports non-200 DDG responses as provider failures instead of treating
  them as empty results.
  Availability depends on DuckDuckGo accepting requests from the host; a live
  request in the current environment received HTTP 202 (anomaly/challenge
  response), and sandboxed requests timed out. No retries are used for these
  provider failures.
- Voice input, speech output, wake word, and microphone capture are absent.
- Settings are a static interface, not application configuration.
- React synchronizes localStorage with SQLite on startup and preserves stable
  conversation/message UUIDs. Browser data is not removed by import. Conflicting
  records or offline backend errors leave localStorage available; no merge UI
  exists.
- SQLite memory tables are empty schema foundation only; chat does not create
  memory records and no retrieval or RAG behavior exists.
- No computer or browser automation is implemented.
- The local API requires a per-session bearer token for all routes except the
  minimal loopback-only `GET /health` response. Development uses an ephemeral
  token shared by the dev launcher. Production Tauri does not yet start or
  supervise a packaged Python backend, so private production token bootstrap
  is incomplete and API requests fail closed without external provisioning.
- SQLite schema version 2 adds turn provenance: search use and successful
  completion are recorded for new metadata-bearing turns. Existing version 1
  messages remain intact without guessed provenance. Memory extraction and
  memory APIs remain unimplemented.

## Agreed phase roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Environment and hardware verification | Complete; RTX 3050 VRAM and `qwen3:4b` verified |
| 1 | React + TypeScript + Tailwind + Tauri foundation | **Complete** |
| 2 | Python FastAPI backend foundation | **Complete** |
| 3 | Frontend/backend communication | **Complete; Milestones 1 and 2 complete** |
| 4 | Ollama integration | **Complete; Milestones 1, 2A, 2B, 2C, 3A, and 3B implemented** |
| 5 | SQLite persistence, conversation context, security and agent/tool work | **In progress; Milestones 1, 2 and 3.1 implemented; production bootstrap and later milestones remain** |
| 6 | Speech recognition | Planned |
| 7 | Text-to-speech | Planned |
| 8 | Desktop and browser automation | Planned |
| 9 | SQLite memory and productivity | Planned beyond the Phase 5 storage foundation |
| 10 | Security, testing, optimization, and packaging | Planned |

## Important project decisions

- The target is a real Windows desktop application using Tauri 2, not a
  browser-only product.
- The frontend is presentation-only and must not have unrestricted OS or
  shell access.
- Tauri capabilities remain limited to `core:default`; additional plugins or
  capabilities require explicit user approval.
- Processing is intended to remain local, with no cloud AI or telemetry.
- Dangerous actions require explicit user confirmation and belong in an
  audited backend/tool layer.
- The Python backend is a sibling of `frontend/`. Phase 2 establishes its
  isolated FastAPI foundation; frontend communication remains Phase 3.
- The legacy PySide6 prototype is archived and read-only.
