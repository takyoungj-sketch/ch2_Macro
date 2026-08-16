# 집합부동산(collective) — Map Hub 이식 계획

> **상태:** **Collective-M1~M3 구현** (열람 + leaf 인접 추가) · 리(ri) API는 후속  
> **관련:** [`MAP_REGION_HUB_DESIGN.md`](./MAP_REGION_HUB_DESIGN.md) · [`BUILT_MAP_HUB_PLAN.md`](./BUILT_MAP_HUB_PLAN.md) · [`COLLECTIVE_HANDOFF.md`](./COLLECTIVE_HANDOFF.md)  
> **작성:** 2026-07-11 · 복합 Map Hub와 동일 UX 패턴

---

## 1. 목적

복합(`frontend-built/`)에서 동작 중인 **Map Region Hub**를 집합(`frontend-collective/`)에 **동일 시각·조작 패턴**으로 이식한다.

| 포함 | 제외 (본 문서 범위 밖) |
|------|------------------------|
| 위성 베이스맵 + 행정 경계 | Regional Profile 카드 |
| 선택 지역 클로즈업·highlight | 법정리(ri) 칩·`/regions/ri` (후속) |
| 읍·면·동 인접 지도 추가 | 시군구 넘는 인접 복수 (§7 복합과 동일 보류) |
| addr ↔ 행정코드 브리지 | `shared/map-hub` 추출 (Built-M4와 함께) |

---

## 2. 결론

**적용 가능.** `/api/map/*` 재사용. 필수 신규는 **이름→코드 resolve** + `CollectiveRegionMapHub`.

| 판정 | 내용 |
|------|------|
| **재사용** | `GET /api/map/config`, `GET /api/map/boundaries` |
| **필수 신규** | `GET /api/collective/regions/resolve-codes` · `CollectiveRegionMapHub` |
| **차이** | 주거: resolve-codes + **건물 지번 라벨** · 상가·공장: commercial resolve + **Road-B 점 + Road-A 하늘색 도로선** ([`COLLECTIVE_COMMERCIAL_ROAD_MAP_PLAN.md`](./COLLECTIVE_COMMERCIAL_ROAD_MAP_PLAN.md) §5·§8) |

---

## 3. 구현 Phase

| Phase | 내용 | 상태 |
|-------|------|------|
| **Collective-M1** | deps·`VITE_VWORLD_API_KEY`·`resolve-codes`·지도 표시·fit·노란 강조 | **완료** |
| **Collective-M2** | 다중 leaf highlight · 구 있는 시 · flat sido · 접기/확대 | **완료** (복합 Hub 이식) |
| **Collective-M3** | 읍·면·동 인접 추가 → `leafList` 칩 동기화 · 시군구 이상 복수 불가 안내 | **완료** |
| **Collective-M3a** | 선택 건물 지번 지오코딩 라벨 + flyTo | **완료** |
| **Collective-M3b** | 법정리 API·칩·지도 `onAddRi` (복합 패리티) | 대기 |
| **Collective-M4** | `shared/map-hub` 추출 | 대기 |

### 성공 기준 (M1–M3)

1. `/collective/` 에서 addr2(또는 leaf) 선택 시 위성 + 경계  
2. 선택 구역 **노란 굵은 외곽** + ~78% width fit  
3. leaf에서만 인접 추가 · 좌측 `leafList`와 일치  
4. 시군구 이상: 「시군구 이상 복수지역 선택 불가.」

---

## 4. 경로

| 구성 | 경로 |
|------|------|
| Hub UI | `frontend-collective/src/components/CollectiveRegionMapHub.tsx` |
| Client | `frontend-collective/src/api/mapClient.ts` |
| Fit / scope | `frontend-collective/src/utils/mapFitBounds.ts`, `mapRegionScope.ts` |
| Resolve API | `backend/app/collective/resolve_codes.py` · `GET /api/collective/regions/resolve-codes` |
| Vite | port **5175**, base `/collective/`, proxy → `:8000` |

---

## 5. 왼쪽 칩 정책 (복합 §7.5와 동일)

- `LEFT_REGION_MULTI_SELECT = false` — 왼쪽은 1개(또는 빈=시군구 전체), 「전체」버튼 숨김.
- 지도 인접만 `leafList`에 추가. 왼쪽에서 다른 동을 고르면 클러스터 교체(새 1개만).
- 되돌리기: 플래그를 `true`로.

## 6. 보류 (복합 §7과 동일)

시군구를 넘는 인접 복수(예: 진천 이월면 + 음성 대소읍)는 **구현하지 않음**. SSOT가 단건 `addr2` + leaf 이름이기 때문.

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-07-11 | Collective-M1~M3 착수·구현 — resolve-codes, CollectiveRegionMapHub, App 연동 |
| 2026-07-11 | 왼쪽 칩 단일(앵커) + 지도 인접 복수 — `LEFT_REGION_MULTI_SELECT` |
| 2026-07-11 | 집합상가·공장(`CommercialApp`) Map Hub 연동 · commercial resolve-codes |
| 2026-07-11 | 상업 도로 지도 — [`COLLECTIVE_COMMERCIAL_ROAD_MAP_PLAN.md`](./COLLECTIVE_COMMERCIAL_ROAD_MAP_PLAN.md) · Road-B |
| 2026-07-11 | 주거 선택 건물 지번 라벨 — `POST /buildings/geocode` · Collective-M3a |