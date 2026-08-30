# CH2 Macro 구현 로드맵 (V1 ~ V3)

> **상태:** 2026-08-02 · **중간점검 개선안:** 2026-08-13 [`CH2_MIDCHECK_IMPROVEMENT_PLAN.md`](./CH2_MIDCHECK_IMPROVEMENT_PLAN.md)  
> **상위:** [CH2_MACRO_VISION.md](./CH2_MACRO_VISION.md) · **상세:** [CANDIDATE_EVALUATION_DESIGN.md](./CANDIDATE_EVALUATION_DESIGN.md)  
> **원칙:** MVP 기능을 깨지 않고, Validation OS·Candidate Factory를 **단계적으로** 도입한다.
>
> **2026-08 중간점검:** 당분간 **기능 추가보다 검증·제품 정의·Twin Validation·월간 SSOT**를 우선한다. 상세는 위 개선안.
> **현행 실행 순서:** 복합부동산에서 후보 생성·공통 표본·검증 지표·UI를 먼저 안정화한 뒤,
> 동일 계약을 토지와 집합으로 확장한다. 집합의 본건 건물 회귀와 인접 건물 코호트 회귀는
> 서로 다른 후보 유형으로 유지하며 기존 사용 흐름을 대체하지 않는다.

---

## 개요

| 단계 | 초점 | 한 줄 |
|------|------|-------|
| **V1** | 후보 생성·검증 기반 | 동일 표본 · Candidate Provider · 후보 검증 · Time/Spatial Validation |
| **V2** | 지역 지식 Pooling | 검증 통과 Twin/Region Group Pool · fallback · Pooling Confidence |
| **V3** | 고급 후보·계층 | National Prior · Mixed/Bayesian · ML 플러그인 |

각 단계는 **완료 게이트**를 통과해야 다음 단계로 진행한다.  
Decision Log 중복 서술은 [DECISIONS.md](./DECISIONS.md)에만 기록한다.

---

## 현재 MVP (기준선)

**이미 동작하는 것:**

- 토지·복합·집합 통계·회귀 (실시간 OLS)
- 복합 모형 추천·비교 (변수 블록 Group Forward / Best Subset)
- 집합 linear vs log `model_comparison`
- Regional Profile SPA, Twin v8/hybrid API
- 복합 `region_leaf_dummy` (읍·면·동·법정리)
- 더미 reference categories UI (토지·복합·집합)

**아직 없는 것:**

- Validation Engine (OS) 공통 패키지
- Twin/Province/National **후보모형** 자동 생성
- Decision Confidence
- 프로덕션 Time Split / Spatial CV

---

## V1 — 공정 비교 기반

**목표:** 후보 비교의 **통계적 공정성**과 **설명력**을 프로덕션 수준으로 올린다.

**현재 진행:** V1-1·V1-3·V1-4의 1차 구현 완료. 복합 모형추천·비교 API가
후보 union complete-case, 블록 Joint F-test, rolling time-split CV-MAPE를 반환하고
복합 프론트엔드에 CV-MAPE 탭과 Joint F-test를 표시한다. 집합 모형비교도
표본내 MAPE와 CV-MAPE를 분리해 반환한다. 토지는 동일 표본 기반 모형 추천 API·UI를,
집합은 본건·코호트 회귀에 변수 블록 후보 목록을 추가했다. 공통 Evaluation Engine
추상화와 토지·집합의 더 정교한 후보 규칙은 후속 작업이다. CV-MAPE 50% 이상
후보에는 예측 주의 경고를 표시한다. Candidate Provider 기본 계약·Local Provider·
Profile Twin Provider(V1 검증까지)를 추가했고, 복합 프론트엔드가 anchor 지역의
Profile-native Twin(v21) 이웃을 조회해 `/regression/suggest`·`/compare` 요청에 포함하며,
응답의 `candidate_validations`(채택/제외·사유)를 UI에 표시한다. 자동 Pooling은 V2로
분리한다.

**2026-08-03 버그 수정:** Twin 후보 검증이 anchor 지역으로 이미 좁혀진 표본
(`ctx.df`)에서 거래건수를 세고 있어, 앵커 밖 지역인 Twin 후보가 항상 0건으로
`region_coverage` 검증에서 탈락하는 구조적 결함을 발견했다. `candidates/factory.py`에
`region_counts_from_db()`를 추가해 후보 지역 전체(anchor + Twin)를 built 원장에서
별도 조회하도록 수정했다 (`selection/service.py::_candidate_validations`). 실제
옥천읍 사례로 `/regression/suggest` API를 검증해 Twin 후보가 정상적으로 채택됨을
확인했다.

