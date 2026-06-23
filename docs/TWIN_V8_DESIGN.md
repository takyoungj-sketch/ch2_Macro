# Twin v8 — 쌍둥이 도시 알고리즘 설계

> **브랜치:** `feature/twin-v8`  
> **상태:** Phase 1 구현 (충청권)  
> **기존 Hybrid V2(algo 6/7)와 병행** — A/B 비교 가능

## 목적

데이터가 부족한 지역(특히 **리**)의 **보완 사례 탐색**. 감정평가 실무에서 설명 가능한 Twin Score + Confidence.

## 범위 (Phase 1)

| 항목 | 값 |
|------|-----|
| 권역 | 충청권 — 충북(43)·충남(44)·대전(30)·세종(36) |
| 행정단위 | 시군구 · 읍면동 · **리(beopjungri)** |
| 후보 범위 | 동일 충청권 내 전체 (scope 고정) |

## 인구 필터 (후보 축소만)

- 비율 **0.6 ~ 1.7** (`pass_population_ratio`)
- 최종 Twin Score에 **미반영**

## 점수 (100점)

| 블록 | 배점 | 방법 |
|------|------|------|
| 토지 구조 | 30 | Top-N 셀 Jaccard \|A∩B\|/\|A∪B\| |
| 토지 가격 | 30 | **교집합** 셀만 `exp(-\|log(pA/pB)\|)` 평균 |
| 집합(아파트) | 40 | p25·median·p75 각 유사도 **단순 평균** |

Top-N: 시군구 10 · 읍면동 5 · 리 3  
셀 = `용도지역|지목` (Hard gate 없음)

## 데이터

| 레벨 | 토지 | 집합 |
|------|------|------|
| 시군구 | `land_upper_stats_v2` | `market_stats` apartment @ sigungu |
| 읍면동 | `land_upper_stats_v2` | `market_stats` @ eupmyeondong |
| 리 | `land_basic_stats_v2` | **읍면동(앞 8자) 대표값** roll-up |

## Confidence (0~100, Twin Score와 별도)

- 토지 총 거래 · Top-N 셀 거래 · 교집합 셀 수 · 집합 데이터 존재

## 산출물

- 테이블: `twin_neighbor_v8` (`db/031_twin_neighbor_v8.sql`)
- 빌더: `pipeline/build_twin_v8.py`
- API: `GET /api/twin-v8/neighbors/{level}/{code}`

## 리 후보 범위 (성능)

리(beopjungri)는 코드 수가 많아 **동일 시군구(sigungu_code 5자) 내** 후보만 비교한다 (Phase 1).  
전 충청권 리↔리 비교는 Phase 2/샘플링 검토.

- 전국 확대
- `lower_mean` / `mid_mean` / `upper_mean` mart
- 리 단위 집합 mart
- 거래량 유사도
