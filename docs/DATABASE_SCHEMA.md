# CH2_MACRO 데이터베이스 스키마

> 최종 업데이트: 2026-06-24  
> 실제 DDL은 `db/*.sql` 참조. 이 문서는 설계·의도·관계 중심 설명.

---

## 1. DB 분리 구조

| DB | 역할 |
|----|------|
| `land_stats` | 토지 원장·사전집계·쌍둥이·Profile·캐시·인구 |
| `built_stats` | 복합부동산(상업·공장·단독) 원장·사전집계 |
| `collective_stats` | 집합부동산(주거·비주거) 원장·Building 통계·Market 통계 |

---

## 2. land_stats — 핵심 테이블

### 2-1. `region_codes` (행정코드 마스터)
```sql
sido_code CHAR(2), sigungu_code CHAR(5), eupmyeondong_code CHAR(8),
beopjungri_code CHAR(10) PK, beopjungri_name VARCHAR,
eupmyeondong_name, sigungu_name, sido_name,
is_active BOOLEAN
```
- **SSOT**: 토지 파이프라인이 관리. built/collective는 복사본.
- `is_active`: 현행 법정동. 폐지·분리 코드는 `region_code_history`로 추적.

### 2-2. `land_transactions` (토지 원장)
```sql
id BIGSERIAL PK,
transaction_hash CHAR(64) UNIQUE,   -- SHA-256, 순번 미포함
contract_year INT, contract_month INT, contract_date DATE,
beopjungri_code CHAR(10) FK region_codes,
sido_code, sigungu_code,
zone_type VARCHAR,                  -- 자녹·1종주거·상업 등
land_category VARCHAR,              -- 대·전·답·임야 등
road_condition VARCHAR,             -- 8미만·12미만·12이상·맹지
area_sqm NUMERIC,
total_price_10k NUMERIC,
unit_price_per_sqm NUMERIC,
lot_display VARCHAR,                -- 지번 표시 (마스킹 번지)
partial_ownership_label VARCHAR,    -- 지분
deal_type VARCHAR,                  -- 직거래·중개거래
is_cancelled BOOLEAN,
is_valid BOOLEAN,                   -- 이상치·결측 제외 여부
needs_review BOOLEAN,               -- 주소 미매핑 검토 대상
transaction_hash 컬럼 COMMENT: SHA-256(법정동·계약일·지번·면적·금액·해제 등). 순번 미포함.
```

**현황 (2026-06):** 9,602,613건 (`is_valid` 포함 약 960만)

**인덱스:** 시도·시군구·유효거래 부분 인덱스, 유료 분석 복합 인덱스 (`db/002_*.sql`).

### 2-3. `land_basic_stats_v2` (법정동/리 사전집계, V2)
```sql
PK: (as_of_month, window_years, beopjungri_code, zone_type, land_category),
period_start DATE, period_end DATE,
count INT, mean NUMERIC, std NUMERIC,
p25 NUMERIC, median NUMERIC, p75 NUMERIC,
ci_lower NUMERIC, ci_upper NUMERIC, is_reliable BOOLEAN
```
- `as_of_month`: 기준월 1일 (예: `2026-05-01`)
- `window_years`: 3 또는 5
- 현황: 3년 598,857행 + 5년 739,138행

### 2-4. `land_upper_stats_v2` (상위 행정구역 사전집계)
```sql
PK: (region_level, region_code, as_of_month, window_years, zone_type, land_category),
region_level: sido|sigungu|eupmyeondong|city
-- 나머지 통계 필드 동일
```
- 현황: 3년 349,900행 + 5년 415,910행

### 2-5. `land_annual_stats` / `land_annual_upper_stats` (장기 연도별)
```sql
(beopjungri_code, calendar_year, zone_type, land_category) →
  transaction_count, mean/median_unit_price
```

### 2-6. `analysis_cache` (응답 캐시, 24h TTL)
```sql
cache_key VARCHAR PK, result_json JSONB,
expires_at TIMESTAMP, hit_count INT
```

### 2-7. `analysis_base_cache` (row_ids 캐시, 4h TTL, lazy 생성)
```sql
cache_key VARCHAR PK,
region_codes TEXT[],
row_ids BIGINT[],       -- land_transactions.id 목록
expires_at TIMESTAMP
```
**⚠ 위험:** `transaction_hash` 변경 (rehash) 후 id가 바뀌면 stale 위험 → 갱신 후 TRUNCATE 필수.

### 2-8. `population_stats`
```sql
(admin_code, stats_year, stats_month) → total_population, ...
```

### 2-9. `twin_region_neighbor_mvp` / `twin_eupmyeondong_neighbor_mvp` (Legacy)
- 시군구·읍면동 단위 쌍둥이 MVP (Hybrid V2)
- `batch_key`, `algorithm_version`, `anchor/twin_*_code`, `similarity_score`, `detail_scores` JSONB

