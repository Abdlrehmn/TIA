# TIA â€” Architecture

This document describes how TIA is put together, why each piece was
chosen, and how the phases fit together. It is the companion to
`AGENTS.md` (agent rules) and `README.md` (usage).

## 1. High-level shape

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚  TIA desktop window (Tauri 2, Rust)                       â”‚
â”‚                                                           â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚  â”‚  WebView2                                           â”‚  â”‚
â”‚  â”‚  React 19 + TypeScript + Tailwind 4 (Vite build)    â”‚  â”‚
â”‚  â”‚  - ChatPage (single screen)                         â”‚  â”‚
â”‚  â”‚  - Sidebar: New Chat / history / Settings           â”‚  â”‚
â”‚  â”‚  - ConversationArea + ChatInput                     â”‚  â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â”‚                     â”‚ (Phase 3: local API; auth planned)  â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚  â”‚  Python 3.14.3 Â· FastAPI Â· Uvicorn Â· Pydantic        â”‚  â”‚
â”‚  â”‚  Phase 2: localhost health endpoint + API docs       â”‚  â”‚
â”‚  â”‚  Future: AI, tools, voice, permissions, SQLite       â”‚  â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

## 2. Why this stack

- **Tauri 2 + React** gives a small, fast, native-feeling Windows app
  with a modern UI ecosystem, instead of a heavier Electron-style shell
  or hand-built native widgets.
- **TypeScript strict** catches UI bugs at compile time; **Tailwind 4**
  keeps styling token-based (`@theme` in `src/index.css`) and consistent
  (dark navy + single cyan accent carried over from the original TIA
  design).
- **Python + FastAPI** hosts local model integration and will host future
  voice, file/system tools, permissions and SQLite memory. Pydantic models
  form the shared contract with the frontend types (`frontend/src/types/chat.ts`).

## 3. Trust boundaries & security model

1. **The WebView/React layer is untrusted** for OS purposes: its Tauri
   capabilities are `core:default` only. No shell, no filesystem, no
   HTTP plugins are enabled.
2. **The Rust shell** owns the window and exposes a minimal command to provide
   the current session token to the WebView. The packaged shell does not yet
   spawn or supervise FastAPI; production bootstrap remains incomplete.
3. **The Python backend** owns all OS-facing work. Every dangerous tool
   (email, delete, uninstall, settings) requires explicit user
   confirmation and will be registered in an auditable tools registry.
4. **Local API authentication (Milestone 3.1 foundation):** non-health routes
   require a bearer token, and the backend rejects non-loopback peers,
   unexpected hosts, and unapproved origins. Development generates an
   ephemeral token shared through the dev launcher, backend, and Tauri process. Production still needs a packaged Python runtime and
   trusted Tauri-supervised private token handoff. This reduces access from
   unrelated local processes but is not a boundary against malware running as
   the same Windows user.
5. **Never:** bypass MFA/CAPTCHA, store plaintext credentials, or give
   the model unrestricted shell access.

## 4. Current data flow (Phases 1-5, Milestone 2)

- `ChatInput â†’ ChatPage.handleSend â†’ authenticated api.ts (POST /api/v1/chat/stream) â†’
  FastAPI search-intent check â†’ either local Ollama or opt-in Bing search (Scrapling, then Playwright fallback) â†’
  bounded untrusted reference context â†’ local Ollama SSE â†’ accumulated Markdown
  response with backend-generated validated source links â†’ localStorage`.
- `POST /api/v1/chat/test` remains available for non-streaming replies.
- The SSE protocol sends `start`, answer-only `delta`, then `done`; sanitized
  `error` events report failures after streaming begins. The frontend reads
  split and combined SSE frames incrementally and batches React updates per
  animation frame. Stopping generation aborts the request; FastAPI closes the
  Ollama response when the client disconnects. During web search, FastAPI sends
  SSE comment heartbeats; the frontend parser ignores comment frames and its
  inactivity timeout resets when each arrives.
- FastAPI calls Ollama with Python's standard-library `urllib`; the frontend
  never connects to Ollama. Defaults are `qwen3:4b` at
  `http://127.0.0.1:11434` with a 120-second timeout and 10-minute keep-alive.
  A backend-only system prompt precedes each user message. Settings use
  `TIA_OLLAMA_BASE_URL`, `TIA_OLLAMA_MODEL`, `TIA_OLLAMA_TIMEOUT`,
  `TIA_OLLAMA_KEEP_ALIVE`, and optionally `TIA_OLLAMA_SYSTEM_PROMPT`; configured
  Ollama hosts must be loopback addresses.
