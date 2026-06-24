# 데이터 무결성 체크리스트 (Data Integrity Checklist)

> 최종 업데이트: 2026-06-24  
> 월간 갱신 후 반드시 이 체크리스트를 순서대로 실행한다.

---

## 1. 중복 방지 전략

### 1-1. `transaction_hash` Semantic Hash

**방식:** `UPSERT ON CONFLICT (transaction_hash) DO UPDATE`

**hash 구성 (transaction_hash.py):**
```python
key = f"{beopjungri_code}|{year}|{month}|{day}|{lot_key}|{area_sqm}|{total_price_10k}|{cancel_flag}"
hash = SHA-256(key)
```

**포함하지 않는 것 (D-012 결정):**
- 엑셀 순번 (`source_row_no`)
- `raw_id`
- `lot_display` (표시 컬럼은 재적재 시 변동 가능)

**효과:** 동일 거래를 다른 엑셀에서 재다운로드해도 UPDATE(충돌)로 처리, 2중 INSERT 방지.

**한계:** `lot_display`를 hash에서 제외했으므로, 이전에 lot_display를 포함한 hash로 적재된 행과는 충돌 미발생 → **dedupe + rehash 주기 실행 필요**.

---

### 1-2. Business Key Dedupe

hash 공식 변경 이력이 있어 의미상 중복이 발생할 수 있음.

**dedupe 기준 (business key):**
```sql
PARTITION BY beopjungri_code, contract_date, area_sqm, total_price_10k,
             COALESCE(land_category, ''), COALESCE(zone_type, ''), is_cancelled
```

**tie-break (더 좋은 행 유지):**
1. `lot_display` 있는 행 우선
2. `partial_ownership_label` 있는 행 우선
3. `deal_type` 있는 행 우선
4. `id DESC` (나중에 적재된 행)

**실행:**
```powershell
python pipeline/dedupe_land_transactions.py --dry-run         # 현황 확인
python pipeline/dedupe_land_transactions.py --execute          # 삭제 실행
python pipeline/dedupe_land_transactions.py --rehash-only      # hash 재계산 (수 시간)
```

---

## 2. 월간 갱신 후 검증 체크리스트

### Level 0: 즉시 확인 (5분)

```sql
-- 중복 없음 확인
SELECT COALESCE(SUM(cnt-1),0) AS extra_rows
FROM (
  SELECT COUNT(*) cnt
  FROM land_transactions
  WHERE is_valid = TRUE
  GROUP BY beopjungri_code, contract_date, area_sqm, total_price_10k,
           COALESCE(land_category,''), COALESCE(zone_type,''), is_cancelled
  HAVING COUNT(*) > 1
) s;
-- 기대값: extra_rows = 0

-- 회귀 샘플 (청주 비하동 보녹·답)
SELECT COUNT(*) FROM land_transactions
WHERE beopjungri_code = '4311313800'
  AND zone_type = '보녹' AND land_category = '답'
  AND is_valid = TRUE;
-- 기대값: 2 (정확히 2건만 있어야 함)

-- 기준월 확인
SELECT MAX(as_of_month) FROM land_basic_stats_v2;
-- 기대값: 2026-MM-01 (갱신 대상 기준월)
```

### Level 1: 거래 건수 검증

```sql
-- 전체 유효 거래 건수
SELECT COUNT(*) FROM land_transactions WHERE is_valid = TRUE;
-- 이전 월 대비 0.5~5% 증가 기대. 급감(>10%) 시 이상.

-- 시도별 건수 이전 월 대비 비교 (이전 배치 기준 직접 비교)
SELECT btrim(sido_code) AS sido, COUNT(*) AS cnt
FROM land_transactions WHERE is_valid = TRUE
GROUP BY 1 ORDER BY 2 DESC;

-- needs_review 비율
SELECT 
  COUNT(*) FILTER (WHERE needs_review = TRUE) AS review_cnt,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE needs_review = TRUE) / COUNT(*), 2) AS pct
FROM land_transactions WHERE is_valid = TRUE;
-- 기대값: pct < 1.0
```

### Level 2: 용도×지목 매트릭스 검증

```sql
-- 사전집계 vs 원장 건수 일치 확인 (샘플: 서울 충정로3가, 5년 창)
SELECT 
  bs.count AS stats_count,
  (SELECT COUNT(*) FROM land_transactions lt
   WHERE lt.beopjungri_code = '1114013400'
     AND lt.is_valid = TRUE AND lt.is_cancelled = FALSE
     AND lt.contract_date BETWEEN '2021-06-01' AND '2026-05-31'
     AND lt.unit_price_per_sqm IS NOT NULL
  ) AS raw_count
FROM land_basic_stats_v2 bs
WHERE bs.beopjungri_code = '1114013400'
  AND bs.as_of_month = '2026-05-01'
  AND bs.window_years = 5
  AND bs.zone_type = 'ALL' AND bs.land_category = 'ALL';
-- stats_count ≒ raw_count (일치 또는 이상치 제외분만큼 차이)

-- 상위 행정구역 건수 교차 확인
SELECT 
  u.count AS upper_count,
  SUM(b.count) AS sum_basic_count
FROM land_upper_stats_v2 u
JOIN land_basic_stats_v2 b 
  ON b.beopjungri_code LIKE (LEFT(u.region_code, 5) || '%')
  AND b.as_of_month = u.as_of_month AND b.window_years = u.window_years
  AND b.zone_type = u.zone_type AND b.land_category = u.land_category
WHERE u.region_level = 'sigungu'
  AND u.region_code = '43113'   -- 청주 흥덕구
  AND u.as_of_month = '2026-05-01'
  AND u.window_years = 5
  AND u.zone_type = '자녹' AND u.land_category = '대'
GROUP BY 1;
-- upper_count ≒ sum_basic_count
```

