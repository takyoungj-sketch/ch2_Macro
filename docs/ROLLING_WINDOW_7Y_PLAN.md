# CH2 Macro — 7개년 롤링 창 추가 계획

> **작성:** 2026-08-09 · **상태:** **로컬 mart 완료** (`feature/rolling-window-7y`) — VPS promote 대기  
> **관련:** [`V2_STATS_DESIGN.md`](V2_STATS_DESIGN.md) · [`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](COLLECTIVE_LEDGER_REBUILD_PLAN.md) · [`BUILT_LEDGER_REBUILD_PLAN.md`](BUILT_LEDGER_REBUILD_PLAN.md) · [`pipeline/constants.py`](../pipeline/constants.py) · [`backend/app/v2_stats_windows.py`](../backend/app/v2_stats_windows.py)

---

## 0. 요약

| 항목 | 결정 |
|---|---|
| **목표** | 전 제품에서 롤링 통계 창을 **3·5·7년** 중 선택 가능하게 한다 |
| **기본값** | **5년** 유지 (목록·모달·회귀 표본 기본) |
| **UI 노출** | **3 \| 5 \| 7** 토글 (1·2·4·6년은 이번 범위 **아님**) |
| **모달** | 건물/클러스터 상세의 **12개월 롤백 추세·구간 요약**도 7년 창·7버킷 지원 |
| **시간 규칙** | 기존 [`V2_STATS_DESIGN.md`](V2_STATS_DESIGN.md) §4 **그대로** — `as_of_month` + 달력 N년, 상한만 **5 → 7** |
| **비범위** | Regional Profile·Twin `window_years=7` (별도 트랙, §8) · 유료 1~5년 정책 재정의 · VPS Promote |

**한 줄:** 상한을 7로 올리고 mart를 `(3,5,7)`로 재빌드한 뒤, API·토글·모달을 같은 SSOT로 맞춘다.

---

## 1. 현재 상태 (왜 7년이 안 되는가)

제품·코드 전반에 **1~5년 상한**이 박혀 있다.

| 계층 | 위치 | 현재 |
|---|---|---|
| 기간 계산 SSOT | `backend/app/v2_stats_windows.py` | `window_years` 1~5만 허용 |
| 배치 상수 | `pipeline/constants.py` `STATS_V2_WINDOW_YEARS_ALL` | `(1,2,3,4,5)` |
| DDL CHECK | `db/007`, `023`, `024`, `027`, `032`, `025`, `010` … | `window_years <= 5`, rolling `bucket_index <= 5` |
| API Query | collective/built/land/upper/profile 라우터 | `le=5` |
| 프론트 타입 | `StatsWindowYears = 3 \| 5` (land·built·collective) | 토글 2개 |
| 월간 cycle | `scripts/monthly/run_*_cycle*.py` | `--windows 3,5` 고정 |

**모달 롤링 추세**는 `collective_building_rolling_stats` 등 mart를 쓴다. grain = `(as_of_month, window_years, bucket_index, …)` 이고, **N년 창 → bucket_index 1..N** (각 12개월, [`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](COLLECTIVE_LEDGER_REBUILD_PLAN.md) §5.2).  
7년을 쓰려면 **DDL·mart·API·차트**가 모두 **bucket 7개**를 받을 수 있어야 한다. `RollingTrendChart`는 `points.length`에 따라 폭을 늘리므로 **차트 자체는 N버킷 대응 가능**.

---

## 2. 제품 정책

### 2.1 사용자-facing

- **기본 선택:** 5년 (앱 state·URL·모달 props 초기값)
- **선택지:** 3년 · **5년(기본)** · 7년
- **표시 문구:** 기존과 동일 — 「YYYY년 M월 말 기준 · 최근 N년」+ `period_start`~`period_end`
- **7년 데이터 없음:** mart miss 시 API `data_source: live` 폴백(집합 기존 패턴) + UI에 「7년 사전집계 없음, 원장 기준 계산」 배지(선택)

### 2.2 분석·회귀

- **목록 통계·모달 추세:** 3/5/7 **동일하게** mart/live
- **건물 회귀·코호트:** 기본 표본은 **5년 유지**. 7년 회귀는 **별도 옵션**(표본 n 경고 강화) — 1차 릴리스에서 회귀까지 7년을 열지 않아도 됨(§6.4)
- **장기 추세 탭:** 변경 없음 (만년력 연도 — 롤링 창과 별축)

