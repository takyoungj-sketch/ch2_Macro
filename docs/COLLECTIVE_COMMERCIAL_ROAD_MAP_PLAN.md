# 집합상가·공장 — 도로 지도 오버레이 계획

> **상태:** **Road-B MVP 완료** (선택 cluster 지오코딩 라벨) · Road-A/D 대기  
> **관련:** [`COLLECTIVE_MAP_HUB_PLAN.md`](./COLLECTIVE_MAP_HUB_PLAN.md) · [`COLLECTIVE_COMMERCIAL_DESIGN.md`](./COLLECTIVE_COMMERCIAL_DESIGN.md) · [`MAP_REGION_HUB_DESIGN.md`](./MAP_REGION_HUB_DESIGN.md)  
> **작성:** 2026-07-11

---

## 1. 목적

비주거 집합은 **도로명(cluster)** 단위로 통계한다. 행정 경계 Map Hub 위에 **선택 도로의 위치·이름**을 보여 탐색을 돕는다.

| 포함 (Road-B) | 제외 / 후속 |
|---------------|-------------|
| 선택 cluster → 점 마커 + 도로명 라벨 | 도로 **중심선(line)** GeoJSON |
| VWorld Search 지오코딩 (기존 `VWORLD_API_KEY`) | 목록 전체 도로를 한꺼번에 표시 |
| 행정 Hub와 공존 (오버레이) | 도로 인접 복수 선택 |

---

## 2. 현황·제약

| 항목 | 내용 |
|------|------|
| cluster | `sha256(asset_type\|addr1…\|road_name)` — **좌표·선 없음** |
| Map Hub | 행정 경계 + 위성만 (`CollectiveRegionMapHub commercial`) |
| 동일 도로명 | 동이 다르면 cluster가 갈라짐 → 점에 여러 라벨이 겹칠 수 있음 |

---

## 3. 접근안 비교 (채택 요약)

| 안 | 내용 | 판정 |
|----|------|------|
| **B** 지오코딩 라벨 | `시군구+동+도로명` → VWorld Search → 점+이름 | **MVP 채택** |
| **A** VWorld 도로망 | Data API 도로선 프록시 | 후속 (레이어·이름 매칭 spike) |
| **D** DB 중심선 | 사전 적재 | 장기 |
| C 거래 지번 추정 | 좌표 없음 | 비채택 |

Kakao Local 프록시(`POST /api/geocode/kakao`)는 FieldNote용·키 미설정 구간이 있어, Macro 상업 지도는 **이미 쓰는 VWorld 키**로 Search API를 쓴다.

---

## 4. Road-B UX

1. 행정 칩 → 지도에 경계 (기존).  
2. 「통계분석」 → 도로(cluster) 목록.  
3. **목록에서 도로 1개 선택** → 지도에 **마커 + 도로명**, 해당 점으로 flyTo.  
4. 선택 해제·다른 도로 선택 시 마커 교체.  
5. 행정 인접 복수 UX와 독립 (도로는 클릭으로 행정 추가하지 않음).

---

## 5. 구현

| 구성 | 경로 |
|------|------|
| API | `POST /api/collective/commercial/roads/geocode` |
| Client | `frontend-collective/src/api/mapClient.ts` → `geocodeCommercialRoad` |
| UI | `CollectiveRegionMapHub` `selectedRoads` + MapLibre `Marker` |
| App | `CommercialApp` — `selected` cluster를 Hub에 전달 |

쿼리 문자열 예: `{addr1} {addr2} {addr3} {addr4} {road_name}`  
VWorld: `service=search&type=address&category=road` (실패 시 `parcel` 등 soft fallback 가능).

---

## 6. Phase

| Phase | 내용 | 상태 |
|-------|------|------|
| **Road-B** | 선택 cluster 지오코딩 라벨 + flyTo | **구현** |
| **Road-A** | VWorld 도로선 레이어 spike · `/api/map/roads` | 대기 |
| **Road-D** | cluster↔centerline DB | 대기 |

### Road-B 성공 기준

1. 상업 UI에서 도로 선택 시 지도에 이름 라벨이 보인다.  
2. 행정 경계 Hub는 그대로 동작한다.  
3. 지오코딩 실패 시 안내만 하고 앱이 깨지지 않는다.

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-07-11 | 권장안 문서화 · Road-B 착수 (VWorld Search 라벨) |
| 2026-07-11 | Road-B 완료: geocode API · Hub Marker · CommercialApp 연동 |
