# CH2 Macro — Windows 로컬 → Lightsail VPS 배포
# Usage:
#   # 에이전트: 먼저 관련 파일만 commit 한 뒤
#   .\deploy\scripts\deploy-from-windows.ps1 -Scope built
#   .\deploy\scripts\deploy-from-windows.ps1 -Scope built -SkipPush   # push 이미 한 경우
param(
  [ValidateSet("built", "land", "collective", "all")]
  [string]$Scope = "built",
  [switch]$SkipCommit = $true,
  [switch]$SkipPush,
  [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$Key = Join-Path $RepoRoot "LightsailDefaultKey-ap-northeast-2.pem"
$VpsHost = "ubuntu@13.209.203.178"
$SshTarget = "${VpsHost}:/opt/ch2_Macro"

if (-not (Test-Path $Key)) {
  Write-Error "SSH key not found: $Key"
}

function Invoke-Scp([string[]]$Paths, [string]$RemoteSubdir) {
  foreach ($rel in $Paths) {
    $local = Join-Path $RepoRoot $rel
    if (-not (Test-Path $local)) {
      Write-Warning "SKIP missing: $rel"
      continue
    }
    $dest = "${VpsHost}:/opt/ch2_Macro/$RemoteSubdir"
    Write-Host "scp -> $rel"
    & scp -i $Key -r $local $dest
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $rel" }
  }
}

Push-Location $RepoRoot
try {
  if (-not $SkipCommit) {
    $dirty = git status --porcelain
    if ($dirty) {
      Write-Warning "SkipCommit=false but auto-commit is discouraged. Commit scope-specific files manually, then re-run with -SkipCommit."
    }
  }

  if (-not $SkipPush) {
    Write-Host "==> git push origin main"
    git push origin main
    if ($LASTEXITCODE -ne 0) { throw "git push failed" }
  }

  Write-Host "==> scp to VPS (scope=$Scope)"
  switch ($Scope) {
    "built" {
      Invoke-Scp @("backend/app/built", "backend/app/ai", "backend/app/config.py", "backend/app/main.py") "backend/app/"
      Invoke-Scp @("shared") "."
      Invoke-Scp @("frontend-built/src") "frontend-built/"
    }
    "land" {
      Invoke-Scp @("backend/app") "backend/"
      Invoke-Scp @("shared") "."
      Invoke-Scp @("frontend/src") "frontend/"
    }
    "collective" {
      Invoke-Scp @("backend/app/collective", "backend/app/collective_commercial", "backend/app/ai", "backend/app/config.py", "backend/app/main.py") "backend/app/"
      Invoke-Scp @("shared") "."
      Invoke-Scp @("frontend-collective/src") "frontend-collective/"
    }
    "all" {
      Invoke-Scp @("backend/app") "backend/"
      Invoke-Scp @("shared") "."
      Invoke-Scp @("frontend/src") "frontend/"
      Invoke-Scp @("frontend-built/src") "frontend-built/"
      Invoke-Scp @("frontend-collective/src") "frontend-collective/"
      Invoke-Scp @("deploy/macro-gateway", "deploy/hub", "deploy/scripts") "deploy/"
    }
  }

  Write-Host "==> VPS build + restart"
  & ssh -i $Key $VpsHost "sed -i 's/\r$//' /opt/ch2_Macro/deploy/scripts/vps_apply_scope.sh 2>/dev/null; bash /opt/ch2_Macro/deploy/scripts/vps_apply_scope.sh $Scope"
  if ($LASTEXITCODE -ne 0) { throw "remote vps_apply_scope failed" }

  if (-not $SkipVerify) {
    Write-Host "==> verify production (health + land + built + collective)"
    & ssh -i $Key $VpsHost @'
bash -s <<'VERIFY'
set -euo pipefail
ENV=/opt/ch2_Macro/backend/.env
TOKEN=$(grep '^API_TOKEN=' "$ENV" | cut -d= -f2- | tr -d '\r')
HDR=(-H "X-Api-Token: $TOKEN")

echo "==> health"
curl -sf http://127.0.0.1:8000/health | head -c 200
echo

echo "==> land regions search"
N=$(curl -sf "${HDR[@]}" "http://127.0.0.1:8000/api/free/v2/regions?search=%EA%B0%80%EA%B2%BD%EB%8F%99&limit=5" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else len(d.get('items',[])))")
if [[ "$N" -lt 1 ]]; then echo "FAIL: land regions search"; exit 1; fi
echo "land hits: $N"

echo "==> collective meta/filters"
curl -sf "${HDR[@]}" http://127.0.0.1:8000/api/collective/meta/filters | head -c 120
echo

echo "==> collective commercial meta/filters"
curl -sf "${HDR[@]}" http://127.0.0.1:8000/api/collective/commercial/meta/filters | head -c 120
echo
VERIFY
'@
    if ($LASTEXITCODE -ne 0) { throw "VPS smoke verify failed" }

    Write-Host "==> verify production built regression (gu vs dong)"
    python -c @"
import json, urllib.request, ssl
body = {
  'asset_type': 'commercial',
  'addr1': '충청북도', 'addr2': '청주시',
  'addr4_list': ['가경동'], 'leaf_level': 'addr4',
  'variables': {
    'gross_area': True, 'land_area': True, 'building_age': True,
    'road_code': True, 'zone_type_dummy': True, 'building_use_dummy': True,
  },
  'exclude_outliers_iqr': False,
}
req = urllib.request.Request(
  'https://macro.ch2data.com/api/built/regression/run',
  data=json.dumps(body).encode(),
  headers={'Content-Type': 'application/json'},
  method='POST',
)
with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=30) as r:
  d = json.load(r)
p = d['primary']
print('primary:', p['admin_level'], p['scope_label'])
if p['admin_level'] != 'gu':
  raise SystemExit('VERIFY FAIL: expected admin_level=gu')
print('OK')
"@
    if ($LASTEXITCODE -ne 0) { throw "production verify failed" }
  }

  Write-Host ""
  Write-Host "OK: deployed scope=$Scope to https://macro.ch2data.com"
} finally {
  Pop-Location
}
