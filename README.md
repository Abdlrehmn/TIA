# TIA — Personal AI Desktop Agent

TIA is a **local-first** Windows desktop assistant. She is being built to
understand English and Roman Urdu, answer through voice, and eventually
perform approved tasks on your computer — with everything running locally
on your machine. No cloud, no telemetry, no secrets in plain text.

> **Current status: Phase 1 · Chunk 1 complete — desktop interface only.**
> Voice, the local AI brain and automation are **not implemented yet**;
> anything unfinished is clearly marked as such inside the app.

## What works today

- A polished PySide6 desktop window — dark navy theme with a cyan accent.
- TIA branding, application icon and a clear status indicator.
- Central conversation/empty-state area with honest "coming soon" chips.
- Disabled microphone control and disabled text input, both labeled as
  not implemented yet.
- Clean resize/close behavior with native window controls.

## What is not implemented yet (planned roadmap)

| Feature | Status |
|---|---|
| Desktop interface (this) | ✅ Phase 1 |
| Voice input: SoundDevice + WebRTC VAD + faster-whisper | ⏳ planned |
| Wake word detection (openWakeWord) | ⏳ planned |
| Local AI brain: Ollama + Qwen3 4B (VRAM check pending) | ⏳ planned |
| Voice output: Piper TTS | ⏳ planned |
| Browser automation (Playwright) | ⏳ planned |
| Windows automation (pywinauto / UIA) | ⏳ planned |
| Email, reminders, calendar, notes | ⏳ planned |
| File/folder management, software install/uninstall | ⏳ planned |
| Local memory, planning, execution verification | ⏳ planned |

## Quick start (PowerShell)

```powershell
cd C:\Users\ZAH\Desktop\RUMMAN\TIA

# One-time setup (already done for this machine)
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Run TIA
python main.py
```

If script activation is blocked, run once (no admin needed):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Project structure

```
TIA/
├── main.py                 # entry point (thin)
├── requirements.txt        # pinned dependencies (PySide6 only, for now)
├── README.md
├── AGENTS.md               # shared rules for AI agents (OpenCode + Codex)
├── .gitignore
└── tia/
    ├── __init__.py         # package identity/version
    ├── app.py              # QApplication bootstrap & lifecycle
    └── ui/
        ├── theme.py        # design tokens + stylesheet (single source of truth)
        ├── app_icon.py     # programmatically drawn icon (no binary assets)
        ├── main_window.py  # window layout composition
        └── widgets/
            ├── status_pill.py   # status indicator (offline/ready/busy/error)
            ├── mic_button.py    # disabled mic control ("coming soon")
            └── empty_state.py   # central conversation empty state
```

## Privacy & safety

- **Local-first:** no cloud services; AI, speech and voice models all run
  on your hardware.
- **Confirmation gates:** sending email, deleting files, uninstalling
  software and modifying important settings will always require your
  explicit confirmation.
- **No security bypasses:** TIA will never bypass MFA, CAPTCHA or account
  security.
- **No unrestricted access:** the AI never receives raw shell access;
  only explicitly registered and validated tools.

## Hardware assumptions

- Windows 10/11, 32 GB RAM, 2 TB storage
- NVIDIA GeForce RTX 3050 (VRAM to be verified before model selection)
- AMD Ryzen 5

## License

To be decided by the project owner.
