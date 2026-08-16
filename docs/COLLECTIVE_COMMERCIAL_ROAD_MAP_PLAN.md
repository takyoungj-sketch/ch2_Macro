# 집합상가·공장 — 도로 지도 오버레이 계획

> **상태:** **Road-B + Road-A(선택 1개 도로선)** 구현 · Road-D·폴리곤 clip·선 캐시 대기  
> **브랜치:** `feature/commercial-road-centerline` (`origin/main` 기준, 2026-08-13)  
> **관련:** [`COLLECTIVE_MAP_HUB_PLAN.md`](./COLLECTIVE_MAP_HUB_PLAN.md) · [`COLLECTIVE_COMMERCIAL_DESIGN.md`](./COLLECTIVE_COMMERCIAL_DESIGN.md) · [`MAP_REGION_HUB_DESIGN.md`](./MAP_REGION_HUB_DESIGN.md)  
> **작성:** 2026-07-11 · **갱신:** 2026-08-13

---

## 1. 목적

비주거 집합은 **도로명(cluster)** 단위로 통계한다. 행정 경계 Map Hub 위에 **선택 도로의 위치·이름·구간**을 보여 탐색을 돕는다.

| 포함 | 후속 |
|------|------|
| 선택 cluster → 점 마커 + 도로명 라벨 (Road-B) | 목록 전체 도로를 한꺼번에 표시 |
| 선택 1개 도로 → VWorld 중심선 오버레이 (Road-A) | 도로 인접 복수 선택 |
| 행정 Hub와 공존 | cluster ↔ 도로명코드(RN) · 전국 SHP 적재 (Road-D) |

---

## 2. 현황·제약

| 항목 | 내용 |
|------|------|
| cluster | `sha256(asset_type\|addr1…\|road_name)` — 원장에 **좌표·선 없음** |
| 원장 필드 | MOLIT CSV **도로명 문자열**만. 도로명코드 없음 |
| 동일 도로명 | 동이 다르면 cluster가 갈라짐. 이름만으로 전국 유일하지 않음 |
| 외부 원천 | VWorld Search(점) + Data API `LT_L_SPRD`(선). 공공데이터포털 「도로명주소 도로」와 **같은 원천** — 포털 키를 따로 받을 필요 없음 |
| 쓰지 않는 것 | WMS 전체 도로 깔기(특정 도로만 강조 불가) · 통계연보 도로명 목록(기하 없음) · `lt_c_uq111`(용도지역으로 오인하기 쉬움) |

---

## 3. 접근안 비교

| 안 | 내용 | 판정 |
|----|------|------|
| **B** 지오코딩 라벨 | `시군구+동+도로명` → VWorld Search → 점+이름 | **완료** |
| **A** VWorld 도로망 | Data API `LT_L_SPRD` + `rn` 매칭 → LineString | **선택 1개 완료** |
| **D** DB 중심선 | cluster_key → GeoJSON 사전 적재 | 장기 (아래 §8) |
| C 거래 지번 추정 | 좌표 없음 | 비채택 |

Kakao Local(`POST /api/geocode/kakao`)은 FieldNote용. Macro 상업 지도는 **기존 `VWORLD_API_KEY`**.

---

## 4. UX (현재)

1. 행정 칩 → 지도에 경계 (노란 외곽).  
2. 「통계분석」 → 도로(cluster) 목록.  
3. **목록에서 도로 1개 선택** → **하늘색(`#38bdf8`) 중심선** + 호박색 마커·라벨.  
4. 선이 있으면 잘린 구간으로 `fitBounds`(maxZoom 16). 선 실패 시 점으로 flyTo.  
5. 선을 못 찾으면 「도로 선은 찾지 못해 위치로 표시합니다.」  
6. 행정 인접 복수 UX와 독립 (도로 클릭으로 행정 추가하지 않음).

---

## 5. 구현 (2026-08-13)

### 5.1 경로

| 구성 | 경로 |
|------|------|
| 선 조회·매칭·BOX clip | `backend/app/collective_commercial/road_geometry.py` |
| 점 지오코딩 | `backend/app/collective_commercial/road_geocode.py` |
| API | `POST /api/collective/commercial/roads/geocode` · `POST .../roads/line` |
| 임의 레이어 GetFeature | `vworld_client.fetch_named_layer_features` |
| Client | `geocodeCommercialRoad` · `fetchCommercialRoadLine` |
| UI | `CollectiveRegionMapHub` `selectedRoads` + Marker + `commercial-road-line` Layer |
| App | `CommercialApp` — 선택 cluster를 Hub에 전달 |
| 테스트 | `backend/tests/test_road_geometry.py` |

### 5.2 점 (Road-B)

쿼리: `{addr1} {addr2} {addr3} {addr4} {road_name}`  
VWorld Search `type=address`, `category=road` → 실패 시 `parcel`. 첫 건 `point.x/y`.  
목록 점(최대 100)은 `collective_commercial_map_geocodes`에 캐시.

