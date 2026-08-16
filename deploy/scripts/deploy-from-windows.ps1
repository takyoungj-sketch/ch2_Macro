# CH2 Macro — Windows 로컬 → Lightsail VPS 배포
# Usage:
#   # 에이전트: 먼저 관련 파일만 commit 한 뒤
#   .\deploy\scripts\deploy-from-windows.ps1 -Scope built
#   .\deploy\scripts\deploy-from-windows.ps1 -Scope built -SkipPush   # push 이미 한 경우
param(
  [ValidateSet("built", "land", "collective", "profile", "rent", "lab", "all")]
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
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()
    Write-Host "==> git push -u origin $branch"
    git push -u origin $branch
    if ($LASTEXITCODE -ne 0) { throw "git push failed" }
  }

  Write-Host "==> scp to VPS (scope=$Scope)"
  if ($Scope -eq "profile" -or $Scope -eq "rent" -or $Scope -eq "lab" -or $Scope -eq "all") {
    & ssh -i $Key $VpsHost "mkdir -p /opt/ch2_Macro/frontend-profile /opt/ch2_Macro/frontend-rent /opt/ch2_Macro/frontend-lab /opt/ch2_Macro/backend/app/ai/knowledge /opt/ch2_Macro/backend/app/ai/bundles /opt/ch2_Macro/deploy/templates"
    if ($LASTEXITCODE -ne 0) { throw "remote mkdir failed" }
  }
  switch ($Scope) {
    "built" {
      Invoke-Scp @("backend/app/built", "backend/app/recommendation", "backend/app/ai", "backend/app/config.py", "backend/app/main.py") "backend/app/"
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
    "profile" {
      Invoke-Scp @("backend/app") "backend/"
      Invoke-Scp @("shared") "."
      Invoke-Scp @("frontend-profile/package.json", "frontend-profile/package-lock.json", "frontend-profile/tsconfig.json", "frontend-profile/vite.config.ts", "frontend-profile/tailwind.config.js", "frontend-profile/postcss.config.js", "frontend-profile/index.html", "frontend-profile/src") "frontend-profile/"
      Invoke-Scp @("deploy/templates/nginx-ch2-macro.conf", "deploy/macro-gateway") "deploy/"
      Invoke-Scp @("deploy/scripts") "deploy/"
    }
    "lab" {
      Invoke-Scp @("backend/app/qa_audit", "backend/app/config.py", "backend/app/main.py") "backend/app/"
      Invoke-Scp @("shared") "."
      Invoke-Scp @("frontend-lab/package.json", "frontend-lab/package-lock.json", "frontend-lab/tsconfig.json", "frontend-lab/vite.config.ts", "frontend-lab/tailwind.config.js", "frontend-lab/postcss.config.js", "frontend-lab/index.html", "frontend-lab/src") "frontend-lab/"
      Invoke-Scp @("frontend-built/src") "frontend-built/"
      Invoke-Scp @("frontend-rent/src") "frontend-rent/"
      Invoke-Scp @("deploy/templates/nginx-ch2-macro.conf") "deploy/templates/"
    }
    "rent" {
      Invoke-Scp @("backend/app/rent", "backend/app/config.py", "backend/app/main.py") "backend/app/"
      Invoke-Scp @("backend/app/ai/knowledge") "backend/app/ai/"
      Invoke-Scp @("backend/app/ai/bundles/extractors.py", "backend/app/ai/bundles/registry.py") "backend/app/ai/bundles/"
      Invoke-Scp @("backend/app/ai/panel_capabilities.py", "backend/app/ai/stats_kb.py") "backend/app/ai/"
      Invoke-Scp @("shared") "."
      Invoke-Scp @("frontend-rent/package.json", "frontend-rent/package-lock.json", "frontend-rent/tsconfig.json", "frontend-rent/vite.config.ts", "frontend-rent/tailwind.config.js", "frontend-rent/postcss.config.js", "frontend-rent/index.html", "frontend-rent/src") "frontend-rent/"
      Invoke-Scp @("deploy/templates/nginx-ch2-macro.conf", "deploy/macro-gateway") "deploy/"
      Invoke-Scp @("deploy/scripts") "deploy/"
    }
    "all" {
      Invoke-Scp @("backend/app") "backend/"
      Invoke-Scp @("shared") "."
      # region_canonical SSOT (backend re-export imports pipeline module)
      Invoke-Scp @("pipeline/region_canonical.py") "pipeline/"
      Invoke-Scp @("frontend/tsconfig.json", "frontend/vite.config.ts", "frontend/tailwind.config.js", "frontend/src") "frontend/"
      Invoke-Scp @("frontend-built/tsconfig.json", "frontend-built/vite.config.ts", "frontend-built/src") "frontend-built/"
      Invoke-Scp @("frontend-collective/tsconfig.json", "frontend-collective/vite.config.ts", "frontend-collective/tailwind.config.js", "frontend-collective/src") "frontend-collective/"
      Invoke-Scp @("frontend-profile/package.json", "frontend-profile/package-lock.json", "frontend-profile/tsconfig.json", "frontend-profile/vite.config.ts", "frontend-profile/tailwind.config.js", "frontend-profile/postcss.config.js", "frontend-profile/index.html", "frontend-profile/src") "frontend-profile/"
      Invoke-Scp @("frontend-rent/package.json", "frontend-rent/tsconfig.json", "frontend-rent/vite.config.ts", "frontend-rent/tailwind.config.js", "frontend-rent/postcss.config.js", "frontend-rent/index.html", "frontend-rent/src") "frontend-rent/"
      Invoke-Scp @("frontend-lab/package.json", "frontend-lab/package-lock.json", "frontend-lab/tsconfig.json", "frontend-lab/vite.config.ts", "frontend-lab/tailwind.config.js", "frontend-lab/postcss.config.js", "frontend-lab/index.html", "frontend-lab/src") "frontend-lab/"
      Invoke-Scp @("deploy/macro-gateway", "deploy/hub", "deploy/scripts", "deploy/templates") "deploy/"
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
