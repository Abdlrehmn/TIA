# TIA — Architecture

This document describes how TIA is put together, why each piece was
chosen, and how the phases fit together. It is the companion to
`AGENTS.md` (agent rules) and `README.md` (usage).

## 1. High-level shape

```
┌───────────────────────────────────────────────────────────┐
│  TIA desktop window (Tauri 2, Rust)                       │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  WebView2                                           │  │
│  │  React 19 + TypeScript + Tailwind 4 (Vite build)    │  │
│  │  - ChatPage (single screen)                         │  │
│  │  - Sidebar: New Chat / history / Settings           │  │
│  │  - ConversationArea + ChatInput                     │  │
│  └──────────────────┬──────────────────────────────────┘  │
│                     │ (Phase 2+: local authenticated API) │
│  ┌──────────────────▼──────────────────────────────────┐  │
│  │  Python 3.11+ · FastAPI · Pydantic (127.0.0.1 only) │  │
│  │  tools registry · permissions · memory (SQLite)     │  │
│  │  AI brain: Ollama + Qwen3 4B · STT/TTS pipeline     │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

## 2. Why this stack

- **Tauri 2 + React** gives a small, fast, native-feeling Windows app
  with a modern UI ecosystem, instead of a heavier Electron-style shell
  or hand-built native widgets.
- **TypeScript strict** catches UI bugs at compile time; **Tailwind 4**
  keeps styling token-based (`@theme` in `src/index.css`) and consistent
  (dark navy + single cyan accent carried over from the original TIA
  design).
- **Python + FastAPI** will host everything that must not live in the UI:
  the AI brain, voice pipeline, file/system tools, permissions and
  SQLite memory. Pydantic models become the shared contract with the
  frontend types (`frontend/src/types/chat.ts`).

## 3. Trust boundaries & security model

1. **The WebView/React layer is untrusted** for OS purposes: its Tauri
   capabilities are `core:default` only. No shell, no filesystem, no
   HTTP plugins are enabled.
2. **The Rust shell** exists to open/own the window and (in later
   phases) spawn/monitor the Python backend process. Anything beyond
   that must be an explicitly reviewed, minimal Tauri command.
3. **The Python backend** owns all OS-facing work. Every dangerous tool
   (email, delete, uninstall, settings) requires explicit user
   confirmation and will be registered in an auditable tools registry.
4. **Local authenticated API (planned, Phase 2+):** FastAPI binds to
   127.0.0.1 only; the Tauri shell starts the backend as a child process
   and hands the frontend a short-lived token (e.g. generated at startup
   and passed via a Tauri command); every request carries it as a
   bearer header. This prevents random local processes from talking to
   TIA's API.
5. **Never:** bypass MFA/CAPTCHA, store plaintext credentials, or give
   the model unrestricted shell access.

## 4. Current data flow (Phase 1)

- Everything is client-side inside the WebView:
  `ChatInput → useConversations (React state) → MessageBubble`.
- Conversations persist to `localStorage` (`tia.conversations.v1`).
- The assistant's reply is a fixed, honest placeholder — no AI is
  connected. The mic button is disabled with an explanatory tooltip.

## 5. Phase roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Tauri 2 + React/TS/Tailwind shell, chat UI foundation | ✅ done |
| 2 | FastAPI + Pydantic backend on 127.0.0.1, token auth, wire frontend | next |
| 3 | Ollama + Qwen3 4B brain, real replies, SQLite memory | planned |
| 4 | Voice: SoundDevice capture, VAD, faster-whisper STT, TTS (Piper/Kokoro) | planned |
| 5 | Tools: files, apps, browser (Playwright), email, reminders — with permission gates | planned |
| 6 | Wake word, autonomous task planning + verification | planned |

Hardware constraint to verify before Phase 3: NVIDIA RTX 3050 VRAM
(Qwen3 4B must fit comfortably; quantization likely).

## 6. Frontend module map

```
frontend/src/
├── main.tsx / App.tsx / index.css   entry, root, design tokens
├── pages/ChatPage.tsx               screen composition + top status bar
├── components/
│   ├── layout/Sidebar.tsx           brand, New Chat, history, Settings entry
│   ├── chat/ConversationArea.tsx    welcome vs. message list (+ auto-scroll)
│   ├── chat/WelcomeMessage.tsx      intro + honest capability chips
│   ├── chat/MessageBubble.tsx       user/TIA message rendering
│   ├── chat/ChatInput.tsx           textarea, send, disabled mic placeholder
│   └── ui/Orb.tsx, SettingsModal.tsx  shared brand orb, static settings dialog
├── hooks/useConversations.ts        chats + messages state, persistence
├── hooks/useAutoScroll.ts           keep message list pinned to bottom
└── lib/                             uid, time, constants, storage
```
