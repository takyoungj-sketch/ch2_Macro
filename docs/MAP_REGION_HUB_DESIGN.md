# CH2 Macro — Map + Region Hub 설계

> **상태:** **Map-A 구현 진행 중** (지도·경계·인접 복수 선택) · **Profile-B 대기** (카드 API·재구축 데이터)  
> **구현 시점:** **1단계(Map-A)** — Profile 완료 **전에** 지도 Hub PoC. **2단계(Profile-B)** — `regional_profile` 재구축·Twin 이후 카드 연동  
> **관련:** [`DECISIONS.md`](./DECISIONS.md) D-010 · [`REGIONAL_PROFILE_ARCHITECTURE.md`](./REGIONAL_PROFILE_ARCHITECTURE.md) · [`REGION_ARCHITECTURE_ROADMAP.md`](./REGION_ARCHITECTURE_ROADMAP.md) · [`TWIN_V8_DESIGN.md`](./TWIN_V8_DESIGN.md)

---

## 1. 목표

### 1.1 문제

토지 통계 화면(무료/유료)에서 **조회 전 오른쪽 패널이 비어** dead screen처럼 보인다.  
사용자는 **「어디인지 → (인접 포함) 분석 범위 결정 → 그 지역이 어떤 시장인지 → 통계 조회」** 순으로 경험하는 것이 자연스럽다.

### 1.2 제품 목표 (Map + Hub)

오른쪽 빈 공간을 **지도 + 지역 프로필 카드** 로 채운다.

| 요소 | 역할 |
|------|------|
| **지도** | 선택 행정구역 **모양·주변 맥락** 식별 (위성으로 도시화·농지·임야 등 **눈으로 판단**) |
| **지도 (유료)** | 1차 선택 **이후** **인접 지역 복수 추가** — 분석 범위 결정 보조 |
| **카드** | 해당 scope **기본 프로필** (Profile DB — 구체 필드는 Profile 완성 후 확정) |

**본 설계는 범용 GIS가 아니라 “Region Profile을 받치는 Hub”** 이다.  
다만 **지도에서의 인접 복수 선택**은 유료 분석 범위를 정하는 핵심 UX로 포함한다.  
상단 **「지역 프로필」** 탭은 Hub의 **확장 뷰**(쌍둥이·AI 리포트 등)로 점진 연결한다.

### 1.3 본 문서 범위

| 포함 (Map-A) | 제외 · 후속 (Profile-B · 별도 과제) |
|------|-------------------------|
| 지도 UX·경계·줌·패닝·인접 복수 선택 | Regional Profile **파이프라인 재구축** (카드 연동 선행) |
| 좌측 `RegionSelector` ↔ 지도 **양방향 동기화** | GeoJSON **수집·적재 SOP** (VWorld 프록시로 1차 대체) |
| 법정동·리까지 **전 행정 레벨** 경계 표시 원칙 | VWorld 쿼터·캐시·shard 최적화 (차후) |
| 토지 우선 → 복합·집합 **동일 UX 패턴** (원칙만) | 복합·집합 addr 매핑·인접 상세 (토지 PoC 후) |
| **Profile 없이** placeholder 카드·지도 Hub | Hub 카드 **Profile 기본정보** (Profile-B) |
| 통계 매트릭스·회귀·차트 | 조회 **후** 기존 Free/Paid 패널 (변경 없음) |

> 본 문서는 구상에 따라 **계속 수정**한다.

---

## 2. 구현 단계 — Map-A / Profile-B

**Profile 재구축을 기다리지 않고** 지도 Hub를 먼저 도입한다. 카드의 Profile 데이터만 2단계로 미룬다.

### 2.1 Map-A (지금 — Profile 비의존)

| 항목 | 내용 |
|------|------|
| **목표** | 조회 전 dead screen 해소, 1차 선택 → 지도·경계·클로즈업, 유료 인접 복수 추가 |
| **베이스맵** | VWorld 위성 타일 (`VITE_VWORLD_API_KEY` / 백엔드 `VWORLD_API_KEY`) |
| **경계** | 백엔드 `/api/map/boundaries` — VWorld Data API 프록시 |
| **카드** | `RegionMapCard` placeholder (선택 목록·안내 문구) |
| **1차 선택** | 좌측 `RegionSelector` only |
| **추가 선택** | 유료만, 지도 **우클릭** → 인접 검사(`@turf/boolean-touches`) → `tierSelection` 동기화 |
| **무료** | 지도 열람·클로즈업, 우클릭 추가 불가 |
| **프로필 탭** | 기존 `ProfilePanel` 유지 (Hub와 분리) |

