# 토지 원장 조회 성능 규칙 (Land Ledger Query Perf)

> **사고일:** 2026-08-13  
> **증상:** 기본통계·매트릭스 셀 모달이 수 초~수십 초 (UI “멈춘 것 같음”)  
> **완화 후:** 단건 stats ~70–100ms · `POST /api/paid/matrix-yearly` 롤링 ~15–30ms  
> **코드 SSOT:** `backend/app/ledger_region_sql.py`  
> **에이전트 규칙:** `.cursor/rules/land-ledger-query-perf.mdc`

---

## 1. 한 줄 규칙

토지 원장(`land_transactions` / `land_transactions_resolved`)의 **선택적 법정동 핫패스**에서는:

1. **`beopjungri_code = ANY(:list)` 쓰지 말 것** → 단건 `=` / 복수 expanding `IN`
2. **같은 기간을 버킷·모드마다 다시 훑지 말 것** → 1회 fetch + 메모리(또는 `FILTER`) 집계
3. **`/health` 전수 `COUNT(*)` / 무거운 `DISTINCT` 금지** → `pg_class.reltuples` 등 추정

---

## 2. 사고 요약

| 경로 | 원인 | 체감 | 수정 |
|------|------|------|------|
| `GET /api/free/v2/stats/{code}` | (1) window·calendar **이중** `GROUP BY` (2) `ANY(:codes)` → Parallel Seq Scan | ~20s | `_fetch_yearly_tx_dual_maps`: 1회 + `FILTER` · `beopjungri_eq_or_in` |
| `POST /api/paid/matrix-yearly` (롤링) | 버킷마다 원장 재조회 × `ANY` | ~45s | 기간 1회 SELECT → 메모리 버킷팅 · `_build_conditions` 가 `eq_or_in` |
| `GET /health` | 전수 COUNT/DISTINCT | 수 초 | `reltuples` + `MAX(year)` |

PostgreSQL은 바인드 `ANY(:array)` 에서 선택도가 낮아 보여 **Index Scan 대신 Parallel Seq Scan**을 자주 고른다. 단건 `=` 은 인덱스(~ms).

---

## 3. 필수 패턴 (코드)

```python
from app.ledger_region_sql import beopjungri_eq_or_in, execute_expanding

pred, params = beopjungri_eq_or_in(codes, column="lt.beopjungri_code")
# 단건 → "lt.beopjungri_code = :region_code"
# 복수 → "lt.beopjungri_code IN :region_codes" + params["_expand_region_codes"]=True
rows = execute_expanding(db, f"SELECT ... WHERE {pred} ...", params).fetchall()
```

**롤링 모달 (`matrix-yearly`):**

```text
금지: for bucket in buckets: db.execute(... date BETWEEN bucket ...)
허용: 전체 period 1회 SELECT (date, px) → for bucket: filter in memory
```

**연도 이중 표 (free v2):**

```text
금지: GROUP BY year 두 번 (window / calendar 각각)
허용: 한 번 GROUP BY + COUNT/SUM(...) FILTER (WHERE contract_date <= :period_end)
```

---

## 4. ANY 가 허용되는 경우

| 허용 | 이유 |
|------|------|
| 작은 마트·카탈로그 (`land_basic_stats_v2` 존재 여부 등) | 행 수가 원장 대비 미미, PK/복합 인덱스 |
| 비지역 필터 (`road_condition = ANY(:…)` 등 소수의 enum) | 카디널리티 낮음 |
| 배치/파이프라인 전량 스캔 | 애초에 Seq Scan 전제 |

원장 핫패스에 “편의상 ANY”를 다시 넣지 말 것. 의심되면 `EXPLAIN (ANALYZE, BUFFERS)` 로 Index vs Parallel Seq 확인.

---

## 5. 회귀 방지

| 수단 | 위치 |
|------|------|
| 공유 헬퍼 | `backend/app/ledger_region_sql.py` |
| 단위 테스트 | `backend/tests/test_ledger_region_sql.py` · `test_paid_region_pred.py` |
| Cursor 규칙 | `.cursor/rules/land-ledger-query-perf.mdc` |
| Risk | `RISK_REGISTER.md` **R-014** |

테스트가 깨지면(=단건이 `ANY`/`IN`만 쓰거나 롤링이 버킷 루프 execute) **머지 금지**.

---

## 6. 관련 파일

- `backend/app/routers/free_v2.py` — `_fetch_yearly_tx_dual_maps`
- `backend/app/routers/paid.py` — `_build_conditions`, `matrix_yearly` rolling
- `backend/app/main.py` — `/health` approx counts
