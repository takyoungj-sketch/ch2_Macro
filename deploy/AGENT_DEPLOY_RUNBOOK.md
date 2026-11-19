# CH2 Macro — Agent 배포 런북 (Cursor 자동 실행용)

> **목적:** 사용자가 「배포해줘」「웹에 반영해줘」「VPS 반영」 등을 요청하면, 에이전트가 **추가 확인 없이** 아래 절차를 끝까지 수행한다.  
> **대상:** `macro.ch2data.com` (Lightsail VPS 1대, 토지 `/land/` · 복합 `/built/` · 집합 `/collective/`).

---

## 1. 고정 값 (매번 묻지 않음)

| 항목 | 값 |
|------|-----|
| VPS 호스트 | `13.209.203.178` |
| SSH 사용자 | `ubuntu` |
| SSH 키 (Windows) | `c:\ch2\ch2_Macro\LightsailDefaultKey-ap-northeast-2.pem` |
| VPS 코드 경로 | `/opt/ch2_Macro` |
| systemd 서비스 | `ch2-macro-backend` |
| 운영 URL | `https://macro.ch2data.com` |
| API 헬스 | `https://macro.ch2data.com/api/...` 또는 VPS 내부 `http://127.0.0.1:8000/health` |
| Git 원격 | `origin` → `https://github.com/takyoungj-sketch/ch2_Macro.git` |
| 기본 브랜치 | `main` |

**중요:** VPS `/opt/ch2_Macro`는 **git clone이 아닌 tar/scp 이력**이 있다. `redeploy.sh`의 `git pull`만으로는 실패할 수 있음 → **§3 경로 B(권장)** 사용.

---

## 2. 사용자 요청 시 에이전트 행동 원칙

1. **로컬 변경**이 있으면 → 관련 파일만 **commit** (메시지: `fix|feat(범위): 한 줄 요약`).
2. **push** `origin main` (배포 요청 = push 포함으로 간주).
3. **VPS 반영** (§3).
4. **운영 스모크 검증** (§5) 후 결과 보고.
5. SSH 키·호스트는 §1 고정값 사용 — 「키 어디 있나요?」 재질문 금지.
6. PowerShell에서는 `$HOST` 변수 사용 금지 → `ubuntu@13.209.203.178` 리터럴 또는 `$VpsHost` 사용.

---

## 3. VPS 코드 반영 (2가지 경로)

### 경로 A — VPS에 git이 있을 때 (이상적)

```bash
ssh -i "c:\ch2\ch2_Macro\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@13.209.203.178 \
  "bash /opt/ch2_Macro/deploy/scripts/redeploy.sh main"
```

`redeploy.sh`가 하는 일: `git pull` → backend deps → `frontend` / `frontend-built` / `frontend-collective` 빌드 → gateway → nginx reload → **backend restart**.

### 경로 B — git 없음 / 부분 배포 (현재 운영 상태, **권장**)

**Windows (로컬):** 스크립트 한 방 (에이전트는 **먼저** 변경 파일만 commit)

```powershell
cd c:\ch2\ch2_Macro
# 1) 관련 파일만 git commit
# 2) 배포
.\deploy\scripts\deploy-from-windows.ps1 -Scope built
# -Scope: built | land | collective | profile | rent | lab | insight | all
# -SkipPush  # 이미 push 된 경우
# -SkipPreflight  # 배포 전 점검 건너뛰기 (비권장)
# -AllowDrift     # 범위 밖 의존이 서버와 달라도 진행 (의도한 경우만)
```

**배포 전 점검 (built, 2026-11-11 추가):**

1. **범위 밖 의존 점검** — `deploy/scripts/deploy_import_closure.py`가 built 패키지(`built`·`recommendation`·`map`·`ai`)의 import를 따라가 scope가 올리지 않는 backend/pipeline 파일을 찾고, 서버 파일과 줄바꿈을 무시한 sha256으로 비교한다. 다르면 **scp 전에 멈춘다** → 그 파일을 scope에 추가하거나 `-Scope all`.
2. **서버 import 점검** — scp 후 restart **전에** 서버 venv로 `import app.main`. 실패하면 restart하지 않는다(실행 중 프로세스는 이전 코드 유지). 서버 파일은 이미 바뀌었으므로 누락 파일을 올리거나 이전 커밋으로 되돌린 뒤 다시 배포한다.

