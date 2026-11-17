# TIA backend setup

Run these commands in PowerShell from the repository root:

```powershell
Set-Location .\backend
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The executable printed should be `...\TIA\backend\.venv\Scripts\python.exe`.
The explicit `python -m uvicorn` command uses that active interpreter and the
backend directory as the import root. The server listens on localhost only.
Omit `--reload` for the normal Windows startup; add it only during development.

In a second PowerShell window, check the health response and interactive docs:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/docs | Select-Object StatusCode
```

The health response is `{"status":"healthy","app":"TIA","version":"0.1.0"}`.

Stop the server with `Ctrl+C` in the window running Uvicorn. To leave the
virtual environment afterward, run `deactivate`.