### 2.2 Profile-B (후속 — 카드·API)

아래 완료 후 Hub 카드를 Profile 데이터로 교체한다.

1. **전국 `regional_profile` 재구축** — grain·feature가 **법정동·리(`beopjungri`)** 와 1:1
2. **쌍둥이 도시 찾기** 제품 경로 (전국 Profile 소비 Twin)
3. Hub 카드 필드·API 확정 — 인구·토지 시장 요약 등 (`§4`)

> 현재 UI의 읍면동 승격(`resolveProfileRegionFromTier`)은 **임시**이며, Profile-B에서 `beopjungri` 직접 조회로 교체한다.

---

## 3. 행정구역 SSOT

### 3.1 토지 — 선택·경계 단위

| 항목 | SSOT |
|------|------|
| 토지 거래·무료/유료 필터 | `beopjungri_code` (10자리) |
| `region_codes` | `beopjungri_code` UNIQUE |
| 지도 **경계선** | 초기 선택 **행정 레벨**에 맞는 polygon (`beopjungri_code` 등 join) |
| Hub **프로필 조회** | 재구축 Profile (목표: `region_level=beopjungri`) |

**최하위 레벨(법정동·리)까지** 행정구역 경계가 구분되어야 한다.  
동(8자리+`00`)·리(10자리) 모두 `beopjungri_code` 로 표현한다.

### 3.2 제품별 grain (Hub 카드)

| 제품 | 분석 grain | Hub 1차 적용 | 비고 |
|------|-----------|-------------|------|
| **토지** | 법정동·리 | ✅ 우선 PoC | 인구 + 토지 요약 |
| **복합부동산** | addr + 건물 특성 | **계획 문서화** | 상세: [`BUILT_MAP_HUB_PLAN.md`](./BUILT_MAP_HUB_PLAN.md) (addr↔코드·Phase Built-M0~M4) |
| **집합부동산** | `building_key` 등 | 토지·복합 후 | 동일 패턴 검토 (**미정**) |

복합 지도 이식은 **토지 Map-A 안정화 후** [`BUILT_MAP_HUB_PLAN.md`](./BUILT_MAP_HUB_PLAN.md) Phase를 따른다. 집합은 복합 이후 별도 문서화.

### 3.3 복수 선택 — 공통 규칙

| 규칙 | 내용 |
|------|------|
| **동일 레벨** | 복수 선택은 **항상 동일 행정구역 레벨**에서만 (시군구끼리, 읍면동끼리, 법정동·리끼리) |
| **1차 선택** | **왼쪽 `RegionSelector`에서만** (검색·Enter·tier 칩) |
| **추가 선택** | **유료만** — **지도**에서 인접 지역 추가 |
| **개수·tier** | 기존 `RegionSelector` 로직 준수 (D-010, `MAX_PAID_LEAF_BEOPJUNGRI_PICK` 등) |
| **인접** | **지도상 옆에 붙어 보이면 인접** (사용자 기준). **코드 구현 방식 미정** |
| **무료** | 지도 **클로즈업·프로필 열람** 가능, **지도에서 추가 선택 불가** |
| **혼합 tier** | 상위(시도·시군구) + 하위(법정) **혼합 복수**는 기존 RegionSelector 정책 그대로 |

- **지도:** 선택된 scope polygon **동시 highlight**, 1차 선택 중심 **클로즈업**
- **카드:** 복수 선택 시 표시 규칙 — Profile API·재구축과 함께 확정 (차후)

---

## 4. Hub 카드 — 표시 규칙 (목표)

Profile 재구축 **이후** 기본정보를 표시한다. **구체 필드·문구는 Profile 작업 완료 후 확정.**

### 4.1 방향 (확정 전 초안)

- **행정명** (전체 경로)
- **인구** (Profile 또는 `population_stats` — SSOT 따름)
- **토지 시장 요약** (Top-N 용도×지목 등 — Profile과 동일 키)
- **면적(㎢)** · 집합·아파트·복합 market · AI 문단 — **Hub 1차 제외 또는 후속**

### 4.2 “시장 특징” / AI

- Profile·Twin·AI 리포트 연동 — **후속**

---

## 5. 지도 UX

### 5.1 표시·줌 원칙

**고정된 “부모 행정구역 범위”를 미리 정할 필요는 없다.**

