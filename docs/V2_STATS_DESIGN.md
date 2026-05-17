# Version 2 통계 구조 설계 (초안)

> 상태: **설계 초안** — 구현·용어는 리뷰 후 확정.  
> v1(`/free`, `land_basic_stats`, `contract_year` 창)과 **병행**할 것을 전제로 한다.  
> **전국 배치·운영:** [V2_STATS_PRODUCTION.md](./V2_STATS_PRODUCTION.md) · [운영자 체크리스트](./V2_OPERATOR_CHECKLIST.md)

---

## 1. 목표

- **기준 시점(as-of)** 이 명확한 롤링 통계: “○○년 ○월 말까지 반영된 데이터로, 최근 N년 구간”.
- 필터 기준을 **`contract_year` 정수 구간**에서 **`contract_date` 날짜 구간**으로 옮긴다.
- 사용자 요청 시 **원장 전체를 다시 훑지 않도록** **사전 집계 + 조회** 구조를 유지·강화한다.
- MVP에서는 **기준월 선택 UI는 없음** — 항상 “배치가 정한 최신 `as_of_month`”만 사용.  
  스키마는 **향후 과거 `as_of_month` 조회**를 허용하도록 설계한다.

---

## 2. v1과의 차이 (요약)

| 항목 | v1 (`land_basic_stats`) | v2 (`land_basic_stats_v2`) |
|------|-------------------------|----------------------------|
| 시간 축 | `year_from` ~ `year_to` (계약연도) | `period_start` ~ `period_end` (`contract_date` 포함 구간) |
| 창 의미 “5년” | 원장 `MAX(contract_year)` 기준 최근 N개 **연도** | **직전 월 말일** `period_end` 기준 **달력 N년** 구간 (정의는 §4) |
| 배치 키 | (법정동, 용도, 지목, year_from, year_to) | (법정동, 용도, 지목, **as_of_month**, **window_years**) |
| 제품 라벨 | 연도 칩 위주 | “**YYYY년 M월 말 기준**” + 기간(N년) |

---

## 3. 기준 시점 `as_of_month`

- **의미**: 통계가 해석되는 “데이터 기준 월”.
- **운영 (권장)**: 배치가 **실행되는 달**을 **U**라 하면, 원장·통계의 반영 마감은 **U의 직전 달 말일**까지로 맞춘다.  
  - 예: **2026년 2월**에 월간 업데이트 → 마감은 **2026년 1월 31일**까지 → `as_of_month = 2026-01-01` (아래 저장 규칙).
  - 예: **2026년 1월**에 실행 → 마감은 **2025년 12월 31일**까지 → `as_of_month = 2025-12-01`.
- **저장 규칙 (초안)**: 위 마감이 속한 달을 달력 **`DATE`**로 **그 달의 1일**에 넣는다.  
  - 예: “2026년 4월 말 기준” → `as_of_month = 2026-04-01`  
  - UI 문구: `2026년 4월 말 기준` (항상 같은 달의 **말일**로 풀어 씀)
- **웹 UI “기준일” (표시 전용)**: 사용자가 “지금 몇 월 갱분인지” 직관적으로 보게 하기 위해, API 필드 **`stats_reference_date`** = **`as_of_month`의 다음 달 1일**을 내려준다.  
  - 예: `as_of_month = 2025-12-01` (12월 말까지 반영) → `stats_reference_date = 2026-01-01`.  
  - DB 키·집계 스냅샷은 여전히 `as_of_month`; 화면 강조는 `stats_reference_date`.
- **웹 API 기본 `as_of_month`**: 쿼리/body에 생략 시 — (1) 환경변수 `STATS_V2_DEFAULT_AS_OF_MONTH` 가 있으면 그 값, (2) 없으면 **요청 시점** 기준 **직전 달 1일** (`default_as_of_month_for_service`). 파이프라인 `build_stats_v2.py` 의 env 미설정 기본과 동일 규칙이다.
- **확장**: 이후 사용자/관리자가 과거 `as_of_month`를 고르면, 동일 테이블에서 `WHERE as_of_month = ?` 로 조회하면 된다.

---

## 4. 통계 창 `window_years` 및 날짜 구간

- **`window_years`**: 소수 연 단위 **정수 1~5** — “**직전 월 말일**”을 끝으로 두고, 그날부터 **달력으로 N년 전**까지 거슬러 올라간 구간(서는 **다음 날**)으로 본다.
- **제품 정책 (설계안)**  
  - **무료**: `3`, `5` 만 노출(또는 기본값 5 + 3 선택).  
  - **유료**: `1`, `2`, `3`, `4`, `5` 선택.
- **`period_end` (포함)**: `as_of_month`가 가리키는 달의 **말일** (= §3에서 말한 **직전 월 말일**과 일치하도록 배치가 `as_of_month`를 맞춘다).  
  - 예: `as_of_month = 2026-04-01` → `period_end = 2026-04-30`
