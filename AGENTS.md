# AGENTS.md — TIA Project Rules for AI Agents

> **Binding for every AI agent working in this repository** (OpenCode =
> primary implementer, Codex = reviewer). Codex does not have access to
> the implementer's conversation, so this file is the shared source of
> truth. If a requested change conflicts with this file, stop and ask
> the user instead of improvising.

## 1. Project identity

- **Name:** TIA (Personal AI Desktop Agent)
- **Goal:** a **local-first** Windows desktop assistant that understands
  English and Roman Urdu, answers through voice, and performs approved
  tasks on the user's computer.
- **Privacy stance:** all processing runs locally. No cloud AI, no
  telemetry, no plaintext secrets — ever.

## 2. Architecture (decided by the user — do not change)

- **Frontend:** React 19 + TypeScript (strict) + Tailwind CSS 4 + Vite.
- **Desktop shell:** Tauri 2 (Rust) — the app must launch as a real
  Windows desktop application, not a browser tab.
- **Backend:** Python 3.14.3 · FastAPI · Uvicorn · Pydantic in `backend/`.
  Chat, SQLite conversation persistence, and conversation-aware context are
  implemented. Non-health routes require a per-session bearer token. The
  development launcher bootstraps it; packaged Python backend supervision and
  private production token handoff remain incomplete.
- **AI:** Ollama with `qwen3:4b` through the local backend. Memory extraction
  and approval are not implemented.
- **Future components:** faster-whisper (STT), SoundDevice (mic input),
  Piper/Kokoro (TTS evaluation), SQLite (conversations + memory),
  Playwright (controlled browser automation).

### Security invariants

- React must **never** receive unrestricted OS or shell access.
- Tauri capabilities stay minimal: `core:default` only; do not add
  shell/fs/http plugins without explicit user approval.
- Dangerous actions (sending email, deleting files, uninstalling
  software, changing important settings) always require explicit user
  confirmation and will be implemented in the audited backend, not the
  frontend.
- Never bypass MFA, CAPTCHA or account security; never automate
  credential entry; no secrets in frontend code.

## 3. Project layout

```
TIA/
├── frontend/                  React app + Tauri 2 shell (Phase 1)
│   ├── src/                   React app (components/, pages/, hooks/, lib/, types/)
│   ├── src-tauri/             Tauri 2 shell (Rust, capabilities, icons, config)
│   └── package.json           scripts: dev / build / tauri
├── backend/                   Python FastAPI backend (Phase 2; sibling of frontend/)
├── docs/                      architecture & design documentation
├── legacy/pyside6-ui/         archived first prototype (do not develop here)
├── AGENTS.md                  this file
├── README.md                  user-facing docs
└── .gitignore
```

Rules:

- Do not create empty folders or placeholder modules without a real
  purpose.
- Keep the Python backend in `backend/`, a sibling of `frontend/`. Do not
  place backend code inside `frontend/` or create a second backend tree.
- UI keeps presentation only: no OS calls, no direct automation, no
  secrets. Future OS integration flows through Tauri commands or the
  local backend API — never inline in React.

## 4. Coding conventions

**TypeScript/React**

- Strict mode on; `verbatimModuleSyntax`; no unused locals/params
  (enforced by `tsc --noEmit` on every build).
- Components: PascalCase files and names; hooks: `useXxx` camelCase;
  shared helpers live in `src/lib/`; shared types in `src/types/`.
- Styling: Tailwind utility classes only; design tokens (colors, font)
  live in `src/index.css` under `@theme` — no stray hard-coded hex values
  in components.
- Reusable UI (Orb, modals, buttons) goes in `src/components/ui/`.

**Rust (Tauri shell)**

- Keep `src-tauri` minimal: default template structure, no extra
  plugins beyond the debug-only log plugin. Run `cargo fmt` and
  `cargo check` after any Rust change.

**General**