**수동 equivalent:**

```powershell
$KEY = "c:\ch2\ch2_Macro\LightsailDefaultKey-ap-northeast-2.pem"
$VPS = "ubuntu@13.209.203.178"

# 예: 복합(built) — 백엔드 + 프론트 소스 (일부만 예시 — 전체 목록은 아래 표)
# 공통 지역 모듈을 빼면 서버 구버전과 섞여 addr1_scope_sql import 오류가 난다.
scp -i $KEY -r "c:\ch2\ch2_Macro\backend\app\built" "${VPS}:/opt/ch2_Macro/backend/app/"
scp -i $KEY "c:\ch2\ch2_Macro\backend\app\region_sido.py" "c:\ch2\ch2_Macro\backend\app\region_canonical.py" "c:\ch2\ch2_Macro\backend\app\region_scope.py" "${VPS}:/opt/ch2_Macro/backend/app/"
scp -i $KEY "c:\ch2\ch2_Macro\pipeline\region_canonical.py" "${VPS}:/opt/ch2_Macro/pipeline/"
scp -i $KEY -r "c:\ch2\ch2_Macro\frontend-built\src" "${VPS}:/opt/ch2_Macro/frontend-built/"

# restart 전에 서버에서 import 가능한지 확인 (실패하면 여기서 멈춘다)
ssh -i $KEY $VPS "cd /opt/ch2_Macro/backend && .venv/bin/python -c 'import app.main'"
ssh -i $KEY $VPS "bash /opt/ch2_Macro/deploy/scripts/vps_apply_scope.sh built"
```

| Scope | scp 대상 (로컬 → VPS) | VPS 빌드 |
|-------|------------------------|----------|
| `built` | `backend/app/{built,recommendation,ai,map}/`, `backend/app/{config,main}.py`, **`backend/app/{region_sido,region_canonical,region_scope}.py`**, `backend/app/collective/schemas.py`, **`pipeline/region_canonical.py`**, `shared/`, `frontend-built/{src,tsconfig.json,vite.config.ts}` (+ 필요 시 `frontend-built/package*.json`) | `frontend-built` |
| `land` | `backend/app/`(collective·built 제외 주의), `frontend/src/` | `frontend` |
| `collective` | `backend/app/collective/`, `backend/app/collective_commercial/`, `frontend-collective/src/` | `frontend-collective` (VPS에 있을 때) |
| `all` | 위 전부 + `deploy/macro-gateway/`, `deploy/hub/` | land + built + collective |

백엔드 Python 변경은 **scp 후 반드시** `systemctl restart ch2-macro-backend`.

---

## 4. 프론트 빌드 (VPS에서)

`backend/.env`의 `API_TOKEN` → 각 앱 `.env`의 `VITE_API_TOKEN`:

```bash
TOKEN=$(grep '^API_TOKEN=' /opt/ch2_Macro/backend/.env | cut -d= -f2- | tr -d '\r')
echo "VITE_API_TOKEN=$TOKEN" > /opt/ch2_Macro/frontend-built/.env
chmod 600 /opt/ch2_Macro/frontend-built/.env
cd /opt/ch2_Macro/frontend-built && npm run build
sudo systemctl restart ch2-macro-backend
```

집합·토지도 동일 패턴 (`vps_rebuild_frontends_with_token.sh` 참고).

---

## 5. 배포 후 검증 (에이전트 필수)

**지역코드(canonical resolver) 변경·mart 재빌드 포함 배포** 시 아래 **5.0 → 5.1 → 5.2** 순서를 따른다.

### 5.0 Canonical resolver 게이트 (로컬 또는 VPS DB)

```powershell
cd c:\ch2\ch2_Macro\backend
# mart가 아직 historical grain이면 --allow-historical-mart (경고만)
..\.venv\Scripts\python.exe ..\pipeline\verify_canonical_resolver_migration.py
# 기대: docs/reports/REGION_CODE_CANONICAL_VERIFY.md status PASS
#       mart historical_rows == 0 (canonical mart 재빌드 후)
```

mart 재빌드 전(프리마이그레이션)에는 `--allow-historical-mart` 허용. **운영 반영 후**에는 historical_rows=0 이어야 PASS.

