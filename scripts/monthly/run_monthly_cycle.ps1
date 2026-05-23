# 월간 반자동 사이클 — 실제 처리는 scripts/monthly/run_monthly_cycle.py
# 예:
#   pwsh -File scripts/monthly/run_monthly_cycle.ps1 -CycleId 202605 -RepoRoot C:\ch2\ch2_Macro

param(
  [Parameter(Mandatory = $true)][string]$CycleId,
  [Parameter(Mandatory = $false)][string]$RepoRoot = "",
  [Parameter(Mandatory = $false)][switch]$SkipFlatten,
  [Parameter(Mandatory = $false)][string]$V2AsOf = "",
  [Parameter(Mandatory = $false)][switch]$WithUpperV2
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

if (Test-Path (Join-Path $RepoRoot "backend\.venv\Scripts\python.exe")) {
  $py = Join-Path $RepoRoot "backend\.venv\Scripts\python.exe"
} elseif (Test-Path (Join-Path $RepoRoot "pipeline\.venv\Scripts\python.exe")) {
  $py = Join-Path $RepoRoot "pipeline\.venv\Scripts\python.exe"
} else {
  $py = "py"
}

$runner = Join-Path $RepoRoot "scripts\monthly\run_monthly_cycle.py"
$argsList = @($runner, "--cycle-id", $CycleId, "--repo-root", $RepoRoot)
if ($SkipFlatten) { $argsList += "--skip-flatten" }
if (-not [string]::IsNullOrWhiteSpace($V2AsOf)) { $argsList += "--v2-as-of", $V2AsOf }
if ($WithUpperV2) { $argsList += "--with-upper-v2" }

& $py @argsList
