# 코드 감사 보고서 (Code Audit Report)

> 작성: 2026-06-24  
> 감사 범위: `transaction_hash` 생성 로직, PostgreSQL 적재 로직, 월간 갱신 멱등성, 통계 생성 결정론  
> **기준: 실제 구현 코드** — 문서 기술이 아닌 소스 코드 실측값  

---

## 감사 항목 1: `transaction_hash` 생성 로직

### 1-1. 사용 컬럼 — `pipeline/transaction_hash.py:9–61`

```python
# transaction_hash_key() 키 구성 필드 (실측)
region_key = beopjungri_code or sigungu_code or sigungu_name  # 우선순위 폴백
lot_key    = lot_number                                        # 1순위
           or (main_number + "|" + sub_number)                # 2순위
           or lot_display                                      # 3순위 (위험)
cancel_flag = cancel_flag_raw
            or ("1" if is_cancelled else "")                  # 이중 표현

final_key = "|".join([region_key, year, month, day,
                      lot_key, area_sqm, total_price_10k,
                      cancel_date, cancel_type, cancel_flag])
```

**포함하지 않는 것:**
- `source_row_no` (엑셀 순번) ✅ 올바름 — 주석에 명시
- `raw_id` ✅ 올바름

### 1-2. 컬럼 정규화 — `_s()` 함수 (`transaction_hash.py:96–101`)

```python
def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and str(v) == "nan":  # np.nan만 처리
        return ""
    return str(v).strip()
```

**발견된 버그 #1 — `pd.NA` 미처리:**

`isinstance(pd.NA, float)` = `False` → `str(pd.NA)` = `"<NA>"` → hash에 `"<NA>"` 포함.  
`clean.py`가 `pd.to_numeric(..., errors="coerce")`를 쓰는 컬럼에서 결측값이 `pd.NA`로 저장될 수 있다.  
**동일 거래를 재처리 시 `None` vs `pd.NA`에 따라 hash가 달라진다.**

**발견된 버그 #2 — 숫자 정밀도 미정규화:**

`area_sqm`·`total_price_10k`는 `str(v).strip()` 그대로 키에 포함.  
- Excel 파싱: `570.18` → `"570.18"`  
- DB 저장 후 PostgreSQL `NUMERIC(12,2)` 읽기: `Decimal('570.18')` → `str()` = `"570.18"` (일치)  
- 그러나 중간 float 연산 거치면 `"570.1800000000001"` 등 부동소수점 오차 가능

현재 실측에서 문제는 발생하지 않은 것으로 보이나, **`round(area_sqm, 2)` 등 명시적 정규화 없음**.

**발견된 버그 #3 — `cancel_date` 플레이스홀더 미정규화:**

`clean.py:147–158`에 `_CANCEL_FIELD_MISSING_MARKERS = {"-", "—", "*", "nan", ...}`가 정의되어 있으나,  
이것은 `_series_nonempty_meaningful()`에서 `is_cancelled` 판별용이다.  
`hash_from_series`에 넘기는 `cancel_date`, `cancel_type`은 **`_s()` (strip만)** 통과.

결과: `cancel_date="-"` 와 `cancel_date=""` 는 서로 다른 hash.

```python
# hash_from_series에서 (clean.py:88–93)
cancel_date=row.get("cancel_date"),   # "-", "—", "nan" 등 raw 값 그대로
cancel_type=row.get("cancel_type"),
cancel_flag_raw=row.get("cancel_flag_raw"),
```

### 1-3. **CRITICAL: `_rehash_batch` vs `hash_from_series` 불일치**

`dedupe_land_transactions.py:167–201`의 rehash 함수:

```python
key = transaction_hash_key(
    beopjungri_code=r.beopjungri_code,
    sigungu_code=r.sigungu_code,
    contract_year=r.contract_year,
    contract_month=r.contract_month,
    contract_day=day,
    lot_display=getattr(r, "lot_display", None),   # lot_number/main/sub 없음
    area_sqm=r.area_sqm,
    total_price_10k=r.total_price_10k,
    is_cancelled=bool(r.is_cancelled),             # cancel_date/type 없음
)
```

