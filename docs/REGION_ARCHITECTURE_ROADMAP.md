# Region · Property 아키텍처 — 장기 과제 (Post-MVP)

> **상태:** 보류 — **현재 MVP(토지·복합·집합 기능 완성) 우선**. 본 문서는 구조 개선 논의·설계 참고용이다.  
> **재논의 시점:** 2026년 6월 말 수정 반영 후, **7월 정기 업데이트 전** 전반적 구조 개선 회의.  
> **관련 결정:** [`DECISIONS.md`](./DECISIONS.md) D-014

---

## 1. 배경

CH2 Macro는 제품·유형별로 **분석 단위(analysis grain)** 가 다르다. 이는 의도된 설계다.

| 제품 | 분석 단위 (Grain) | 비고 |
|------|-------------------|------|
| 토지 | `beopjungri_code` (10자) | 거래 밀도 높음, 동·리 단위 의미 있음 |
| 복합부동산 | 주소(addr) + 건물 특성 | `built_transactions`, addr 기반 API |
| 집합부동산 | `building_key` | 단지·건물 단위 |
| 집합상가 | `cluster_key` (도로·상권) | 표본 희소 → 상권 해상도 |

**「사용자가 지역을 선택하는 방식(Region)」** 과 **「통계가 쌓이는 단위(Grain / Property)」** 는 별개 개념이다.  
Post-MVP에서는 이 둘을 명시적으로 분리하고, 장기적으로 **Property Registry** 를 플랫폼 SSOT로 올리는 방향을 검토한다.

---

## 2. 목표 아키텍처 (참고 — 미구현)

### 2.1 5층 모델

```
Region (Scope)      — 사용자가 “어디”를 고르는가
    ↓
Resolution          — Scope → 필터·Property 후보·fallback grain
    ↓
Property (Entity)   — 분석·외부 데이터 연결의 “무엇”
    ↓
Transaction (Fact)  — 거래 원장
    ↓
Statistics          — 집계·추세·회귀
```

### 2.2 SSOT 이원

| SSOT | 역할 | 현재 |
|------|------|------|
| **Admin Vocabulary** | `region_codes` — 행정 코드·명칭 | land_stats, built/collective에 복제 |
| **Property** | 필지·건물·단지·상권 cluster 등 **엔티티 허브** | **미구축** — `building_key` 등 분산 ID만 존재 |

장기 비전: 건축물대장·공시지가·인구·상권·AI 추천·쌍둥이 도시 등을 **Property Registry** 에 attach → “통계 앱”에서 “부동산 데이터 플랫폼”으로 확장.

---

## 3. 설계 원칙 (Post-MVP 확정 예정)

| ID | 원칙 | 요약 |
|----|------|------|
| P1 | One Vocabulary, Many Grains | 행정은 `region_codes` 하나, grain은 제품별 |
| P2 | Region ≠ Property | Scope vs 분석 대상 분리 |
| P3 | Resolve, Don’t Re-aggregate | 새 Region 타입은 filter predicate로, 원장 재적재 최소 |
| P4 | Product Declares Grain Policy | primary grain, fallback, min_n 제품별 선언 |
| P5 | Stable Grain IDs, Versioned Keys | `building_key_v2` 등 mapping table |
| P6 | Land SoT for Admin Codes | `region_codes` master = land_stats only |
| P7 | Additive API Evolution | `scope_id` 등 additive, legacy 파라미터 유지 |
| P8 | Explicit Escalation | n 부족 시 grain 상향 (upper stats / cluster / eup rollup) |
| P9 | Property First | Region / Property / Transaction / Statistics 4분법 |
| P10 | Property Registry as Platform SSOT | 외부·cross-product join의 허브 |

---

## 4. 단계별 로드맵 (Post-MVP)

### v1 — 명문화·얇은 연결 (MVP 직후)

