# 복합부동산(built) — 작업 인수·로드맵

> **작성:** 2026-06-03 · **대상:** `macro.ch2data.com` 복합부동산 MVP + VPS 통합  
> **다음 우선 작업:** (1) AI 연동 (2) **2026년 7월 초** 월간 데이터 업데이트 (`cycle_id=202607`)

---

## 1. 이번에 완료된 것

### 제품·기능

| 영역 | 내용 |
|------|------|
| **DB** | `built_stats` · `built_transactions` (상업·공장·단독) · `region_codes` (land 동기화) |
| **백엔드** | `/api/built/*` — 거래 목록, 지역 구조, 표본 필터, OLS 회귀·예측 |
| **프론트** | `frontend-built/` — `/built/` SPA (유형·지역·표본필터·회귀·예측) |
| **Macro 통합** | `/` 게이트웨이 · `/land/` 토지 · `/built/` 복합 |
| **월간 배치** | `run_built_monthly_cycle.py` + SOP ([`BUILT_MONTHLY_UPDATE_SOP.md`](BUILT_MONTHLY_UPDATE_SOP.md)) |

### VPS 배포 (Lightsail `13.209.203.178`)

- `built_stats` restore 완료 (약 416k 건, PG16 plain SQL 경로)
- Nginx: 게이트웨이 + land/built alias + `/api/` 프록시
- Basic Auth: 정적 페이지 보호 · **API는 Basic Auth 제외**
- **API 토큰 이중 경로:** 프론트 `VITE_API_TOKEN` + nginx `X-CH2-Proxy-Token` 주입 ([`vps_sync_nginx_api_token.sh`](../deploy/scripts/vps_sync_nginx_api_token.sh))
- 운영 중 해결: 반복 비밀번호 창, 시도/시군구 빈 목록(캐시·토큰)

### 로컬 실행 요약

```powershell
# DB·적재
cd c:\ch2\ch2_Macro\pipeline\built
py setup_db.py
py import_refined.py

# API
cd c:\ch2\ch2_Macro\backend
# backend/.env → BUILT_DATABASE_URL, (선택) API_TOKEN
uvicorn app.main:app --reload --port 8000

# UI
cd c:\ch2\ch2_Macro\frontend-built
npm install && npm run dev   # http://localhost:5174/built/
```

상세: [`BUILT_RESEARCH_MVP.md`](BUILT_RESEARCH_MVP.md)

---

## 2. VPS 현재 상태 (2026-06-03 기준)

| 항목 | 값 |
|------|-----|
| 코드 경로 | `/opt/ch2_Macro` (tar/scp 배포 이력 있음 → **`git pull` + `redeploy.sh` 권장**) |
| DB | `land_stats` + `built_stats` |
| 서비스 | `ch2-macro-backend` (uvicorn :8000) |
| Nginx | `/etc/nginx/sites-available/ch2-macro` |
| API 토큰 스니펫 | `/etc/nginx/snippets/ch2-api-proxy-token.conf` (배포 스크립트가 생성) |

### 재배포 (코드만)

```bash
cd /opt/ch2_Macro
git pull origin main
bash deploy/scripts/redeploy.sh main
sudo cp deploy/templates/nginx-ch2-macro.conf /etc/nginx/sites-available/ch2-macro
bash deploy/scripts/vps_sync_nginx_api_token.sh
sudo nginx -t && sudo systemctl reload nginx
```

### 검증

```bash
bash deploy/scripts/vps_check_built_regions.sh
curl -s https://macro.ch2data.com/api/built/meta/filters | python3 -c "import sys,json;d=json.load(sys.stdin);print(len(d['addr1_list']))"
# → 17
```

---

## 3. 아키텍처 (한 장)

```
macro.ch2data.com/
  /              → deploy/macro-gateway/     (유형 선택)
  /land/         → frontend/dist           (토지 SPA)
  /built/        → frontend-built/dist     (복합 SPA)
  /api/          → FastAPI :8000
                   ├─ /api/free/v2/*       (토지 V2)
                   └─ /api/built/*         (복합, built_stats)

land_stats  ←── region_codes 정본
built_stats ←── built_transactions + region_codes(land에서 sync)
```

