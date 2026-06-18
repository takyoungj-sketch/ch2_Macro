#Requires -Version 5.1
param([switch]$WithExe)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Dist = Join-Path $Root "dist"
$Stage = Join-Path $env:TEMP "molit_csv_collector_staging_$PID"
$Zip = Join-Path $Dist "molit_csv_collector.zip"
$BuildDir = Join-Path $Root "build"
$SpecDir = Join-Path $Root "spec"

if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $Stage -Force | Out-Null

Copy-Item (Join-Path $Root "molit_csv_collector") (Join-Path $Stage "molit_csv_collector") -Recurse
Copy-Item (Join-Path $Root "requirements.txt") $Stage
Copy-Item (Join-Path $Root "run_gui.bat") $Stage
Copy-Item (Join-Path $Root "run_collector.py") $Stage
Copy-Item (Join-Path $Root "README.md") $Stage
Copy-Item (Join-Path $Root "..\..\docs\MOLIT_CSV_COLLECTOR_WARNINGS.md") (Join-Path $Stage "WARNINGS.md")

if ($WithExe) {
    py -m pip install -q pyinstaller
    Push-Location $Root
    if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
    py -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name "MolitCsvCollector" `
        --paths "$Root" `
        --hidden-import molit_csv_collector `
        --hidden-import molit_csv_collector.gui `
        --hidden-import molit_csv_collector.downloader `
        --hidden-import molit_csv_collector.csv_validate `
        --hidden-import molit_csv_collector.config `
        --hidden-import molit_csv_collector.manifest `
        --collect-all selenium `
        "$Root\run_collector.py"
    Pop-Location
    $Exe = Join-Path $Root "dist\MolitCsvCollector.exe"
    if (-not (Test-Path $Exe)) { throw "PyInstaller exe not found: $Exe" }
    Copy-Item $Exe (Join-Path $Stage "MolitCsvCollector.exe")
}

if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $Zip -Force
Write-Host "Created: $Zip"
if ($WithExe) { Write-Host "EXE in zip: MolitCsvCollector.exe" }

# 임시 스테이징 정리
Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
if ($WithExe) { Remove-Item (Join-Path $Dist "MolitCsvCollector.exe") -Force -ErrorAction SilentlyContinue }
Remove-Item (Join-Path $Root "build") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Root "MolitCsvCollector.spec") -Force -ErrorAction SilentlyContinue
Write-Host "dist contains: $(Get-ChildItem $Dist | ForEach-Object { $_.Name })"
