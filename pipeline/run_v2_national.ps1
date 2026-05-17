# V2 무료 통계 전국 사전집계 (시도별 청크).
# 전제: land_transactions 에 해당 기간 데이터가 전국 단위로 적재되어 있음.
#       db/007, db/008 적용 및 preflight 권장 — docs/V2_STATS_PRODUCTION.md
#
# 사용 예 (서비스 기준 2026-01-01 → as_of 2025-12-01, 무료 3·5년):
#   .\run_v2_national.ps1
#   .\run_v2_national.ps1 -AsOf "2025-12-01" -Windows "3,5"
#
# STATS_V2_SIDO_CODE 가 현재 세션·시스템에 잡혀 있으면 여기서 제거한 뒤 실행합니다.

param(
    [string] $AsOf = "2025-12-01",
    [string] $Windows = "3,5"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($env:STATS_V2_SIDO_CODE) {
    Write-Host "INFO: Clearing STATS_V2_SIDO_CODE for national run (was: $($env:STATS_V2_SIDO_CODE))."
}
Remove-Item Env:\STATS_V2_SIDO_CODE -ErrorAction SilentlyContinue

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    $pyExe = $venvPy
} else {
    $pyCmd = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pyCmd) {
        Write-Error "Python not found. Create pipeline\.venv or add python to PATH."
        exit 1
    }
    $pyExe = $pyCmd.Source
}

& $pyExe build_stats_v2.py --as-of $AsOf --windows $Windows @args
exit $LASTEXITCODE
