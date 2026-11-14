# legacy/pyside6-ui — Archived Prototype (read-only)

This folder is a **frozen snapshot** of TIA's first desktop prototype,
built before the project switched architecture (user decision, Phase 1):
the UI stack moved from **PySide6 (Python)** to **React + TypeScript +
Tailwind inside a Tauri 2 (Rust) shell**.

- Superseded by: `frontend/` (the active app).
- Do **not** develop, refactor or delete files here; it is kept only as
  historical reference (it is also preserved in git history at commit
  `755a2f8` "Pre-Tauri snapshot: Phase 1 PySide6 UI work").
- The Python 3.14 virtual environment (`.venv/` at the repository root)
  was created for this prototype. It is **not** part of the active stack
  and can be deleted or kept for the future Python backend phase.

Contents (original structure preserved):

```
main.py                 PySide6 entry point
requirements.txt        PySide6==6.12.0 (this prototype's only dependency)
tia/                    GUI package: app.py, ui/{theme, app_icon, main_window,
                        widgets/{status_pill, mic_button, empty_state}}
```

Useful ideas that carried over into the active app: the dark navy +
cyan design tokens, the TIA orb branding (now generated as real Windows
app icons), the status indicator, and the "honest placeholder" approach
for unimplemented features.
