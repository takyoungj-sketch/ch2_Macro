# Dot-source this file: . ./scripts/local/use-env.ps1
param([string]$NodeHome = $env:CH2_NODE_HOME)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
if (-not $NodeHome) {
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($nodeCommand -and (Test-Path (Join-Path (Split-Path $nodeCommand.Source) "npm.cmd"))) {
        $NodeHome = Split-Path $nodeCommand.Source
    } else {
        $toolsRoot = Join-Path ([System.IO.Path]::GetPathRoot($RepoRoot)) "tools"
        $install = Get-ChildItem $toolsRoot -Directory -Filter "node-v*-win-x64" -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^node-v\d+\.\d+\.\d+-win-x64$' -and (Test-Path (Join-Path $_.FullName "npm.cmd")) } |
            Sort-Object { [version]($_.Name -replace '^node-v|-win-x64$', '') } -Descending |
            Select-Object -First 1
        if ($install) { $NodeHome = $install.FullName }
    }
}
if (-not $NodeHome -or -not (Test-Path (Join-Path $NodeHome "node.exe")) -or -not (Test-Path (Join-Path $NodeHome "npm.cmd"))) {
    throw "Node.js with npm is required. Pass -NodeHome or set CH2_NODE_HOME."
}
$activate = Join-Path $RepoRoot "backend/.venv/Scripts/Activate.ps1"
if (-not (Test-Path $activate)) { throw "Backend virtual environment missing: $activate" }
. $activate
$env:PATH = "$NodeHome;$env:PATH"
Write-Host "CH2 local environment: $RepoRoot"
Write-Host "Node/npm: $NodeHome"
Write-Host "Python: $env:VIRTUAL_ENV (use python -m pip for packages)"