| 항목 | 규칙 |
|------|------|
| **초기 프레이밍** | 1차 선택 지역이 **화면 중앙**, 해당 행정구역 **너비 약 15cm** 전후 |
| **경계 레이어** | 1차 선택과 **동일 행정 레벨**의 경계선 표시 (예: 읍면 선택 → 읍면 경계 격자) |
| **카드** | 같은 패널에서 **지역 프로필 기본정보** 표시 가능할 만큼 지도 높이 확보 (약 45~55%) |
| **전국 드라마틱 줌** | 앱 최초 진입 시 전국 뷰(시군구 라벨) **가능** — 1차 선택 후 위 15cm 규칙으로 전환 |
| **휠 줌** | 사용자가 **자유롭게** 확대·축소 |
| **선택 레벨** | 휠 줌과 **무관** — 복수 추가는 **1차 선택과 동일 행정 레벨**만 |

### 5.2 베이스맵·레이어

| 항목 | 방침 |
|------|------|
| **타일·지도 서비스** | **VWorld** (위성·일반지도·경계 등 — **레이어 조합 미정**) |
| **경계 오버레이** | 행정구역 polygon — join 키는 레벨별 SSOT (`beopjungri_code` 등) |
| **식별 목적** | 위성으로 **도시화·농지·임야** 등 지역 성격을 **눈으로** 확인 |

### 5.3 포인터·제스처

| 동작 | 동작 |
|------|------|
| **좌클릭 드래그** | 지도 **패닝** (동일 축척에서 상하·좌우 이동) |
| **휠** | 줌 인·아웃 |
| **우클릭** (유료, 인접·동일레벨·한도 내) | **「분석 지역을 추가할까요?」** 확인 (추가 확정) |
| **비인접·무료·한도 초과** | 피드백 방식 **미정** (토스트·메뉴 비활성 등) |
| **선택 해제** | 좌측 칩 삭제 ↔ 지도 highlight 해제 (**양방향 동기화**) |

> 좌클릭으로 지역을 **직접 토글 선택**하지 않는다 — **우클릭 확인**으로 추가한다.

### 5.4 좌측 ↔ 지도 흐름

```
[1] 좌측 RegionSelector — 1차 지역 선택 (검색·tier)
        ↓
[2] Hub — 동일 레벨 경계 표시 + 1차 지역 클로즈업 (~15cm) + highlight
        ↓
[3] Hub — Profile 기본정보 카드 갱신 (Profile API 준비 후)
        ↓
[4] (유료) 지도 우클릭 — 인접·동일레벨 지역 추가 → 좌측 tierSelection 동기화
        ↓
[5] 사용자 — 기본 통계 / 필터 분석 실행
        ↓
[6] 기존 FreeStats / Paid 패널 — 통계·매트릭스 (Hub 유지)
```

- **조회 전**에도 1차 선택만으로 **지도 + 카드** 갱신 (Profile API 준비 후)
- **통계 본문**은 기존 UX; Hub는 조회 전·후 **유지**

### 5.5 레이아웃 (와이어)

```
┌─────────────────────────────────────────┐
│  Map (VWorld + 행정 경계)                 │
│    · 1차 선택 highlight (fill)           │
│    · 복수 선택 시 추가 highlight          │
│    · 동일 레벨 인접 경계 (클릭 후보 시각)   │
├─────────────────────────────────────────┤
│  RegionProfileCard                       │
│    · 행정명 · 인구 · (Profile 기본정보)    │
└─────────────────────────────────────────┘
```

---

## 6. 경계 데이터 — 설계 메모 (미정)

구현 시 과제. **원칙만 고정.**

| 항목 | 방침 |
|------|------|
| Join 키 (토지) | `beopjungri_code` (10자) = `region_codes.beopjungri_code` |
| 레벨 | 시도·시군구·읍면동·법정동·리 — **레벨별 polygon** (상세 스키마 **미정**) |
| 인접 | 사용자 기준 **지도상 접촉**; polygon touch vs **인접 테이블** — **구현 미정** |
| 배포 | 전국 단일 파일 비권장 — shard·뷰포트 로드 등 **미정** |
| 출처 | VWorld·행정안전부 등 — **미정** |

---

## 7. 현재 코드와의 차이 (재구축 시 정리)

