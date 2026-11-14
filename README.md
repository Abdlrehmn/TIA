# TIA — Personal AI Desktop Agent

A **local-first** Windows desktop assistant for English and Roman Urdu.
TIA runs entirely on your computer: no cloud AI, no telemetry, no secrets
in plain text.

> **Current status: Phase 1 complete — desktop shell + UI foundation.**
> Text input works today with an honest placeholder reply. The AI brain,
> voice and automation are **not implemented yet** and are marked as such
> everywhere in the UI.

## Tech stack

| Layer | Technology | Status |
|---|---|---|
| Desktop shell | Tauri 2 (Rust) | ✅ active |
| Frontend | React 19 + TypeScript + Tailwind CSS 4 (Vite) | ✅ active |
| Backend | Python 3.11+ · FastAPI · Pydantic | ⏳ future phase |
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
| Python backend (FastAPI) + SQLite | ❌ future phase |

## Privacy & safety principles

- Local-first: AI, speech and storage all stay on your machine.
- The frontend never gets raw shell/OS access (minimal Tauri capabilities).
- Dangerous actions (email, file deletion, uninstalling software, system
  settings) will always require explicit confirmation in later phases.
- No bypassing of MFA, CAPTCHA or account security. Ever.

## License

To be decided by the project owner.
