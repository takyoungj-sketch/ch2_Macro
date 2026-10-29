# Local development only. Production starts must not set CH2_LOCAL_DEV_ACCESS.
param([switch]$NoBrowser)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "use-env.ps1")
$builtRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$builtLogs = Join-Path $builtRoot "logs/local-built"
New-Item -ItemType Directory -Path $builtLogs -Force | Out-Null
function Test-BuiltHttp([string]$url) {
    try { return (Invoke-WebRequest $url -TimeoutSec 2).StatusCode -eq 200 } catch { return $false }
}
if (-not (Test-BuiltHttp "http://127.0.0.1:8000/health")) {
    $previousLocalAccess = $env:CH2_LOCAL_DEV_ACCESS
    try {
        $env:CH2_LOCAL_DEV_ACCESS = "1"
        Start-Process -FilePath (Join-Path $builtRoot "backend/.venv/Scripts/python.exe") -WindowStyle Hidden `
            -WorkingDirectory (Join-Path $builtRoot "backend") `
            -ArgumentList @("-B", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
            -RedirectStandardOutput (Join-Path $builtLogs "api.out.log") -RedirectStandardError (Join-Path $builtLogs "api.err.log")
    } finally { $env:CH2_LOCAL_DEV_ACCESS = $previousLocalAccess }
}
if (-not (Test-BuiltHttp "http://127.0.0.1:5174/built/")) {
    Start-Process -FilePath (Get-Command node.exe).Source -WindowStyle Hidden `
        -WorkingDirectory (Join-Path $builtRoot "frontend-built") `
        -ArgumentList @("node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "5174", "--strictPort") `
        -RedirectStandardOutput (Join-Path $builtLogs "vite.out.log") -RedirectStandardError (Join-Path $builtLogs "vite.err.log")
}
for ($builtAttempt = 0; $builtAttempt -lt 40; $builtAttempt++) {
    if ((Test-BuiltHttp "http://127.0.0.1:8000/health") -and (Test-BuiltHttp "http://127.0.0.1:5174/built/")) {
        $access = Invoke-RestMethod "http://127.0.0.1:8000/api/auth/status"
        if (-not $access.local_dev_access) { throw "Existing API is not in local development mode. Restart API with CH2_LOCAL_DEV_ACCESS=1 and no API_TOKEN." }
        Write-Host "Built: http://localhost:5174/built/ (local development access)"
        if (-not $NoBrowser) { Start-Process "http://localhost:5174/built/" }
        return
    }
    Start-Sleep -Seconds 1
}
throw "Local servers did not become ready. Check $builtLogs"