**2026-08-03 추가 구현 — Local vs Twin Pooling 실측 비교:** "후보는 검증만 통과했지,
실제로 회귀에 쓰였는지는 모른다"는 피드백에 따라, 검증을 통과한 Twin 후보 전체를
하나의 pool로 묶어 Local과 **동일 변수블록**으로 실제 적합·비교하는
`selection/pooling.py::evaluate_local_vs_twin_pool`을 추가했다. `/regression/suggest·compare`
응답에 `pooling_evaluation`(Local·Twin Pooling 각각의 n·CV-MAPE·AIC, 승자 결정,
1위·2위 격차 기반 `decision_confidence` ★·A~E)을 포함하고, 프론트엔드에
`PoolingEvaluationCard`(패널 상단, 최종 추천 + Confidence + Local/Twin 비교표)와
`CandidateValidationList`의 "후보 생성 → 검증 통과 → 실제 사용" 3단계 표시로
반영했다. 구현 중 log-scale rolling CV-MAPE가 test fold 외삽 시 수치적으로
발산(10^150% 등)할 수 있는 별개 결함을 발견해 train 관측 가격 범위로 예측을
clip하도록 `selection/fit.py::_rolling_time_cv_mape`를 수정했다 (실제 옥천읍 pool
사례로 재현·검증).

**2026-08-03 추가 구현 — Twin Pooling V2(hard gate + 복수 pool 조합):**
`evaluate_local_vs_twin_pool`을 `evaluate_pooling_candidates`로 확장해 두 가지
hard gate를 추가했다 — 가격수준(anchor 대비 asset_type별 ㎡당 가격 median ratio
∈ [0.5, 2.0], `candidates/factory.py::region_price_levels_from_db`가 built 원장에서
직접 계산)과 인접성(같은 시도이거나 인접 시도, `candidates/adjacency.py` — GIS 경계
인접이 아니라 `pipeline/sido_adjacency.py`와 동일한 시도 레벨 근사를 backend에
복제해 사용). gate를 통과한 Twin(유사도 순위 보존)으로 **복수 pool 조합**(상위
1개/3개/전체, 중복 크기는 생략)을 만들어 Local과 함께 실제 적합·CV-MAPE 경쟁시키고,
전체 candidate 집합 기준으로 1위·2위 격차 `decision_confidence`를 재계산한다.
API 응답에 `pooling_evaluation.twin_gates`(Twin별 가격ratio·인접성·accepted·
reasons)를 추가해 "왜 이 Twin이 빠졌는지" 그대로 노출하고, 프론트엔드
`PoolingEvaluationCard`는 N개 candidate 카드 + 접고 펴는 gate 상세 목록으로
확장했다. 실제 옥천읍 재검증: Twin 5개 전부 gate 통과(가격ratio 0.55~0.97,
충북↔충남 인접) → `twin_pool_n1/n3/n5` 3개 조합이 Local과 경쟁해 `twin_pool_n5`
(전체, CV-MAPE 86.27%)가 근소하게 최우수 채택(Confidence D, gap 3.6%p) — pool
크기가 클수록 항상 이기지 않는다는 것도 함께 확인했다.

### 산출물

| # | 산출물 | 설명 |
|---|--------|------|
| V1-1 | **selection_sample SSOT** | ✅ 1차 구현 — model compare/selection 시 `candidate_union_vars` complete-case 고정, `selection_n` API 노출 |
| V1-2 | **Candidate Provider·후보 검증 계약** | ✅ `CandidateProvider`·`CandidateSpec`·`CandidateValidation`·Local Provider 기본 계약 |
| V1-3 | **Joint F-test** | ✅ 1차 구현 — 복합 후보 응답에 블록 F-test 반환 |
| V1-4 | **Rolling Time Split CV-MAPE** | ✅ 1차 구현 — 복합 model compare에 CV 지표 탭 (in-sample과 **분리 표시**) |
| V1-5 | **설명형 vs 예측형 탭** | Adj R²/AIC vs CV-MAPE — 사용자 혼동 방지 |
| V1-6 | **Validation Contract v1** | `validation_contract_version`, split 파라미터, row_ids hash 메타 |
| V1-7 | **Local vs Twin Pooling 실측 비교** | ✅ `evaluate_pooling_candidates`(V1.5→V2로 확장) — 가격수준·인접성 hard gate를 통과한 Twin으로 복수 pool 조합을 만들어 Local과 실제 적합·CV-MAPE/AIC 비교 + Decision Confidence(★·A~E) |

