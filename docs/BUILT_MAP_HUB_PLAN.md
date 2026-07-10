# 복합부동산(built) — Map Hub 이식 계획

> **상태:** **문서화 완료 · 구현 대기** (토지 Map-A PoC 이후)  
> **관련:** [`MAP_REGION_HUB_DESIGN.md`](./MAP_REGION_HUB_DESIGN.md) · [`BUILT_HANDOFF_AND_ROADMAP.md`](./BUILT_HANDOFF_AND_ROADMAP.md) · [`REGION_ARCHITECTURE_ROADMAP.md`](./REGION_ARCHITECTURE_ROADMAP.md) D-015  
> **작성:** 2026-07-11 · 토지 Map Hub 적용 가능성 검토 결과 반영

---

## 1. 목적

토지(`frontend/`)에서 동작 중인 **Map Region Hub** UX·경계·강조 표시를 복합(`frontend-built/`)에 **동일 시각·조작 패턴**으로 이식한다.

| 포함 | 제외 (본 문서 범위 밖) |
|------|------------------------|
| 위성 베이스맵 + 행정 경계 | Regional Profile 카드 데이터 재구축 |
| 선택 지역 클로즈업·highlight | 토지 `RegionSelector` / `tierSelection` 통합 |
| (후속) 인접 구역 지도 추가 | 집합부동산 이식 (별도) |
| addr ↔ 행정코드 브리지 | Property Registry 등 Post-MVP |

---

## 2. 결론 (적용 판정)

**적용 가능.** 새 GIS 백엔드는 불필요하다.

| 판정 | 내용 |
|------|------|
| **재사용** | `GET /api/map/config`, `GET /api/map/boundaries` (`backend/app/map/*`) — 토지·복합 동일 프로세스 |
| **재사용 (추출)** | 타일·fit·노란 선택 외곽·붉은 인접선·DOM 라벨·turf 인접 판정 |
| **필수 신규** | 복합 **이름(addr) → 행정코드** resolve API + `BuiltRegionMapHub` 어댑터 |
| **비권장** | `RegionMapHub.tsx` 통째 복붙(토지 store·유료/무료 결합) · 복합을 토지 `tierSelection`으로 강제 통합 |

**공수 감:** 열람 PoC **M** · 칩 동기화 **M–L** · 인접 복수 패리티 **L**

---

## 3. 현황 대비

### 3.1 토지 Map-A (참조 구현)

| 구성 | 경로 |
|------|------|
| Hub UI | `frontend/src/components/RegionMapHub.tsx` |
| 스코프 | `frontend/src/utils/mapRegionScope.ts` + `cityBucket.ts` |
| Fit | `frontend/src/utils/mapFitBounds.ts` |
| Client | `frontend/src/api/mapClient.ts` |
| 선택 SSOT | `tierSelection` (sido / city / sigungu / eup / beop **코드**) |
| 강조 | 선택 = **굵은 노란 경계** · 인접 = 붉은 선 · 면 채움은 hit용 연한 회색 |
| 복수 | 시·도·시군구: **「시군구 이상 복수지역 선택 불가.」** · 읍면동·리만 인접 추가 |

### 3.2 복합 (지도 없음)

| 구성 | 경로 / 상태 |
|------|-------------|
| UI | `frontend-built/src/App.tsx` — `addr1`·`addr2`·`guList`·`leafList`·`riList` **이름** state |
| API | `baseURL: "/api/built"` — `/regions/addr2|structure|addr3|leaf|ri` |
| 지도 deps | `maplibre-gl` / `react-map-gl` / `@turf/*` **미설치** |
| VWorld 키 | `frontend-built` 에 `VITE_VWORLD_API_KEY` **미정** (토지·백엔드 키는 공용 가능) |
| DB | `built_transactions` 적재 시 `sido_code`…`beopjungri_code` **부착됨** — **API·UI 미노출** |
| Proxy | `vite.config.ts` `/api` → `:8000` → **`/api/map` 호출 가능** |

### 3.3 핵심 갭

```
복합 UI (이름 칩)  ──✗──  VWorld /api/map (행정코드)
        │
        └── 필요: resolve-codes (또는 동등 브리지)
```

토지는 코드 카탈로그(`region_codes`)가 선택 SSOT이고, 복합은 **addr 이름 캐스케이드**가 SSOT이다. 지도만 코드가 필요하다.

---

