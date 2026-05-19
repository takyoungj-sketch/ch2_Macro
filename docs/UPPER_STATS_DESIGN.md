# 상위 행정구역 사전집계 및 쌍둥이 지역 기능 설계

> 상태: **설계 초안** — 구현 전 리뷰 및 확정 필요.
> 관련 결정: [`docs/DECISIONS.md`](./DECISIONS.md) D-009 · D-010 · D-011
> 선행 조건: §2의 DB 재구축 이슈 해소 후 구현 진행.

---

## 1. 배경 및 목표

### 1-1. 현황 문제

| 문제 | 내용 |
|------|------|
| 사전집계 범위 부족 | `land_basic_stats_v2`는 **법정동/리 단위만** 사전집계. 흥덕구 등 상위 단계 조회 시 매번 원장(`land_transactions`) 전체를 실시간 집계 → 서버 부하. |
| DB 재구축 필요 | 법정동/리 이름에 **한자가 병기된 경우** (`예: 가경동(佳景洞)`) `beopjungri_code` 매핑 오류 발생. 기존 `land_basic_stats_v2` 전체 재구축 필요. |
| 무료 복수지역 | 현재 무료 bulk API가 복수 지역 합산을 허용하고 있어 의미론적 경계가 불명확. |

### 1-2. 목표

1. **모든 단일 행정구역 레벨**에 사전집계 DB 구축 (법정동/리 → 읍면동 → 시군구 → 시도).
2. **실시간 집계**는 유료 복수지역 쿼리(읍면동/동/리, 최대 10개)에만 한정.
3. **무료는 단건만** — 단일 법정동/리 단건 조회로 제한.
4. **쌍둥이 지역 찾기** — 사전집계 벡터 기반으로 유사 시군구·읍면동을 검색 (유료).

---

## 2. 선행 조건: 법정동 한자 병기 코드 오류 해소

### 이슈 내용

국토부 원장에 동리 이름이 `가경동(佳景洞)` 형태로 기재된 경우, `clean.py`의 주소 매핑이
`region_codes.beopjungri_name`과 불일치 → 해당 거래가 `beopjungri_code = NULL` 또는
오매핑된 채로 `land_transactions`에 적재됨.

### 해소 절차 (별도 이슈로 추적)

```
1. clean.py: 주소 파싱 시 괄호+한자 제거 전처리 규칙 추가
2. land_transactions 재정제 (--reprocess-all)
3. land_basic_stats_v2 전체 재구축 (build_stats_v2.py)
4. land_upper_stats_v2 구축 (build_upper_stats_v2.py) ← 본 문서 대상
```

> **이 이슈가 해소되기 전에는 `land_upper_stats_v2` 구축을 시작하지 않는다.**
> (원장이 오염된 상태에서 상위 집계를 만들면 같이 오염됨.)

---

## 3. 행정구역 레벨 정의

```
시도 (sido)           2자리  예: 43
 └ 시군구 (sigungu)   5자리  예: 43113
    └ 읍면동 (eupmyeondong) 8자리  예: 43113105
       └ 법정동/리 (beopjungri) 10자리  예: 4311310500
```

`region_codes` 테이블이 이 4계층을 모두 보유하고 있으므로,
JOIN만으로 임의 레벨의 집계 그룹을 만들 수 있다.

---

## 4. 사전집계 접근 정책

| 레벨 | 무료 | 유료 |
|------|------|------|
| 법정동/리 (beopjungri) | **단건 조회** (`land_basic_stats_v2`) | 복수 최대 10개 (실시간) |
| 읍면동 (eupmyeondong) | 불가 | **단건** (`land_upper_stats_v2`) |
| 시군구 (sigungu) | 불가 | **단건** (`land_upper_stats_v2`) |
| 시도 (sido) | 불가 | **단건** (`land_upper_stats_v2`) |

- **복수지역 실시간 집계**: 읍면동/동/리 레벨만 허용, 최대 10개.
- 시군구·시도는 복수지역 선택 자체를 API·프론트에서 차단.
- 사전집계가 구축되면 상위 단계 단건 조회 비용은 사실상 0.