### 2-10. `twin_neighbor_v8` (새 알고리즘)
```sql
PK: (batch_key, region_level, anchor_region_code, rank),
region_level: sigungu|eupmyeondong|beopjungri,
anchor_region_code VARCHAR(10), anchor_region_name,
twin_region_code VARCHAR(10), twin_region_name,
similarity_score NUMERIC(6,2),  -- 0~100 Twin Score
confidence_score NUMERIC(6,2),  -- 0~100 Confidence
detail_scores JSONB,
explanation_ko TEXT
```
- 현황: 41,118행 (충청권 Phase 1, `batch_key=twin_v8_202605_...`)

### 2-11. `regional_profile` (Regional Profile)
```sql
PK: (profile_version, region_level, region_code, as_of_month, window_years),
features JSONB,            -- 피처 벡터 (토지·집합·인구·비중)
feature_count INT,
builder_version VARCHAR,
validation_status VARCHAR
```

### 2-12. `market_stats` / `market_annual_stats`
```sql
(market_domain, region_level, region_code, as_of_month, window_years) →
  p25, median, p75, count, ...
market_domain: land_residential|land_commercial|apartment_market|...
```

---

## 3. built_stats — 핵심 테이블

### `built_transactions`
```sql
transaction_hash CHAR(64) UNIQUE,
asset_type: commercial|factory|detached,
addr1~addr5 VARCHAR,     -- 시도→동(리) 5단계
beopjungri_code,
contract_date DATE,
total_price NUMERIC,
unit_price NUMERIC,
road_width_label VARCHAR, -- 도로폭 원문 저장 (D-024)
deal_type, buyer_type, seller_type
```

### `built_scope_stats`
```sql
PK: (asset_type, addr1, addr2, as_of_month, window_years),
median_price, count, ...
```

---

## 4. collective_stats — 핵심 테이블

### `collective_transactions`
```sql
transaction_hash CHAR(64),   -- UNIQUE 아님 (행 식별용만, D-017)
building_key VARCHAR,        -- 건물 단위 집계 키
asset_type: apartment|rowhouse|officetel|detached_multi,
addr1~addr4, display_name,
exclusive_area, land_area,
floor INT, dong VARCHAR,
contract_date, price, unit_price,
deal_type, buyer_type, seller_type
```

### `commercial_clusters` / `collective_commercial_transactions`
```sql
-- 비주거 집합 (상가·공장·상업업무)
cluster_key VARCHAR PK,    -- 도로명 기반 클러스터
road_name, display_label, beopjungri_code,
addr1~addr4, zone_type

-- 거래
transaction_hash CHAR(64) UNIQUE,
cluster_key FK,
price, unit_price, area, floor, road_width_label
```

---

## 5. 참조 무결성 현황

| 관계 | 방식 | 비고 |
|------|------|------|
| `land_transactions.beopjungri_code` → `region_codes` | FK (명시적) | `needs_review=true`인 행은 매핑 실패 |
| `land_basic_stats_v2.beopjungri_code` → `region_codes` | 논리적 (FK 없음) | 집계 시 자동 연결 |
| `twin_neighbor_v8.anchor_region_code` | 논리적 | DB FK 없음, 코드 수준 검증 |
| `collective_transactions.building_key` | 논리적 | MOLIT 마스킹 번지로 외부 매핑 불가 |
| `commercial_clusters` → `region_codes` | 논리적 | `beopjungri_code` 컬럼 존재 |

**개선 필요:** 사전집계 테이블들은 명시적 FK가 없어 원장 삭제 후 stale row가 남을 수 있음.

---

## 6. 주요 인덱스 전략

| 테이블 | 인덱스 | 목적 |
|--------|--------|------|
| `land_transactions` | `(beopjungri_code, is_valid, contract_year)` | 유료 분석 쿼리 |
| `land_transactions` | `(transaction_hash)` UNIQUE | dedupe |
| `land_transactions` | `(sido_code, is_valid)` 부분 | 시도별 필터 |
| `land_basic_stats_v2` | `(beopjungri_code, as_of_month, window_years)` | 무료 V2 조회 |
| `land_upper_stats_v2` | `(region_level, region_code, as_of_month)` | 상위 행정구역 |
| `twin_neighbor_v8` | `(region_level, anchor_region_code, batch_key)` | 쌍둥이 조회 |
| `analysis_cache` | `(cache_key, expires_at)` | 캐시 히트 |

---

## 7. DDL 적용 순서

```
001_init.sql              # 핵심 테이블 생성
002_indexes.sql           # 기본 인덱스
007_land_basic_stats_v2.sql
010_land_upper_stats_v2.sql
011_land_transactions_display_columns.sql  # lot_display 등
012~013_twin_*.sql        # MVP 쌍둥이
014_land_annual_stats.sql
015_built_transactions.sql
016~017_collective_*.sql
019_collective_commercial.sql
021_land_annual_upper_stats.sql
023_collective_building_stats.sql
024_market_stats.sql
025_regional_profile.sql
026~030_*.sql             # 패치
031_twin_neighbor_v8.sql  # v8 쌍둥이
```

> **신규 환경 초기화:** `db/001_init.sql` → `db/002_*.sql` → 순서대로 적용.  
> 각 파일은 `IF NOT EXISTS` / `IF NOT EXISTS CONSTRAINT` 등으로 멱등 설계.
