# 표시 컬럼 백필 → 거래 중복 INSERT 사고 (2026-06-29)

> **심각도:** CRITICAL — UI 거래목록 2배 표시, 통계 표본 2배 오염 가능  
> **상태:** dedupe + raw_id UNIQUE + UPDATE-only 백필로 재발 방지

---

## 1. 증상

- 토지 매트릭스 **거래목록** 모달에서 동일 계약이 **2행**씩 표시
- `transaction_hash` UNIQUE는 통과 (hash가 서로 다름)

## 2. 원인

| 단계 | 내용 |
|------|------|
| 1 | `lot_display`/`deal_type` 비어 있는 구간(2021~24) 존재 |
| 2 | **`clean.py --backfill-display`** 가 `clean_dataframe` → **`upsert_transactions`(UPSERT)** 실행 |
| 3 | hash의 `lot_key`에 `lot_display` 포함 → 백필 후 **hash 변경** |
| 4 | `ON CONFLICT (transaction_hash)` 미매칭 → **신규 INSERT** (동일 `raw_id`, 다른 `id`) |
| 5 | ~**207만 raw_id** × 2행 ≈ UI·API에서 중복 |

**안전한 경로:** `backfill_land_display.py` — `raw_id` 기준 **UPDATE only** (INSERT 없음)

## 3. 복구 (로컬/VPS)

```bash
cd pipeline

# 1) 현황
python dedupe_land_transactions.py --dry-run
python rebuild_land_coverage.py --gate   # raw_id_dup_groups > 0 이면 FAIL

# 2) 중복 제거 (raw_id pass → business key pass → unique index)
python dedupe_land_transactions.py --execute

# 3) 게이트 재확인
python rebuild_land_coverage.py --by-year --gate

# 4) (선택) mart 재빌드 — 표본 수 변경 반영
# build_stats_v2 / upper / annual …
```

dedupe `--execute` 는 **paid analysis cache TRUNCATE** 포함.

## 4. 재발 방지 (코드·DDL)

| 조치 | 위치 |
|------|------|
| `clean.py --backfill-display` → `backfill_land_display.run_backfill` 위임 | `pipeline/clean.py` |
| 표시 백필 SSOT | `pipeline/backfill_land_display.py` |
| dedupe raw_id 1차 pass + `uq_land_transactions_raw_id` | `pipeline/dedupe_land_transactions.py`, `db/033_*.sql` |
| Promote 게이트: `raw_id_dup_groups = 0` | `pipeline/rebuild_land_coverage.py --gate` |
| 에이전트 규칙 | `.cursor/rules/land-ledger-ingest-gates.mdc` |

## 5. 절대 금지

- 표시 컬럼만 채울 때 **`clean.py` UPSERT / `--reprocess-all`** 로 “백필” 시도
- dedupe·게이트 없이 Promote
- `backfill_land_display` 대신 hash 재계산이 동반되는 임의 스크립트

## 6. 참고

- [`TRANSACTION_HASH_DEDUPE.md`](./TRANSACTION_HASH_DEDUPE.md) — hash drift·business key dedupe
- [`DATA_INTEGRITY_CHECKLIST.md`](./DATA_INTEGRITY_CHECKLIST.md) §1