`hash_from_series`(clean.py가 사용)와 비교:

| 필드 | `hash_from_series` | `_rehash_batch` | 비고 |
|------|-------------------|-----------------|------|
| `lot_number` | ✅ 전달 | ❌ 전달 안 함 | lot_display 폴백만 |
| `main_number` | ✅ 전달 | ❌ 전달 안 함 | lot_display 폴백만 |
| `sub_number` | ✅ 전달 | ❌ 전달 안 함 | lot_display 폴백만 |
| `sigungu_name` | ✅ 전달 | ❌ 전달 안 함 | beopjungri 없을 때 폴백 |
| `cancel_date` | ✅ 전달 | ❌ 전달 안 함 | 해제일 → hash 제외 |
| `cancel_type` | ✅ 전달 | ❌ 전달 안 함 | 해제사유 → hash 제외 |
| `cancel_flag_raw` | ✅ 전달 | ❌ (is_cancelled만) | 표현 불일치 가능 |

**영향:**  
- 비해제 거래(대다수): `lot_number`가 DB에 저장되지 않는 경우 `lot_display`로 동일 결과 → **일치 가능성 높음**
- 해제 거래 (`is_cancelled=True`): rehash는 `cancel_flag="1"`로 기록, clean.py는 `cancel_flag_raw` 원본값 사용 → **해제 거래 hash 불일치**
- 재처리 시: rehash된 hash와 clean.py가 새로 계산하는 hash가 달라 **동일 해제 거래 2중 INSERT** 가능

### 1-4. hash 충돌 가능성

SHA-256(64자 hex). 생일 공격 기준으로 `sqrt(2^256 / P)` — 9.6M건 기준 충돌 확률 사실상 0.  
**수학적 hash 충돌은 무시 가능.** 이슈는 모두 입력 키 생성 단계.

---

## 감사 항목 2: PostgreSQL 적재 로직

### 2-1. UNIQUE 제약조건 실제 존재 확인 — `db/001_init.sql:83–84`

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uix_land_tx_hash
    ON land_transactions (transaction_hash);