---

## 5. 신규 테이블: `land_upper_stats_v2`

마이그레이션 파일: `db/010_land_upper_stats_v2.sql`

```sql
CREATE TABLE IF NOT EXISTS land_upper_stats_v2 (
    id             BIGSERIAL PRIMARY KEY,

    -- 지역 계층
    region_level   VARCHAR(12)  NOT NULL,
    -- 허용값: 'sido' | 'sigungu' | 'eupmyeondong'
    region_code    VARCHAR(10)  NOT NULL,

    -- V2와 동일한 시간 축
    as_of_month    DATE         NOT NULL,
    window_years   SMALLINT     NOT NULL CHECK (window_years BETWEEN 1 AND 5),
    period_start   DATE         NOT NULL,
    period_end     DATE         NOT NULL,

    zone_type      VARCHAR(20)  NOT NULL DEFAULT 'ALL',
    land_category  VARCHAR(10)  NOT NULL DEFAULT 'ALL',

    -- 통계 (land_basic_stats_v2와 동일 스키마)
    count          INTEGER      NOT NULL DEFAULT 0,
    mean           NUMERIC(14,2),
    std            NUMERIC(14,2),
    ci_lower       NUMERIC(14,2),
    ci_upper       NUMERIC(14,2),
    p_min          NUMERIC(14,2),
    p25            NUMERIC(14,2),
    median         NUMERIC(14,2),
    p75            NUMERIC(14,2),
    p_max          NUMERIC(14,2),

    computed_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    batch_id       TEXT,

    CONSTRAINT land_upper_stats_v2_grain_uq UNIQUE (
        region_level, region_code,
        as_of_month, window_years,
        zone_type, land_category
    )
);
```

### 5-1. 집계 행 수 추정

| 레벨 | 단위 수 | zone×cat 조합(≈9) | window(5) | 합계 |
|------|---------|-----------------|-----------|------|
| 시도 | ~17 | ×9 | ×5 | ~765 |
| 시군구 | ~250 | ×9 | ×5 | ~11,250 |
| 읍면동 | ~3,500 | ×9 | ×5 | ~157,500 |
| *(참고) 법정동/리* | *~36,000* | *×9* | *×5* | *~1.6M* |

→ 상위 3레벨 합계 약 170,000행. 스토리지 및 배치 부담 경미.

### 5-2. 집계 원칙

- **반드시 `land_transactions` 원장에서 직접 집계**한다.
- `land_basic_stats_v2`의 mean/count를 단순 합산·가중평균하는 방식 **금지**
  (하위 동리의 평균 → 상위 구 평균으로 직접 변환 불가 — 표준편차·백분위는 더욱 불가).
- 집계 WHERE 조건은 `land_basic_stats_v2` 와 동일
  (`is_valid=TRUE, is_cancelled=FALSE, unit_price_per_sqm IS NOT NULL, contract_date BETWEEN period_start AND period_end`).

---

## 6. 파이프라인 변경

### 신규 스크립트: `pipeline/build_upper_stats_v2.py`

`build_stats_v2.py`와 구조를 공유하되, GROUP BY 대상만 다르다.

```
land_transactions
  JOIN region_codes ON beopjungri_code
  GROUP BY {sido_code | sigungu_code | eupmyeondong_code}
         × zone_type × land_category
         × (as_of_month, window_years, period_start, period_end)
  → compute_stats()
  → UPSERT land_upper_stats_v2
```

`--level` 인수로 `sido`, `sigungu`, `eupmyeondong` 중 선택 또는 전체 실행:

```bash
# 전체 상위 레벨 재구축
python build_upper_stats_v2.py --as-of 2025-12-01 --windows 1,2,3,4,5

# 특정 시도만
python build_upper_stats_v2.py --as-of 2025-12-01 --windows 3,5 --sido-code 43
```

### `run_pipeline.py` 연동

기존 `build_stats_v2.py` 완료 직후 실행:

```
build_stats_v2.py (법정동/리)
  ↓
build_upper_stats_v2.py (읍면동 → 시군구 → 시도)
  ↓
_truncate_paid_caches()   ← 기존 그대로
```

