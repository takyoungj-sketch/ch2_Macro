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
# -Scope: built | land | collective | all
# -SkipPush  # 이미 push 된 경우
```

**수동 equivalent:**

```powershell
$KEY = "c:\ch2\ch2_Macro\LightsailDefaultKey-ap-northeast-2.pem"
$VPS = "ubuntu@13.209.203.178"

# 예: 복합(built) — 백엔드 + 프론트 소스
scp -i $KEY -r "c:\ch2\ch2_Macro\backend\app\built" "${VPS}:/opt/ch2_Macro/backend/app/"
scp -i $KEY -r "c:\ch2\ch2_Macro\frontend-built\src" "${VPS}:/opt/ch2_Macro/frontend-built/"

ssh -i $KEY $VPS "bash /opt/ch2_Macro/deploy/scripts/vps_apply_scope.sh built"
```

| Scope | scp 대상 (로컬 → VPS) | VPS 빌드 |
|-------|------------------------|----------|
| `built` | `backend/app/built/`, `frontend-built/src/` (+ 필요 시 `frontend-built/package*.json`) | `frontend-built` |
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

### 5.1 백엔드

```bash
ssh -i "c:\ch2\ch2_Macro\LightsailDefaultKey-ap-northeast-2.pem" ubuntu@13.209.203.178 \
  "systemctl is-active ch2-macro-backend && curl -sf http://127.0.0.1:8000/health | head -c 300"
```

### 5.2 복합 회귀 (구·동 2-way 스모크)

로컬 Python:

```python
import json, urllib.request, ssl
body = {
    "asset_type": "commercial",
    "addr1": "충청북도", "addr2": "청주시",
    "addr4_list": ["가경동"], "leaf_level": "addr4",
    "variables": {
        "gross_area": True, "land_area": True, "building_age": True,
        "road_code": True, "zone_type_dummy": True, "building_use_dummy": True,
    },
    "exclude_outliers_iqr": False,
}
req = urllib.request.Request(
    "https://macro.ch2data.com/api/built/regression/run",
    data=json.dumps(body).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, context=ssl.create_default_context(), timeout=30) as r:
    d = json.load(r)
assert d["primary"]["admin_level"] == "gu"
assert "흥덕" in d["primary"]["scope_label"] or d["primary"]["scope_label"] == "흥덕구"
```

**기대:** `primary.admin_level == "gu"`, scope **흥덕구** (시군구·청주시 아님).

### 5.3 브라우저

- `https://macro.ch2data.com/built/` — **Ctrl+Shift+R** (정적 JS 캐시 무시)
- nginx는 `index.html` no-cache, `assets/*` hash — 빌드 후 새 hash면 자동 갱신

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
