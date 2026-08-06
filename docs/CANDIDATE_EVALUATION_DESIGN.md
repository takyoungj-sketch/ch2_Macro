# Candidate · Evaluation 상세 설계

> **상태:** 설계 SSOT (2026-08-02)  
> **범위:** 후보모형 생성·표본 계약·검증·순위·Confidence·AI Bundle 경계  
> **상위:** [CH2_MACRO_VISION.md](./CH2_MACRO_VISION.md) · [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)  
> **Profile 도메인:** [REGIONAL_PROFILE_ARCHITECTURE.md](./REGIONAL_PROFILE_ARCHITECTURE.md) (후보·평가는 본 문서, Profile 스키마·빌드는 Profile 문서)

---

## 1. 목적

CH2 Macro의 모형 선택은 **하나의 회귀식**이 아니라 **여러 후보의 공정한 경쟁**이다.

본 문서는 다음을 정의한다.

1. **표본 계약** — selection / fit / validation 분리, complete-case 동일 표본
2. **후보 유형** — Local, Twin Pooling, Region Group, Province, National Prior 등
3. **Validation Contract** — Time Split, Spatial Group, Holdout, 동일 규칙
4. **Confidence** — Profile, Pooling, Model, Decision
5. **Evaluation Bundle** — AI 입력 경계

**현재 구현 vs 장기 목표**는 각 절末尾 또는 표에 `[현재]` / `[장기]` 로 표기한다.

---

## 2. Validation Contract (OS)

Validation Engine은 **모든 후보**에 동일 규칙을 적용한다. Profile·Twin·Lasso·MixedLM·XGBoost 등 후보 유형과 무관.

### 2.1 표본 3분할

| 표본 | 역할 | 정의 |
|------|------|------|
| **selection_sample** | 후보 **생성·변수 선택** | 동일 scope·기간·필터 내 complete-case 행 집합 |
| **fit_sample** | 모형 **적합** | 기본 = selection_sample; Pooling 시 학습 구간만 |
| **validation_sample** | **평가** (out-of-sample) | Time Split / Spatial Group / Holdout |

**불변 규칙:**

- 후보 간 **AIC/BIC/MAPE 비교**는 반드시 **동일 selection_sample (complete-case)** 위에서 수행
- `n`이 후보마다 다르면 비교 **금지** — missing pattern을 먼저 고정
- 거래 건수 `n_tx`와 **독립 표본 수** `n_groups`(지역·시간 fold 수)를 **구분 표기**

### 2.2 Complete-case 정의

```
selection_sample = { row | ∀ 변수 ∈ candidate_union_vars, value not missing }
```

- `candidate_union_vars`: 비교 대상 **모든 후보**가 사용할 수 있는 변수의 **합집합**
- 변수 블록 ON/OFF 탐색 시: 비교 pool 내 후보는 **동일 complete-case** 재사용
- `[현재]` 복합 `model_selection`은 scope 내 complete-case이나 **후보 간 union 고정은 부분적`
- `[장기]` Evaluation API가 union_vars·row_ids를 SSOT로 반환

### 2.3 검증 방법

| 방법 | 용도 | 규칙 |
|------|------|------|
| **Rolling Time Split** | 시계열 예측력 | train = 과거 T년, test = 다음 H개월; 롤링 k-fold |
| **Spatial Group Validation** | 지역 일반화 | group = region_code; leave-one-region-out 또는 k-region holdout |
| **Holdout** | 단순 OOS | 단일 시간·공간 holdout (최소 표본 게이트) |
| **In-sample AIC/BIC** | **설명형** 모형 비교만 | `[현재]` 복합·집합 모형추천; `[장기]` 예측형 순위와 **분리 표시** |

**원칙:** 예측형 순위의 1차 지표 = **Time Split CV-MAPE** (또는 CV-RMSE). In-sample MAPE는 **참고**만.

### 2.4 버전·재현성 (Validation 메타)

모든 평가 결과에 다음을 기록:

- `validation_contract_version`
- `profile_version`, `as_of_month`, `window_years`
- `selection_row_ids` (또는 hash)
- split 규칙 (time/spatial 파라미터)
- `evaluated_at` (UTC)

---

## 3. Candidate Factory

### 3.0 V1 실행 범위

V1은 자동 Pooling까지 한 번에 수행하지 않는다.

```text
Profile Twin
    ↓
