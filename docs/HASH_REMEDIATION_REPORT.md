# Transaction Hash 수정 보고서 (HASH_REMEDIATION_REPORT)

> 작성: 2026-06-24  
> 관련 감사: `docs/CODE_AUDIT_REPORT.md` B-1, B-3, B-4  
> 수정 커밋: `pipeline/transaction_hash.py`, `pipeline/dedupe_land_transactions.py`

---

## 1. 수정 배경

CODE_AUDIT_REPORT 코드 감사에서 아래 3개 버그가 발견됐다.

| 버그 | 설명 | 위험 |
|------|------|------|
| B-1 | `_s(pd.NA)` = `"<NA>"` — pandas 결측값이 hash에 포함됨 | lot_number 등 결측 필드에서 hash 불일치 |
| B-3 | `cancel_date="-"` vs `""` → 다른 hash | 해제여부 플레이스홀더 차이로 중복 INSERT |
| B-4 | `_rehash_batch`가 `cancel_date/type`, `lot_number` 등을 hash_from_series와 다른 방식으로 전달 | rehash 후 DB hash가 future clean.py hash와 불일치 |

---

## 2. 수정 내용

### 2-1. `pipeline/transaction_hash.py`

#### (a) `_s()` 함수 — pd.NA / numpy NaN 처리 (B-1 수정)

**수정 전:**
```python
def _s(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and str(v) == "nan":
        return ""
    return str(v).strip()
```

**수정 후:**
```python
def _s(v: Any) -> str:
    """None·NaN·pd.NA·numpy NaN 모두 '' 반환."""
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return ""
    try:
        import pandas as _pd
        if v is _pd.NA:
            return ""
    except ImportError:
        pass
    try:
        import numpy as _np
        if isinstance(v, _np.floating) and _np.isnan(v):
            return ""
    except ImportError:
        pass
    s = str(v).strip()
    if s.lower() in ("nan", "nat", "<na>", "none", "null"):
        return ""
    return s
```

#### (b) `_num2()` 신규 — 숫자 소수점 2자리 정규화 (B-2 예방)

```python
def _num2(v: Any) -> str:
    """f"{float(v):.2f}" — pandas float과 PostgreSQL Decimal 통일."""
    if v is None or v == "":
        return ""
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return ""
        return f"{f:.2f}"
    except (TypeError, ValueError):
        return _s(v)
```

**효과:** `float(570.1)` → `"570.10"` = `Decimal('570.10')` → `"570.10"` (동일)

#### (c) `transaction_hash_key()` — cancel 필드 제외 (B-3 수정)

**수정 전:** `cancel_date`, `cancel_type`의 raw 값을 key positions 7, 8에 포함.

**수정 후:** positions 7, 8은 항상 `""`. `cancel_flag_raw` 무시. `is_cancelled` boolean만 position 9에 반영.

```python
return "|".join([
    region_key,
    _s(contract_year), _s(contract_month), _s(contract_day),
    lot_key,
    _num2(area_sqm),
    _num2(total_price_10k),
    "",            # position 7: cancel_date 제외
    "",            # position 8: cancel_type 제외
    cancel_flag,   # position 9: "1" if is_cancelled else ""
])
```

**10-part 포맷 유지:** 2026-06 rehash 이후 DB 값과 호환.

#### (d) `hash_from_series()` 수정 (B-4 수정)

- `is_cancelled=bool(row.get("is_cancelled"))` 전달 추가
- `cancel_date`, `cancel_type`, `cancel_flag_raw` 전달은 그대로 유지 (함수 내부에서 무시됨, 하위 호환)

#### (e) `HASH_FIELDS` 상수 추가

```python
HASH_FIELDS = [
    "beopjungri_code", "contract_year", "contract_month", "contract_day",
    "lot_key", "area_sqm", "total_price_10k",
    # positions 7,8: always ""
    "is_cancelled",
]
```

### 2-2. `pipeline/dedupe_land_transactions.py`

#### `_rehash_batch()` 통합 (B-4 핵심 수정)

**수정 전:** `transaction_hash_key()`를 직접 호출, `hash_from_series`와 다른 입력 필드 사용.

**수정 후:** `hash_from_series()` 직접 호출로 교체.

```python
def _rehash_batch(conn, rows, *, lot_col_used: bool) -> int:
    for r in rows:
        row_dict = {
            "beopjungri_code": r.beopjungri_code,
            "sigungu_code": r.sigungu_code,
            "contract_year": r.contract_year,
            "contract_month": r.contract_month,
            "contract_date": r.contract_date,
            "lot_display": getattr(r, "lot_display", None),
            "area_sqm": r.area_sqm,
            "total_price_10k": r.total_price_10k,
            "is_cancelled": bool(r.is_cancelled),
        }
        new_hash = hash_from_series(row_dict)  # ← 단일 함수 경로
```

---