```

**관찰:** `UNIQUE INDEX`로 선언 (UNIQUE CONSTRAINT 아님).  
PostgreSQL에서는 기능적으로 동일하게 작동하며 `ON CONFLICT (transaction_hash)`도 지원한다.  
단, `pg_dump`로 복원 시 스키마 정보가 index로만 보이고 constraint로 노출되지 않아 **다른 도구(ORM, ERD)에서 외래키 참조 경로 표시 불가**.

`land_basic_stats_v2`는 정식 `CONSTRAINT ... UNIQUE` (`db/007:58–64`) → 일관성 없음.

### 2-2. ON CONFLICT 구현 확인 — `clean.py:936–971`

```python
insert_sql = """
    INSERT INTO land_transactions (...)
    VALUES %s
    ON CONFLICT (transaction_hash) DO UPDATE SET
        contract_year = EXCLUDED.contract_year,
        ...
        lot_display = EXCLUDED.lot_display,     # 주목: 재적재 시 갱신됨
        ...
        raw_id = EXCLUDED.raw_id,               # 주목: raw_id도 덮어씀
        updated_at = NOW()
"""
```

**구현 확인:** ✅ 실제 `ON CONFLICT ... DO UPDATE` UPSERT 구현됨.

**발견된 문제 — `raw_id` 덮어쓰기:**  
`raw_id`는 원본 `land_transactions_raw.id`를 가리킨다.  
UPSERT 시 `raw_id = EXCLUDED.raw_id`로 새 raw 레코드의 id가 덮어씌워진다.  
이는 원본 원장 추적성을 끊는다. `lot_display` 등 표시 컬럼은 갱신이 맞지만, `raw_id`는 **최초 INSERT 값을 유지**하거나 `CASE WHEN`으로 NULL 대체 전략이 더 적합하다.

### 2-3. 배치 내 중복 제거 — `clean.py:925–932`

```python
before_hash_dedupe = len(prep)
prep = prep.drop_duplicates(subset=["transaction_hash"], keep="last")
```

**확인:** 배치 내에 동일 hash가 여러 개일 경우 마지막 행 유지.  
이는 PostgreSQL `ON CONFLICT`가 same-batch 중복에서 오류를 내기 전에 미리 처리. ✅ 올바름.

---

## 감사 항목 3: Monthly Update Pipeline 멱등성 (Idempotent ETL)

### 3-1. `collect.py` → `land_transactions_raw`

```sql
-- collect.py (실측: INSERT 직접, UPSERT 아님)
INSERT INTO land_transactions_raw (source_year, source_month, raw_data)
VALUES (...)
-- ON CONFLICT 없음
```

**⚠ 경고:** `land_transactions_raw`는 중복 허용 INSERT. 동일 월 재수집 시 동일 raw행 2배.  
단, raw 테이블은 중간 저장소이며 실제 중복은 `clean.py`의 UPSERT에서 흡수.

**영향:** `land_transactions_raw` 테이블은 재처리 후 행이 증가한다. 디스크 낭비 및 재처리 시간 증가.

### 3-2. `clean.py` → `land_transactions`

**멱등성: 조건부 YES**

같은 달 데이터를 두 번 처리:
1. 첫 번째 처리: `transaction_hash`로 INSERT
2. 두 번째 처리: `ON CONFLICT (transaction_hash) DO UPDATE`

**조건:** `transaction_hash` 함수가 동일 입력에 동일 hash를 생성해야 한다.

**위험:** 버그 #1(`pd.NA`), #2(float정밀도), #3(cancel 플레이스홀더)가 동일 row에 대해 다른 hash를 생성하면 → **동일 거래 2중 INSERT**.

실측 사례 (2026-06 발생): 구버전 hash (순번 포함) ≠ 신버전 hash → 9.6M건 dedupe 필요.

### 3-3. `build_stats_v2.py` → `land_basic_stats_v2`

**멱등성: YES** (코드 확인)

```python
# build_stats_v2.py:421
ON CONFLICT (as_of_month, window_years, beopjungri_code, zone_type, land_category)
DO UPDATE SET
    count = EXCLUDED.count,
    mean = EXCLUDED.mean,
    ...
    computed_at = NOW()
```

동일 `as_of_month`·`window_years`로 두 번 실행해도 동일 결과. ✅ 완전 멱등.

단, `computed_at = NOW()` 갱신으로 실행 시각은 달라진다 — 통계값에는 영향 없음.

### 3-4. 파이프라인 전체 멱등성 평가

| 단계 | 멱등성 | 조건 |
|------|-------|------|
| `collect.py` → raw | ❌ 중복 INSERT | raw 재처리 시 행 증가 |
| `clean.py` → transactions | 조건부 ✅ | hash 함수 안정적일 때만 |
| `dedupe_land_transactions.py` | ✅ | dry-run 확인 후 실행 |
| `build_stats_v2.py` | ✅ | ON CONFLICT DO UPDATE |
| `build_upper_stats_v2.py` | ✅ | ON CONFLICT DO UPDATE (동일 패턴) |
| Cache TRUNCATE | ✅ | 항상 비워도 무방 |

---

## 감사 항목 4: 통계 생성 결정론 및 원본 일치

### 4-1. `compute_stats()` 결정론 — `pipeline/stats.py:23–64`

```python
arr = np.asarray(prices, dtype=float)
arr = arr[~np.isnan(arr)]