---

## 7. API 변경

### 7-1. 신규 유료 엔드포인트

```
GET /api/paid/upper-stats/{region_level}/{region_code}
    ?as_of_month=2026-01-01
    &window_years=3
    &zone_type=ALL
    &land_category=ALL
```

- `region_level`: `eupmyeondong` | `sigungu` | `sido`
- 사전집계 미적재 시: **HTTP 404** (실시간 폴백 없음 — 재구축 필요 메시지 포함)
- 응답 구조: `land_basic_stats_v2` 단건 응답과 동일 스키마 (`StatsResult`)

### 7-2. 복수지역 제한 강화

기존 `/api/paid/analyze` 및 `/api/free/v2/stats/bulk`에 레벨 검증 추가:

| 요청 레벨 | 허용 여부 | 최대 코드 수 |
|-----------|-----------|-------------|
| beopjungri (10자리) | 무료·유료 모두 허용 | 무료: **1개**, 유료: **10개** |
| eupmyeondong (8자리) | 유료만 허용 | **1개** (사전집계 조회) |
| sigungu (5자리) | 유료만 허용 | **1개** (사전집계 조회) |
| sido (2자리) | 유료만 허용 | **1개** (사전집계 조회) |

> beopjungri 복수지역(유료 최대 10개)은 단독 읍면동/동/리를 초월하는
> 사용자 정의 구역 분석용으로만 유지. 상위 레벨은 단건 사전집계로 충분.

---

## 8. 쌍둥이 지역 찾기 기능

### 8-1. 개요

유사한 토지 시장 특성을 가진 행정구역을 찾아주는 유료 기능.
`land_upper_stats_v2`에 사전집계된 통계 벡터와 인구 데이터를 결합해
**통계적 거리**가 가장 가까운 지역 상위 N개를 반환한다.

- **대상 레벨**: 시군구(`sigungu`), 읍면동(`eupmyeondong`)
- **시도 레벨 쌍둥이**: 향후 고려 (현재 ~17개로 의미 있는 비교 샘플 부족)
- **접근**: 유료 전용

### 8-2. 유사도 피처 벡터

#### 가격 그룹 (Price)
| 피처 | 출처 | 비고 |
|------|------|------|
| `price_mean` | `land_upper_stats_v2` zone=ALL, cat=ALL, `mean` | 가격 수준 |
| `price_median` | `median` | 이상치 저항 중위값 |
| `price_p25`, `price_p75` | `p25`, `p75` | 가격 분포 폭 |
| `price_std` | `std` | 가격 변동성 |

#### 시장 활성도 그룹 (Volume)
| 피처 | 출처 | 비고 |
|------|------|------|
| `log_count` | `count` (log1p 변환) | 거래량 규모 |

#### 인구 그룹 (Population)
| 피처 | 출처 | 비고 |
|------|------|------|
| `log_population` | `population_stats` SUM(total_population) (log1p) | 규모 |
| `pop_density` | `population_stats` `density_per_km2` | 도시/농촌 성격 |

> **인구 데이터 현황 제약**: 현재 `population_stats`는 `beopjungri` 레벨만 적재됨.
> 시군구·읍면동 레벨 쌍둥이를 위해 `region_codes JOIN population_stats`로
> 상위 레벨 집계(SUM/AVG)를 추가해야 함. 단기: 집계 뷰 활용, 장기: 레벨별 시드 추가.

#### 토지 구성 그룹 (Composition)
| 피처 | 출처 | 비고 |
|------|------|------|
| `ratio_residential_zone` | zone='주거지역' count / ALL count | 주거 비중 |
| `ratio_commercial_zone` | zone='상업지역' count / ALL count | 상업 비중 |
| `ratio_agri_zone` | zone 농림·녹지 count / ALL count | 농림/자연 비중 |
| `ratio_land_danji` | cat='대' count / ALL count | 대지 비중 |
| `ratio_land_rice` | cat '전'+'답' count / ALL count | 농경지 비중 |
| `ratio_land_forest` | cat='임야' count / ALL count | 임야 비중 |