**토지 파이프라인은 건드리지 않음.** 복합 ingest·API·UI는 land와 분리.

---

## 4. 다음 작업 A — AI 연동

> **SSOT:** [`CH2_AI_CONSTITUTION.md`](./CH2_AI_CONSTITUTION.md) · [`CH2_AI_ARCHITECTURE.md`](./CH2_AI_ARCHITECTURE.md)  
> **API:** `/api/ai/chat` · `/api/ai/explain` · `/api/ai/suggested-questions`  
> **코드:** `backend/app/ai/` · Pilot UI: `frontend-built` `AiAssistantPanel`

### Phase A (완료)

- [x] 헌법·아키텍처 문서
- [x] AiContext · Evidence · Reasoning Bundle (`bundle_id`)
- [x] 6-way Router (refusal · ch2 · explain · statistics · opinion · web)
- [x] 세션 기반 chat · 질문 추천
- [x] 복합 회귀 패널 «통계 분석 어시스턴트»

### Phase B (완료)

- [x] `AI_RATE_LIMIT_PER_MINUTE` · `/api/ai/*` rate limit
- [x] `land_explain.py` · `collective_explain.py`
- [x] land · collective `AiAssistantPanel` (`shared/ai-assistant`)
- [x] 세션 scope **comparison bundle** (최근 2 scope diff)
- [ ] ~~Web search (Phase E)~~ ✅
- [ ] `OPENAI_API_KEY` + `AI_POLISH_ENABLED` 운영 polish layer (선택)

### Phase D (완료)

- [x] `trend_narrative.py` · `prediction_narrative.py` — 추세·예측 내러티브
- [x] land 매트릭스 연도별·장기추세 탭 AI (`TrendCard`)
- [x] 복합 예측 패널 AI (`PredictionCard` / `PredictPanel`)
- [x] bundle 라우팅 (`trend_diagnostic` · `prediction_explain`)

### Phase E (완료)

- [x] `web_search.py` — Tavily · DuckDuckGo Instant
- [x] `web_answer.py` · 웹 route 실연동 (출처 URL evidence)
- [x] `AI_POLISH_ENABLED` — 템플릿 내러티브 OpenAI polish (숫자 보존 검증)
- [x] TrustBadge 웹 출처 링크 표시

### 구 API 초안 (대체)

~~`POST /api/built/regression/interpret`~~ → **`POST /api/ai/chat`** (app·panel·facts in context)

---

## 5. 다음 작업 B — 2026년 7월 초 업데이트 (`cycle_id=202607`)

### 일정 가정

| 단계 | 시기 | 비고 |
|------|------|------|
| 토지 cycle | 7월 초 | 기존 [`MONTHLY_UPDATE_SOP.md`](MONTHLY_UPDATE_SOP.md) |
| 복합 cycle | 토지 Promote **직후** | [`BUILT_MONTHLY_UPDATE_SOP.md`](BUILT_MONTHLY_UPDATE_SOP.md) |
| VPS Promote | 검증 후 | land dump → built ingest → built dump → VPS restore |

### `cycle_id=202607` 수집 연월 (현재 규칙)

`built_cycle_utils.collection_yyyymm_range_from_cycle_id("202607")`  
→ **`202508` ~ **`202606`** (직전 12개월, 토지와 동일 규칙)

> ingest는 현재 `contract_year` 중심. 월 단위 창 정밀화는 `contract_month`/`contract_date` 컬럼 적재 후.

### 실행 순서 (로컬)

