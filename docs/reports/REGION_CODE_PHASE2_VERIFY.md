# Phase 2 — canonical resolve + partial V2 rebuild 검증

- **일자:** 2026-07-21
- **as_of_month:** 2026-06-01
- **windows:** [3, 5]
- **pairs rebuilt:** 191 (failed=0)
- **elapsed_rebuild_s:** 57.1

## 원칙

- `land_transactions.beopjungri_code` **미변경** (historical 보존)
- mart grain = `region_code_history` canonical (`to_code`)
- API: GIS 코드 → `resolve_to_canonical` → mart; 원장 조회는 `expand_to_ledger_codes`
- unresolved 2건: history 없음 → resolve identity / 제외

## 영향 테이블

| 테이블 | 변경 |
|--------|------|
| `region_code_history` | (Phase 1b 유지, 191) |
| `region_codes` | canonical upsert 191, historical deactivate 191 |
| `land_basic_stats_v2` | delete 29995 rows → rebuild 191 regions |
| `land_transactions` | **무변경** |

## 대소 수태리

| 항목 | 값 |
|------|----|
| resolve(4377025626) | `4377025626` |
| resolve(4377034026) | `4377025626` |
| ledger expand(canonical) | ['4377025626', '4377034026'] |
| Master tx @ historical | 220 (before=220) |
| mart ALL×ALL count @ canonical (3y category) | {'count': 98, 'mean': Decimal('8.40'), 'median': Decimal('6.50')} |
| window txs via ledger expand | 98 |
| mart rows hist@as_of before→expect stale deleted | before=0 |

## GIS bulk 시뮬레이션 (수태리+신척리)

- 신척리 `4375025329` + 수태리 canonical `4377025626`
- mart ALL×ALL 보유 코드: ['4375025329', '4377025626']
- 합산 가능 여부: **OK**
- 원장 합산 거래수(3y window, ledger expand): 241

### free_v2 경로 검증 (2026-07-21)

```
input ['4377025626', '4375025329']
resolved ['4377025626', '4375025329']
kept […] missing []
ledger includes historical 4377034026
bulk total.count 241
master hist tx 220 (unchanged)
```

수태리 전체 Master 220건 중 3년 창(as_of 2026-06) 유효 단가 거래는 98건 → mart ALL×ALL `count=98`과 일치.

## 실패 목록

_(없음)_

## 재실행

```
cd backend
.venv/Scripts/python.exe ../pipeline/rebuild_stats_v2_canonical_phase2.py
```

