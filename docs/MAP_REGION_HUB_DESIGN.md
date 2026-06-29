# CH2 Macro — Map + Region Hub (토지) 설계

> **상태:** **설계 확정 · 구현 보류**  
> **구현 시점:** **전국 Regional Profile 재구축** 및 **쌍둥이 도시 찾기** 제품화 이후  
> **관련:** [`DECISIONS.md`](./DECISIONS.md) D-026 · [`REGIONAL_PROFILE_ARCHITECTURE.md`](./REGIONAL_PROFILE_ARCHITECTURE.md) · [`REGION_ARCHITECTURE_ROADMAP.md`](./REGION_ARCHITECTURE_ROADMAP.md) · [`TWIN_V8_DESIGN.md`](./TWIN_V8_DESIGN.md)

---

## 1. 목표

### 1.1 문제

토지 통계 화면(무료/유료)에서 **조회 전 오른쪽 패널이 비어** dead screen처럼 보인다.  
사용자는 프로그램을 열자마자 **「어디인지 → 그 지역이 어떤 시장인지 → 통계 조회」** 순으로 경험하는 것이 자연스럽다.

### 1.2 제품 목표 (Map + Hub)

오른쪽 빈 공간을 **지도 + 지역 프로필 카드** 로 채운다.

- **지도:** 선택 행정구역 **모양 식별** (어디인지 감)
- **카드:** 해당 scope의 **요약 수치** (프로필 DB 기반, 법정리 레벨 규칙 §4)

**본 설계는 “지도 앱”이 아니라 “Region Profile을 받치는 Hub”** 이다.  
상단 **「지역 프로필」** 탭은 Hub의 **확장 뷰**(브라우저·쌍둥이·AI 리포트 등)로 점진 연결한다.

### 1.3 본 문서 범위

| 포함 | 제외 (별도 과제) |
|------|------------------|
| 지도 UX·줌·경계·레이아웃 | Regional Profile **파이프라인 재구축** (선행) |
| 법정리 레벨 Hub 카드 **표시 규칙** | 전국 GeoJSON **수집·적재 SOP** (구현 시 상세) |
| 구현 **보류 조건** | 쌍둥이 알고리즘·API 상세 (기존 Twin 문서) |
| | 통계 매트릭스·회귀·차트 (조회 **후** 기존 패널) |

---

## 2. 선행 조건 (구현 보류)

아래가 완료되기 전 **Map Hub 프론트·API 구현을 시작하지 않는다.**

1. **전국 `regional_profile` 재구축**
   - grain·feature 정의가 **법정동·리(`beopjungri`)** 선택과 1:1로 맞아야 함
   - 현재 UI의 읍면동 승격(`resolveProfileRegionFromTier`)은 **임시 동작**이며, Hub SSOT와 불일치 → **Profile 재구축 후 교체**

2. **쌍둥이 도시 찾기** 제품 경로 정리 (전국 Profile 소비 Twin)

> **참고:** `frontend`에 `react-map-gl` 의존성만 선행 추가되어 있음. **컴포넌트·GeoJSON·API는 미구현.**

---

## 3. 행정구역 SSOT — 법정동·리

### 3.1 선택 단위

| 항목 | SSOT |
|------|------|
| 토지 거래·무료/유료 필터 | `beopjungri_code` (10자리) |
| `region_codes` | `beopjungri_code` UNIQUE |
| 지도 **경계선** | **법정동·리** polygon (`beopjungri_code` join) |
| Hub **프로필 조회** | 재구축 Profile의 **`region_level=beopjungri`** (목표) |

**법정리(리) 단위까지 선택 가능해야 한다.**  
동(8자리+`00`)·리(10자리) 모두 `beopjungri_code` 로 표현한다 (`db/001_init.sql` 주석).

### 3.2 집합부동산과 레벨 분리

| 제품 | Profile / market grain | Hub 카드 |
|------|----------------------|-----------|
| 토지 | **법정동·리** | 인구 + **토지** |
| 집합부동산 | **읍면동** (`market_stats` 등) | **Hub MVP 미포함** |

집합 건물·아파트 시장 지표는 **읍면동 수준을 차용**한다.  
**법정리 scope에서는 집합·아파트 블록을 Hub 카드에 넣지 않는다** (오해·데이터 grain 불일치 방지).

### 3.3 복수 선택

- **지도:** 선택된 `beopjungri_code` 목록의 polygon을 **동시 highlight**, bbox fit
- **카드:** 복수 법정리·상위 행정과 **혼재** 시 규칙은 Profile 재구축 시 확정 (MVP Hub는 **단일 beop 또는 동일 읍·면·동 내 단일 beop** 우선)

---

## 4. Hub 카드 — 법정리 레벨 표시 규칙 (목표)

Profile 재구축 **이후** 아래만 표시한다. **면적(㎢)은 제공하지 않는다** (행정 GIS 면적 미보유·계산 범위外).

### 4.1 MVP 카드 필드

```
{시도} {시군구} {읍면동} {법정동/리명}

인구              {population}명

토지시장 (최근 window_years)
  ① {용도지역} × {지목}   {count}건   평균 {mean}만원/㎡
  ② …
  ③ …
```

- **인구:** `population_stats` (법정리 또는 Profile feature — 재구축 SSOT 따름)
- **토지:** Profile feature 또는 `land_upper_stats_v2` / Top-N 용도×지목 셀 (재구축 Profile과 **동일 키**)
- **제외:** 행정구역 **면적**, 집합·아파트·복합 market, AI 문단, 쌍둥이 비교 (후속)

### 4.2 “시장 특징” bullet / AI 문단

- **Hub MVP:** 미포함
- **후속:** Profile feature + 템플릿 → AI 지역 리포트 (`ProfilePanel` 확장)

