$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $repoRoot "backend"
$frontendRoot = Join-Path $repoRoot "frontend"
$pythonPath = Join-Path $backendRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $pythonPath)) {
  throw "TIA's backend virtual environment is missing. Create backend\.venv before using this launcher."
}

$portProbe = [System.Net.Sockets.TcpClient]::new()
try {
  $portProbe.Connect("127.0.0.1", 8000)
  throw "Port 8000 is already in use. Stop the existing listener before starting TIA."
} catch [System.Net.Sockets.SocketException] {
  # No listener is present; the backend can safely claim the configured port.
} finally {
  $portProbe.Dispose()
}

$sessionToken = (& $pythonPath -c "import secrets; print(secrets.token_urlsafe(32))").Trim()
if ($LASTEXITCODE -ne 0 -or $sessionToken.Length -lt 43) {
  throw "Could not generate a local API session credential."
}

$env:TIA_API_TOKEN = $sessionToken
$env:TIA_API_PORT = "8000"
$backendProcess = $null
try {
  $backendProcess = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $backendRoot `
    -NoNewWindow `
    -PassThru

  $backendReady = $false
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    if ($backendProcess.HasExited) {
      throw "TIA's backend exited during startup. Check the backend error output above."
    }
    try {
      $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 1
      if ($health.status -eq "healthy" -and $health.app -eq "TIA") {
        $backendReady = $true
        break
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  if (-not $backendReady) {
    throw "TIA's backend did not become ready within 30 seconds."
  }

  Push-Location $frontendRoot
  try {
    & npm.cmd run tauri dev
    if ($LASTEXITCODE -ne 0) {
      throw "TIA's desktop development app exited with code $LASTEXITCODE."
    }
  } finally {
    Pop-Location
  }
} finally {
  if ($backendProcess -and -not $backendProcess.HasExited) {
    Stop-Process -Id $backendProcess.Id -Force
  }
  Remove-Item Env:TIA_API_TOKEN -ErrorAction SilentlyContinue
  Remove-Item Env:TIA_API_PORT -ErrorAction SilentlyContinue
}