### 2.4 원장 vs 장기추세 — 2019·2020 bridge (2026-08-10 확정)

| 구간 | 역할 | 저장 |
|------|------|------|
| **7년 롤링 창** (`as_of` 기준 ≈ **2019-08~**) | 사용자 **건별·12개월 버킷** 상세 (추세·거래목록) | **`collective_transactions`** 등 **건별 원장** |
| **2010~2018** | **장기 추세선**(연도별)만 | **`collective_building_annual_stats`** / `land_annual_stats` (long term ingest) |
| **2019·2020** | 7년 창 **첫 버킷**(19.8~20.7 등) + 거래목록 | long term CSV → **원장에 추가** (2010~2018 전량 원장화 **하지 않음**) |

- **집합 주거·비주거:** `raw/raw long term/{유형}_2010_2020/*_{2019,2020}.csv` → 기존 `import_refined` 경로로 **`collective_transactions` / `collective_commercial_transactions` upsert-style INSERT** → rolling mart 재빌드(7년).
- **복합:** Phase A SSOT는 2021~ — 7년 창 bucket 1 보강 시 동일하게 **2019·2020만** long term/base에서 원장 추가(§13).
- **토지:** 원장에 2010~ 이미 존재 — **추가 ingest 불필요**. 기본통계 모달 거래목록은 롤링 창 필터(§7)만 인지.

### 2.3 유료 1~5년과의 관계

기존 문서의 「유료 1~5년」과 충돌하지 않게:

- **무료/공통 UI:** 3 · 5(기본) · 7
- **1·2·4·6년:** 이번 작업 **미노출**. DDL 상한만 7로 올려 두면 추후 유료 세분화 여지는 남음

---

## 3. 영향 범위 (도메인별)

| 도메인 | mart / API | 모달 롤링 | 1차 포함 |
|---|---|---|---|
| **토지** V2 | `land_basic_stats_v2`, upper | 매트릭스 모달·FreeStats | ✅ |
| **집합 주거** | `collective_building_stats`, `collective_building_rolling_stats` | `BuildingDetailModal` 추세 | ✅ |
| **집합 비주거** | `collective_commercial_cluster_*` rolling | `CommercialClusterDetailModal` | ✅ (parity) |
| **복합 built** | `built_scope_stats` | (목록 위주, 모달 롤링 적음) | ✅ 목록 |
| **Regional Profile** | `regional_profile` window=3 SSOT | profile 앱 | ⏸ 2차 (§8) |
| **단지 속성 P3~** | quality index `window_years=5` 고정 | — | ⏸ 별도 |

---

## 4. 기술 설계

### 4.1 SSOT — 기간 계산 (변경 최소)

[`backend/app/v2_stats_windows.py`](../backend/app/v2_stats_windows.py) 한 곳에서 상한 변경:

```python
MAX_WINDOW_YEARS = 7  # 신규 상수

def period_bounds_for_window(as_of_month, window_years):
    if not (1 <= window_years <= MAX_WINDOW_YEARS):
        raise ValueError(...)
    # anchor / period_start / period_end 로직은 변경 없음
```

- `pipeline/build_stats_v2.py` 등 **복제된 검증**은 SSOT import로 통일(가능한 곳만)
- `iter_rolling_year_buckets_old_first(period_end, bucket_count=window_years)` — **bucket_count = window_years** (기존 규칙 유지)

### 4.2 배치 상수

[`pipeline/constants.py`](../pipeline/constants.py):

```python
STATS_V2_WINDOW_YEARS_UI = (3, 5, 7)          # UI·월간 cycle 기본
STATS_V2_WINDOW_YEARS_ALL = (1, 2, 3, 4, 5, 6, 7)  # DDL 상한; 배치는 UI 집합만 계산해도 됨
```

**권고:** 운영 mart는 **`3,5,7`만** 매월 빌드(저장·시간 절약). 1·2·4·6은 요청 시에만.

### 4.3 DDL 마이그레이션 (신규 `db/053_window_years_max_7.sql`)

CHECK만 완화 — **컬럼 추가 없음**.

| 테이블 | 변경 |
|---|---|
| `land_basic_stats_v2` | `window_years <= 7` |
| `land_upper_stats_v2` | 동일 |
| `collective_building_stats` | 동일 |
| `collective_building_rolling_stats` | `window_years <= 7`, **`bucket_index <= 7`** |
| `collective_commercial_cluster_stats` / `_rolling` | 동일 |
| `market_stats` | 동일 |
| `regional_profile` | 동일 (2차 빌드 전에도 스키마만 선반영 가능) |
| `built_scope_stats` | CHECK 없음 — 코드 검증만 |

