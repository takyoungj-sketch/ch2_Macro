# Built·Collective canonical 전환 — 단계 요약

## 0. 영향 조사
→ [`REGION_CODE_BUILT_COLLECTIVE_IMPACT.md`](./REGION_CODE_BUILT_COLLECTIVE_IMPACT.md)

## 1. History sync (설계·실행)
- DDL: `db/046_region_code_history_shared.sql`
- Script: `pipeline/sync_region_code_history.py`
- Interim SSOT: land → built/collective **복제** (매핑 포크 금지)
- Long-term: 공통 지역 마스터로 승격 (Land 비소유)
- Verify: [`REGION_CODE_HISTORY_SYNC_VERIFY.md`](./REGION_CODE_HISTORY_SYNC_VERIFY.md) — integrity **True**, 191/191

## 2. P0 mart 부분 재빌드
- Orchestrator: `pipeline/rebuild_built_collective_market_canonical_p0.py`
- Targets: market_stats, market_annual_stats, built_annual_stats, collective_commercial_region_annual_stats
- Verify: [`REGION_CODE_BUILT_COLLECTIVE_P0_VERIFY.md`](./REGION_CODE_BUILT_COLLECTIVE_P0_VERIFY.md)
- 재발급 15 stale eup **0**, ledger hist **불변**

## 3. P1 API
→ [`REGION_CODE_BUILT_COLLECTIVE_P1_VERIFY.md`](./REGION_CODE_BUILT_COLLECTIVE_P1_VERIFY.md)

## 4. E2E (최종)
→ [`REGION_CODE_BUILT_COLLECTIVE_E2E_VERIFY.json`](./REGION_CODE_BUILT_COLLECTIVE_E2E_VERIFY.json)

| 케이스 | Built resolve | Collective resolve | market hist eup | 비고 |
|--------|---------------|--------------------|-----------------|------|
| 대소읍 | `43770256` | `43770256` | 0 / canon 7 | Built hist eup 잔류·NULL beopjungri → `canonical_prefix_expr` + name fallback |
| 화성분구 sample | (leaf 없음) | — | 0 / canon 18 | history resolve OK |

API: resolve-codes / stats/scope / buildings·transactions **5xx 없음**. user-facing grain에 hist eup **미노출**.

## 제외 유지
- unresolved 2건
- cluster / building_key grain
- 원장 beopjungri UPDATE