```powershell
cd c:\ch2\ch2_Macro

# 1) 토지 (기존)
py scripts\monthly\run_monthly_cycle.py --cycle-id 202607
# … 검증 · Promote land_stats

# 2) 복합 — raw 배치 또는 legacy 경로
py scripts\monthly\run_built_monthly_cycle.py --cycle-id 202607 --require-land-cycle
# raw 미구축 전환기:
# py scripts\monthly\run_built_monthly_cycle.py --cycle-id 202607 --use-legacy-defaults --require-land-cycle

# 3) 스냅샷·비교
py scripts\monthly\snapshot_built_tx_counts.py --cycle-id 202607
py scripts\monthly\compare_built_count_snapshots.py --before ... --after ...

# 4) VPS dump·Promote
# deploy/scripts/dump_built_stats_local.ps1
# scp → promote_built_restore.sh 또는 vps_built_restore_sql.sh (PG 버전 주의)
```

### Promote 전 체크

- [ ] `region_codes` sync (`import_refined --refresh-region-codes` 또는 cycle 기본 ON)
- [ ] commercial / factory / detached 건수·시도별 스냅샷 diff
- [ ] 로컬 `/api/built/meta/filters` · 회귀 smoke
- [ ] VPS `backups/built_stats_pre_promote_202607.dump` 보관

### VPS Promote

[`deploy/09-macro-built-vps.md`](../deploy/09-macro-built-vps.md) §9.6 · [`promote_built_restore.sh`](../deploy/scripts/promote_built_restore.sh)

**PG18 → PG16:** custom dump 실패 시 plain SQL + `sed` 필터 (이전 장애 이력).

---

## 6. 백로그 (우선순위 낮음)

- **원장 재구축 (Phase A — 진행 예정):** [`BUILT_LEDGER_REBUILD_PLAN.md`](BUILT_LEDGER_REBUILD_PLAN.md) — MOLIT raw base 21~26, GUKTO 폐기, `road_width_label`, 주소 B (DECISIONS D-024)
- **건축물대장 연계** — [`BUILDING_REGISTER_ROADMAP.md`](BUILDING_REGISTER_ROADMAP.md) (구현 보류, 1순위 `building_register_title` 적재)
- 세 유형 **통합 회귀** (`asset_type` 더미, zone 결측 처리) — Phase B
- 집합상가/집합공장 별도 `asset_type`
- 행정코드 매칭률 개선 (`addr` 텍스트 ↔ `region_codes`)
- VPS를 git 기반 `redeploy.sh` 단일 경로로 통일 (tar 배포 이력 정리)

---

## 7. 문서·스크립트 색인

| 문서/스크립트 | 용도 |
|---------------|------|
| [`BUILT_RESEARCH_MVP.md`](BUILT_RESEARCH_MVP.md) | 로컬 개발·API 목록 |
| [`BUILDING_REGISTER_ROADMAP.md`](BUILDING_REGISTER_ROADMAP.md) | 건축물대장 표제부 — 향후 tier 매칭·구조 변수 |
| [`BUILT_MONTHLY_UPDATE_SOP.md`](BUILT_MONTHLY_UPDATE_SOP.md) | 월간 ingest·Promote |
| [`deploy/09-macro-built-vps.md`](../deploy/09-macro-built-vps.md) | VPS URL·Nginx·restore |
| `deploy/scripts/vps_rebuild_frontends_with_token.sh` | 프론트 .env + 빌드 |
| `deploy/scripts/vps_sync_nginx_api_token.sh` | nginx API 토큰 스니펫 |
| `deploy/scripts/vps_fix_built_regions_remote.sh` | 지역 선택 hotfix 일괄 |
| `deploy/scripts/vps_check_built_regions.sh` | API·지역 smoke |

---

## 8. 연락 메모

- **Basic Auth:** nginx `.htpasswd-ch2` — 정적 자산만. API는 토큰(nginx 주입 + 선택적 프론트 헤더).
- **브라우저 캐시:** `/built/` 문제 시 Ctrl+Shift+R. `index.html`은 nginx `no-cache`.
- **land 건드리지 않기:** 복합 작업은 `built_stats` / `frontend-built` / `backend/app/built/` 범위 유지.