**Built ledger eup NULL 보정 (promote 후 대소읍 등 scope=0):**

원장 hash는 있으나 `eupmyeondong_code` NULL인 경우 — 로컬에서 slice export → VPS update-codes:

```powershell
cd backend
..\.venv\Scripts\python.exe ..\pipeline\built\sync_ledger_slice.py export `
  --prefixes 43770340,43770256 --out ..\logs\built_slice_daeso.jsonl
scp -i LightsailDefaultKey-ap-northeast-2.pem ..\logs\built_slice_daeso.jsonl ubuntu@13.209.203.178:/opt/ch2_Macro/logs/
ssh -i LightsailDefaultKey-ap-northeast-2.pem ubuntu@13.209.203.178 `
  "cd /opt/ch2_Macro/backend && .venv/bin/python ../pipeline/built/sync_ledger_slice.py import --in ../logs/built_slice_daeso.jsonl --mode update-codes && sudo systemctl restart ch2-macro-backend"
```

### 5.0b API entry-point smoke

```powershell
cd c:\ch2\ch2_Macro\backend
# 로컬
..\.venv\Scripts\python.exe ..\pipeline\smoke_region_code_deploy.py
# 운영 (VPS 내부 또는 외부)
..\.venv\Scripts\python.exe ..\pipeline\smoke_region_code_deploy.py --base-url https://macro.ch2data.com
```

커버: health · land free/v2(`window_years=5`) · upper-stats(`window_years=5`) · collective resolve · map · region search는 무료 조건으로 기능을 확인한다. 이 무료 경로의 기존 404·503 skip은 유지한다. built lookup/resolve/scope · regional-profile · twin은 비로그인 **401**과 detail `로그인이 필요합니다.`만 통과다. 200·404·503을 포함한 다른 응답은 실패다. twin 하나가 404여도 나머지 twin 검사는 건너뛰지 않는다.  
무료 200 응답의 user-facing 코드에 historical code(`43770340` 등) **금지**.

### 5.1 백엔드

```bash
ssh -i "c:\ch2\ch2_Macro\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@13.209.203.178 \
  "systemctl is-active ch2-macro-backend && curl -sf http://127.0.0.1:8000/health | head -c 300"
```

VPS에서 region-code smoke (토큰 필요):

```bash
ssh -i "c:\ch2\ch2_Macro\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@13.209.203.178 \
  "cd /opt/ch2_Macro/backend && API_TOKEN=\$(grep '^API_TOKEN=' .env | cut -d= -f2-) \
   ../pipeline/.venv/bin/python ../pipeline/smoke_region_code_deploy.py --base-url http://127.0.0.1:8000"
```

### 5.2 복합 회귀 게이트 스모크

배포 스크립트 검증은 `POST /api/built/regression/run`을 비로그인으로 호출한다. 계산 결과 단언은 하지 않는다.

**기대:** HTTP **401**, detail `로그인이 필요합니다.` 200·403·500과 다른 detail은 실패다. nginx가 공개 URL에 `X-Api-Token`(또는 `X-CH2-Proxy-Token`)을 넣으므로 호출자가 토큰을 붙이지 않아도 API 토큰 검사는 통과한다. 비로그인을 막는 것은 구독 게이트다. VPS 안 `http://127.0.0.1:8000`은 nginx를 거치지 않으므로 스크립트가 `X-Api-Token`을 붙인다.

회귀가 실제로 가경동·흥덕구를 계산하는지는 §5.3 로그인 브라우저 확인이다.

### 5.3 브라우저

- `https://macro.ch2data.com/built/` — **Ctrl+Shift+R** (정적 JS 캐시 무시)
- nginx는 `index.html` no-cache, `assets/*` hash — 빌드 후 새 hash면 자동 갱신
- **배포 후 T(또는 관리자) 로그인 확인:** 가경동 복합 회귀를 연다. 초점 `primary`는 가경동(`eupmyeondong`)이고, 비교에는 흥덕구(`gu`)가 붙어야 한다. 이 기능 확인은 자동 스모크가 하지 않는다.

---

## 6. 장애·롤백

