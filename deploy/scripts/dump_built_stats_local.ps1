# 로컬 built_stats → VPS Promote용 dump (Windows)
# Usage: pwsh deploy/scripts/dump_built_stats_local.ps1

param(
    [string]$PgDump = "",
    [string]$PgHost = "localhost",
    [string]$User = "postgres",
    [string]$Database = "built_stats",
    [string]$OutDir = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
if (-not $PgDump) {
    $command = Get-Command pg_dump.exe -ErrorAction SilentlyContinue
    if ($command) {
        $PgDump = $command.Source
    } else {
        $install = Get-ChildItem (Join-Path $env:ProgramFiles "PostgreSQL") -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^\d+(\.\d+)*$' -and (Test-Path (Join-Path $_.FullName "bin/pg_dump.exe")) } |
            Sort-Object { [version]($_.Name + '.0') } -Descending |
            Select-Object -First 1
        if ($install) { $PgDump = Join-Path $install.FullName "bin/pg_dump.exe" }
    }
}
if (-not $PgDump -or -not (Test-Path -LiteralPath $PgDump -PathType Leaf)) {
    throw "pg_dump not found. Specify -PgDump with the installed PostgreSQL binary."
}
if (-not $OutDir) { $OutDir = Join-Path $RepoRoot "backups" }
$OutDir = [System.IO.Path]::GetFullPath($OutDir)
$ts = Get-Date -Format "yyyyMMdd_HHmm"
$out = Join-Path $OutDir "built_stats_$ts.dump"
if ($DryRun) {
    [PSCustomObject]@{ PgDump = $PgDump; Database = $Database; Output = $out }
    return
}
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

& $PgDump -h $PgHost -U $User -d $Database -Fc --no-owner --no-acl -f $out
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Get-Item $out | Select-Object FullName, @{ N = "MB"; E = { [math]::Round($_.Length / 1MB, 2) } }
Write-Host "SCP example:"
Write-Host "scp -i `$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-northeast-2.pem `"$out`" ubuntu@13.209.203.178:/var/backups/ch2/"
