# Built·Collective P0 market canonical rebuild verify

- as_of=2026-06-01 windows=3,5 sidos=41,43
- deleted (broad 41590/stale-eup pass): `market_stats=862`, `market_annual=475`, `cc_region_annual=200`, `built_annual=460`

## Ledger (immutable)

| 지표 | before → after |
|------|----------------|
| built_transactions hist(191 from) | 6288 → **6288** |
| collective_transactions hist | 17901 → **17901** |

## Grain (재발급 15 eup prefix 기준 — 정확한 성공 지표)

| 테이블 | stale eup15 | canon eup (재발급 to) |
|--------|-------------|----------------------|
| `market_stats` | **0** | **185** |
| `market_annual_stats` | **0** | **218** |
| `built_annual_stats` | **0** | **234** |
| `collective_commercial_region_annual_stats` | **0** | **68** |

`left(region_code,5)='41590'` 잔류(265 등)는 **191 code_reissue 밖**의 화성 구코드(history 미매핑) identity grain — 이번 범위 밖.  
재발급 대상 15 stale eup 은 **전부 제거**되고 canonical eup 이 채워짐.

## 판정

- ledger_immutable_ok: **True**
- reissue_stale_eup_cleared_ok: **True**
- history_n built/coll: **191**
- cluster/building_key marts: **미변경** (범위 제외)

빌더: `build_collective_market_stats` / `build_built_market_stats` / `build_collective_commercial_market_stats`  
공용: `pipeline/region_canonical.py` only.