## 4. 아키텍처

### 4.1 권장 구조

```
shared/map-hub/          (또는 Vite alias로 단계적 추출)
  mapClient.ts
  mapFitBounds.ts
  cityBucket.ts
  featureAdminCode / adjacency / paint helpers
  RegionMapCanvas (MapLibre 프레젠테이션)

frontend/                BuiltRegionMapHub ← resolveMapSelectionState(tier)
frontend-built/          BuiltRegionMapHub ← resolveBuiltMapSelection(addrState)
backend/app/map/*        공유 (변경 최소)
backend/app/built/       GET …/regions/resolve-codes  (신규)
```

### 4.2 선택 → 지도 스코프

복합 칩 상태 → 토지와 **동일 shape**의 `MapSelectionState`:

| 필드 | 의미 |
|------|------|
| `level` | `sido` \| `sigungu` \| `eupmyeondong` \| `beopjungri` |
| `selectedCodes` | VWorld·highlight용 코드 목록 |
| `contextSidoCode` / `contextSigunguCode` | 이웃 경계 로드 맥락 |
| `hasSelection` | boundaries 쿼리 enable |

**매핑 초안**

| 복합 선택 | 지도 level (목표) | selected |
|-----------|-------------------|----------|
| `addr1`만 | `sido` | 시도 코드 |
| `addr2` (구 없는 시·군) | `sigungu` | 시군구 코드 1개 |
| `addr2` (청주·천안 등 구 있는 시) | `sigungu` | 하위 **구 코드 전부** (토지 `city_codes` 버킷과 동등) |
| `guList` | `sigungu` | 선택 구 코드들 |
| `leafList` (동·읍·면) | `eupmyeondong` | 읍면동 코드들 |
| `riList` | `beopjungri` | 리(법정) 코드들 |

이름→코드는 **현재 asset_type·addr 필터로 `built_transactions` DISTINCT** 하거나, land `region_codes` 조인. 전자가 거래 커버리지와 일치해 안전하다.

### 4.3 API 초안 — `resolve-codes`

```
GET /api/built/regions/resolve-codes
  ?asset_type=
  &addr1= &addr2=
  &gu=… (repeat) &leaf=… &ri=…
→ {
    level,
    selected_codes: string[],
    context_sido_code,
    context_sigungu_code,
    labels?: Record<string, string>
  }
```

- 빈 선택 / 코드 미부착 행만 있으면 `selected_codes=[]` + 프론트 안내.
- `needs_review`·코드 NULL 비율은 운영 지표로 별도 점검.

---

## 5. UX 규칙 (복합)

토지 Map-A와 **시각·제스처는 맞추고**, 제품 게이트만 복합에 맞게 조정한다.

| 항목 | 복합 방침 |
|------|-----------|
| 베이스맵 | VWorld 위성 (토지와 동일) |
| 선택 강조 | **굵은 노란색** 행정 경계 (파란 면 채움 사용 안 함) |
| 인접 격자 | 붉은 외곽선 |
| 초기 fit | 선택 polygon ~15cm 규칙 (`mapFitBounds`) |
| 1차 선택 | 좌측 addr 칩만 (지도에서 시군구 신규 1차 선택 없음) |
| **addr2(시군구·의사 시)만 선택** | 지도 인접 추가 **불가** — 안내: **「시군구 이상 복수지역 선택 불가.」** |
| leaf / ri | (Phase 3) 인접·동일레벨만 지도 추가 → 칩 목록 동기화 |
| 무료/유료 | 복합에 토지형 유료 게이트 **없음** → 인접 추가는 **항상 허용 / 피처 플래그 / 연구 MVP에선 열람만** 중 제품 확정 |
| 칩 다중선택 | 기존 좌측 다중 칩은 유지. 지도 인접은 **추가 경로** (충돌 시 한도·동일레벨 규칙 문서화) |

> Phase 1(열람 PoC)에서는 클릭·우클릭 추가를 **넣지 않는다**.

### 5.1 레이아웃

`frontend-built` 메인 컬럼(회귀 카드 위)에 Hub 배치 — 토지 `App.tsx`와 같이 **접기 / 보통 / 확대** 모드 재사용.

```
┌─ 좌: 유형·addr 칩·필터 ─┬─ 우: Map Hub (접기 가능) ─┐
│                         │  회귀·예측 카드            │
└─────────────────────────┴──────────────────────────┘
```