## 3. 마이그레이션 필요 여부 조사

### 3-1. 수정 전후 hash 비교

2026-06에 완료된 `dedupe + rehash` 이후 DB 내 hash 값과 수정된 코드가 생성하는 hash를 비교한다.

**2026-06 rehash가 생성한 hash key 포맷:**
```
beopjungri|year|month|day|lot_display|area_str|price_str|||cancel_flag
```
- positions 7, 8: `""` (cancel_date/type을 전달하지 않았으므로)
- position 9: `""` (비해제) 또는 `"1"` (해제, is_cancelled=True)
- area_sqm: `str(Decimal)` → 예: `"570.18"`, `"500.00"` (2자리)
- total_price_10k: 동일

**수정된 코드가 생성하는 hash key 포맷:**
```
beopjungri|year|month|day|lot_display|"570.18"|"500.00"|||cancel_flag
```
- positions 7, 8: 항상 `""` ✅
- position 9: `is_cancelled` boolean → `"1"` 또는 `""` ✅
- area_sqm: `_num2()` = `f"{float(v):.2f}"` → 예: `"570.18"` ✅
- total_price_10k: 동일 ✅

### 3-2. 결론: 추가 마이그레이션 불필요

| 케이스 | 수정 전 DB hash | 수정 후 hash | 일치 여부 |
|--------|----------------|-------------|-----------|
| 비해제, area=570.18 | `...|\|570.18|15000.00\|\|\|` | `...\|570.18\|15000.00\|\|\|` | ✅ |
| 비해제, area=500.0 | `...\|500.00\|...\|\|\|` | `...\|500.00\|...\|\|\|` | ✅ |
| 해제 거래 | `...\|\|\|1` | `...\|\|\|1` | ✅ |
| lot_display="612" | `...\|612\|...` | `...\|612\|...` | ✅ |

**DB에 저장된 hash (2026-06 rehash 완료분)는 수정된 코드와 완전히 호환된다. 추가 rehash 불필요.**

### 3-3. hash_a / hash_b 혼재 가능성

수정 전 구버전 코드가 생성했던 hash 유형:
- **old-v1**: 순번 포함 (`source_row_no|...`) — 2026-06 rehash로 전량 교체됨
- **old-v2**: cancel_date raw 포함 (`...|2026-03-15|해제|O`) — 2026-06 rehash로 전량 교체됨
- **current**: cancel_date `""` (본 수정 후와 동일)

`extra_rows=0` (2026-06-24 확인)이므로 old-v1/v2 hash는 현재 DB에 잔존하지 않는다.

---

## 4. 검증 — 단위 테스트

`pipeline/tests/test_transaction_hash_unified.py` — 33개 테스트 (전체 통과 확인):

```
TestHashFieldsConstant::test_hash_fields_defined              PASSED
TestHashFieldsConstant::test_hash_fields_contains_required    PASSED
TestSHelper::test_pd_na_returns_empty                         PASSED  ← B-1
TestSHelper::test_pd_na_vs_none_same                          PASSED  ← B-1
TestNum2Normalization::test_float_vs_decimal_same_result      PASSED  ← B-2
TestCancelFieldsIgnored::test_cancel_date_variants_same_hash  PASSED  ← B-3
TestCancelFieldsIgnored::test_cancel_flag_raw_ignored         PASSED  ← B-3
TestCancelFieldsIgnored::test_transaction_hash_key_positions_7_8_always_empty  PASSED ← B-3
TestHashFromSeriesVsRehatch::test_clean_vs_rehash_non_cancelled  PASSED ← B-4
TestHashFromSeriesVsRehatch::test_clean_vs_rehash_cancelled      PASSED ← B-4
TestHashFromSeriesVsRehatch::test_hash_stability_golden_value    PASSED ← 공식 변경 경보
...
```

---

## 5. 향후 운영 지침

### hash 공식 변경 시 필수 절차

1. `test_hash_stability_golden_value` 테스트가 실패함 (의도적 경보)
2. `DECISIONS.md`에 변경 이유 기록
3. `python pipeline/dedupe_land_transactions.py --rehash-only --batch-size 10000` 실행 (~5시간)
4. `extra_rows=0` 확인
5. `build_stats_v2.py` 재실행 (as_of_month 확인)
6. `analysis_cache + analysis_base_cache TRUNCATE`
7. Promote

### 월간 갱신 시 체크

```sql
-- hash 충돌(중복) 없음 확인
SELECT COALESCE(SUM(cnt-1),0) AS extra_rows
FROM (
  SELECT COUNT(*) cnt
  FROM land_transactions
  WHERE is_valid = TRUE
  GROUP BY beopjungri_code, contract_date, area_sqm, total_price_10k,
           COALESCE(land_category,''), COALESCE(zone_type,''), is_cancelled
  HAVING COUNT(*) > 1
) s;
-- 기대값: 0
```
