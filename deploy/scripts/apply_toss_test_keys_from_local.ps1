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
Get-Content $LocalFile -Encoding UTF8 | ForEach-Object {
  $line = $_.Trim()
  if ($line -match "^#") { return }
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

$mergeBash = @'
set -euo pipefail
REMOTE_TMP="$1"
ENV_FILE="/opt/ch2_Macro/backend/.env"
set -a
source "$REMOTE_TMP"
set +a
test -n "$TOSS_CLIENT_KEY" && test -n "$TOSS_SECRET_KEY"
grep -v -E '^TOSS_CLIENT_KEY=|^TOSS_SECRET_KEY=|^TOSS_WEBHOOK_SECRET=' "$ENV_FILE" > "${ENV_FILE}.new" || cp "$ENV_FILE" "${ENV_FILE}.new"
{
  echo "TOSS_CLIENT_KEY=$TOSS_CLIENT_KEY"
  echo "TOSS_SECRET_KEY=$TOSS_SECRET_KEY"
} >> "${ENV_FILE}.new"
mv "${ENV_FILE}.new" "$ENV_FILE"
chmod 600 "$ENV_FILE"
rm -f "$REMOTE_TMP"
sudo systemctl restart ch2-macro-backend
sleep 2
bash /opt/ch2_Macro/deploy/scripts/verify_toss_billing_ready.sh
'@

$mergeBash | & ssh -i $Key $VpsHost "tr -d '\r' | bash -s -- $remoteTmp"
if ($LASTEXITCODE -ne 0) { throw "remote merge/verify failed" }
Write-Host "OK: Toss test keys applied and verify script passed."