### 8-3. 알고리즘

```
1. 같은 region_level의 전체 지역에서 피처 벡터 조회
   (land_upper_stats_v2 + population_stats 집계)

2. 피처별 z-score 정규화 (전국 평균·표준편차 기준)

3. 가중 유클리드 거리 계산:
   distance(A, B) = sqrt( Σ w_i × (z_A_i - z_B_i)² )

4. 가중치 모드 (weight_mode):
   - "uniform"     : 모든 피처 w=1 (기본)
   - "price"       : 가격 그룹 w=3, 나머지 w=1
   - "population"  : 인구 그룹 w=3, 나머지 w=1
   - "composition" : 구성 그룹 w=3, 나머지 w=1

5. 거리 오름차순 정렬 → top_n 반환 (자기 자신 제외)

6. 유사도 점수: similarity = 1 / (1 + distance)  →  [0, 1]
```

### 8-4. API

```
POST /api/paid/twin-regions
{
  "region_level":  "sigungu",
  "region_code":   "43113",
  "as_of_month":   "2026-01-01",
  "window_years":  3,
  "top_n":         10,
  "weight_mode":   "uniform"
}
```

응답:

```json
{
  "query_region": {
    "region_level": "sigungu",
    "region_code": "43113",
    "region_name": "청주시 흥덕구"
  },
  "as_of_month": "2026-01-01",
  "window_years": 3,
  "weight_mode": "uniform",
  "results": [
    {
      "rank": 1,
      "region_code": "44130",
      "region_name": "천안시 서북구",
      "similarity": 0.923,
      "distance": 0.077,
      "feature_snapshot": {
        "price_mean": 42.5,
        "log_count": 5.2,
        "log_population": 12.1
      }
    }
  ]
}
```

### 8-5. 구현 단계

```
Phase 1 (기반 데이터)
  ① 한자 병기 코드 오류 해소 → land_transactions 재정제
  ② build_upper_stats_v2.py 구현 및 전국 구축

Phase 2 (인구 데이터 보강)
  ③ population_stats 시군구·읍면동 레벨 집계 뷰 또는 시드 추가
     → region_codes JOIN population_stats 집계 방식으로 시작
  
Phase 3 (API)
  ④ GET /api/paid/upper-stats/{level}/{code}
  ⑤ POST /api/paid/twin-regions

Phase 4 (프론트)
  ⑥ 상위 행정구역 단건 분석 패널 (유료 탭)
  ⑦ 쌍둥이 지역 카드 UI
     - 기준 지역의 주요 지표 vs 유사 지역 비교 테이블
     - 지역명 클릭 → 해당 지역 분석 화면 이동
```

---

## 9. 미결 사항

| ID | 항목 | 비고 |
|----|------|------|
| U-1 | 한자 병기 beopjungri_code 매핑 오류 해소 구체 일정 | §2 참고 |
| U-2 | 유료 복수지역 10개 상한 프론트 UI 반영 | 기존 `_MAX_STATS_REGIONS` 상수 조정 |
| U-3 | 인구 데이터 시군구·읍면동 레벨 적재 방식 확정 (집계 뷰 vs CSV 시드) | Phase 2 |
| U-4 | 쌍둥이 기능 가중치 모드 UI (슬라이더 vs 프리셋 버튼) | Phase 4 |
| U-5 | 시도 레벨 사전집계 포함 여부 (지금은 포함하되 쌍둥이 기능은 제외) | 추후 조정 |
| U-6 | window_years 무료 3·5 / 유료 1~5 정책을 상위 레벨에도 동일 적용할지 | 현재 동일로 설계 |

---

## 관련 문서

- 기존 V2 설계: [`docs/V2_STATS_DESIGN.md`](./V2_STATS_DESIGN.md)
- 결정 기록: [`docs/DECISIONS.md`](./DECISIONS.md)
- 운영 SOP: [`docs/V2_OPERATOR_CHECKLIST.md`](./V2_OPERATOR_CHECKLIST.md)
- 다음 작업: [`NEXT_STEPS.md`](../NEXT_STEPS.md)