- `useBackendHealth` polls `GET /health` every 3 s to drive the status chip.
- An independent `POST /api/v1/search` endpoint discovers Bing results using
  Scrapling `AsyncFetcher`, with a shared headless Chromium Playwright fallback
  when Scrapling fails, is blocked, times out, or yields no valid links. It is
  disabled unless `TIA_WEB_SEARCH_ENABLED=true`, validates and normalizes
  result metadata, rejects Bing navigation/ad links and unsafe or duplicate
  destinations; the explicit metadata endpoint does not fetch pages. Chat fetches
  up to three result pages asynchronously, with DNS-pinned Scrapling and a shared
  Playwright browser fallback routed through an authenticated loopback HTTP proxy
  that pins connections to validated public IP addresses.
  Redirects and browser subrequests are validated, page bytes and extracted
  text are bounded, and fetched text/snippets are untrusted evidence. Search
  queries and selected source URLs leave the machine only when opt-in search runs.
  DDGS remains as a pinned rollback dependency but is no longer active.
- A deterministic backend detector triggers search for time-sensitive wording
  and inherently changing topics such as news, weather, prices, scores, updates,
  versions, and releases. Ordinary educational and coding prompts stay on the
  local model path. If search is disabled, fails, or returns no usable results,
  the stream sends a clear `error` event and does not ask Qwen to answer with
  stale training knowledge.
- The frontend retains `localStorage` (`tia.conversations.v1`) as a resilient
  copy and synchronizes conversation IDs/messages with the per-user SQLite
  database.
- Schema version 2 adds `conversation_turns`, linking user and expected
  assistant message IDs and recording search augmentation and completion.
  Existing version 1 messages remain valid without inferred turn metadata.
- Completed replies use recent SQLite history with actual user/assistant roles.
  Memory tables remain schema-only; no extraction, approval API, or retrieval
  is implemented. The microphone remains disabled.

## 5. Phase roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Environment and hardware verification | Complete; RTX 3050 VRAM and `qwen3:4b` verified |
| 1 | React + TypeScript + Tailwind + Tauri foundation | **Complete** |
| 2 | Python FastAPI backend foundation | **Complete** |
| 3 | Frontend/backend communication | **Complete; Milestones 1 and 2 complete** |
| 4 | Ollama integration | **In progress; Milestones 1, 2A, 2B, 2C, 3A, and 3B implemented** |
| 5 | SQLite persistence, conversation context, security and agent/tool work | **In progress; Milestones 1, 2 and 3.1 implemented; packaged bootstrap incomplete** |
| 6 | Speech recognition | Planned |
| 7 | Text-to-speech | Planned |
| 8 | Desktop and browser automation | Planned |
| 9 | SQLite memory and productivity | Planned |
| 10 | Security, testing, optimization and packaging | Planned |

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for implementation details,
limitations, and owner-reported validation results.

## 6. Frontend module map

```
frontend/src/
â”œâ”€â”€ main.tsx / App.tsx / index.css   entry, root, design tokens
â”œâ”€â”€ pages/ChatPage.tsx               screen composition + top status bar
â”œâ”€â”€ components/
â”‚   â”œâ”€â”€ layout/Sidebar.tsx           brand, New Chat, history, Settings entry
â”‚   â”œâ”€â”€ chat/ConversationArea.tsx    welcome vs. message list (+ auto-scroll)
â”‚   â”œâ”€â”€ chat/WelcomeMessage.tsx      intro + honest capability chips
â”‚   â”œâ”€â”€ chat/MessageBubble.tsx       user/TIA message rendering
â”‚   â”œâ”€â”€ chat/ChatInput.tsx           textarea, send, disabled mic placeholder
â”‚   â””â”€â”€ ui/Orb.tsx, SettingsModal.tsx  shared brand orb, static settings dialog
â”œâ”€â”€ hooks/useConversations.ts        chats + messages state, persistence
â”œâ”€â”€ hooks/useAutoScroll.ts           keep message list pinned to bottom
â””â”€â”€ lib/                             uid, time, constants, storage
```

