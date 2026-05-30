# land_transactions 중복 제거 (2026-06 월간 갱신)

> **상태:** 코드·스크립트 준비 완료 (2026-05-30). **DB 실행은 6월 초 월간 갱신·Promote 전** 로컬에서 1회.

## 배경

- `transaction_hash`에 Excel **순번(`source_row_no`)** / `raw_id` 가 포함되어, 파이프라인 재적재 시 **동일 거래가 다른 hash** 로 INSERT 됨.
- 예: 청주 비하동 보녹·답 — 엑셀 2건, DB/UI **4건** (2025-05·07 각 2중).
- 전국 **초과 중복 행** 약 35만 건 수준 (business key 기준).

## 코드 변경 (이미 반영)

| 파일 | 내용 |
|------|------|
| `pipeline/transaction_hash.py` | hash 공식 단일화 (순번 제외) |
| `pipeline/clean.py` | `hash_from_series` 사용 |
| `pipeline/dedupe_land_transactions.py` | 중복 DELETE + 선택 `--rehash` |
| `pipeline/tests/test_transaction_hash.py` | 회귀 테스트 |

## 6월 초 실행 순서 (로컬)

| # | 작업 | 명령 |
|---|------|------|
| 0 | **백업** | `pg_dump -Fc ... land_stats_pre_dedupe.dump` |
| 1 | (선택) 6월 원장 수집·`run_monthly_cycle` **전** dedupe | 아래 §1 |
| 2 | **중복 제거 + rehash** | `python dedupe_land_transactions.py --execute --rehash` |
| 3 | **집계 재생성** | `build_stats_v2`, `build_upper_stats_v2`, twin MVP 등 |
| 4 | **검증** | 비하동 보녹·답 **2건**, `rehearse_v2_update.py` |
| 5 | **Promote** | `pg_dump` → dev VPS `pg_restore` ([`deploy/03-data-migration.md`](../deploy/03-data-migration.md)) |

§1 순서는 **「6월 신규 데이터 반영 전 dedupe」** vs **「6월 cycle 후 dedupe」** 중 하나로 고정.  
권장: **B3 `run_pipeline` 직후·V2 배치 전** dedupe (신규 거래도 새 hash 로 UPSERT).

### §1 명령

```powershell
cd pipeline
python dedupe_land_transactions.py --dry-run
python dedupe_land_transactions.py --execute --rehash
```

기대:

- `biha_borok_dap_valid=2`
- `extra_rows` → 0 (또는 dedupe 후 0)

### 대안: 전량 재정제

`clean.py --reprocess-all` 은 `land_transactions` **전 삭제** 후 raw 재처리.  
시간은 길지만 hash·매핑을 한 번에 맞출 수 있음. **dedupe + rehash** 가 더 빠름.

## Promote 시 주의

- 로컬 **PostgreSQL 18** `pg_dump -Fc` → VPS **`postgresql-client-18`의 `pg_restore`** ([`deploy/03-data-migration.md`](../deploy/03-data-migration.md)).
- dedupe **후** dump — VPS는 수정된 DB만 받음.

## 리허설 체크

`python pipeline/rehearse_v2_update.py` — §「land_transactions 중복」 경고 없어야 함.

## dev VPS (Promote 전)

- 현재 VPS는 **dedupe 전 dump** 기준 → 건수 2배 가능. **의사결정용 수치 금지**.
- 6월 Promote 후 IP/도메인에서 비하동 **2건** 재확인.
