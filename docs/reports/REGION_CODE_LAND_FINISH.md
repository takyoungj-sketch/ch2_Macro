# Land canonical 전환 완료 (D-028 · 2026-07-21)

## 결론

토지(Land) 파이프라인·API는 **canonical grain** 기준으로 마감한다.  
Master `beopjungri_code` 불변(수태리 구코드 **220건**). unresolved **2건**은 계속 제외·별도 큐.

## 검증 (수태리 GIS `4377025626` + 신척리 `4375025329`)

| 경로 | 결과 |
|------|------|
| `/free/v2/regions?search=수태리` | 명칭 **수태리**, 읍 **대소읍**, 코드 `4377025626` |
| `/free/v2/stats/bulk` 3y | count **241**, title `수태리, 신척리`, kept 둘 다 |
| `/free/v2/stats/bulk` 5y | count **441** |
| `/paid/analyze` | by_region keys = **canonical만** (`4377025626`, `4375025329`) |
| UI 지도 | neighbors/boundaries/bulk에 동일 두 코드 반복 요청 확인 (프론트→API) |

산출: [`REGION_CODE_LAND_FINISH_VERIFY.json`](./REGION_CODE_LAND_FINISH_VERIFY.json)  
upper/annual: [`REGION_CODE_LAND_UPPER_ANNUAL_VERIFY.md`](./REGION_CODE_LAND_UPPER_ANNUAL_VERIFY.md)

## 재빌드

- `land_upper_stats_v2` — 시도 **41·43**, as_of `2026-06-01`, windows 3·5, col_axis both  
- `land_annual_stats` + `land_annual_upper_stats` — years 2010–2026, same sidos  
- 오케스트레이터: `pipeline/rebuild_land_upper_annual_canonical.py`

## 공통 모듈

- SSOT: `pipeline/region_canonical.py`  
- Backend re-export: `backend/app/region_canonical.py`  
- Built/Collective: market 빌드 grain + `region_scope` beopjungri expand 동일 규칙 공유 (독자 변환 금지)

## unresolved (제외 유지)

Phase 1a 2건 — 통영 산양읍 당포리(신·누락) / 삼덕리(구·활성). history 미적재.
