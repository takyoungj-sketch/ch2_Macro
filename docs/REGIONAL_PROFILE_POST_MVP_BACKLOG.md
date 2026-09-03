# Regional Profile · 쌍둥이 지역 — MVP 완료 & Post-MVP 백로그

> **작성:** 2026-07-28  
> **상태:** **MVP 동결** — 신규 대형 개발 보류, 실사용(feedback) 기반 수정  
> **설계 SSOT:** [`REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) §12  
> **Twin 엔진:** [`PROFILE_TWIN_HYBRID.md`](PROFILE_TWIN_HYBRID.md) §7 (Profile-native v2.1)

---

## 1. MVP 완료 범위 (2026-07-28 기준)

### 1.1 지역 프로필 (Phase A)

| 항목 | 내용 |
|------|------|
| grain | 시·도 · city · 시군구 · 읍·면·동 · **법정리(동·리)** |
| 버전 | `profile_version=v2.1-national`, **`window_years=3`만** |
| Feature | 인구 · 8대 시장 `yearly_mix` · 대표시장 · 토지 Top1~3 · beop 아파트 P25/P50/P75 (≥15건) |
| UI | 독립 `/profile/` · 토지와 **동일 region-picker** · beop grain 유지 |
| 데이터 | 전국 ~23,931 profile rows (재빌드 2026-07-27) |

### 1.2 쌍둥이 지역 (Phase B)

| grain | API | 배치 (algo 21) |
|-------|-----|----------------|
| 읍·면·동 | `GET /api/regional-profile/twins/{eup8}` | `twin_eupmyeondong_neighbor_mvp` · scope=**region**(권역) |
| 시군구 | `GET .../twins-sigungu/{sg5}` | `twin_region_neighbor_mvp` · scope=**national** |
| 법정리 | `GET .../twins-beop/{beop10}` | `twin_neighbor_v8` · scope=**same_sigungu** |

- 파이프라인: **Candidate → Catalog → Vector → Weight → Similarity → Top-N**
- 설정: `profile_feature_catalog.yaml` (`twin_vector`) + `profile_weight.yaml`
- 빌더: `pipeline/build_twin_profile.py` · orchestrator `--twin-mode catalog`(기본)
- 스모크: `python pipeline/verify_profile_twin_smoke.py`

### 1.3 MVP 비범위 (의도적)

- **시·도 / city grain Twin** — 없음
- **레벨 혼합** (읍↔시군구) — 없음
- **Profile 5년 window** — 제품 SSOT 3년만
- **scope UI 토글** (권역/인접/전국) — API·배치 메타만, UI 미노출
- **회귀 pooling · AI Twin 제안** — 후속 Phase
- **Legacy hybrid v6/v7 · Twin v8 제품 경로** — fallback/병행만 (제거 일정 미정)

---

## 2. 운영 원칙 (MVP 동결 이후)

1. **구조 변경 금지** — Candidate / Catalog / Weight / Similarity 경계 유지. 튜닝은 YAML·Catalog version bump.
2. **버그·명백한 UX 결함** — 즉시 수정 가능.
3. **「쌍둥이가 이상하다」** — 우선 **가중치·후보 scope** 의심 → §4 이슈 템플릿으로 기록 후 일괄 튜닝.
4. **연간 갱신 (D-054)** — 매년 초 1회 Profile 재빌드 후 Twin·rank 같은 스냅샷 + `verify_profile_twin_smoke.py`. 월간 토지/복합/집합 사이클에 넣지 않는다 ([`MONTHLY_UPDATE_CHECKLIST.md`](MONTHLY_UPDATE_CHECKLIST.md) §7).

---

## 3. 실사용(feedback) 체크리스트

사용하며 아래를 메모해 두면 Phase C 튜닝 입력이 된다.

### 3.1 지역 선택 · Profile

- [ ] 토지에서 고른 grain과 Profile URL grain 일치 (실제 리 → beop. 리가 없는 동 `…00` → eup, D-057)
- [ ] loose 주소·Enter (예: `옥천읍 마암리`) 정상 확정
- [ ] city(청주시 등) · sigungu · eup · beop 각각 population·yearly_mix·Top3·아파트 분위 표시
- [ ] 아파트 표본 <15 리: 분위 `-` / mask 동작
- [ ] 대표시장 카드 · 딥링크 (토지/집합/built)

### 3.2 쌍둥이 지역

- [ ] **동·리** (가경동 등): 법정리 Twin 카드 + 동일 시군구 후보
- [ ] **읍·면** (옥천읍 등): 권역 내 유사 읍·면·동
- [ ] **시군구**: 전국 유사 시군구
- [ ] 설명 태그 (`score_detail.features` note)가 직관적인지
- [ ] 「말이 안 되는」 1위 후보 — anchor grain·scope·인구 필터·대표시장 가감점 중 원인 추정

### 3.3 샘플 앵커 (스모크 외 QA용)

| 지역 | grain | code | 메모 |
|------|-------|------|------|
| 가경동 | beop | `4311311300` | 청주 아파트 중심 동 |
| 옥천읍 | eup | `43730250` | 충북 읍 단위 |
| 옥천읍 마암리 | beop | `4373025034` | 리 + apt 분위 |
| 청주 흥덕구 | sigungu | `43111` | 시군구 Twin |
| 청주시 | city | `43110` | Twin **없음** (정상) |

---

## 4. 이슈 기록 템플릿

GitHub 이슈·로컬 메모·`NEXT_STEPS.md` §2b 하단에 아래 형식 권장.

```text
[Profile|Twin] 앵커: {이름} ({region_level}/{code})
기대: …
실제: …
grain/scope: eup|beop|sigungu · region|national|same_sigungu
추정 원인: 가중치 | scope | mask | 데이터 | UI | API
우선순위: P0 버그 | P1 튜닝 | P2 nice-to-have
```

---

## 5. Post-MVP 백로그 (착수 보류 · 우선순위만)

> **Phase C 이하는 MVP 동결 중 일괄 착수하지 않음.** §3·§4 피드백이 쌓이면 항목을 골라 진행.

### Phase C — 튜닝 · UX (피드백 충분 시)

| # | 항목 | 메모 |
|---|------|------|
| C1 | **`profile_weight.yaml` v1.1** | 블록 비율·대표시장 가감점 · §3 샘플 QA |
| C2 | Candidate 파라미터 실험 | 인구 ±50% YAML화 · eup scope adjacent/national UI |
| C3 | Explainability UI | note 태그 → 블록별 카드/바 (인구·8대·토지·아파트) |
| C4 | Twin 빌드 성능 | beop O(n²) shard · 연초 SOP 게이트 고정 (D-054) |

### Phase D — Legacy 정리 (안정화 후)

| # | 항목 | 메모 |
|---|------|------|
| D1 | hybrid v6/v7 배치 중단 | API fallback 제거 일정 |
| D2 | `build_twin_from_profile` v5 deprecate | v2.1-only |
| D3 | Twin v8 `/twin-v8` 병행 종료 | Profile Twin 단일 경로 |
| D4 | 문서 archive | `PROFILE_TWIN_HYBRID` legacy 절 분리 |

### Phase E — 제품 확장 (별도 기획)

| # | 항목 | 메모 |
|---|------|------|
| E1 | Twin → **회귀 pooling** | D-022 · Top-k 후보 pool — ✅ V2 구현 (`built/regression/selection/pooling.py::evaluate_pooling_candidates`, 2026-08-03). 가격수준·인접성 hard gate를 통과한 Twin으로 복수 pool 조합(상위 1개/3개/전체)을 만들어 Local과 CV-MAPE/AIC로 실측 경쟁, `pooling_evaluation`으로 API·UI 반영. Profile Confidence gate·GIS 경계 인접(시군구)은 미구현 |
| E2 | **city grain** Twin 정책 | 대표 sigungu proxy vs city aggregate |
| E3 | Catalog 확장 | 연립·오피스텔 분위 · **built/commercial block**. E1이 실사용에 들어가면서 우선순위 상승 — Twin 유사도가 토지(0.30)·아파트(0.20) 중심이라 **상가 가격 수준은 전혀 반영하지 않음** (2026-08-03 논의). **스코프 결정: 상가(commercial)만** — 아파트 블록과 대칭적이고 표본이 가장 안정적. 단독다가구 등 포함은 표본 부족 지역에서 마스킹 복잡도가 커져 보류. **2026-08-04 재우선순위**: V2 실측(옥천읍)에서 "Pool 크기가 클수록 항상 좋아지지 않는다"·"Pooling 품질은 Twin 유사도 품질에 달렸다"가 확인되며 `CH2_MACRO_IMPLEMENTATION_ROADMAP.md` **V3-8**로 다음 착수 후보에 편입. **이 항목(Twin 벡터에 상가 가격분포·층수·연식·규모 추가)과 "회귀 설명변수 확장"(구조·시공사·브랜드·주차·건폐율·용적률·역세권·코너 여부)은 서로 다른 두 트랙**이다 — 전자는 Twin/Pooling 품질, 후자는 built 원장 자체의 설명력을 올린다. 착수는 사용자 승인 후 |
| E4 | VPS Promote · 연간 파이프라인 (D-054) | 매년 초 `rebuild_regional_profile_national.py` + smoke. 월간 금지 |

### Phase F — 전국 위치 (계획 확정 · 미구현 · D-053)

MVP 동결과 별개로 **2026-08-29 제품 방향이 잠겼다.** Twin 튜닝(Phase C)과 섞지 않는다.

| # | 항목 | 메모 |
|---|------|------|
| F1 | **전국 지역 순위 카드** | 같은 grain 전국(시군구·읍면동·리). 3탭·pin·검색 스크롤·하단 세 위. 순위 마트 + 가상 스크롤 |
| F2 | **특화도 배지** | 시장 구성 막대. 전국 대비 ±%p. 별도 Insight 문장 없음 |
| F3 | 전국 산점도 | ✅ 순위 카드 canvas. 인구×탭값 로그. 클릭=목록 이동 |

SSOT: [`PROFILE_NATIONAL_RANK_PLAN.md`](PROFILE_NATIONAL_RANK_PLAN.md)

### Phase G — CH2 한눈 거시 (D-055 · 미착수)

뉴스판(최신 GDP·M2·금리 표) 금지. 결을 섞지 않는다.

| # | 항목 | 메모 |
|---|------|------|
| G1 | 인구-거래 동조 r | ✅ 산점도 로그 Pearson. n&lt;10 숨김 |
| G2 | 유형 동조 | ✅ 8×8 비중 행렬(금액·건수). mix.type_corr |
| G3 | 유동성·금리 동조 | **전국** 월별 총액·유형별 총액 ↔ M2·대표 금리 1개. 증감률. 지역 r 없음 |
| G4 | 공표 원숫자 | 넣을 거면 출처·기준일 단서만. 주인공 아님 |

---

## 6. 빠른 참조

```bash
# 로컬
http://127.0.0.1:5177/profile/
cd pipeline && python verify_profile_twin_smoke.py

# Profile API
GET /api/regional-profile?region_level=beopjungri&region_code=4373025034&profile_version=v2.1-national&window_years=3

# Twin API
GET /api/regional-profile/twins-beop/4373025034?profile_version=v2.1-national&window_years=3
```

**관련 문서**

- [`NEXT_STEPS.md`](../NEXT_STEPS.md) §2b — 짧은 운영 메모
- [`REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) §12 — 설계 SSOT
- [`PROFILE_NATIONAL_RANK_PLAN.md`](PROFILE_NATIONAL_RANK_PLAN.md) — 전국 순위 1단계 (D-053). **§9 리 grain=법정리만**은 차후
- [`REGIONAL_PROFILE_PHASE_B_PREFLIGHT.md`](REGIONAL_PROFILE_PHASE_B_PREFLIGHT.md) — P1/P2 완료 이력

---

*MVP 동결 선언: 2026-07-28 · Phase C 착수 조건 = §3 체크리스트 + §4 이슈 10건 이상 (또는 P0 버그 0건 유지)*