| 현재 | Hub 목표 |
|------|----------|
| `resolveProfileRegionFromTier`: beop → 읍면동 **승격** (임시) | **`beopjungri` Profile 직접 조회** |
| `ProfilePanel`: 별도 탭 + 「프로필 조회」 버튼 | **오른쪽 Hub 상시 표시** |
| `PaidIntro` / 무료 조회 전: **빈 패널** | **`RegionMapHub` + 카드** |
| 지도 선택 **없음** | 유료: **인접·동일레벨** 지도 추가 |
| Profile feature: domain 집계 위주 | **beop + Profile 기본정보** (재구축) |

---

## 8. 구현 Phase

| Phase | 내용 | 상태 |
|-------|------|------|
| **Map-A1** | 백엔드 VWorld config + `/api/map/boundaries` 프록시 | **진행** |
| **Map-A2** | `RegionMapHub` — 타일·경계·15cm fit·highlight·placeholder 카드 | **진행** |
| **Map-A3** | 유료 우클릭 인접 복수 → `tierSelection` 동기화 | **진행** |
| **Map-A4** | `App.tsx` 통합 (무료·유료·조회 전 Hub 상시) | **진행** |
| **Profile-B0** | 전국 `regional_profile` (beop grain) + Twin | 대기 |
| **Profile-B1** | Hub 카드 Profile API·필드 연동 | 대기 |
| **Profile-B2** | 복합·집합 동일 UX 패턴 이식 | **복합: 계획 문서화** → [`BUILT_MAP_HUB_PLAN.md`](./BUILT_MAP_HUB_PLAN.md) · 집합: 후속 |

---

## 9. 성공 기준 (토지 Hub MVP)

1. 1차 선택 시 **동일 레벨 경계** + **~15cm 클로즈업** + highlight
2. **법정동·리**까지 경계 구분 가능 (해당 레벨 선택 시)
3. 카드에 **Profile 기본정보** (Profile 재구축 데이터)
4. **유료:** 인접·동일레벨 **지도 추가** → 좌측·통계 scope 일관
5. **무료:** 지도 열람만, 추가 선택 불가
6. 조회 전 dead screen **해소**

---

## 10. 미정 · 차후 논의

- 인접 판정 **구현** (polygon topology vs 사전 테이블)
- VWorld 레이어·키·쿼터·캐시
- GeoJSON shard·API 형태
- 복합·집합: addr 레벨별 인접·복수 선택 상세 → **복합은 [`BUILT_MAP_HUB_PLAN.md`](./BUILT_MAP_HUB_PLAN.md) §5·§6 로 이관** (집합 미정)
- 복수 선택 시 **카드** UI (목록 vs 합산 vs 탭)
- 비인접 클릭·한도 초과·선택 해제 우클릭 UX
- 전국 초기 뷰 vs 빈 지도 진입

---

## 11. 관련 문서

| 문서 | 관계 |
|------|------|
| [`REGIONAL_PROFILE_ARCHITECTURE.md`](./REGIONAL_PROFILE_ARCHITECTURE.md) | Profile 5-Layer, feature SSOT |
| [`REGION_ARCHITECTURE_ROADMAP.md`](./REGION_ARCHITECTURE_ROADMAP.md) | beop vs eup grain, Post-MVP Region |
| [`TWIN_V8_DESIGN.md`](./TWIN_V8_DESIGN.md) | Twin (Profile 소비) |
| [`UPPER_STATS_DESIGN.md`](./UPPER_STATS_DESIGN.md) | 상위·쌍둥이 (유료) |
| [`DECISIONS.md`](./DECISIONS.md) D-010 | 행정 레벨·유료 복수 정책 |
| [`BUILT_MAP_HUB_PLAN.md`](./BUILT_MAP_HUB_PLAN.md) | 복합 Map Hub 이식 계획 (Built-M0~M4) |

---

## 변경 이력

| 일자 | 내용 |
|------|------|
| 2026-06-25 | 초안 — Map Hub 범위, beop 경계·카드 규칙, Profile/Twin 선행 후 구현 |
| 2026-07-09 | 인터랙티브 인접 복수 선택·VWorld·15cm 클로즈업·동일레벨·무료/유료·패닝/우클릭 UX 반영; 복합·집합 원칙 추가 |
| 2026-07-09 | **Map-A / Profile-B** 2단계 분리 — Profile 선행 없이 지도 Hub PoC 시작; §2·§8 재정의 |
| 2026-07-11 | 복합 지도 이식 → [`BUILT_MAP_HUB_PLAN.md`](./BUILT_MAP_HUB_PLAN.md) 분리 문서화; §3.2·Profile-B2·§10 갱신 |