| 증상 | 조치 |
|------|------|
| `redeploy.sh`: `not a git repository` | 경로 B (scp + `vps_apply_scope.sh`) |
| `scp`: `Could not resolve hostname` | PowerShell `$HOST` 충돌 — 호스트 문자열 직접 사용 |
| API 여전히 구버전 | backend restart 누락 확인; scp 경로 오타 확인 |
| 프론트만 구버전 | VPS `frontend-*/dist` 재빌드; 브라우저 강력 새로고침 |
| DB 롤백 | [09-macro-built-vps.md](./09-macro-built-vps.md) §9.10, `promote_built_restore.sh` |

---

## 7. VPS를 git 기반으로 전환 (1회 작업, 선택)

```bash
ssh -i "c:\ch2\ch2_Macro\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@13.209.203.178
sudo mv /opt/ch2_Macro /opt/ch2_Macro.bak.$(date +%Y%m%d)
git clone git@github.com:takyoungj-sketch/ch2_Macro.git /opt/ch2_Macro
# backend/.env, DB는 bak에서 복사
cp /opt/ch2_Macro.bak.*/backend/.env /opt/ch2_Macro/backend/.env
bash /opt/ch2_Macro/deploy/scripts/redeploy.sh main
```

이후 배포는 **경로 A만**으로 충분.

---

## 8. 관련 문서

- [04-deploy-checklist.md](./04-deploy-checklist.md) — 최초 구축
- [09-macro-built-vps.md](./09-macro-built-vps.md) — 복합·built_stats
- [scripts/redeploy.sh](./scripts/redeploy.sh) — VPS git pull 전체 재배포
- [scripts/deploy-from-windows.ps1](./scripts/deploy-from-windows.ps1) — Windows → VPS 자동
- [scripts/vps_apply_scope.sh](./scripts/vps_apply_scope.sh) — VPS 빌드·restart
- [../AGENTS.md](../AGENTS.md) — Cursor 에이전트 요약

---

**한 줄:** 배포 요청 = commit → push → scp(또는 git pull) → VPS build → restart → macro.ch2data.com 검증.

---

## 9. 로컬 정리에서 지우면 안 되는 것 (2026-11-18)

- raw 실제 위치는 `D:\ch2\ch2_Macro\raw`(원본 폴더)다. 백업은 `G:\raw`다. 2026-11-18 대조에서 파일 4,176개, 142,118,369,568바이트가 같았고, `raw addition/` 무작위 200개와 가장 큰 파일 20개의 SHA-256이 같았다. 자세한 표는 [docs/ops/reports/20261118_cleanup_B1.md](../docs/ops/reports/20261118_cleanup_B1.md).
- `D:\ch2\ch2_Macro-collp2\raw`는 원본 raw를 가리키는 정션이다. collp2를 지우거나 옮길 때는 먼저 `cmd /c rmdir D:\ch2\ch2_Macro-collp2\raw`로 정션만 끊는다. `/s`는 금지다.
- collp2 삭제 금지. 체크아웃을 지우는 작업에 이 폴더를 넣지 않는다. raw는 이 폴더 안의 사본이 아니다.
- 2026-11-19에 `dir /AL /S /B`로 다른 worktree를 봤다. 원본 폴더를 가리키는 정션은 collp2에만 있다. 폴더를 지우기 전에 `/s` 없이 `rmdir`로 끊는다.
  - `D:\ch2\ch2_Macro-collp2\raw` → `D:\ch2\ch2_Macro\raw`
  - `D:\ch2\ch2_Macro-collp2\frontend-built\node_modules` → `D:\ch2\ch2_Macro\frontend-built\node_modules`
  - `D:\ch2\ch2_Macro-collp2\frontend-collective\node_modules` → `D:\ch2\ch2_Macro\frontend-collective\node_modules`
  - `D:\ch2\ch2_Macro-collp2\frontend-rent\node_modules` → `D:\ch2\ch2_Macro\frontend-rent\node_modules`
- 링크가 없던 worktree: `coll0`, `collp2-wip14-ro`, `deploypaths`, `landlink`, `wip1109`, Codex `workflow-rules`, Codex `p2-baseline`.

## 11. 개선 목록

- 배포 키를 `%USERPROFILE%\.ssh` 한 곳으로 모으고, 저장소 루트의 사본을 정리한다(서버 접속 테스트 필요, T 승인).