---

## 5. 지도 UX

### 5.1 원칙 — 크게 확대하지 않음

**대한민국 → 시도 → … 단계적 드라마틱 확대는 필요 없다.**

| 항목 | 규칙 |
|------|------|
| 패널 | 오른쪽 **고정 높이** (지도 약 45~55%, 아래 카드) |
| 줌 | 선택 polygon **bbox 1회 fit** + padding |
| 목표 크기 | 화면에서 선택 구역이 **약 8~12cm(10cm 전후)** 로 식별 가능하면 충분 |
| 맥락 | 전국·시도 **대확대 금지**; 필요 시 **연한 상위 outline** 1~2단계만 |

### 5.2 시각 레이어 (3단계 — 구현 우선순위)

| 단계 | 내용 | Hub MVP |
|------|------|---------|
| **1** | 법정동·리 **경계선** + 선택 **채우기** | ✅ 필수 |
| **2** | OSM / VWorld **베이스맵**(도로 맥락) | ✅ 권장 (타일 교체 가능) |
| **3** | 말풍선 오버레이(거래·인구 요약) | ❌ 후속 |

베이스맵은 **식별 보조**; highlight는 **자체 GeoJSON**(법정구역) SSOT.

### 5.3 좌측 연동

```
좌측 RegionSelector — beopjungri 선택 변경
        ↓
Hub — 해당 code polygon highlight + fitBounds
        ↓
Hub — Profile API (beopjungri) → 카드 갱신
        ↓
(사용자) 기본 통계 / 필터 분석 실행
        ↓
기존 FreeStats / Paid 패널 — 통계·매트릭스 (Hub 유지 또는 하단 스크롤)
```

- **조회 전**에도 지역만 고르면 **지도 + 카드 자동 갱신** (별도 「프로필 조회」 버튼 불필요 — Profile API 준비 후)
- **통계 본문**은 기존 UX; Hub는 **조회 전·후 모두** 유지 가능

### 5.4 레이아웃 (와이어)

```
┌─────────────────────────────────────────┐
│  Map (고정 영역)                         │
│    · 연한 주변/상위 경계 (선택)           │
│    · 선택 beop polygon (fill)            │
├─────────────────────────────────────────┤
│  RegionProfileCard                       │
│    · 행정명 (beopjungri)                 │
│    · 인구                              │
│    · 토지 Top3 (용도×지목)               │
└─────────────────────────────────────────┘
```

---

## 6. 경계 데이터 (GeoJSON) — 설계 메모

구현 시 과제. **본 문서는 원칙만 고정.**

| 항목 | 방침 |
|------|------|
| Join 키 | `beopjungri_code` (10자) = `region_codes.beopjungri_code` |
| 동 vs 리 | 동: 8자리+`00`, 리: 10자리 전체 |
| 배포 | **전국 단일 파일 비권장** — 시도별 shard 또는 **선택 code만** fetch |
| 출처 | 행정안전부 법정구역 등 (구현 시 출처·갱신 주기 문서화) |

---

## 7. 현재 코드와의 차이 (재구축 시 정리)

| 현재 | Hub 목표 |
|------|----------|
| `resolveProfileRegionFromTier`: beop만 선택 시 **읍면동 8자리로 승격** | **`beopjungri` Profile 직접 조회** |
| `ProfilePanel`: 별도 탭 + 「프로필 조회」 버튼 | **오른쪽 Hub 상시 표시** |
| `PaidIntro`: 빈 카드 | **`RegionMapHub` 로 교체** |
| Profile feature: domain 집계 위주 | **beop Top-N 용도×지목 + 인구** (재구축) |

---

## 8. 구현 Phase (보류 — 순서만)

| Phase | 내용 | 상태 |
|-------|------|------|
| **P0** | 전국 `regional_profile` (beop grain) + Twin | **선행** |
| **P1** | GeoJSON ingest + `beopjungri` join 검증 | 대기 |
| **P2** | `RegionMapHub` + `RegionProfileCard` (토지 App 오른쪽) | 대기 |
| **P3** | 베이스맵·다크모드·말풍선·Profile 탭 통합 | 후속 |

---

## 9. 성공 기준 (Hub MVP 완료 정의)

1. 법정동·**리** 선택 시 지도에 **해당 polygon** 표시 (~10cm 식별)
2. 같은 scope에서 카드에 **인구 + 토지 Top3** (Profile 재구축 데이터)
3. **집합·아파트·면적** 미표시
4. 조회 전 dead screen **해소**
5. 「기본 통계 보기」 후 통계 패널과 **동일 beop scope** 일관성

---

## 10. 관련 문서

| 문서 | 관계 |
|------|------|
| [`REGIONAL_PROFILE_ARCHITECTURE.md`](./REGIONAL_PROFILE_ARCHITECTURE.md) | Profile 5-Layer, feature SSOT |
| [`REGION_ARCHITECTURE_ROADMAP.md`](./REGION_ARCHITECTURE_ROADMAP.md) | beop vs eup grain, Post-MVP Region |
| [`TWIN_V8_DESIGN.md`](./TWIN_V8_DESIGN.md) | land_cells, Twin (Profile 소비) |
| [`UPPER_STATS_DESIGN.md`](./UPPER_STATS_DESIGN.md) | 상위·쌍둥이 (유료) |
| [`DECISIONS.md`](./DECISIONS.md) D-010, D-026 | 행정 레벨 정책, Map Hub 보류 |

---

## 변경 이력

| 일자 | 내용 |
|------|------|
| 2026-06-25 | 초안 — Map Hub 범위, beop 경계·카드 규칙, Profile/Twin 선행 후 구현 |
