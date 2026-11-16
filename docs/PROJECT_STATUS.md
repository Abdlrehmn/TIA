# TIA Project Status

## Project overview

TIA is a local-first Windows desktop assistant. Its long-term goal is to
support English and Roman Urdu, answer through voice, and carry out approved
computer tasks. The current application is a desktop and chat interface
foundation; it is not yet an AI assistant.

## Current phase

- **Phase 1: COMPLETE** — React, TypeScript, Tailwind CSS, Vite, and Tauri
  desktop foundation.
- **Phase 2: NOT STARTED** — Python FastAPI backend foundation.

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
| Conversation storage | Browser `localStorage` | Implemented; local to the app profile |
| Backend | Python 3.11+, FastAPI, Pydantic | Planned; Phase 2 not started |
| AI | Ollama + Qwen3 4B Instruct candidate | Planned; hardware/VRAM suitability must be checked |
| Speech | faster-whisper, SoundDevice, Piper/Kokoro evaluation | Planned |
| Memory | SQLite | Planned |
| Automation | Playwright and reviewed desktop tools | Planned |

## Current limitations

- There is no connected model, so replies are fixed placeholders.
- Voice input, speech output, wake word, and microphone capture are absent.
- Settings are a static interface, not application configuration.
- Conversations use `localStorage`; there is no backend or SQLite database.
- No computer or browser automation is implemented.
- Phase 1 has no authenticated local API or backend process.

## Agreed phase roadmap

| Phase | Scope | Status |
|---|---|---|
| 0 | Environment and hardware verification | Complete for the Phase 1 environment; model hardware verification remains relevant before AI integration |
| 1 | React + TypeScript + Tailwind + Tauri foundation | **Complete** |
| 2 | Python FastAPI backend foundation | **Not started** |
| 3 | Frontend/backend communication | Planned |
| 4 | Ollama integration | Planned |
| 5 | Tool calling and agent loop | Planned |
| 6 | Speech recognition | Planned |
| 7 | Text-to-speech | Planned |
| 8 | Desktop and browser automation | Planned |
| 9 | SQLite memory and productivity | Planned |
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
- The Python backend is a sibling of `frontend/` and begins in Phase 2; it is
  not part of the completed Phase 1 implementation.
- The legacy PySide6 prototype is archived and read-only.
