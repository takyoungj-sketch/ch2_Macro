# 로컬 built_stats → VPS Promote용 dump (Windows)
# Usage: pwsh deploy/scripts/dump_built_stats_local.ps1

param(
    [string]$PgDump = "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe",
    [string]$PgHost = "localhost",
    [string]$User = "postgres",
    [string]$Database = "built_stats",
    [string]$OutDir = "C:\ch2\ch2_Macro\backups"
)

$ts = Get-Date -Format "yyyyMMdd_HHmm"
$OutDir = Resolve-Path $OutDir -ErrorAction SilentlyContinue
if (-not $OutDir) {
    New-Item -ItemType Directory -Path "C:\ch2\ch2_Macro\backups" -Force | Out-Null
    $OutDir = "C:\ch2\ch2_Macro\backups"
}
$out = Join-Path $OutDir "built_stats_$ts.dump"

if (-not (Test-Path $PgDump)) {
    Write-Error "pg_dump not found: $PgDump"
}

& $PgDump -h $PgHost -U $User -d $Database -Fc --no-owner --no-acl -f $out
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Get-Item $out | Select-Object FullName, @{ N = "MB"; E = { [math]::Round($_.Length / 1MB, 2) } }
Write-Host "SCP example:"
Write-Host "scp -i `$env:USERPROFILE\.ssh\LightsailDefaultKey-ap-northeast-2.pem `"$out`" ubuntu@13.209.203.178:/var/backups/ch2/"