### 5.3 선 (Road-A)

1. 검색 상자 = **선택 행정 bbox ∩ 지오코딩 점 버퍼(~1.3km)**. 교집합이 비면 점 버퍼.  
2. `LT_L_SPRD` GetFeature: `geomFilter=BOX(...)` + `attrFilter` `rn:=:` / `rn:like:` / bbox만.  
3. 속성 `rn`과 원장 도로명 **공백 제거 후 정확 일치**만 채택 (`중앙로` ≠ `중앙로2길`).  
4. 매칭된 LineString/MultiLineString을 같은 BOX로 **Liang-Barsky clip**.  
5. 실패 시 점만 유지. 앱은 깨지지 않음.

실측: 청주 흥덕 봉명 인근 `1순환로` → `rn` 일치 MultiLineString 3구간.

---

## 6. Phase

| Phase | 내용 | 상태 |
|-------|------|------|
| **Road-B** | 선택 cluster 지오코딩 라벨 + flyTo | **완료** |
| **Road-A** | `LT_L_SPRD` 선택 1개 선 · bbox∩버퍼 · BOX clip · 하늘색 | **완료** |
| **Road-A2** | 동 **폴리곤** clip · 선 GeoJSON DB 캐시 | 대기 (§8) |
| **Road-D** | 도로명코드(RN) 매칭 · 사전 적재 | 대기 |
| **Road-목록** | 목록 도로를 한꺼번에 선으로 | 대기 (쿼터·가독성) |

### 성공 기준 (현재)

1. 상업 UI에서 도로 선택 시 이름 라벨이 보인다.  
2. 가능하면 해당 도로 **하늘색 선**이 행정 노란 외곽과 구분된다.  
3. 행정 경계 Hub는 그대로 동작한다.  
4. 지오코딩·선 실패 시 안내만 하고 앱이 깨지지 않는다.

---

## 7. 데이터 소스 메모 (조사 2026-08-13)

| 후보 | 결론 |
|------|------|
| VWorld Data `LT_L_SPRD` | **채택** — 기존 키, 행정 경계와 같은 API |
| 공공데이터 국토부 도로명주소 도로 / WFS | 원천 동일. 키 추가 불필요. VWorld가 막힐 때 백업 |
| 국토부 도로명주소 **건물** | 비주거 선 비대상. 주거 단지 점 보강용으로만 검토 |
| 행안부 통계연보 위계·지역별 도로명 | 기하 없음. 사용 안 함 |
| WMS로 도로 전체 | “이 도로만” 강조 불가 |

---

## 8. 차후 개선

우선순위는 위→아래. **실패 사례(도로명·시·동)가 쌓인 뒤에** 이름 규칙을 느슨히 할 것.

| ID | 항목 | 왜 | 난이도 |
|----|------|-----|--------|
| A2-1 | **선 결과 DB 캐시** (`cluster_key` → GeoJSON). 점 캐시 `collective_commercial_map_geocodes`와 대칭 | 선택마다 VWorld Data 재호출 | 중 (DDL + collective_stats) |
| A2-2 | **동 폴리곤 clip** (지금은 축정렬 BOX) | 사각형 밖·모서리 잘림, 동 모양과 불일치 | 중 (shapely 또는 turf) |
| A2-3 | 점 버퍼와 행정 bbox 교집합이 비면 **안내** (지금은 점 버퍼로 조용히 fallback) | 지오코딩이 동 밖에 찍힌 줄 모름 | 소 |
| D-1 | 원장 도로명 ↔ **도로명코드(RN)** lookup | `로`/`길`/`대로`·공백·옛 이름 불일치 | 대 |
| D-2 | Road-D: 도로구간 SHP/WFS **사전 적재** | 실시간 size=400·쿼터, 긴 순환로 잘림 | 대 |
| UX-1 | 목록의 다른 도로를 얇은 선으로 (선택만 굵게) | 탐색은 좋아지나 호출·가독성 비용 | 중 |
| UX-2 | fit을 「동 경계 + 선택 구간」으로 고정 | 긴 도로 clip 후에도 줌이 빠질 수 있음 | 소 |
| MATCH-1 | 정규화 확장 (`1순환로` vs `제1순환로`)는 **오탐 로그 후** | 정확 일치가 빈 화면을 만들면 | 소, 데이터 의존 |

하지 말 것: 공공데이터 키를 VWorld와 **동시에** 쓰기, OSM/카카오로 선 대체, WMS 전체 도로 레이어.

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-07-11 | 권장안 문서화 · Road-B 착수 (VWorld Search 라벨) |
| 2026-07-11 | Road-B 완료: geocode API · Hub Marker · CommercialApp 연동 |
| 2026-08-13 | Road-A: `LT_L_SPRD` 선택 도로 선 · bbox∩버퍼 · BOX clip · 하늘색 구분 · §8 백로그 |
