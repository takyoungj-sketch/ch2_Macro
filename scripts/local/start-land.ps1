# Starts local servers in hidden windows; reuses servers already responding.
param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "use-env.ps1")
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$logDir = Join-Path $RepoRoot "logs/local-land"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Test-LocalHttp([string]$Url) {
    try { return (Invoke-WebRequest $Url -TimeoutSec 2).StatusCode -eq 200 }
    catch { return $false }
}

if (-not (Test-LocalHttp "http://127.0.0.1:8000/health")) {
    Start-Process -FilePath (Join-Path $RepoRoot "backend/.venv/Scripts/python.exe") -WindowStyle Hidden `
        -WorkingDirectory (Join-Path $RepoRoot "backend") `
        -ArgumentList @("-B", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
        -RedirectStandardOutput (Join-Path $logDir "backend.out.log") `
        -RedirectStandardError (Join-Path $logDir "backend.err.log") | Out-Null
}
if (-not (Test-LocalHttp "http://127.0.0.1:5173/land/")) {
    Start-Process -FilePath (Get-Command node.exe).Source -WindowStyle Hidden `
        -WorkingDirectory (Join-Path $RepoRoot "frontend") `
        -ArgumentList @("node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "5173", "--strictPort") `
        -RedirectStandardOutput (Join-Path $logDir "frontend.out.log") `
        -RedirectStandardError (Join-Path $logDir "frontend.err.log") | Out-Null
}
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ((Test-LocalHttp "http://127.0.0.1:8000/health") -and (Test-LocalHttp "http://127.0.0.1:5173/land/")) {
        Write-Host "Land: http://127.0.0.1:5173/land/"
        if (-not $NoBrowser) { Start-Process "http://127.0.0.1:5173/land/" }
        return
    }
    Start-Sleep -Seconds 1
}
throw "Local servers did not become ready. Check $logDir"