적용: 로컬 `--apply-ddl` → mart `--windows 3,5,7 --replace` (또는 해당 as_of만 upsert).

### 4.4 파이프라인·월간 cycle

**공통:** 모든 `build_*`의 `--windows` 기본값 **`3,5,7`**, 검증 **`1..7`**.

| 스크립트 | 비고 |
|---|---|
| `pipeline/build_stats_v2.py` | 토지 V2 |
| `pipeline/build_upper_stats_v2.py` | 상위 통계 |
| `pipeline/build_collective_building_stats.py` | 목록 mart |
| `pipeline/build_collective_building_rolling_stats.py` | **모달 추세 — 7버킷** |
| `pipeline/build_collective_commercial_cluster_stats.py` | 비주거 parity |
| `pipeline/build_collective_commercial_cluster_rolling_stats.py` | 비주거 모달 |
| `pipeline/build_collective_market_stats.py` | profile 입력 |
| `pipeline/built/build_scope_stats.py` | 복합 |
| `scripts/monthly/run_land_cycle_csv.py` 등 | `--windows 3,5,7` |

**재빌드 순서 (로컬 검증):**

1. DDL 053 적용  
2. 토지 `build_stats_v2` + upper  
3. 집합 building_stats + rolling (+ commercial 동시)  
4. built scope (해당 시)  
5. smoke: 대표 법정동·building_key 3/5/7 각 200 OK

### 4.5 API

**패턴:** `Query(5, ge=1, le=7)` — 기본값 **5 유지**.

대상 (grep `le=5` 기준 일괄):

- `backend/app/routers/free_v2.py` (또는 land v2 라우터)
- `backend/app/routers/upper_stats.py`
- `backend/app/collective/router.py` — `/buildings`, `/stats/rolling`, 회귀 관련
- `backend/app/collective_commercial/router.py`
- `backend/app/built/router.py` (scope stats)
- `backend/app/regional_profile/router.py` — **2차까지 `le=5` 유지 가능** (profile 미빌드 시)

**응답:** 기존처럼 `window_years`, `period_start`, `period_end`, `as_of_month` 필수. rolling 응답 `points[]` 길이 = `window_years`.

### 4.6 프론트엔드

#### 공통 SSOT (권고)

지금 `StatsWindowToggle`이 **3벌 복제**(land / built / collective). 이번에 **한 번만** 맞춘다:

```typescript
export type StatsWindowYears = 3 | 5 | 7;

export function normalizeStatsWindowYears(v: unknown): StatsWindowYears {
  if (v === 3) return 3;
  if (v === 7) return 7;
  return 5; // default
}
```

| 앱 | 파일 | 변경 |
|---|---|---|
| 토지 | `frontend/src/types.ts`, `FreeStatsWindowToggle.tsx` | 3·5·7, default 5 |
| 복합 | `frontend-built/.../StatsWindowToggle.tsx`, `App.tsx` | 동일 |
| 집합 주거 | `frontend-collective/.../StatsWindowToggle.tsx`, `App.tsx` | 동일 |
| 집합 비주거 | `CommercialApp.tsx`, `CommercialClusterDetailModal` | 동일 (parity) |

#### 모달

- `BuildingDetailModal` / `CommercialClusterDetailModal`: 상위 `windowYears` prop 그대로 rolling API에 전달 — **토글 변경 시 모달 추세·구간표 동기 갱신**
- `RollingTrendChart`: 7포인트 시 가로 스크롤 또는 `min-width` 증가 확인 (현재 동적 폭 — **QA만**)
- 구간별 수치 테이블: 7행 렌더 (기존 map 그대로)

#### localStorage / store

- 토지 `freeStatsWindowYears` persist: `7` 저장 시 normalize 통과하도록

### 4.7 회귀 (선택 — 1차 또는 1.1)

| 옵션 | 내용 |
|---|---|
| **A (권고 1차)** | 회귀 API는 **5년 고정** 유지, UI 회귀 탭에 「표본은 5년 롤링」 고정 문구 |
| **B (1.1)** | 회귀에도 window 선택 추가 — n≥30 게이트·경고를 7년에서 더 강하게 |

