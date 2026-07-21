# Built·Collective P1 API verify (map resolve + regression DF expand)

## 변경

| 경로 | 내용 |
|------|------|
| `backend/app/built/resolve_codes.py` | 지도 코드를 `canonical_select_expr` / `resolve_to_canonical` 로 반환 |
| `backend/app/collective/resolve_codes.py` | beopjungri → resolve; eup/sigungu → history 경유 prefix |
| `backend/app/built/regression/engine.py` | DF `region_codes` beopjungri 필터 시 `expand_to_ledger_codes(conn)` |
| `backend/app/region_scope.py` | (기적용) beopjungri expand — Built transaction_scope 경유 |

새 resolver 모듈 없음. `app.region_canonical` = `pipeline/region_canonical` re-export.

## 전제

- Built/Collective DB에 `region_code_history` 191행 sync 완료 (`REGION_CODE_HISTORY_SYNC_VERIFY.md`)
- unresolved 2건 history 없음 → expand/resolve identity

## 스모크

- `from app.built import resolve_codes` / collective / regression.engine import **ok**
- 원장 UPDATE 없음

## 제외

- cluster_key / building_key grain API·mart