mean   = float(np.mean(arr))
p25    = float(np.percentile(arr, 25))    # 기본값: linear interpolation
median = float(np.median(arr))
p75    = float(np.percentile(arr, 75))
ci     = st.t.interval(1 - ALPHA, df=n-1, loc=mean, scale=st.sem(arr))
```

**결정론: YES** — 동일 float 배열 → 동일 결과.  
`np.percentile(arr, 25)` 기본 보간 방식(`linear`)은 버전 고정 시 결정론적.

**주의:** numpy 버전 업그레이드 시 `np.percentile` 기본 `method` 변경 가능  
(numpy 1.22+ `interpolation` → `method` 파라미터 rename, 기본값 동일하나 미래 변경 가능성).

### 4-2. 원본 건수 vs 통계 건수 일치 확인

**집계 쿼리 (`build_stats_v2.py:175–188`):**
```sql
SELECT beopjungri_code, zone_type, land_category,
       unit_price_per_sqm, contract_date
FROM land_transactions
WHERE is_valid = TRUE
  AND is_cancelled = FALSE
  AND unit_price_per_sqm IS NOT NULL
  AND contract_date IS NOT NULL
  AND contract_date >= :p_start
  AND contract_date <= :p_end
```

**`build_stats_for_region_v2` 내부 pandas 필터:**
```python
# zone='ALL', cat='ALL' 조합: 필터 없이 전체
prices = sub.loc[mask, "unit_price_per_sqm"].dropna().tolist()
stats = compute_stats(prices)  # stats["count"] = len(arr after NaN 제거)
```

**검증:**
- `stats.count(ALL, ALL)` = SQL 조건에 맞는 해당 법정동 행 수  
- `stats.count(zone='자녹', cat='ALL')` = 위 조건 + `zone_type='자녹'` 행 수

이론적으로 `SUM(stats.count for all non-ALL zone and cat) != stats.count(ALL, ALL)` — **중복 집계 아님**, 각 (zone, cat) 조합은 독립.

**발견된 잠재적 불일치:**  
`build_stats_for_region_v2`는 SQL에서 받은 DataFrame을 pandas로 재필터하는데, SQL `unit_price_per_sqm IS NOT NULL` 후 pandas `dropna()`를 한 번 더 한다. 이는 중복이지만 결과에 영향 없음.

**실제 count ≠ raw count 원인:**  
`is_valid = FALSE` 행, `unit_price_per_sqm IS NULL` 행, `is_cancelled = TRUE` 행이 원장에 있지만 통계에서 제외됨 → **의도적 차이**이며 정상. UI에서 "분석 대상 건수"로 표시되는 count는 통계 건수와 일치해야 하며, 전체 원장 건수와 다를 수 있음.

### 4-3. 상위 통계와 하위 통계의 합산 일치

`build_upper_stats_v2.py`는 별도 SQL로 `land_transactions`에서 집계. 이론적으로:

```
SUM(land_basic_stats_v2.count FOR all beopjungri IN sigungu)
≒ land_upper_stats_v2.count FOR sigungu (zone=ALL, cat=ALL)
```

"≒"인 이유: 상위 집계는 `ALL×ALL` cross에서 (zone='ALL', cat='ALL')로 집계하는 반면, 하위 합산은 개별 법정동의 ALL×ALL count를 더하는 것과 같음. 동일 SQL 조건이면 일치해야 하나, **시도별 청크 처리 타이밍 차이**(원장 갱신 중 집계)가 있으면 불일치 가능.

---

## 종합 발견사항 요약

### 버그 등급

| 번호 | 위치 | 설명 | 심각도 | 즉시 조치 |
|------|------|------|--------|-----------|
| B-1 | `transaction_hash.py:97` | `pd.NA` → `"<NA>"` hash 포함 | 🔴 HIGH | `isinstance(v, type(pd.NA))` 추가 |
| B-2 | `transaction_hash.py:47–61` | `area_sqm`·`price` 부동소수점 미정규화 | 🟡 MEDIUM | `round(float(v), 2)` 적용 |
| B-3 | `transaction_hash.py:57–58` | `cancel_date` 플레이스홀더("-" 등) 미정규화 | 🟠 HIGH | `_CANCEL_FIELD_MISSING_MARKERS`와 동일 필터 적용 |
| B-4 | `dedupe_land_transactions.py:167–201` | `_rehash_batch`가 `cancel_date/type`, `lot_number`, `sigungu_name` 미전달 | 🔴 CRITICAL | rehash 입력 필드를 `hash_from_series`와 동일하게 |
| B-5 | `clean.py:968` | UPSERT에서 `raw_id` 덮어씌움 | 🟡 MEDIUM | `raw_id = COALESCE(land_transactions.raw_id, EXCLUDED.raw_id)` |
| B-6 | `collect.py` | `land_transactions_raw` 중복 INSERT | 🟢 LOW | `ON CONFLICT DO NOTHING` or 재처리 skip 로직 |

### 확인된 안전 항목

| 항목 | 상태 |
|------|------|
| `transaction_hash` UNIQUE 인덱스 존재 | ✅ `db/001_init.sql:83` |
| `ON CONFLICT (transaction_hash) DO UPDATE` 구현 | ✅ `clean.py:947` |
| `land_basic_stats_v2` UNIQUE CONSTRAINT 존재 | ✅ `db/007:58–64` |
| stats UPSERT 멱등 | ✅ `build_stats_v2.py:421` |
| Excel 순번 hash 미포함 | ✅ `transaction_hash.py:32` 주석 명시 |
| 배치 내 hash 중복 사전 제거 | ✅ `clean.py:926` |
| `compute_stats` 결정론 | ✅ numpy/scipy 순수 함수 |
| `as_of_month` 1일 검증 | ✅ `build_stats_v2.py:74,108–110` |

---

## 수정 권고

### 즉시 수정 (B-4: CRITICAL)

`pipeline/dedupe_land_transactions.py`의 `_rehash_batch`를 수정해 `hash_from_series`와 동일한 입력을 사용하도록:

```python
# 수정 전 (현재)
key = transaction_hash_key(
    beopjungri_code=r.beopjungri_code,
    sigungu_code=r.sigungu_code,
    contract_year=r.contract_year,
    contract_month=r.contract_month,
    contract_day=day,
    lot_display=getattr(r, "lot_display", None),
    area_sqm=r.area_sqm,
    total_price_10k=r.total_price_10k,
    is_cancelled=bool(r.is_cancelled),
)