### 완료 게이트

- [x] 동일 scope에서 후보 3개 이상 compare 시 **selection_n 동일** (자동 테스트)
- [x] region_leaf 블록 ON 시 추천·compare 결과에 loc_* / Joint F 포함
- [x] CV-MAPE가 in-sample MAPE와 **별도 컬럼**으로 표시
- [x] Evaluation 메타가 API JSON에 포함 (재현 가능) — `validation_contract_version`, `selection_n`, `candidate_union_variables`
- [ ] 토지·집합 **패리티 검토** (집합 model_comparison에 동일 원칙 적용 계획 문서화)
- [x] Profile Twin 후보가 v21·Profile snapshot·canonical code·행정레벨·최소 거래수 검증을 통과해야 후보 목록에 포함 (실제 옥천읍 API 스모크 테스트로 확인, 2026-08-03)
- [x] 검증 통과 Twin 후보를 실제로 pool해 Local과 CV-MAPE/AIC로 비교하고 Decision Confidence를 반환 (실제 옥천읍 사례: Local CV-MAPE 98.13% vs Twin Pooling 86.27% → Pooling 채택, Confidence C 확인, 2026-08-03)
- [x] Twin Pooling **hard gate**(가격수준·인접성) + **복수 pool 조합**(상위 1개/3개/전체) 비교 — V2로 앞당겨 구현(`evaluate_pooling_candidates`). 옥천읍 재검증: Twin 5개 전부 gate 통과, `twin_pool_n5`(전체)가 CV-MAPE 86.27%로 최우수 채택(Confidence D, 2026-08-03)

### 비목표 (V1)

- Mixed Model / ML (V3)
- Profile latent PCA 프로덕션 (V2 이후)

---

## V2 — Twin · Region Group Pooling

**목표:** V1에서 검증된 Profile Twin 후보를 사용해 **표본 확대 Pooling**을 만들고, **공간 검증**으로 평가한다.

### 선행 조건

- V1 완료 게이트 통과
- Profile Phase B preflight ([REGIONAL_PROFILE_PHASE_B_PREFLIGHT.md](./REGIONAL_PROFILE_PHASE_B_PREFLIGHT.md)) 진행

### 산출물

| # | 산출물 | 설명 |
|---|--------|------|
| V2-1 | **Candidate C3 Twin Pooling** | ✅ 구현됨(`evaluate_pooling_candidates`, 2026-08-03) — 가격수준(anchor 대비 ㎡당 median ratio 0.5~2.0)·인접성(시도 레벨) hard gate를 통과한 Twin으로 상위 1개/3개/전체 pool 조합을 만들어 Local과 CV-MAPE/AIC로 실측 경쟁. Profile Confidence gate·GIS 시군구 경계 인접은 남음(V2-5) |
| V2-2 | **Candidate C4 Region Group** | Profile cluster 기반 pool |
| V2-3 | **Local fallback 규칙** | `fit_n < n_min` → Province 후보 제안 (C5 lite) |
| V2-4 | **Spatial Group Validation** | leave-one-region-out CV + 지역별 거래수·커버리지 |
| V2-5 | **Profile Confidence → gate** | low confidence 시 Twin 후보 억제. 가격수준·인접성 gate는 V2-1로 구현됨 — Profile Confidence 점수 자체가 아직 없어(§5.1) 이 항목만 남음 |
| V2-6 | **Pooling Confidence** | UI·Bundle |
| V2-7 | **PCA/Factor training-only** | Profile latent 내부 적합, UI는 원천 변수 설명 |

### 완료 게이트