---

## 5. 단계별 구현 (권장 순서)

| Phase | 내용 | 산출 | 공수(초안) |
|---|---|---|---|
| **W0** | 본 문서 승인 + `MAX_WINDOW_YEARS=7` SSOT | `v2_stats_windows.py`, constants | 0.5일 |
| **W1** | DDL 053 + 파이프라인 `--windows 3,5,7` | db 마이그레이션, build_* | 1~2일 |
| **W2** | API `le=7` + 단위/스모크 테스트 | router 일괄, `test_collective_rolling_stats` 7년 케이스 | 1일 |
| **W3** | 프론트 토글 3·5·7 (4앱) + 모달 연동 QA | StatsWindowToggle, modals | 1~2일 |
| **W4** | 월간 cycle·operator 문서 갱신 | `V2_STATS_PRODUCTION.md`, `MONTHLY_UPDATE_SOP.md`, checklist | 0.5일 |
| **W5** | (선택) VPS mart 재빌드·Promote | deploy runbook | 운영 일정 따름 |

**총:** 로컬 end-to-end **약 4~6일** (회귀 7년·Profile 7년 제외).

---

## 6. 검증 기준 (완료 판정)

### 6.1 기간 계산

- `as_of_month=2026-06-01`, `window_years=7` → `period_end=2026-06-30`, `period_start` = 2019-07-01 (윤·말일 클램프 포함, [`V2_STEP3_VERIFICATION_REPORT.md`](V2_STEP3_VERIFICATION_REPORT.md) 패턴)

### 6.2 mart

- `collective_building_rolling_stats` where `window_years=7` → **bucket_index 1..7** 각 1행 이상(거래 있는 단지)
- tier A 단지 1곳: 3/5/7 **mean 순서·건수**가 직관적(7년 ≥ 5년 ≥ 3년 count)

### 6.3 API

- `GET .../stats/rolling?window_years=7` → 200, `points.length === 7`
- `window_years=8` → 422

### 6.4 UI

- 목록 토글 7년 → 테이블 수치 변경
- 모달 열린 채 토글 7년 → 추세 차트·구간표 **7구간**
- 새로고침 후 **기본 5년**

### 6.5 회귀 non-regression

- 기존 3/5년 API·회귀 응답 스키마 **byte-level 동일**(기본 파라미터)

---

## 7. 리스크·완화

| 리스크 | 완화 |
|---|---|
| mart 행 수 ~40% 증가 (5→7) | UI mart `(3,5,7)`만 빌드; rolling은 building grain이라 증가율 제한적 |
| 집합 원장 2021~만 — 7년 bucket 1 공백 | **§2.4 bridge:** long term **2019·2020** → `collective_*_transactions` 추가 후 rolling mart 재빌드 (2010~2018 annual은 장기 탭 전용) |
| 토지·복합 모달 거래목록이 롤링 창만 | DB에는 2019~ 있음(토지 전구간·복합 legacy). **의도된 분석 scope** — 7년 상세는 창 안, 그 이전은 장기추세 |
| Profile/Twin은 window=3 | profile API는 당분간 3만; 7년 창과 **혼동 문구** 금지 |
| DDL CHECK 변경 중 mart 불일치 | DDL → full rebuild `--replace` 한 번에 |
| 토글 3벌 drift | W3에서 타입·normalize **동일 문자열** 복붙 또는 shared 패키지(범위 최소면 복붙 허용) |

---

## 8. 2차 백로그 (이번 계획 비범위)

1. **Regional Profile `window_years=7`** — feature 재계산·Twin 재학습·[`REGIONAL_PROFILE_POST_MVP_BACKLOG.md`](REGIONAL_PROFILE_POST_MVP_BACKLOG.md) 영향
2. **단지 품질지수(P3)** — 현재 설계 5년 고정; 7년 sensitivity는 별도
3. **유료 1·2·4·6년** — 정책 재정의 후 API gate만 추가
4. **shared `StatsWindowToggle`** — `frontend-shared` 또는 macro-shell 승격

---

## 9. 문서 갱신 목록 (구현 시)

