# Map Hub — Display ≠ Selection (위상 인접)

> **상태:** **구현 착수** (토지 우선)  
> **관련:** [`MAP_REGION_HUB_DESIGN.md`](./MAP_REGION_HUB_DESIGN.md)  
> **작성:** 2026-07-12

---

## 1. 원칙

| 축 | 역할 | SSOT |
|----|------|------|
| **Display (표시)** | 지도 맥락 — “지금 화면에 무엇이 있나” | **Viewport(bbox)** 기준 경계 로드 |
| **Selection (선택)** | 분석 scope의 **공간 연속성** | **`region_neighbors` 그래프** |

둘을 같게 맞추지 않는다. 지도는 답답하지 않게, 분석은 떨어진 지역을 합치지 않게 한다.

---

## 2. Display

1. MapLibre `moveend` / 초기 fit 후 **현재 뷰 bbox**로 `GET /api/map/boundaries?bbox=…`  
2. 선택 코드 polygon은 **항상 포함** (뷰 밖이어도 highlight 유지)  
3. 시군구 전체 격자·선택 bbox±5km 이웃 링은 **표시 SSOT에서 제외** (레거시 `fetch_context_collection` 은 폴백용)

---

## 3. Selection

1. 동일 행정 레벨만  
2. 추가 가능 코드 = `⋃ neighbors(selected_i)` − `selected`  
3. 런타임: `GET /api/map/neighbors?level=&codes=`  
4. 테이블이 비어 있으면 **일시적으로** 기존 turf 인접 폴백 (마이그레이션·빌드 전)  
5. **상위 시군구가 달라도** 위상상 맞닿으면 선택 가능(토지). edge는 시군구 링/시도 빌드로 생성.

연쇄 확장: A 선택 → A의 neighbor만 추가 가능 → B 추가 → A∪B의 neighbor로 확장.

---

## 4. 데이터

```text
region_neighbors (level, code, neighbor_code)  -- 대칭 edge 저장
```

- `level`: `eupmyeondong` | `beopjungri` (1차는 읍면동)  
- 생성: `pipeline/build_region_neighbors.py` (VWorld polygon + shapely buffer touch)  
- 행정개편 시 재빌드

---

## 5. Phase

| Phase | 내용 | 상태 |
|-------|------|------|
| **N0** | 본 문서 · Display≠Selection 합의 | **완료** |
| **N1** | 테이블 · neighbors API · 토지 선택 게이트 | **진행** |
| **N2** | 토지 표시 = viewport boundaries | **진행** |
| **N3** | 전국/권역 neighbor 빌드 파이프라인 | **진행** (`--all --skip-existing`) |
| **N4** | 리(beopjungri) 그래프 · 복합/집합 이식 | **리 전국 빌드 완료** · Hub 이식 대기 |
| **N5** | 시군구 횡단 정책(토지 vs 복합) 제품 확정 | 대기 |

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-07-12 | 초안 — Display(viewport) / Selection(neighbor_codes) 분리 |
| 2026-07-12 | 시군구 횡단 인접 edge 빌드(링) · 토지 선택 허용 명시 |
