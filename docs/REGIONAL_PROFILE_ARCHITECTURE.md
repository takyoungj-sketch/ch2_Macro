# Regional Profile · 집합부동산 · Market Stats — 통합 설계 (계획)

> **상태:** 계획 (2026-06) · **브랜치:** `feature/collective-work`  
> **목적:** CH2 Macro의 **최종 지향점인 Regional Profile DB**를 중심에 두고, 토지·집합·복합·AI가 공유할 **Statistics → Profile → 회귀/쌍둥이** 파이프라인을 정의한다.  
> **관련:** [`DECISIONS.md`](DECISIONS.md) D-016, [`REGION_ARCHITECTURE_ROADMAP.md`](REGION_ARCHITECTURE_ROADMAP.md), [`UPPER_STATS_DESIGN.md`](UPPER_STATS_DESIGN.md), [`COLLECTIVE_HANDOFF.md`](COLLECTIVE_HANDOFF.md)

---

## 1. 핵심 철학

### 1.1 기존 vs CH2 Macro

| | 기존형 분석 도구 | CH2 Macro |
|--|------------------|-----------|
| 접근 | 실거래 데이터를 직접 분석 | **지역 특성을 먼저 정량화** |
| 회귀 | 건물 변수만 | **건물 변수 + Regional Profile(지역요인)** |
| AI (장기) | — | Profile에서 **Feature Selection** |

**「지역을 설명하는 데이터」** 와 **「가격을 설명하는 데이터(거래·건물)」** 를 분리하는 것이 핵심이다.

### 1.2 Regional Profile이 최종 목적

- `upper_stats` / `market_stats` 는 **Profile을 만들기 위한 중간 산출물**이다. UI 목적이 아니다.
- Profile은 **Feature Vector** 단계이며, **개별 건물(building_key)은 절대 포함하지 않는다.**
- 현재 단계의 검증 목표는 **AI가 아니다.** Profile에서 추출한 지역요인으로 **지역 결합 회귀의 MAPE·Adj R²·유의성**이 개선되는지 확인하는 것이다.

---

## 2. 출발점 — 복합부동산 표본 부족

동 단위 상가·공장 회귀는 거래량이 적어(n≈40 전후) 회귀식이 불안정하다.

**해결:** 인접·유사 행정구역을 결합해 표본을 확대한다.

**문제:** 단순 합치면 지역마다 가격 수준이 달라 회귀가 지역차를 설명하지 못한다.

**해법 — 지역요인(Regional Factor):**  
복합부동산 데이터가 아니라 **토지 시장 통계**로 지역 가격 차를 설명한다.

예)

| 지역 | 토지 2종주거×대 (만원/㎡) |
|------|---------------------------|
| 복대동 | 267 |
| 가경동 | 94 |

회귀식:

```
금액 ~ 연면적 + 대지면적 + 연식 + … + 지역요인(Profile에서 추출)
```

지역차는 **토지·시장 Profile**이 설명하고, **건물 자체의 가격형성**은 회귀가 설명한다.

---

## 3. 5-Layer 아키텍처 (최종)

```
Layer 1  Transactions (원장)
              │
              ▼
Layer 2  Object Stats (객체 통계 — UI grain)
              │
              ▼
Layer 3  Market Stats (시장 통계 — Profile 재료)
              │
              ▼
Layer 4  Regional Profile (Feature Vector)
              │
              ▼
Layer 5  Regression · 쌍둥이도시 · AI (장기)
```

### Layer 1 — Transactions

| 제품 | 테이블 (예) | 비고 |
|------|-------------|------|
| 토지 | `land_transactions` | |
| 집합 주거 | `collective_transactions` | apartment · rowhouse · officetel |
| 집합 상업 | `collective_commercial_transactions` | collective_shop · collective_factory |
| 복합 | `built_transactions` | 단독·상가·공장 등 |

원장은 제품별 DB에 분리 유지. **행정 코드 SSOT:** `land_stats.region_codes` → sync.

---

### Layer 2 — Object Stats (객체 통계)

**토지와 집합의 UI grain이 다르다.** Object Stats는 **화면·상세 분석의 직접 대상**이다.

| 제품 | Object Stats (가칭) | Grain | UI |
|------|---------------------|-------|-----|
| 토지 | `land_matrix_stats` | 지역 × 용도지역 × 지목 | **Matrix** |
| 집합 | `building_stats` | `building_key` | **건물 목록** |
| 복합 (향후) | addr/건물 단위 stats | 주소·건물 | built UI |

#### 집합 — `building_stats`

사용자가 **1개 행정구역**을 선택하면, 그 안의 집합건물별:

- 거래수(n), 평균, 중앙값, 표준편차, 95% CI, `is_reliable`(n≥15)
- `display_name`, `asset_type`, 주소 메타

**건물 행 클릭 → 모달:** 추세선, 거래목록, 회귀분석, 층·동 효용지수.

보조 mart (선택):

- `building_annual_stats` — `building_key × year` (장기 추세·모달, 2010–2020 CSV + 2021~ 원장)

**현재 MVP:** live `GROUP BY building_key` + `compute_stats` → **mart로 이전 예정** (`feature/collective-work`).

---

### Layer 3 — Market Stats (시장 통계)

> **명칭:** `upper_stats` 가 아니라 **`market_stats`**.  
> 「상위 행정」이 목적이 아니라 **「지역 시장 전체」** 를 설명하기 때문.

**Grain:** `region_level` + `region_code` + **`market_domain`** + `window_years` + `as_of_month`

**건물이 아니라 시장** — 예: 복대동 · 아파트 · 3년 · 거래수·평균·중앙값·상승률·표준편차.

#### Market Domain (공통 스키마)

도메인별 **동일 컬럼** → Profile은 **JOIN만** 수행.

| `market_domain` | 원장/소스 | 비고 |
|-----------------|-----------|------|
| `land_residential` | 토지 matrix → 2종주거×대 등 **추출 규칙** | 회귀 지역요인 **핵심** |
| `land_commercial` | 토지 matrix → 상업지역×대 등 | |
| `land_industrial` | 토지 matrix → 공업·준공업 등 | |
| `apartment_market` | `collective_transactions` (apartment) | |
| `rowhouse_market` | collective (rowhouse) | |
| `officetel_market` | collective (officetel) | |
| `commercial_market` | built / collective_commercial | 상가 |
| `factory_market` | built / collective_commercial | 공장 |
| `detached_market` | built | 단독·다가구 |

**공통 필드 (예):** `count`, `mean`, `median`, `std`, `p25`, `p75`, `iqr`, `ci_lower`, `ci_upper`, `yoy`, `volatility` …

**물리 구현:** 단일 테이블 `market_stats(market_domain, region_level, region_code, as_of_month, window_years, …)` 권장. (레거시 `land_upper_stats_v2`는 점진 이전·alias.)

#### Building Stats vs Market Stats — 절대 혼합 금지

| | Building Stats | Market Stats |
|--|----------------|----------------|
| **목적** | 사용자 UI, 개별 건물 조회 | 지역 시장 설명, Profile 생성 |
| **Grain** | `building_key` | region × domain |
| **Profile** | ✗ | ✓ |
| **쌍둥이** | ✗ | ✓ (벡터 재료) |
| **복합 회귀 지역요인** | ✗ | ✓ |
| **집합 모달 회귀 대상** | ✓ | ✗ |

파이프라인·API·폴더명까지 분리: 예) `/buildings/*` vs `/markets/*` , `build_building_stats.py` vs `build_market_stats.py`.

---

### Layer 4 — Regional Profile

**더 이상 “통계 테이블”이 아니다.** Feature Engineering 결과.

**Grain:** `region_level` + `region_code` (+ `as_of_month`)

**예 — 복대동 Feature Vector**

| Feature | 출처 |
|---------|------|
| population, density | `population_stats` rollup |
| employment | (향후) |
| land_residential_mean | `market_stats` land_residential |
| land_commercial_mean | land_commercial |
| apartment_mean, apartment_yoy, apartment_volatility | apartment_market |
| officetel_mean | officetel_market |
| commercial_mean | commercial_market |
| factory_mean | factory_market |

**규칙**

- Profile **전체**를 회귀에 넣지 않는다. **유형별 필요 Feature만** 추출한다.
- 상가 회귀 → `commercial_market` + `land_commercial` …
- 단독 회귀 → `detached_market` + `land_residential` + `apartment_market`(보조) …

**장기 — AI Feature Selection:** Profile 안에서 유형별 최적 Feature subset 선택 (현 단계 범위 밖).

---

### Layer 5 — Regression · 쌍둥이 · AI

| 용도 | 입력 |
|------|------|
| **복합 built — 지역 결합 회귀** | built 거래 + **Profile Feature (지역요인)** |
| **집합 — 건물 모달 회귀** | **building_key(들)** 거래 + 건물 변수 (면적·층·동). Profile **미사용** |
| **쌍둥이 도시** | Profile 벡터 간 거리 ([`UPPER_STATS_DESIGN.md`](UPPER_STATS_DESIGN.md) §8 확장) |
| **AI Summary / 예측** (향후) | Profile 기반 |