- Minimal dependencies: justify every package before installing; no
  LangChain/LangGraph, no UI kits, no state libraries unless a phase
  demands it.
- Never silently swallow errors: log warnings (console.warn) with
  context.
- Never claim a feature works without testing it.
- Do not rewrite working code for style alone; work incrementally.

## 5. Environment & commands (verified in this project)

```powershell
cd C:\Users\ZAH\Desktop\RUMMAN\TIA\frontend

npm install            # install frontend dependencies (first time)
npm run dev            # Vite dev server at http://localhost:1420 (fixed port)
npm run build          # TypeScript check + production web build
npm run tauri dev      # real desktop window (requires Rust toolchain)
npm run tauri build    # NSIS installer (requires Rust toolchain)
```

Rust and the Windows build environment are available in the project owner's
environment; Phase 1 Rust compilation and Tauri packaging have been reported
as passing. For a new machine without them, install:

```powershell
winget install --id Rustlang.Rustup -e
winget install --id Microsoft.VisualStudio.2022.BuildTools -e --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
```

Vite dev port is fixed to **1420** (`vite.config.ts` strictPort) to match
`tauri.conf.json` → `build.devUrl`. Do not change one without the other.

## 6. Current phase & boundaries

- **Phase 1 (COMPLETE):** Tauri 2 + React/TS/Tailwind foundation; single
  ChatPage; sidebar (New Chat / history / Settings); welcome state;
  text input; mic button as disabled visual placeholder; conversations
  persisted to localStorage; TIA branding (navy + cyan, generated icon
  set); docs. Its original fixed placeholder reply was replaced in Phase 3.
- **Phase 2 (COMPLETE):** Python FastAPI + Pydantic backend foundation in
  `backend/`: localhost-only health endpoint and generated API docs.
- **Phase 3 (COMPLETE):** frontend/backend communication and conversation
  synchronization are implemented.
- **Phase 4 (COMPLETE):** local Ollama chat, SSE streaming, and opt-in search
  are implemented.
- **Phase 5 (IN PROGRESS):** Milestones 1 and 2 are complete. Milestone 3.1
  adds authenticated API access, sequential migrations, and turn provenance.
  Packaged backend process supervision remains incomplete.
- **Still NOT implemented (do not implement without instruction):** memory
  extraction, memory APIs/approval UI, embeddings/RAG, voice libraries, browser
  automation, account switching, packaged backend supervision.
- The agreed roadmap is: Phase 0 environment and hardware verification;
  Phase 1 React + TypeScript + Tailwind + Tauri foundation; Phase 2 Python
  FastAPI backend foundation; Phase 3 frontend/backend communication;
  Phase 4 Ollama integration; Phase 5 SQLite conversations, security, memory
  and later agent work; Phase 6 speech recognition; Phase 7 text-to-speech; Phase 8 desktop and browser
  automation; Phase 9 SQLite memory and productivity; Phase 10 security,
  testing, optimization and packaging.
- `docs/PROJECT_STATUS.md` records the current state and distinguishes
  tested work from planned work.

## 7. Validation checklist (every chunk)

1. `npm run build` — TypeScript + production build pass.
2. `npm run dev` — server responds 200 on port 1420.
3. Rust changes: `cargo check` / `cargo fmt` inside `src-tauri/`.
4. `npm run tauri dev` — desktop window opens and closes cleanly.
5. `npm run tauri build` — when the environment supports it.
6. Report created/changed files, deps + reasons, test results with real
   output, launch commands, unresolved problems. Stop at the chunk
   boundary and wait for the user.

## 8. Review expectations (Codex)

- Verify the architecture and security invariants above.
- Flag: scope creep into future phases, unapproved plugins/capabilities,
  missing type hints (TS strict failures), fake feature claims, secrets
  in code, or changes to `legacy/` (frozen snapshot — read-only).
- Do not expand scope; out-of-boundary work belongs to the next phase.