### Level 3: 이상치 검증

```sql
-- NULL 비율 (주요 컬럼)
SELECT 
  ROUND(100.0 * COUNT(*) FILTER (WHERE unit_price_per_sqm IS NULL) / COUNT(*), 2) AS null_price_pct,
  ROUND(100.0 * COUNT(*) FILTER (WHERE area_sqm IS NULL) / COUNT(*), 2) AS null_area_pct,
  ROUND(100.0 * COUNT(*) FILTER (WHERE beopjungri_code IS NULL OR beopjungri_code = '') / COUNT(*), 2) AS null_beop_pct
FROM land_transactions WHERE is_valid = TRUE;
-- 기대값: 모두 < 1%

-- 단가 극단값 (단위: 만원/㎡)
SELECT 
  MIN(unit_price_per_sqm), MAX(unit_price_per_sqm),
  PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY unit_price_per_sqm) AS p99
FROM land_transactions
WHERE is_valid = TRUE AND unit_price_per_sqm > 0;
-- MAX가 비현실적으로 크면 이상치 미제거 의심 (10만 만원/㎡ 이상이면 검토)

-- 사전집계 통계 일관성
SELECT 
  beopjungri_code, zone_type, land_category,
  p25, median, p75
FROM land_basic_stats_v2
WHERE as_of_month = '2026-05-01' AND window_years = 5
  AND p25 > median   -- 이상: p25 > median 불가
  LIMIT 10;
-- 기대값: 0행
```

### Level 4: Statistics Integrity

```sql
-- 사전집계 mean vs 원장 mean 교차 검증 (충북 충주시 앙성면)
WITH raw AS (
  SELECT AVG(unit_price_per_sqm) AS raw_mean, COUNT(*) AS raw_count
  FROM land_transactions lt
  WHERE lt.beopjungri_code LIKE '4315082%'
    AND lt.is_valid = TRUE AND lt.is_cancelled = FALSE
    AND lt.contract_date BETWEEN '2021-06-01' AND '2026-05-31'
    AND lt.unit_price_per_sqm IS NOT NULL
    AND lt.zone_type = 'ALL'  -- ALL은 필터 없음으로 해석
)
SELECT 
  bs.mean AS stats_mean, raw.raw_mean,
  ABS(bs.mean - raw.raw_mean) AS diff,
  bs.count AS stats_count, raw.raw_count
FROM land_basic_stats_v2 bs, raw
WHERE bs.beopjungri_code LIKE '4315082%'
  AND bs.as_of_month = '2026-05-01'
  AND bs.window_years = 5
  AND bs.zone_type = 'ALL' AND bs.land_category = 'ALL';
-- diff ≒ 0 (이상치 처리 정책 차이 허용)
```

---

## 3. 자동화 검증 도구

```powershell
# 환경·DB 읽기 전용 점검
python pipeline/rehearse_v2_update.py

# L1/L2 정합성 게이트 (Promote 전 필수)
python pipeline/verify_monthly_integrity.py

# 전국 V2 샘플 검증
python pipeline/verify_v2_national_samples.py
```

---

## 4. 복합부동산·집합부동산 무결성

| 항목 | 방식 |
|------|------|
| 복합: `transaction_hash` UNIQUE | `ON CONFLICT DO NOTHING` |
| 집합 주거: 행 단위 식별 | hash = `asset_type\|파일명\|순번` (UNIQUE 아님, D-017) |
| 비주거 집합: `cluster_key` UNIQUE | `ON CONFLICT (cluster_key) DO UPDATE` |

**집합 주거 중복 위험:** hash가 UNIQUE 아니므로 재적재 시 추가 INSERT 가능. 재구축은 TRUNCATE + 전량 재적재.

---

## 5. 캐시 무결성

| 캐시 | 위험 | 대응 |
|------|------|------|
| `analysis_cache` (24h) | 갱신 전 통계 반환 | 갱신 후 TRUNCATE |
| `analysis_base_cache` (4h) | rehash 후 stale row_ids | 갱신 후 TRUNCATE (특히 rehash 시) |

```powershell
python backend/scripts/clear_analysis_cache.py --with-base-cache
```