---

## 4. 집합부동산 — 제품 흐름

### 4.1 사용자 여정

1. **행정구역 선택** — 토지와 동일 tier·`region_codes` / `beopjungri_code` (region 공통화)
2. **건물 목록** — `building_stats` (Layer 2)
3. **건물 클릭 → 모달**
   - 추세·연도별 (`building_annual_stats` + 원장)
   - 거래목록 (원장 live)
   - **층·동·면적 효용지수** (회귀 목적 ①)
   - **회귀 분석** (회귀 목적 ②)

### 4.2 회귀·효용지수의 목적

집합 모달 회귀의 **1차 목적**은 **층별·동별 효용지수** 산출이다.

- 기준: 코호트(또는 단지) **중앙값 = 100**
- 셀 n&lt;15 경고 (토지·집합 공통 `MIN_RELIABLE_COUNT=15`)
- 게이트 ([`analysis_gates.py`](../backend/app/collective/analysis_gates.py)): 효용지수 n≥50, 회귀 n≥30 & 최근 3년 n≥15

### 4.3 다중 아파트 통합 분석 (Analysis Cohort)

**배경:** `building_key`는 **단지명(building_name)** 이 다르면 분리된다 ([`building_keys.py`](../pipeline/collective/building_keys.py)). 대규모 단지에서 이름만 다른 아파트들이 쪼개져 n 부족 → 층·동 효용·회귀 불안정.

**기능 (계획):** 모달에서 **「분석에 아파트 추가」** — 같은 행정구역·같은 `asset_type`의 다른 `building_key`를 코호트에 포함.

```
Building Stats 행 (UI) = building_key 1개
        │
        ▼  사용자: +아파트 추가
Analysis Cohort = [bk1, bk2, bk3]   ← Layer 2 확장, Profile/Market 아님
        │
        ├─ POST .../cohort/floor-index
        └─ POST .../cohort/regression/run
```

**API (안)**

- `building_keys[]`, `contract_year_from/to`, `floor_mode`
- 표본: `WHERE building_key = ANY(:keys)`
- 게이트: **합산 n**
- 응답: `cohort_buildings[]`, `n_per_building`

**회귀 필수 — building 고정효과**

여러 단지명 통합 시 가격 **수준 차** 통제:

```
unit_price ~ exclusive_area + age + floor_dummies + dong_dummies + building_dummies
```

없으면 층·동 계수가 단지 간 레벨 차와 **혼재**된다.

**장기 (선택):** `complex_key` 또는 사용자 저장 「분석 그룹」으로 동일 블록 **추천**. Building Stats 행 수는 유지.

### 4.4 장기 추세 (2010–2020)

- 원본: [`raw/raw long term/`](../raw/raw%20long%20term/) — 토지·아파트 등 CSV
- `building_annual_stats` 또는 region×year **market** 보조 (UI는 building 연도 mart 우선)
- 토지 [`land_annual_stats`](../db/014_land_annual_stats.sql) 패턴 준용

---

## 5. Market Stats → Profile 파이프라인

```
Apartment Market ──┐
Commercial Market ─┤
Land Markets ──────┼──► JOIN (+ Population, Employment)
Factory Market ────┤         │
Detached Market ───┘         ▼
                    Regional Profile (Feature Vector)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         쌍둥이도시      built 지역결합 회귀    AI (장기)
```

**소스 경로 (둘 다 허용)**

- 집합/복합: Transactions → **Market Stats** (직접 집계)
- 토지: Transactions → **Matrix Stats** → **Market Stats** (용도×지목 → 시장 지표 **추출**)

Profile 빌더는 **소스를 몰라도** `market_stats` + `population_stats` 만 읽는다.

---

## 6. 토지와의 정렬

| 항목 | 토지 (현행·계획) | 집합 (계획) |
|------|------------------|-------------|
| Object Stats | `land_basic_stats_v2` + matrix | `building_stats` |
| Market Stats | matrix/upper → **`market_stats` land_* domain** | **`market_stats` apartment_* domain** |
| Region 선택 | `region_codes`, tier | **동일 SSOT·UI** |
| as_of · window | V2 롤링 3·5년 | **동일 정책** |
| 장기 연도 | `land_annual_stats` 2010–2026 | `building_annual_stats` + market annual |
| Promote | `land_stats_next` → `land_stats` | **`collective_stats_next`** (병렬 DB 패턴) |

토지 promote·검증과 **집합 Phase A–B는 병렬 가능**. Profile Phase C는 토지 **market_stats(land_*)** 가 안정된 뒤가 이상적.

