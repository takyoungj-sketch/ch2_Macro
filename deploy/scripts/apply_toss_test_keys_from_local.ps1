# 로컬 deploy/local/toss-test-keys.env → VPS backend/.env 반영 (시크릿 출력 없음)
param(
  [string]$LocalFile = "",
  [string]$VpsHost = "ubuntu@13.209.203.178",
  [string]$Key = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
if (-not $LocalFile) {
  $LocalFile = Join-Path $RepoRoot "deploy/local/toss-test-keys.env"
}
if (-not $Key) {
  $Key = Join-Path $RepoRoot "LightsailDefaultKey-ap-northeast-2.pem"
}
if (-not (Test-Path $LocalFile)) {
  Write-Error "Missing $LocalFile"
}
if (-not (Test-Path $Key)) {
  Write-Error "Missing SSH key $Key"
}

$client = ""
$secret = ""
$content = Get-Content $LocalFile -Encoding UTF8 -Raw
$content = $content.TrimStart([char]0xFEFF)
foreach ($line in ($content -split "`r?`n")) {
  $line = $line.Trim()
  if (-not $line -or $line.StartsWith("#")) { continue }
  if ($line -match "^TOSS_CLIENT_KEY=(.+)$") { $client = $Matches[1].Trim() }
  if ($line -match "^TOSS_SECRET_KEY=(.+)$") { $secret = $Matches[1].Trim() }
}
if (-not $client -or -not $secret) {
  Write-Error "TOSS_CLIENT_KEY / TOSS_SECRET_KEY 값이 비어 있습니다. $LocalFile 을 채운 뒤 다시 실행하세요."
}
if (-not $client.StartsWith("test_ck_")) {
  Write-Error "TOSS_CLIENT_KEY must start with test_ck_ (API 개별 연동). 결제위젯 test_gck_ 는 사용하지 않습니다."
}
if (-not $secret.StartsWith("test_sk_")) {
  Write-Error "TOSS_SECRET_KEY must start with test_sk_"
}

$remoteTmp = "/tmp/ch2-toss-keys.$([guid]::NewGuid().ToString('n')).env"
$localTmp = [System.IO.Path]::GetTempFileName()
@(
  "TOSS_CLIENT_KEY=$client"
  "TOSS_SECRET_KEY=$secret"
) | Set-Content -Path $localTmp -Encoding ASCII -NoNewline
Add-Content -Path $localTmp -Value "" -Encoding ASCII

& scp -i $Key $localTmp "${VpsHost}:$remoteTmp"
Remove-Item -Force $localTmp
if ($LASTEXITCODE -ne 0) { throw "scp failed" }

$mergeScript = Join-Path $RepoRoot "deploy/scripts/merge_toss_keys_remote.sh"
& scp -i $Key $mergeScript "${VpsHost}:/opt/ch2_Macro/deploy/scripts/merge_toss_keys_remote.sh"
if ($LASTEXITCODE -ne 0) { throw "scp merge script failed" }
& ssh -i $Key $VpsHost "sed -i 's/\r$//' /opt/ch2_Macro/deploy/scripts/merge_toss_keys_remote.sh; bash /opt/ch2_Macro/deploy/scripts/merge_toss_keys_remote.sh $remoteTmp"
if ($LASTEXITCODE -ne 0) { throw "remote merge/verify failed" }
Write-Host "OK: Toss test keys applied and verify script passed."