- [x] 복합 상업 scope에서 Local vs Twin Pool CV-MAPE 비교 (`pooling_evaluation`로 API·UI에 구현, 2026-08-03) — [ ] **충북 파일럿 자동 리포트**는 남음
- [x] gate 실패 Twin은 후보 목록에서 **제외 + 사유** 노출 (`pooling_evaluation.twin_gates[].reasons`, UI에 접고 펴는 상세 목록으로 표시, 2026-08-03)
- [ ] Spatial CV와 Time Split CV **동시** Bundle 제공
- [ ] Profile 가격 변수 **누수 검사** 통과 (holdout)
- [ ] 집합 주거·비주거 **동시** Pooling 후보 (패리티)

### 비목표 (V2)

- National Prior full (V3)
- XGBoost 등 ML 후보

---

## V3 — 고급 후보 · 계층 모형

**목표:** 표본 부족·계층 구조를 **prior·partial pooling**으로 다루고, Candidate Factory **플러그인**을 완성한다.

**2026-08-04 사용자 리뷰(GPT 평가 경유) 반영 — 우선순위 재정렬:** V2 실측(옥천읍)
결과 "Pool 크기가 클수록 항상 좋아지지 않는다"·"Pooling은 표본 확보, 설명력은
설명변수가 좌우한다"는 것이 확인되면서, V3의 핵심 두 축을 **Forward Pooling**
(V3-7, top1/top3/전체 3점 비교 → 필요한 만큼만 자동 선택)과 **Built Profile
강화**(V3-8, Twin 유사도에 상가 가격분포·층수·구조 등을 반영해 Pooling 품질
자체를 올림)로 재정렬한다. 아래 V3-1~V3-6(계층 모형·플러그인)은 그대로 유효한
장기 과제지만, 사용자 체감 개선 효과가 더 큰 V3-7·V3-8을 먼저 착수한다.

### 산출물

| # | 산출물 | 설명 |
|---|--------|------|
| V3-1 | **Candidate C5/C6 Province·National Prior** | hierarchical shrinkage (단순 concat 금지) |
| V3-2 | **Mixed / Bayesian partial pooling** | region random intercept (Profile 설명 후 residual) |
| V3-3 | **Candidate Factory 플러그인 API** | `register_candidate()` · 공통 validate |
| V3-4 | **ML 후보 (optional)** | XGBoost 등 — Validation Contract 통과 시만 |
| V3-5 | **Decision Confidence 개선** | rank gap 등급(★·A~E)만으로는 "왜 이 등급인지"가 안 보인다는 피드백(2026-08-04) — `metric_gap_pct`에 더해 ①격차 원인 문장("Local과 Twin 차이 X%"), ②(가능하면) CV fold별 승률("5회 중 3회 Local 우세"), ③"차이가 작음 = Twin이 Local과 비슷한 시장을 찾음(성공 신호)" vs "차이가 큼 = Twin 부적합" 해석 문구를 `DecisionConfidence.note`에 구조화해 담는다 |
| V3-6 | **Evaluation API 통합** | `POST /api/{domain}/evaluation/run` |
| V3-7 | **Forward Pooling** | 지금은 Twin 상위 1개/3개/전체 **3점**만 비교(`evaluate_pooling_candidates`). Forward Pooling은 변수 forward selection과 동일한 원리로 Twin을 유사도 순으로 하나씩 추가하며 CV-MAPE가 더 개선되지 않는 지점에서 멈춘다(Twin1 → Twin1+2 → Twin1+2+3 → … → Stop). "가능한 만큼 다 pool" 대신 "필요한 만큼만 pool"로 전환 — Top-k를 사용자가 고르는 게 아니라 **알고리즘이 CV-MAPE 기준으로 자동 결정** |
| V3-8 | **Built Profile 강화** | `REGIONAL_PROFILE_POST_MVP_BACKLOG.md` §5 E3와 연결. 현재 Twin(v21)은 상가 **거래 비중**만 보고 가격 수준·건축물 특성은 전혀 안 본다. 상가 가격분포(P25/median/P75)·평균 층수·평균 연식·평균 규모(전용면적)를 Twin 벡터에 추가해 유사도 자체를 개선한다(→ Pooling 품질 상승). 구조·시공사·브랜드·주차·건폐율·용적률·역세권·코너 여부는 Twin 벡터가 아니라 **회귀 설명변수 자체의 확장**(built 원장 데이터 보강, 장기 과제)로 별도 트랙 — 두 트랙을 문서에서 명확히 구분해야 혼동이 없다. 이 "회귀 설명변수 확장" 트랙의 매칭 가능성 조사·계획은 [`DATA_ENRICHMENT_RAW_ADDITION_PLAN.md`](DATA_ENRICHMENT_RAW_ADDITION_PLAN.md)(2026-08-04, Phase 0 실측 완료) — 집합 시공사(K-apt, 실측 매칭률 57~71%)를 1순위로 Phase 1 착수 제안, 단독다가구 용도지역(AL_D155, 다수결 정확度 62%·완전동질 6.4% — "확정" 아닌 "소프트 신호"로 스코프 축소)을 2순위로 제안 |
| V3-9 | **Land Signal → 복합 Feature** | [`LAND_BUILT_SIGNAL_DESIGN.md`](./LAND_BUILT_SIGNAL_DESIGN.md) — 토지 Signal Feature; **2026-08 구상, 구현 보류** |
| V3-10 | **CH2 Recommendation Engine UX** | [`CH2_RECOMMENDATION_ENGINE_DESIGN.md`](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) — 기본통계 vs 추천 역할 분리, `analysis_scope` SSOT, 1단계→2단계 Twin, 이중 랭킹, 종료 이유; **2026-08 설계 초안, R0~R3 built 우선** |