---

## 7. 구현 우선순위

### Phase 0 — 문서·브랜치 ✅

- [`feature/collective-work`](../../) 브랜치
- 본 문서

### Phase A — 집합 기반 (region + Object Stats)

| # | 작업 |
|---|------|
| A-1 | 지역 선택 land·collective **공통화** (`region_catalog`, tier, beopjungri) |
| A-2 | `collective_stats_next` + DDL `building_stats`, `building_annual_stats` |
| A-3 | `build_collective_building_stats.py`, API mart 우선 |
| A-4 | 모달: mart 연동 (live `/buildings` 축소) |

### Phase B — Market Stats + 장기

| # | 작업 |
|---|------|
| B-1 | `market_stats` DDL (domain enum + 공통 스키마) |
| B-2 | `build_market_stats.py` — apartment/rowhouse/officetel (+ land domain 추출) |
| B-3 | `raw/raw long term` ingest → annual mart |
| B-4 | UI 장기 추세 탭 (building) |

### Phase C — Analysis Cohort (모달 다중 아파트)

| # | 작업 |
|---|------|
| C-1 | `POST /collective/analysis/cohort/floor-index` |
| C-2 | `POST /collective/analysis/cohort/regression/run` (building FE) |
| C-3 | 모달 UI 「아파트 추가」+ n breakdown |
| C-4 | (선택) complex_key / 저장 그룹 |

### Phase D — Regional Profile + 검증

| # | 작업 |
|---|------|
| D-1 | `regional_profile` 테이블 + `build_regional_profile.py` |
| D-2 | built **가경+복대** 등 지역 결합 회귀 A/B (Profile on/off) |
| D-3 | MAPE · Adj R² · 유의성 비교 리포트 |
| D-4 | 쌍둥이 MVP (Profile 벡터) |

### Phase E — (검증 성공 후)

- AI Feature Selection
- Regression Profile (지역별 회귀계수·성능 저장)
- AI Summary

---

## 8. 레거시 명칭 매핑

| 레거시 | 본 설계 |
|--------|---------|
| `land_upper_stats_v2` | `market_stats` (land_* domains) — **중간 산출물** |
| `land_basic_stats_v2` + matrix | **Object Stats** (토지) |
| collective live `/buildings` | → **`building_stats`** |
| (없음) | **`regional_profile`** |

---

## 9. CH2 Macro 전체 데이터 흐름 (요약)

```
                    Transactions
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
  Land Matrix Stats  Building Stats   (built object stats)
        │                 │
        └────────┬────────┘
                 ▼
           Market Stats  ←── domain × region × window
                 │
                 ▼
         Regional Profile  ←── Feature Vector (건물 없음)
                 │
     ┌───────────┼───────────┐
     ▼           ▼           ▼
  쌍둥이     built 회귀      AI
             (+ Profile)

  Building Stats ──► 집합 UI · 모달 · cohort 회귀/효용지수 (Profile 미경유)
```

**확장성:** 호텔·물류 등 신규 유형 → **`market_stats` domain 1개 추가** → Profile·회귀·쌍둥이 **거의 수정 없이** 재사용.

---

## 10. 연구 과제 (향후)

- 회귀용 지역요인: 토지 2종×대 단일 vs 복수 Feature
- AI Feature Selection (유형별)
- Regression Profile (지역별 계수·성능 저장)
- AI Summary (Profile 기반 자동 해설)
- Property Registry ([`REGION_ARCHITECTURE_ROADMAP.md`](REGION_ARCHITECTURE_ROADMAP.md) — Post-MVP)

---

## 11. 관련 문서

| 문서 | 내용 |
|------|------|
| [`DECISIONS.md`](DECISIONS.md) D-016 | 본 아키텍처 채택 |
| [`COLLECTIVE_HANDOFF.md`](COLLECTIVE_HANDOFF.md) | 집합 MVP·원장·게이트 |
| [`COLLECTIVE_RESEARCH_MVP.md`](COLLECTIVE_RESEARCH_MVP.md) | 로컬 실행 |
| [`UPPER_STATS_DESIGN.md`](UPPER_STATS_DESIGN.md) | 쌍둥이 피처 (→ Profile로 흡수) |
| [`LAND_LEDGER_REBUILD_PLAN.md`](LAND_LEDGER_REBUILD_PLAN.md) | 토지 원장·V2 재구축 |
| [`LONG_TERM_TREND_DESIGN.md`](LONG_TERM_TREND_DESIGN.md) | 토지 장기 연도 mart |

---

*최종 갱신: 2026-06 · 작성: CH2 Macro 설계 논의 반영*
