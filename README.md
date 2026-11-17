# TIA — Personal AI Desktop Agent

A **local-first** Windows desktop assistant for English and Roman Urdu.
TIA runs entirely on your computer: no cloud AI, no telemetry, no secrets
in plain text.

> **Current status: Phases 1 and 2 complete — desktop foundation and backend health service.**
> Text input works today with an honest placeholder reply. The AI brain,
> voice and automation are **not implemented yet** and are marked as such
> everywhere in the UI.

See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for implementation
status, limitations, decisions, and the full agreed roadmap.

## Tech stack

| Layer | Technology | Status |
|---|---|---|
| Desktop shell | Tauri 2 (Rust) | ✅ active |
| Frontend | React 19 + TypeScript + Tailwind CSS 4 (Vite) | ✅ active |
| Backend | Python 3.14.3 · FastAPI · Uvicorn · Pydantic | ✅ Phase 2 health service |
| AI | Ollama + Qwen3 4B Instruct (candidate) | ⏳ future phase |
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
├── docs/architecture.md         # stack rationale, data flow, security model
├── legacy/pyside6-ui/           # archived first prototype (superseded stack)
├── AGENTS.md                    # binding rules for AI agents (OpenCode + Codex)
├── README.md
└── .gitignore
```

## Run the desktop app

```powershell
cd C:\Users\ZAH\Desktop\RUMMAN\TIA\frontend

npm install            # first time only
npm run tauri dev      # launches the real Windows desktop window
```

`npm run dev` alone starts the Vite dev server at http://localhost:1420
(browser preview of the UI, no native shell).

## Production build (Windows installer)

```powershell
cd C:\Users\ZAH\Desktop\RUMMAN\TIA\frontend
npm run tauri build    # outputs NSIS installer under src-tauri/target/release/bundle/
```

## Run the backend

In PowerShell:

```powershell
cd C:\Users\ZAH\Desktop\RUMMAN\TIA\backend
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The printed executable should be `...\TIA\backend\.venv\Scripts\python.exe`.
In another PowerShell window, check the health endpoint and API docs:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/docs | Select-Object StatusCode
```

The health response is `status: healthy`, `app: TIA`, `version: 0.1.0`.
Stop the server with `Ctrl+C`; run `deactivate` to leave the environment.

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
| Text input + send (local echo + placeholder reply) | ✅ |
| Conversation history saved locally (localStorage) | ✅ |
| Microphone button | ❌ visual placeholder only (disabled) |
| Real AI replies (Ollama + Qwen3) | ❌ future phase |
| Voice input / TTS / wake word | ❌ future phase |
| Python backend health service (FastAPI) | ✅ Phase 2; no frontend connection yet |
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
| 0 | Environment and hardware verification | Complete for Phase 1 environment |
| 1 | React + TypeScript + Tailwind + Tauri foundation | **Complete** |
| 2 | Python FastAPI backend foundation | **Complete** |
| 3 | Frontend/backend communication | **Next; not started** |
| 4 | Ollama integration | Planned |
| 5 | Tool calling and agent loop | Planned |
| 6 | Speech recognition | Planned |
| 7 | Text-to-speech | Planned |
| 8 | Desktop and browser automation | Planned |
| 9 | SQLite memory and productivity | Planned |
| 10 | Security, testing, optimization and packaging | Planned |

## License

To be decided by the project owner.