- [ ] 본 문서·DECISIONS 확정본 반영
- [ ] `product_grain_policy` 상수 또는 yaml (DB 불필요 가능)
- [ ] built/collective ingest: land `map_beopjungri_codes` **공유 모듈** 검토
- [ ] 세종 등 특수 주소 → annual/upper **재빌드 checklist** 운영 SOP화
- [ ] **하지 않음:** 통합 RegionSelector, Property Registry DB, unified mart

### v2 — Region Resolution + Property Registry (read → canonical)

- [ ] `property_entity` + `property_alias` (legacy `building_key` 매핑)
- [ ] `POST /api/region/resolve` — scope → predicates + property candidates
- [ ] 집합 `/buildings` = registry query 로 **개념 정렬** (adapter, API 하위 호환)
- [ ] cross-product: 동일 eup scope → 토지·집합 탭 전환 (beopjungri join)
- [ ] **규칙:** 신규 cross-product 기능은 registry 경유

### v3 — Property SSOT · 플랫폼 허브

- [ ] `building_register_title` 적재 → Property enrich ([`BUILDING_REGISTER_ROADMAP.md`](./BUILDING_REGISTER_ROADMAP.md))
- [ ] 공시지가·인구·상권 → Property edge / attrs
- [ ] AI 사용자 정의 Region = saved scope; 유사 단지 = Property similarity ([`TWIN_REGION_SIMILARITY_ENGINE.md`](./TWIN_REGION_SIMILARITY_ENGINE.md) 연계)
- [ ] optional: geometry scope (생활권 polygon)

---

## 5. MVP 기간 중 **하지 않을 것**

- Property Registry 테이블·API 신규 구축
- 토지·집합·복합 **Region UI 통합**
- 단일 unified stats mart
- `region_code_history` backfill ([`LONG_TERM_TREND_DESIGN.md`](./LONG_TERM_TREND_DESIGN.md) §2.3 장기 과제는 그대로)
- 집합 grain을 beopjungri로 **통일**

---

## 6. MVP 기간 중 **유지·소폭 개선** (현재 코드 충실)

| 항목 | 내용 |
|------|------|
| 토지 | `beopjungri` + upper stats + 장기추세 annual 마트 — **운영 안정화** |
| ingest | `clean.py` / remap 스크립트, CSV 검증, 시도별 annual rebuild |
| 집합·복합 | addr API + `building_key` / `cluster_key` — **기존 MVP 기능 완성** |
| 버그fix | 상위지역 선택 시 paid API 8자↔10자 코드 등 **제품 버그만** |

---

## 7. 7월 업데이트 전 논의 안건 (체크리스트)

- [ ] MVP 완료 범위 확정 (토지 / built / collective / commercial 각 “done” 정의)
- [ ] v1 착수 여부 — Property Registry를 v2 read model vs 즉시 SSOT 설계
- [ ] Admin SSOT(`region_codes`) vs Property SSOT 경계 최종 확정
- [ ] cross-product Region picker 통합 우선순위
- [ ] `BUILDING_REGISTER_ROADMAP` 과 Property Registry 일정 정렬
- [ ] twin region · AI scope 와 Resolution layer 연결 방식

---

## 8. 관련 문서

| 문서 | 관계 |
|------|------|
| [`UPPER_STATS_DESIGN.md`](./UPPER_STATS_DESIGN.md) | 토지 상위 행정 Region + 사전집계 |
| [`LONG_TERM_TREND_DESIGN.md`](./LONG_TERM_TREND_DESIGN.md) | 장기추세 · 행정 이력 (별도 장기) |
| [`BUILDING_REGISTER_ROADMAP.md`](./BUILDING_REGISTER_ROADMAP.md) | Property SSOT 데이터 소스 |
| [`TWIN_REGION_SIMILARITY_ENGINE.md`](./TWIN_REGION_SIMILARITY_ENGINE.md) | 쌍둥이 · 유사 Property |
| [`COLLECTIVE_COMMERCIAL_DESIGN.md`](./COLLECTIVE_COMMERCIAL_DESIGN.md) | cluster grain · 2-tier |

---

*최초 작성: 2026-06 — MVP 우선 보류 결정. Cursor·GPT 아키텍처 검토 합의본 요약.*
