# 9. CH2 Macro — 복합부동산 VPS 통합 배포

> **목표:** `macro.ch2data.com` 하나에서 **유형 선택 → 토지(`/land/`) / 복합(`/built/`)** 제공.  
> **전제:** 기존 Lightsail VPS·토지 Promote 절차는 [`03-data-migration.md`](./03-data-migration.md) 유지.

---

## 9.1 URL 구조

| URL | 내용 |
|-----|------|
| `https://macro.ch2data.com/` | 유형 선택 게이트웨이 (`deploy/macro-gateway/`) |
| `https://macro.ch2data.com/land/` | 토지 SPA (`frontend/dist`, Vite `base: /land/`) |
| `https://macro.ch2data.com/built/` | 복합 SPA (`frontend-built/dist`, Vite `base: /built/`) |
| `https://macro.ch2data.com/api/*` | FastAPI (land + `/api/built/*`) |

허브 [`hub/index.html`](./hub/index.html): **CH2 Macro — 토지·복합부동산 실거래 통계**

---

## 9.2 DB

| DB | 용도 |
|----|------|
| `land_stats` | 토지 (기존) |
| `built_stats` | 복합부동산 (**신규 restore**) |

VPS PostgreSQL **같은 인스턴스**, DB만 분리.

```bash
sudo -u postgres psql -c "CREATE DATABASE built_stats OWNER ch2app;"
```

---

## 9.3 backend/.env (추가)

```env
BUILT_DATABASE_URL=postgresql+psycopg2://ch2app:***@127.0.0.1:5432/built_stats
CORS_ORIGINS=https://macro.ch2data.com
API_TOKEN=...
```

`BUILT_DATABASE_URL` 이 있으면 `/api/built/*` 활성. `/health` 에 `built_stats` 요약 포함.

---

## 9.4 프론트 빌드 (VPS)

```bash
# 토지
cp deploy/templates/frontend.env.production.example frontend/.env
# VITE_API_TOKEN = backend API_TOKEN
cd frontend && npm ci && npm run build

# 복합
cp deploy/templates/frontend-built.env.production.example frontend-built/.env
cd frontend-built && npm ci && npm run build
```

---

## 9.5 Nginx

템플릿: [`templates/nginx-ch2-macro.conf`](./templates/nginx-ch2-macro.conf)

```bash
sudo cp /opt/ch2_Macro/deploy/templates/nginx-ch2-macro.conf /etc/nginx/sites-available/ch2-macro
bash /opt/ch2_Macro/deploy/scripts/vps_sync_nginx_api_token.sh
sudo nginx -t && sudo systemctl reload nginx
```

**기존** `root frontend/dist` 단일 SPA 설정은 **교체** 필요.

### API 인증 (2026-06)

| 계층 | 역할 |
|------|------|
| Basic Auth | `/`, `/land/`, `/built/` **정적 파일** (`.htpasswd-ch2`) |
| `auth_basic off` | `/api/` — 브라우저 비밀번호 반복 방지 |
| `X-CH2-Proxy-Token` | nginx → uvicorn ( [`vps_sync_nginx_api_token.sh`](./scripts/vps_sync_nginx_api_token.sh) ) |
| `X-Api-Token` | 프론트 빌드 `VITE_API_TOKEN` (이중 보호, 캐시 대비 nginx가 필수) |

`index.html` 은 `Cache-Control: no-cache` — JS 해시 파일은 장기 캐시 가능.

---

## 9.6 로컬 → VPS: built_stats Promote

### Windows (로컬 dump)

```powershell
$env:PGPASSWORD = "로컬비밀번호"
$ts = Get-Date -Format "yyyyMMdd"
$out = "C:\ch2\ch2_Macro\backups\built_stats_$ts.dump"

& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" `
  -h localhost -U postgres -d built_stats `
  -Fc --no-owner --no-acl -f $out
```

### SCP

```powershell
scp -i $env:USERPROFILE\.ssh\LightsailDefaultKey-ap-northeast-2.pem `
  C:\ch2\ch2_Macro\backups\built_stats_20260601.dump `
  ubuntu@13.209.203.178:/var/backups/ch2/
```

### VPS restore

```bash
bash /opt/ch2_Macro/deploy/scripts/promote_built_restore.sh \
  /var/backups/ch2/built_stats_20260601.dump
```

토지 Promote와 **독립**. 월간: 토지 cycle → built cycle → 각각 dump ( [`BUILT_MONTHLY_UPDATE_SOP.md`](../docs/BUILT_MONTHLY_UPDATE_SOP.md) ).

---

## 9.7 재배포 (코드만)

```bash
/opt/ch2_Macro/deploy/scripts/redeploy.sh main
```

- backend restart
- `frontend` + `frontend-built` build
- macro gateway 확인
- nginx reload

---

## 9.8 검증 체크리스트

- [ ] `https://macro.ch2data.com/` — 토지·복합 2카드
- [ ] `https://macro.ch2data.com/land/` — 토지 UI, API 200
- [ ] `https://macro.ch2data.com/built/` — 복합 UI, 회귀 실행
- [ ] `curl -s http://127.0.0.1:8000/health` — `built_stats.total_transactions` > 0
- [ ] Basic Auth (`setup-ch2-basic-auth.sh`) macro 사이트 적용
- [ ] 허브 `ch2data.com` Macro 카드 문구

---

## 9.9 로컬 개발 URL (참고)

| 앱 | dev URL |
|----|---------|
| 게이트웨이 | `deploy/macro-gateway/index.html` 파일 열기 또는 VPS |
| 토지 | `http://localhost:5173/land/` |
| 복합 | `http://localhost:5174/built/` |
| API | `uvicorn` `:8000` |

---

## 9.10 롤백

- **코드:** `git checkout` + `redeploy.sh`
- **built DB만:** Promote 이전 `built_stats_vps_pre_promote_*.dump` restore
- **Nginx:** 이전 `ch2-macro` 설정 백업 복원

---

## 9.11 다음 작업

[`docs/BUILT_HANDOFF_AND_ROADMAP.md`](../docs/BUILT_HANDOFF_AND_ROADMAP.md) — **AI 연동**, **202607 월간 업데이트** 절차·체크리스트.
