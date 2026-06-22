# 복합부동산 연구 MVP — 로컬 실행 가이드

상업(일반상가) · 공장창고 · **단독다가구** 일반 거래를 `built_stats` DB에 적재하고, 웹에서 탐색·OLS 회귀 실험을 할 수 있습니다. **토지(land) MVP와 완전 분리**되어 있습니다.

## 데이터 현황

| asset_type | 설명 |
|------------|------|
| commercial | 상업 일반상가 |
| factory    | 공장창고 (집합 제외) |
| detached   | 단독다가구 (`유형`→`building_use`, 용도지역 없음, 용적률 미적재) |

출처: MOLIT `raw/raw base` CSV (21~26) — [`BUILT_LEDGER_REBUILD_PLAN.md`](BUILT_LEDGER_REBUILD_PLAN.md) (D-024)

```powershell
cd c:\ch2\ch2_Macro\pipeline
py rebuild_built_ledger.py              # TRUNCATE + 전국 ingest
py rebuild_built_ledger.py --smoke      # 서울 2021 smoke
py built/import_molit.py --commercial-only --truncate
```

Legacy GUKTO xlsx (`import_refined.py`) — **사용 중단**, fallback only.

## 1. DB (이미 생성됨)

```powershell
cd c:\ch2\ch2_Macro\pipeline\built
py setup_db.py          # built_stats CREATE (1회)
py import_refined.py    # xlsx → built_transactions (재실행 시 해당 유형 truncate 후 재적재)
```

환경: `pipeline/.env.built` → `BUILT_DATABASE_URL=postgresql+psycopg2://postgres:8972@localhost:5432/built_stats`

## 2. 백엔드

```powershell
cd c:\ch2\ch2_Macro\backend
pip install statsmodels pandas   # requirements.txt 반영됨
uvicorn app.main:app --reload --port 8000
```

`backend/.env`에 `BUILT_DATABASE_URL` 설정 시 `/api/built/*` 활성.

### API

- `GET /api/built/meta/filters` — 필터 메타
- `GET /api/built/transactions` — 거래 목록 (페이지)
- `GET /api/built/regions/addr2?addr1=` — 시군구
- `GET /api/built/regions/addr3?addr1=&addr2=` — 읍면동
- `POST /api/built/regression/run` — OLS (금액=DV, 3-way 행정단위 n/R² 비교)

## 3. 프론트 (연구 UI)

```powershell
cd c:\ch2\ch2_Macro\frontend-built
npm install
npm run dev
```

브라우저: **http://localhost:5174/built/** (land: **http://localhost:5173/land/**)

VPS: `https://macro.ch2data.com/` → 유형 선택 → `/land/` · `/built/` — [`deploy/09-macro-built-vps.md`](../deploy/09-macro-built-vps.md)

## 사용 팁

1. **유형**을 commercial / factory / **detached** 중 하나 선택
2. **시도 → 시군구 → 읍면동**으로 범위 좁히기 (전국 회귀는 n는 크지만 해석 어려움)
3. **읍면동** — 시군구 선택 후 체크박스로 **복수 읍면동** 선택 가능 (미선택 = 시군구 전체)
4. **회귀 실행** → 시군구 / 읍면동 / 법정리 스코프별 n, R², 유의 변수 수 비교
5. n&lt;30이면 경고 표시 — sigungu 단위가 기본 권장
6. **IQR 이상치 제외**는 극단값 민감도 실험용

## 파일 구조 (land 미접촉)

```
db/015_built_transactions.sql
pipeline/built/          # ingest
backend/app/built/       # API + regression
frontend-built/          # Vite React UI
```

## 다음 단계

- **인수·로드맵 (AI · 202607 월간):** [`docs/BUILT_HANDOFF_AND_ROADMAP.md`](BUILT_HANDOFF_AND_ROADMAP.md)
- **월간 갱신 SOP:** [`docs/BUILT_MONTHLY_UPDATE_SOP.md`](BUILT_MONTHLY_UPDATE_SOP.md) · `scripts/monthly/run_built_monthly_cycle.py`
- **VPS:** [`deploy/09-macro-built-vps.md`](../deploy/09-macro-built-vps.md) (`macro.ch2data.com/built/`)

### 백로그

- AI 회귀 해석 API + UI
- 세 유형 **통합 회귀** (`asset_type` 더미, zone 결측 처리)
- 집합상가/집합공장 별도 asset_type
- 행정코드 매칭률 개선 (현재 addr 텍스트 ↔ region_codes 이름 매칭)