### 완료 게이트

- [ ] 후보 유형 ≥4 동시 compare (Local, Twin, Region, Province)
- [ ] Decision Confidence가 1위·2위 근접 시 **경고** 표시
- [ ] Decision Confidence에 등급 산출 근거(격차 %·해석 문구)가 **한 줄 이상** 노출 (V3-5)
- [ ] Forward Pooling이 top1/top3/전체 3점 비교보다 **적거나 같은 CV-MAPE**로 pool 크기를 선택 (V3-7, 회귀 테스트로 옥천읍 등 재현)
- [ ] 새 후보 플러그인 추가 시 Validation Engine **변경 없음** (Contract-only)
- [ ] AI Bundle이 후보·Confidence·limitations **Facts-only** 해설

---

## 횡단 과제 (V1~V3)

| 과제 | 설명 | 우선순위 |
|------|------|----------|
| **원장 매칭·Coverage** | 건축물대장·용도지역 결측 → complete-case 축소 | 지속 |
| **region_code canonical** | D-028 history layer | V1 전제 |
| **집합·복합 패리티** | 회귀·model selection·evaluation 동시 | V1~V2 |
| **Land Signal (토지→복합)** | Feature·Ensemble·Prior — UNION 금지 | V3 — [`LAND_BUILT_SIGNAL_DESIGN.md`](./LAND_BUILT_SIGNAL_DESIGN.md) |
| **Recommendation Engine UX** | scope SSOT·단계형 추천·종료 이유 | V3 — [`CH2_RECOMMENDATION_ENGINE_DESIGN.md`](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) |
| **AI Bundle 확장** | Evaluation 결과 필드 추가 | V1~V3 |
| **연간 프로필 파이프라인** | Profile·Twin·rank — 연초 1회 (D-054). 월간 토지/복합/집합과 분리 | V2 |

---

## 타임라인 (가이드)

일정은 **완료 게이트** 기준으로 조정한다. 아래는 상대적 순서만 제시.

```
2026 Q3  V1 (표본·Joint F·Time Split)
2026 Q4  V2 시작 (Twin Pooling 파일럿)
2027 H1  V2 완료 · Spatial CV
2027 H2  V3 (Prior · Mixed · Decision Confidence)
```

---

## 관련 문서

| 문서 | 역할 |
|------|------|
| [CH2_MACRO_VISION.md](./CH2_MACRO_VISION.md) | 불변 철학 |
| [CANDIDATE_EVALUATION_DESIGN.md](./CANDIDATE_EVALUATION_DESIGN.md) | 알고리즘·계약 상세 |
| [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) | 모듈·API |
| [BUILT_MODEL_SELECTION_DESIGN.md](./BUILT_MODEL_SELECTION_DESIGN.md) | 복합 V1 기반 |
| [REGIONAL_PROFILE_ARCHITECTURE.md](./REGIONAL_PROFILE_ARCHITECTURE.md) | Profile V2 입력 |
| [REGRESSION_REGION_PROFILE_EXP.md](./REGRESSION_REGION_PROFILE_EXP.md) | Profile vs 더미 근거 |