- [`V2_STATS_DESIGN.md`](V2_STATS_DESIGN.md) §4 — 1~**7**
- [`V2_STATS_PRODUCTION.md`](V2_STATS_PRODUCTION.md) — `--windows 3,5,7`
- [`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](COLLECTIVE_LEDGER_REBUILD_PLAN.md) §5.2 — bucket 1..**7**
- [`BUILT_LEDGER_REBUILD_PLAN.md`](BUILT_LEDGER_REBUILD_PLAN.md) §2.4 — 3·5·**7**
- [`UPPER_STATS_DESIGN.md`](UPPER_STATS_DESIGN.md) CHECK·U-6
- [`DECISIONS.md`](DECISIONS.md) — **D-0xx** 한 줄 결정 추가(승인 시)

---

## 10. 승인 시 첫 커밋 범위 (제안)

1. `docs/ROLLING_WINDOW_7Y_PLAN.md` (본 문서)  
2. `db/053_window_years_max_7.sql`  
3. `v2_stats_windows.py` + `constants.py`  
4. 파이프라인 `--windows` + cycle 스크립트  
5. API `le=7`  
6. 프론트 3·5·7 토글 + 모달 QA  

**브랜치:** `experiment/collective-danji-attributes`와 분리 — **`feature/rolling-window-7y`** 권장 (통계 인프라 vs 단지 속성 실험).

---

## 13. 후속 — 2019·2020 bridge ingest (집합·복합)

**목표:** 7년 창·거래목록에서 **19.8~20.7** 등 첫 버킷이 비지 않게 한다. 2010~2018 건별 원장은 **만들지 않는다**.

| Step | 작업 |
|------|------|
| 1 | long term 폴더에서 `*_매매_2019.csv`, `*_매매_2020.csv`만 paths-file로 `import_refined` (주거 4유형 + 집합상가·공장) |
| 2 | `building_key` = base ingest와 동일 `attach_building_identity` (기존 파이프라인 재사용) |
| 3 | ingest 후 `build_collective_building_rolling_stats --windows 3,5,7` (+ commercial rolling) |
| 4 | 스모크: 극동늘푸른 등 bucket 1 count>0, 거래목록 2019·2020 행 표시 |
| 5 | (복합) `built_transactions`에 2019·2020 gap 있으면 동일 패턴 — `pipeline/ingest_built_bridge_years.py` |

**비범위:** 2010~2018 → `collective_transactions` / `built_transactions` 전량 backfill.

---

## 12. 구현 진행 (2026-08-09, `feature/rolling-window-7y`)

| 항목 | 상태 |
|---|---|
| W0 SSOT (`MAX_WINDOW_YEARS=7`, constants) | ✅ |
| W1 DDL 053 (조건부 ALTER, land·collective 각 적용) | ✅ 로컬 |
| W1 파이프라인·월간 cycle `--windows 3,5,7` | ✅ |
| W1 소스 DDL 007·010·023·024·025·027·032 `<=7` | ✅ |
| W2 API `le=7` (Profile `le=5` 유지) | ✅ |
| W2 단위 테스트 (`test_v2_stats_windows`, `test_collective_rolling_stats`) | ✅ 5 passed |
| W3 프론트 토글 3·5·7 (land·built·collective) | ✅ `tsc` 통과 |
| W4 `V2_STATS_DESIGN`·`V2_STATS_PRODUCTION` 갱신 | ✅ |
| 로컬 mart 스모크 (서울 addr1, 법정동 1114017100) | ✅ 7년 rolling 154,856행 |
| 전국 mart 재빌드 (로컬, `as_of=2026-07-01`) | ✅ 11/11 · 3.77h · `logs/rebuild_mart_7y_20260809_200935.log` |
| **§13 2019·2020 bridge ingest** (집합·복합 원장) | ✅ 로컬 2026-08-10 · `pipeline/ingest_collective_bridge_years.py` · ~195만 주거 + 11.5만 commercial |
| rolling mart 재빌드 (bridge 후) | ✅ 주거 ~150만행 · commercial ~12.8만행 (`as_of=2026-07-01`, 3·5·7) |
| **복합 built bridge** (`ingest_built_bridge_years.py`) | ✅ 2026-08-10 · commercial 43,920 + factory 16,178 + **detached 181,297** (32 CSV, `단독다가구_2010_2020`) · scope_stats 재빌드 |
| UI·API E2E (API 서버 기동 후) | ⏸ |

---

**`window_years` 상한을 7로 올리고 mart를 (3,5,7)로 재빌드한 뒤, 토글·모달·rolling API를 같은 SSOT로 맞추면 된다. 기본값 5년·장기 추세 탭·Profile 3년은 그대로 둔다.**