Candidate Provider
    ↓
Candidate Validation
    ↓
동일 표본·동일 Validation 비교
    ↓
사용자 채택
```

Pooling은 후보 검증을 통과한 후보에 대해서만 후속 단계에서 실행한다.
이 순서를 지키면 Twin 추천 오류가 곧바로 회귀 표본 오류로 전파되지 않는다.

Provider 공통 계약은 `backend/app/built/regression/candidates/base.py`에 둔다.

```text
generate(context) → CandidateSpec[]
validate(candidate) → CandidateValidation
```

`CandidateProvider`는 회귀 적합·순위·최종 채택을 수행하지 않는다.
Provider 목록과 검증 실행은 `candidates/factory.py`의 `generate_candidates()`가 담당한다.
반환값은 `accepted` 후보와 모든 후보의 `validations`를 함께 보존한다.

### 3.1 후보 유형

| ID | 후보명 | 설명 | fit_sample | Profile 의존 |
|----|--------|------|------------|--------------|
| **C1** | Local | 선택 지역만, 거래 OLS | local rows | 없음 |
| **C2** | Local + Profile | Local + Profile 연속/잠재지수 | local rows | 변수·가설 |
| **C3** | Twin Pooling | Twin hard gate 통과 지역 pool | pooled rows | Twin 후보 |
| **C4** | Region Group | Profile 유사도·cluster 그룹 pool | group rows | Region Group |
| **C5** | Province Prior | 시도 내 hierarchical / prior | province rows | 약함 |
| **C6** | National Prior | 전국 prior / partial pooling | national sample | 약함 |
| **C8** | Land-signal augmented | 토지 Signal Layer → `expected_land_value` Feature; Local과 CV 경쟁 | local rows (+ cross-DB lookup) | matrix·Profile·Twin |

**추가 플러그인 (장기):** Rule-based baseline, Mixed/Bayesian partial pooling, ML (XGBoost 등).  
**Land Signal 상세:** [`LAND_BUILT_SIGNAL_DESIGN.md`](./LAND_BUILT_SIGNAL_DESIGN.md).  
**모형 추천 UX (단계형·scope SSOT):** [`CH2_RECOMMENDATION_ENGINE_DESIGN.md`](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) — **2026-08 설계 초안, 미구현**.

### 3.2 Candidate 메타데이터 (필수 반환)

```json
{
  "candidate_id": "twin_pool_v1",
  "model_type": "ols_pooled",
  "scope": { "admin_level": "eupmyeondong", "region_codes": ["..."] },
  "variables": ["gross_area", "land_area", "profile_latent_1"],
  "selection_n": 412,
  "fit_n": 412,
  "pooling_regions": ["43111...", "43112..."],
  "profile_snapshot": { "profile_version": "v2.0-national", "as_of_month": "2026-06-01" },
  "failure_reason": null,
  "model_version": "built.regression.v3"
}
```

### 3.3 Profile / Twin 기반 후보 생성

Profile Engine은 **회귀 적합을 하지 않고** 후보만 제안한다.

**Profile Twin 후보 (V1):**

1. anchor region의 **Profile-native Twin v21** Top-N 조회
2. CandidateSpec 생성 — 이 단계에서는 자동 Pooling·회귀 적합을 하지 않음
3. **Candidate Validation**:
   - 동일 행정레벨
   - canonical region code
   - `profile_version`·`as_of_month`·`window_years`
   - Profile-native algorithm v21
   - 후보별 최소 거래수
   - 생활권·가격수준
   - 공간 커버리지(후속: 방향·생활권 분포)
4. 검증 실패 후보는 제외하고 사유를 반환

**구현 주의:** 후보 검증의 거래건수는 anchor 지역으로 이미 좁혀진 selection
표본(`ctx.df`)이 아니라, built 원장에서 **후보 지역 자체**(anchor + Twin)를 별도
조회해 계산해야 한다 (`candidates/factory.py::region_counts_from_db`). anchor
표본만 보면 Twin 지역은 정의상 그 표본에 없으므로 항상 0건으로 잡혀 모든 Twin
후보가 `region_coverage`에서 탈락한다 — 2026-08-03 발견·수정.

**Twin Pooling (V1.5 — 구현됨, `selection/pooling.py::evaluate_local_vs_twin_pool`, 2026-08-03):**

검증을 통과한 Twin 후보 전체를 하나의 pool로 묶어 Local과 **동일 변수블록**으로
실제로 적합·비교한다 (`/regression/suggest·compare` 응답의 `pooling_evaluation`).
CV-MAPE(둘 다 있으면) 또는 AIC(fallback)로 승자를 정하고, 1위·2위 격차 기반
`decision_confidence`(★·A~E)를 함께 반환한다. Hard gate가 없어 검증을 통과한
Twin 후보는 가격수준·인접성 구분 없이 모두 하나의 pool에 들어갔다 — 이 한계는
V2에서 해소했다.

**Twin Pooling (V2 — hard gate + 복수 pool 조합, 구현됨 `selection/pooling.py::evaluate_pooling_candidates`, 2026-08-03):**

1. 검증을 통과한 Twin 후보에 **두 가지 hard gate**를 적용:
   - **가격수준**: anchor 대비 ㎡당 가격(price/gross_area) median ratio ∈
     [0.5, 2.0]. `candidates/factory.py::region_price_levels_from_db`가 built
     원장에서 anchor·Twin 각각의 asset_type별 median을 직접 계산한다(market_stats
     같은 별도 DB 테이블에 의존하지 않음 — built_stats 단일 연결로 anchor·Twin
     scope와 완전히 동일한 필터를 적용할 수 있다). 표본이 min_n(기본 3) 미만이면
     "가격수준 표본 부족으로 gate 생략"으로 처리해 **결측을 불합격으로 오판하지
     않는다**.
   - **인접성**: anchor와 같은 시도이거나 인접 시도(`candidates/adjacency.py`).
     GIS 경계 인접(`region_neighbors`, land_stats DB)이 아니라 **시도 레벨** 근사를
     쓴다 — Twin candidate scope(`pipeline/sido_adjacency.py`)가 이미 동일 규칙으로
     후보를 좁혀 생성하므로, 여기서는 "이상치 방어용 재검증"에 가깝다. 엄격한
     GIS 경계 인접을 기준으로 하면 Twin이 찾아주는 '멀지만 비슷한 지역'을 대부분
     걸러내 버려 Pooling의 취지(표본 확대)와 충돌하기 때문에 의도적으로 느슨하게
     잡았다. `region_neighbors`는 시군구 레벨 인접 자체가 없어(읍면동·법정리만)
     엄격한 구현이 애초에 쉽지 않다.
   - Profile Confidence ≥ θ, `fit_n ≥ n_min` 게이트는 **미구현** — Profile
     Confidence 자체가 아직 없고(§5.1 참고), 최소 표본은 `with_complete_case`의
     `selection_n < local_ctx.selection_n` 체크로 대략 대체된다.
2. gate를 통과한 Twin(순위 보존)으로 **복수 pool 조합**을 만든다: 상위 1개 /
   상위 3개 / 전체(중복 크기는 생략) — `twin_pool_n{k}` candidate_id.
3. Local + 각 pool 조합을 모두 실제로 적합해 CV-MAPE(또는 AIC)로 순위를 매기고,
   1위·2위 격차 기반 `decision_confidence`를 전체 candidate 집합 기준으로 계산한다.
4. API 응답(`pooling_evaluation.twin_gates`)에 Twin별 gate 결과(가격ratio·인접성·
   accepted·reasons)를 그대로 노출해 "왜 이 Twin이 pool에서 빠졌는지" 설명 가능.
5. 옥천읍 실측(2026-08-03): Twin 5개 전부 가격ratio 0.55~0.97·인접(충북↔충남)으로
   gate 통과 → `twin_pool_n1/n3/n5` 3개 조합이 Local과 경쟁, CV-MAPE 기준
   `twin_pool_n5`(전체, 86.27%)가 근소하게 최우수(Confidence D, gap 3.6%p) —
   pool 조합 간 CV-MAPE 차이가 작아 "가장 큰 pool이 항상 이기지 않는다"는 것을
   추가로 확인.

**알려진 한계 (2026-08-03 논의):** Twin 유사도(v21)는 토지(0.30)·아파트(0.20)
블록이 핵심이고 **상가/복합 가격 수준은 반영하지 않는다** — `market_mix`에서
"상가 거래 비중"만 볼 뿐 상가 가격대는 안 본다. 즉 Twin 자체는 "토지·아파트
특성이 비슷한 지역"을 찾아줄 뿐이고, "상가 가격대가 비슷한 지역"이라는 보장은
V2의 가격수준 hard gate가 **사후에** 걸러주는 것이다(사전에 유사도 계산 단계에서
반영하는 것이 아님). 상가 분위(`commercial_p25/median/p75`)를 Twin 벡터에 추가하는
`built_profile` 블록은 `REGIONAL_PROFILE_POST_MVP_BACKLOG.md` §5 E3로 백로그에
있음(스코프: 상가 전용으로 결정, 착수는 보류).

**결과 해석 가이드(2026-08-04, 사용자 리뷰 반영):**

- **Local ≈ Twin Pooling(격차가 작음)은 실패가 아니라 성공 신호다.** Twin이
  Local과 비슷한 CV-MAPE를 낸다는 것은 "Twin이 Local과 충분히 비슷한 시장을
  찾아냈다"는 뜻이지, "Pooling이 효과가 없다"는 뜻이 아니다. 반대로 Local과
  Twin의 격차가 매우 크면(예: 33% vs 80%) 그 Twin 자체가 부적합한 후보라는
  신호로 읽어야 한다 — `decision_confidence`의 낮은 등급(D~E)을 "Twin이 별로다"로
  오독하지 않도록 UI 문구·AI 해설에 이 구분을 반영해야 한다(V3 과제).
- **Pool 크기가 클수록 항상 좋아지지 않는다** — 옥천읍 사례에서도 `twin_pool_n1
  < n3 < n5` 순으로 항상 개선되는 게 아니라 조합마다 CV-MAPE가 오르내렸다. 이는
  "가능한 만큼 다 pool하라"가 아니라 "필요한 만큼만 pool하라"는 **Forward
  Pooling**(§ V3 다음 단계, `CH2_MACRO_IMPLEMENTATION_ROADMAP.md` V3-7)의
  근거 데이터다 — top1/top3/전체 3점만 비교하는 지금 구조로도 이미 이 사실이
  드러난다.
- **Pooling의 역할은 표본 확보이고, 설명력 향상은 설명변수에서 나온다.** Twin
  Pooling이 MAPE를 극적으로 낮추는(예: 60%→20%) 효과를 기대하면 안 된다 —
  같은 지역이라도 연면적·대지면적·연식·도로조건만으로는 상가 가격의 상당
  부분이 설명되지 않기 때문이다(§0 데이터 원천 한계와 동일 맥락). 구조·시공사·
  브랜드·주차·층수·건폐율·용적률·역세권·코너 여부 같은 변수가 추가돼야 회귀
  자체의 설명력이 Twin Pooling보다 더 크게 개선될 가능성이 높다 — 이는 Twin/
  Pooling 엔진이 아니라 **built 원장 변수 확장**(장기 데이터 과제)의 몫이다.

**구현 주의 (2026-08-03 발견·수정):** log-scale rolling CV-MAPE에서 test fold의
범주 조합이 train에 드물게 나타나면 `exp(pred) * duan_smearing`이 수치적으로
발산해(관측 값 대비 10^150배 등) CV-MAPE가 무의미하게 커질 수 있다
(`selection/fit.py::_rolling_time_cv_mape`). train 표본의 관측 가격 범위로 예측을
clip해 외삽 발산을 막았다 — pool처럼 여러 지역을 합친 표본에서 특히 발생하기
쉽다.

**Region Group (C4):**

- Profile cluster / 유사도 threshold로 **다중 지역 그룹** 정의
- 그룹 내 pool + **region_leaf_dummy** 또는 Profile latent (잔여 효과)

**Province / National Prior (C5/C6):**

- 단순 전국 concat **금지**
- Prior = 시도·전국 **계층적 절편/계수 shrinkage** 또는 **표본 가중 prior**
- local 표본 부족 시 **fallback** 후보로만 사용

### 3.4 후보 유형과 Profile 사용

V1 후보는 최소 Local과 Profile Twin으로 시작한다.

| 후보 | 설명 |
|------|------|
| **C1 Local** | 선택 지역만 사용하는 기준선 |
| **C2 Profile Twin** | Profile Twin이 제안하고 검증한 후보 지역 집합 |
| **C3 Twin + Profile Residual** | V2 이후. Twin 생성에 사용한 Profile과 동일 정보를 중복 투입하지 않도록 독립 Profile residual 또는 training-only latent가 필요 |

`Twin + Profile`을 처음부터 일반 Profile 변수로 넣으면 Twin 생성과 회귀 설명변수 사이의 정보 중복·누수가 생길 수 있다. 따라서 C3는 V1에서 구현하지 않는다.

### 3.5 지역더미 vs Profile (장기 방향)

| | 지역더미 | Profile |
|---|----------|---------|
| 설명 | “A지역 = +5300만원” | “토지 baseline·인구·용도 구성이 …” |
| 역할 | **잔여 지역효과** (Profile 미설명분) | **설명 가능한 지역 차** |
| 장기 | Profile 신뢰·커버리지 ↑ 시 **축소** | **주력** |

`건물특성 + Profile 잠재지수 + region residual (dummy 또는 RE)`

- Profile 없음 / Confidence 낮음 → region_leaf_dummy fallback
- `[현재]` 복합 `region_leaf_dummy` (읍·면·동/법정리) 구현됨
- `[장기]` Profile latent + residual RE (Mixed Model, V3)

### 3.6 PCA / Factor Analysis (내부 전용)

- **Training-only** 적합: validation fold의 test 구간에 train PCA loadings 적용
- **가격 직접 변수** Profile 투입 시 **누수 검사** 필수 ([REGRESSION_REGION_PROFILE_EXP.md](./REGRESSION_REGION_PROFILE_EXP.md))
- UI·AI에는 **원천 Profile 변수** + “잠재지수 = … 요인 조합” 설명
- 모델 설계행렬에는 **latent scores** 사용 가능

---

## 4. Regression Engine (후보 적합)

Regression Engine은 Candidate Factory가 요청한 **fit_sample**으로 OLS(또는 플러그인) 적합.

### 4.1 변수 블록 (복합 SSOT)

[`BUILT_MODEL_SELECTION_DESIGN.md`](./BUILT_MODEL_SELECTION_DESIGN.md)와 동일:

| 블록 ID | 내용 |
|---------|------|
| `gross_area`, `land_area`, `building_age` | 연속 |
| `road_width`, `zone_type`, `building_use`, `asset_type` | 더미 블록 전체 |
| `region_leaf` | 읍·면·동/법정리 더미 블록 전체 |

**Joint F-test:** 더미 **블록** 추가 시 개별 p-value만 보지 않고 **블록 전체 F-test / Wald** 로 유의성 보고.

- `[현재]` 블록 단위 Group Forward / Best Subset
- `[장기]` API 응답에 `joint_f_tests: { block_id: { f, p, df } }`

### 4.2 설명형 vs 예측형 분리

| 목적 | 1차 지표 | UI |
|------|----------|-----|
| **설명형** | Adj R², AIC/BIC, Joint F | “설명형 후보” 탭 |
| **예측형** | CV-MAPE (Time Split) | “예측형 후보” 탭 |

동일 후보 pool에서 **Pareto archetypes** (설명형·균형형·예측형) — [`BUILT_MODEL_SELECTION_DESIGN.md`](./BUILT_MODEL_SELECTION_DESIGN.md) §6.1.

---

## 5. Confidence

### 5.1 Profile Confidence

Profile 변수·Twin·Pooling 신뢰도. Profile Engine 산출.

- 입력: feature 결측률, 거래수, window 커버리지, validation_status
- 출력: `[0,1]` 또는 tier (high / medium / low)
- low → Twin/Profile 후보 **생성 억제** 또는 UI 경고

### 5.2 Pooling Confidence

- pool 지역 수, gate 통과율, pool 전후 `n` 증가율
- pool 내 가격 분산·Twin similarity 분포

### 5.3 Model Confidence

- Adj R², CV-MAPE, VIF, Joint F 유의 블록 수
- 표본 `n` vs 파라미터 `p` 비율

### 5.4 Decision Confidence

**1위 후보 선택의 신뢰도** — 상위 후보 간 성능 격차.

```
decision_confidence = f( rank1_metric - rank2_metric, rank1_metric - rank3_metric, validation_n )
```

- 격차 작음 → “1위와 2위가 유사, 사용자 판단 권장”
- 격차 큼 → “검증 기준 1위가 뚜렷”
- `[장기]` UI·AI Bundle에 `decision_confidence` 필드

---

## 6. Evaluation Bundle · AI 경계

AI는 Evaluation 결과를 **해설**만 한다 ([CH2_AI_CONSTITUTION.md](./CH2_AI_CONSTITUTION.md)).

### 6.1 Bundle 포함 (Facts)

- 후보 목록 + `candidate_id`, metrics (in-sample + CV)
- `selection_n`, validation split 설명
- 채택 후보 (사용자 선택)
- Joint F-test, reference categories
- Profile / Pooling / Decision Confidence
- limitations (n, missing, profile_version, gate 실패 목록)

### 6.2 Bundle 제외

- LLM 재계산 회귀·예측
- “최적 모형” 단정
- Profile이 Twin보다 우수하다는 **판단** (수치 인용만)

---

## 7. 현재 구현 매핑

| 설계 요소 | 현재 | 갭 |
|-----------|------|-----|
| Local OLS | ✅ built, collective, land | — |
| 변수 블록 Candidate | ✅ built model_selection/compare, collective model_comparison | Province/National 후보 없음 |
| region_leaf_dummy | ✅ built (eupmyeondong, beopjungri) | Profile residual 연동 없음 |
| reference categories UI | ✅ land, built, collective | — |
| 동일 complete-case union | ✅ built (`with_complete_case`) | 토지·집합 검토 진행 중 |
| Time Split CV-MAPE | ✅ built (rolling time-split) | 토지·집합은 in-sample MAPE만 |
| Profile Twin 후보 생성·검증 (V1) | ✅ built — `ProfileTwinCandidateProvider` + `/regression/suggest·compare`에 연동, UI에 `candidate_validations` 표시 | — |
| Twin Pooling 후보 (C3) | ✅ V2 — `evaluate_pooling_candidates`가 가격수준·인접성 hard gate를 통과한 Twin으로 복수 pool 조합(상위 1개/3개/전체)을 만들어 Local과 함께 실제 적합·CV-MAPE/AIC 경쟁(`pooling_evaluation.candidates`), UI에 N개 후보 카드 + gate 상세로 표시 | Profile Confidence gate·GIS 경계 인접(시군구)은 미구현 |
| Joint F-test | ✅ built (`joint_f_tests` API 필드 + UI 색상 표시) | 토지·집합 미적용 |
| Decision Confidence | ✅ V2 — Local + 복수 Twin Pooling 조합 전체 중 1위·2위 상대 격차 기반 ★·A~E 휴리스틱(`decision_confidence`) | 휴리스틱 임계값 미보정(운영 데이터로 재보정 계획) |
| Validation Contract 버전 | ✅ `validation_contract_version="v1-complete-case"` | split 파라미터·row_ids hash 미기록 |

---

## 8. API 방향 (장기)

```
POST /api/{domain}/evaluation/run
  → selection_sample meta + candidates[] + ranking + confidence

POST /api/{domain}/regression/run  (현행)
  → 단일 OLS (수동·채택 후)
```

Evaluation run은 Regression run을 **내부 호출**하되, 표본·검증을 Evaluation Engine이 **선행 고정**.

---

## 9. 관련 문서

| 문서 | 내용 |
|------|------|
| [CH2_MACRO_IMPLEMENTATION_ROADMAP.md](./CH2_MACRO_IMPLEMENTATION_ROADMAP.md) | V1~V3 구현 순서 |
| [BUILT_MODEL_SELECTION_DESIGN.md](./BUILT_MODEL_SELECTION_DESIGN.md) | 복합 변수블록·Group Forward |
| [REGRESSION_REGION_PROFILE_EXP.md](./REGRESSION_REGION_PROFILE_EXP.md) | Profile vs 더미 실험 |
| [PROFILE_TWIN_HYBRID.md](./PROFILE_TWIN_HYBRID.md) | Twin hybrid v2 |
| [REGIONAL_PROFILE_ARCHITECTURE.md](./REGIONAL_PROFILE_ARCHITECTURE.md) | Profile SSOT |