---

## 6. 구현 Phase

| Phase | 내용 | 공수 | 상태 |
|-------|------|------|------|
| **Built-M0** | Spike: 복합 앱에서 `/api/map/config`·hardcoded boundaries 호출 · 청주 등 표본 `beopjungri_code` NOT NULL 확인 | ½–1일 | 대기 |
| **Built-M1** | 열람 PoC: deps·`VITE_VWORLD_API_KEY`·`resolve-codes`·지도 표시·fit·노란 강조 · **추가 선택 없음** · level은 sigungu·eup 우선 | **M** | 대기 |
| **Built-M2** | 다중 leaf/ri highlight · 구 있는 시(addr2→구 코드) · flat sido · 접기/확대 | **M–L** | 대기 |
| **Built-M3** | 인접 복수 추가 (제품 규칙 확정 후) · code→이름 칩 · 시군구 이상 안내 문구 | **L** | 대기 |
| **Built-M4** | `shared/map-hub` 추출 · 토지 Hub thin wrapper · 본 문서·`MAP_REGION_HUB_DESIGN` 동기화 · 집합 재사용 준비 | **L** | 대기 |

### 6.1 Built-M1 성공 기준

1. `/built/` 에서 addr2(또는 leaf) 선택 시 위성 + 경계 표시  
2. 선택 구역 **노란 굵은 외곽** + ~15cm fit  
3. 토지 `/api/map` 와 **동일 백엔드** 사용  
4. 지도 클릭으로 선택 변경 **없음** (회귀·칩 UX 회귀 없음)

### 6.2 Built-M3 성공 기준 (후속)

1. leaf/ri에서만 인접 추가 · addr2에서는 복수 불가 안내  
2. 지도 추가 ↔ 좌측 칩·회귀 scope 일치  
3. D-015(구 없는 시 리 addr)와 충돌 시 **리 레벨은 보류 또는 정규화 선행**

---

## 7. 블로커 · 리스크

| # | 항목 | 심각도 | 대응 |
|---|------|--------|------|
| 1 | name→code API 부재 | Hard | Built-M1에서 `resolve-codes` 필수 |
| 2 | Hub↔토지 store 결합 | Hard | 프레젠테이션 분리 + 복합 어댑터 |
| 3 | 인접·복수 제품 규칙 미정 | Medium | M1은 열람만 · M3 전 제품 합의 |
| 4 | D-015 리 addr 왜곡 | Medium | 리 지도는 정규화 후 또는 M2에서 제외 |
| 5 | 코드 NULL / needs_review 행 | Medium | resolve 커버리지 로그 · 부분 highlight 허용 |
| 6 | 청주·천안 등 의사 시 | Medium | 토지 `cityBucket`과 동등하게 구 코드 전개 |

---

## 8. 의존 · 환경

| 항목 | 비고 |
|------|------|
| 백엔드 | 기존 `uvicorn` `:8000` — map 라우터 이미 mount |
| 프론트 | `frontend-built`에 maplibre·react-map-gl·turf 추가 |
| Env | `VITE_VWORLD_API_KEY` (타일) · 백엔드 `VWORLD_API_KEY` (Data API) |
| 설계 SSOT | 토지 UX 변경 시 본 문서 §5·토지 Hub를 함께 갱신 |

---

## 9. 관련 문서

| 문서 | 관계 |
|------|------|
| [`MAP_REGION_HUB_DESIGN.md`](./MAP_REGION_HUB_DESIGN.md) | 토지 Map-A / Profile-B · 공통 UX |
| [`BUILT_HANDOFF_AND_ROADMAP.md`](./BUILT_HANDOFF_AND_ROADMAP.md) | 복합 인수·로드맵 |
| [`BUILT_RESEARCH_MVP.md`](./BUILT_RESEARCH_MVP.md) | 복합 MVP 범위 |
| [`REGION_ARCHITECTURE_ROADMAP.md`](./REGION_ARCHITECTURE_ROADMAP.md) | D-015 리 addr · Region 통합(후속) |
| [`DECISIONS.md`](./DECISIONS.md) | D-010 복수 정책(토지) — 복합은 §5에서 별도 확정 |

---

## 변경 이력

| 일자 | 내용 |
|------|------|
| 2026-07-11 | 초안 — 토지 Map Hub → 복합 적용 검토 결과·Phase·resolve-codes·UX 규칙 문서화 |
