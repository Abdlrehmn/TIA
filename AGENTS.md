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
- **Privacy stance:** all processing runs on the local machine. No cloud
  AI, no telemetry, no plaintext secrets, ever.

## 2. Target hardware (design constraints)

- Windows 10/11, 32 GB RAM, 2 TB storage
- NVIDIA GeForce RTX 3050 (VRAM unconfirmed — verify before choosing models)
- AMD Ryzen 5 (generation unconfirmed)
- Candidate model: Qwen3 4B via Ollama, pending VRAM verification. Every
  future model/tool choice must fit comfortably in the available VRAM.

## 3. Technology stack

| Layer | Choice | Status |
|---|---|---|
| Language | Python 3.11+ (currently 3.14.3) | active |
| GUI | PySide6 | active |
| AI runtime | Ollama + Qwen3 4B | planned |
| STT | faster-whisper | planned |
| Wake word | openWakeWord (or equivalent local solution) | planned |
| VAD | WebRTC VAD | planned |
| Audio IO | SoundDevice | planned |
| TTS | Piper (replaceable) | planned |
| Browser automation | Playwright | planned |
| Windows automation | pywinauto / Windows UI Automation | planned |
| Database | SQLite | planned |
| Credentials | Windows Credential Manager / secure OAuth | planned |

## 4. Architecture (module map)

Independent modules; the UI never performs OS actions directly, and the
AI brain never receives unrestricted shell access.

### Current (Phase 1 · Chunk 1)

```
main.py                  entry point (thin: logging + tia.app.run)
tia/__init__.py          package identity and version
tia/app.py               QApplication bootstrap, theming, lifecycle
tia/ui/theme.py          design tokens (Palette) + QSS stylesheet
tia/ui/app_icon.py       programmatically drawn application icon
tia/ui/main_window.py    main window layout composition
tia/ui/widgets/          StatusPill (+ StatusLevel), MicControl/MicButton,
                         EmptyState
```

### Planned (create files only when their chunk starts — no placeholders)

`tia/audio/`, `tia/vad/`, `tia/wake/`, `tia/stt/`, `tia/brain/` (Ollama
client), `tia/tts/`, `tia/planning/`, `tia/tools/` (explicitly registered
and validated tools), `tia/permissions/`, `tia/memory/` (SQLite),
`tia/verification/`, `tia/config/`, `tia/security/`, `tia/integrations/`.

### Structural rules

- UI code stays inside `tia/ui/` and must not call the OS, network, or
  any automation API.
- Tools are registered and validated explicitly; the AI never gets raw
  shell/OS access.
- Long-running work must never block the Qt event loop: use worker
  threads communicating over Qt signals when implemented.

## 5. Coding conventions

- Python 3.11+; full type hints on all public functions;
  `from __future__ import annotations` at the top of each module.
- A short, factual docstring on every module, class and public function.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes,
  `UPPER_SNAKE` for constants; Qt widget `objectName`s match the names
  used in `tia/ui/theme.py`.
- Keep dependencies minimal: add a package only when the chunk that needs
  it starts, pinned to an exact version in `requirements.txt`.
- Error handling: log through the `logging` module; never swallow
  exceptions silently; the GUI must not crash on bad input.
- No hardcoded secrets, API keys, or passwords; no plaintext credential
  storage (Windows Credential Manager or secure OAuth when needed).
- All colors/styling live in `tia/ui/theme.py`; widgets reference design
  tokens, never stray hex values.
- Keep `main.py` thin; application lifecycle logic belongs in `tia/app.py`.

## 6. Safety requirements (non-negotiable)

- These actions require **explicit user confirmation** before execution:
  sending email, deleting files, uninstalling software, modifying
  important system settings, and any purchase/payment flow.
- Never bypass MFA, CAPTCHA, or account security. Never automate
  credential entry.
- Account/profile switching (ChatGPT, Claude, VS Code) only through
  user-approved, auditable steps.
- Every proposed file/system tool must be reviewed by the user before it
  is wired into the AI brain.
- Never pretend unimplemented features work: mark them disabled or
  "coming soon" in the UI until the real implementation lands.

## 7. Environment

- Project-local virtual environment: `.venv/`, created from the
  standalone **Python 3.14.3** (`py -3.14`), 64-bit.
- The system Python / Anaconda base must never be modified; no global
  installs; no administrator privileges.
- PowerShell (project root):

  ```powershell
  .\.venv\Scripts\Activate.ps1
  python -m pip install -r requirements.txt   # only after requirements change
  python main.py
  ```

- Validation commands (run after every change):

  ```powershell
  python -m compileall -q tia main.py
  python -c "import tia.app, tia.ui.main_window; print('imports ok')"
  $env:QT_QPA_PLATFORM = "offscreen"
  python -c "from PySide6.QtWidgets import QApplication; from tia.ui.main_window import MainWindow; app = QApplication([]); w = MainWindow(); w.show(); w.close(); print('offscreen ok')"
  Remove-Item Env:QT_QPA_PLATFORM
  ```

## 8. Current phase & implementation boundaries

- **Current phase: Phase 1 — TIA Foundation.**
- **Chunk 1 (COMPLETE):** environment, project skeleton, PySide6 desktop
  shell (dark navy + cyan accent, status pill, disabled mic control,
  disabled text input, honest empty state).
- **Next chunk (do NOT start without explicit user instruction):
  Chunk 2 — voice input pipeline** (SoundDevice capture, WebRTC VAD,
  faster-whisper STT, GUI wiring).
- Work incrementally; never rewrite unrelated files or working features;
  inspect the workspace before changing anything.
- Update `README.md` and this file whenever behavior, structure or
  boundaries change.

## 9. Reporting expectations (every chunk)

Report: files created/changed, dependencies installed, tests performed
and results, exact launch commands, and anything that still needs
attention. Stop at the agreed chunk boundary and wait for the user.

## 10. Review expectations (Codex)

- Verify the conventions and safety rules above.
- Flag: missing type hints, secrets in code, unconfirmed features,
  out-of-boundary edits, global installs, or GUI-blocking work.
- Do not expand scope; changes outside the current chunk belong to the
  next chunk.
