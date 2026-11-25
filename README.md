# TIA — Personal AI Desktop Agent

A **local-first** Windows desktop assistant for English and Roman Urdu.
TIA runs entirely on your computer: no cloud AI, no telemetry, no secrets
in plain text.

> **Current status: Phases 1 and 2 complete; Phase 3 Milestones 1 and 2 complete.**
> Text input receives a deterministic backend test reply. The AI brain,
> voice and automation are **not implemented yet** and are marked as such
> everywhere in the UI.

See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for implementation
status, limitations, decisions, and the full agreed roadmap.

## Tech stack

| Layer | Technology | Status |
|---|---|---|
| Desktop shell | Tauri 2 (Rust) | ✅ active |
| Frontend | React 19 + TypeScript + Tailwind CSS 4 (Vite) | ✅ active |
| Backend | Python 3.14.3 · FastAPI · Uvicorn · Pydantic | ✅ Health and test-message endpoints |
| AI | Ollama + `qwen3:4b` (downloaded and verified) | ⏳ not connected to TIA yet |
| Speech | faster-whisper · SoundDevice · Piper/Kokoro | ⏳ future phase |
| Storage | SQLite | ⏳ future phase |
| Automation | Playwright (controlled) | ⏳ future phase |

React never receives unrestricted OS or shell access: the Tauri
configuration ships with the minimal `core:default` capability only, and
all future OS work goes through the audited Python backend.

## Prerequisites

1. **Node.js 20+** (installed: Node 24) — for Vite and the Tauri CLI.
2. **Rust stable + MSVC Build Tools** — required to compile the Tauri shell:

   ```powershell
   # 1) Rust (per-user, no admin needed)
   winget install --id Rustlang.Rustup -e
   # 2) MSVC Build Tools (~2-6 GB, one-time admin approval)
   winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
   # 3) Open a NEW terminal, then verify:
   rustc --version
   cargo --version
   ```

3. **WebView2 Runtime** — preinstalled on Windows 10/11 (verified present).

## Project structure

```
TIA/
├── frontend/                    # React + TypeScript + Tailwind (Vite)
│   ├── src/
│   │   ├── components/          # layout/, chat/, ui/ reusable components
│   │   ├── pages/               # ChatPage — the single application screen
│   │   ├── hooks/               # useConversations, useAutoScroll
│   │   ├── lib/                 # constants, storage, uid, time helpers
│   │   └── types/               # shared TypeScript types
│   ├── src-tauri/               # Tauri 2 shell (Rust) + minimal capabilities
│   ├── package.json
│   └── vite.config.ts
├── backend/                     # Python FastAPI backend (.venv, app/)
├── docs/architecture.md         # stack rationale, data flow, security model
├── legacy/pyside6-ui/           # archived first prototype (superseded stack)
├── AGENTS.md                    # binding rules for AI agents (OpenCode + Codex)
├── README.md
└── .gitignore
```

## Run the authenticated desktop development app

```powershell
cd C:\Users\ZAH\Desktop\RUMMAN\TIA
.\scripts\dev.ps1
```

The launcher generates a new session token, runs FastAPI on loopback, and
starts the Tauri app with Vite. The token is held in process memory and not
written to a file or browser storage. It stops FastAPI when Tauri exits. The
backend `.venv` and frontend dependencies must already be installed. Running
`npm run dev` alone previews the UI without authenticated backend access.

## Production build (Windows installer)

```powershell
cd C:\Users\ZAH\Desktop\RUMMAN\TIA\frontend
npm run tauri build    # outputs NSIS installer under src-tauri/target/release/bundle/
```

## API security and backend lifecycle

`GET /health` is unauthenticated and returns only process status/name/version
for startup checks. All other endpoints require a per-launch bearer token.
The backend also restricts clients to loopback peers, exact local hosts, and
the exact Vite development and packaged Tauri origins. CORS does not provide
authentication.

The packaged app does **not** yet bundle or supervise a Python backend. The
Tauri credential command and backend token checks are a safe foundation, but
production startup needs a trusted packaged Python runtime and private
per-launch bootstrap. Until that work is complete, production API access fails
closed without an external bootstrap.

## Frontend-only checks (no Rust needed)

```powershell
npm run build          # TypeScript check + production web build
npm run dev            # dev server on port 1420 (fixed for Tauri)
```

## What works / what doesn't (honest list)

| Feature | Status |
|---|---|
| Desktop window (Tauri 2, branded, dark navy + cyan) | ✅ |
| Sidebar: New Chat, conversation history, Settings | ✅ |
| Text input + send (backend test-message reply) | ✅ |
| Conversation history saved locally (localStorage) | ✅ |
| Microphone button | ❌ visual placeholder only (disabled) |
| Real AI replies (Ollama + Qwen3) | ✅ local backend; requires Ollama |
| Voice input / TTS / wake word | ❌ future phase |
| Authenticated local FastAPI API and conversation-aware chat | ✅ development workflow; packaged backend lifecycle remains incomplete |
| SQLite memory | ❌ future phase |

## Privacy & safety principles

- Local-first: AI, speech and storage all stay on your machine.
- The frontend never gets raw shell/OS access (minimal Tauri capabilities).
- Dangerous actions (email, file deletion, uninstalling software, system
  settings) will always require explicit confirmation in later phases.
- No bypassing of MFA, CAPTCHA or account security. Ever.

## Phase roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Environment and hardware verification | Complete; RTX 3050 and `qwen3:4b` verified |
| 1 | React + TypeScript + Tailwind + Tauri foundation | **Complete** |
| 2 | Python FastAPI backend foundation | **Complete** |
| 3 | Frontend/backend communication | **In progress; Milestones 1 and 2 complete** |
| 4 | Ollama integration | Planned |
| 5 | Tool calling and agent loop | Planned |
| 6 | Speech recognition | Planned |
| 7 | Text-to-speech | Planned |
| 8 | Desktop and browser automation | Planned |
| 9 | SQLite memory and productivity | Planned |
| 10 | Security, testing, optimization and packaging | Planned |

## License

To be decided by the project owner.