# 수정 후 (권고)
# SELECT 쿼리에 lot_number, main_number, sub_number, cancel_date, cancel_type, cancel_flag_raw 추가 후
from transaction_hash import hash_from_series
new_hash = hash_from_series(dict(r._mapping))
```

또는 rehash SELECT에서 raw 원본 필드를 가져와 `hash_from_series` 직접 호출.

### 단기 수정 (B-1: HIGH)

```python
# pipeline/transaction_hash.py:96–101
def _s(v: Any) -> str:
    if v is None:
        return ""
    # pd.NA 처리 추가
    try:
        import pandas as pd
        if v is pd.NA:
            return ""
    except ImportError:
        pass
    if isinstance(v, float) and (str(v) in ("nan", "inf", "-inf") or v != v):
        return ""
    return str(v).strip()
```

### 단기 수정 (B-3: HIGH)

```python
# pipeline/transaction_hash.py에 추가
_MISSING_MARKERS = frozenset({"", "-", "—", "–", "*", "nan", "nat", "none", "<na>", "null"})

def _s_cancel(v: Any) -> str:
    """cancel 관련 필드: 플레이스홀더를 빈 문자열로 통일"""
    s = _s(v)
    return "" if s.lower() in _MISSING_MARKERS else s
```

그 후 `transaction_hash_key`에서 `_s(cancel_date)` → `_s_cancel(cancel_date)` 등 변경.