- **`period_start` (포함)**:  
  - `anchor` = `period_end`와 **같은 월·일**을 유지한 채 **연도만** `window_years`만큼 뺀 날짜(윤년·말일은 해당 연·월의 유효한 일로 클램프).  
  - `period_start` = `anchor`의 **다음 날**.  
  - 예: `period_end = 2025-12-31`, `window_years = 5` → `anchor = 2020-12-31` → `period_start = 2021-01-01`  
  - 예: `period_end = 2026-01-31`, `window_years = 5` → `anchor = 2021-01-31` → `period_start = 2021-02-01`  
  - 집계 WHERE: `contract_date >= period_start AND contract_date <= period_end`  
  - `contract_date IS NULL` 행은 v2 정책에서 제외하거나 별도 규칙(필요 시 §8).

> **참고**: `period_end`가 항상 **달의 말일**이면, 위 정의는 과거에 쓰던 “`period_end`에서 12N개월 되감아 말일의 익일”과 **같은 `period_start`**가 된다. 표현만 “달력 N년”으로 맞춘 것이다.

> **주의**: 윤년·말일 클램프는 `backend/app/v2_stats_windows.py` 및 `pipeline/build_stats_v2.py` 에서 Python `date`로 일원화한다.

---

## 5. 원장 필터 (v2 사전 집계 공통)

아래는 v1 `build_stats.py`와 동일한 정신으로 맞춘다(세부는 구현 시 `LAND_CLEANING.md`와 일치).

- `is_valid = TRUE`
- `is_cancelled = FALSE`
- `unit_price_per_sqm IS NOT NULL`
- **`contract_date`가 `period_start` ~ `period_end` (포함)**  
  - v1 대체: “`contract_year` BETWEEN …” 제거

---

## 6. 차원(그레인)

v1과 동일하게 **법정동·리 × 용도지역 × 지목**을 유지한다.

- `beopjungri_code` — `region_codes`와 정규화된 10자리 등 기존 규칙 따름.
- `zone_type`, `land_category` — 실거래 원장 축약명. 합계 행은 `'ALL'`.

---

## 7. 지표(통계 필드)

v1 `land_basic_stats`와 동일한 스칼라 지표를 재사용한다(단가 분포 기준).

- `count`, `mean`, `std`, `ci_lower`, `ci_upper`, `p_min`, `p25`, `median`, `p75`, `p_max`  
- **신뢰성**: API 레이어에서 `count >= 15` 등으로 `is_reliable` 표시 가능( v1 응답과 동일한 정책).

---

## 8. 월별 배치(운영 흐름 — 요약)

설계안(7단계)과 정렬:

1. 최근 약 1년·원장 소스 반영 및 `land_transactions` 갱신  
2. 중복 제거·해제 반영 등 정제  
3. 이번 배치의 **`as_of_month`** 확정(직전 달 1일 저장 등)  
4. **`window_years ∈ {1,2,3,4,5}`** 각각에 대해 `period_start`/`period_end` 계산  
5. 지역·조합별로 단가 벡터 집계 → 위 지표 계산  
6. `land_basic_stats_v2` 에 **UPSERT** (`pipeline/build_stats_v2.py`)  
7. (선택) API용 요약 캐시 / 버전 테이블

**MVP**: 무료에 필요한 `window_years`만 먼저 넣고, 유료·동적 필터는 기존 원장 경로와 단계적 통합 가능.

---

## 9. 테이블 초안

PostgreSQL 마이그레이션(UP + 롤백 주석): **`db/007_land_basic_stats_v2.sql`**  
(`docs/sql/land_basic_stats_v2.sql` 은 위 경로 안내용.)

- **PK**: 인조키 `id` + **유니크**  
  `(as_of_month, window_years, beopjungri_code, zone_type, land_category)`
- **조회 인덱스**: 최신 as-of 단건 조회, 법정동 단위 목록 등

---

## 10. API·프론트 (후속 작업 — 이 문서 범위 밖 개요)

- 응답에 `as_of_month`, `period_start`, `period_end`, `window_years` 노출.
- 화면 상단 고정: `YYYY년 M월 말 기준`.
- 유료 기간 선택: 칩/슬라이더는 **N년**만; 실제 구간은 서버가 위 규칙으로 확정.

---

## 11. 미결정 / 리스크

- `contract_date` 가 비어 있는 행 비율·처리(제외 vs `contract_year` 보조).
- 전 수도권·전 차원 FULL 그리드 시 **저장 용량·배치 시간** — 단계적 롤아웃(지역 샘플 → 전체).
- v1 API와 URL/버전(`/v2`) 분리 여부.

---

## 12. 참고 (v1)

- ORM: `backend/app/models.py` — `LandBasicStats`
- 파이프라인: `pipeline/build_stats.py`, `pipeline/constants.py` — `DEFAULT_YEARS_BACK`
