# 집합(주거) 2단계 헤도닉 설계 — 브랜드 프리미엄·단지 가치분석 기반

> **작성:** 2026-08-09 · **상태:** **트랙 C SSOT** (기존 단지 품질지수·특성회귀).  
> 프로젝트 상위 목적(신규 예상가·시공사 밸류·기존 프리미엄)은 [`NEW_APARTMENT_REGRESSION_DESIGN.md`](NEW_APARTMENT_REGRESSION_DESIGN.md)가 우선한다.  
> 이 문서의 \(Q\)는 신규 단지 예측의 입력이 아니다.
> **상위 검토:** [`COLLECTIVE_RESIDENTIAL_VALUATION_EXPANSION_REVIEW.md`](COLLECTIVE_RESIDENTIAL_VALUATION_EXPANSION_REVIEW.md) §2.1
> **데이터 보강:** [`DATA_ENRICHMENT_RAW_ADDITION_PLAN.md`](DATA_ENRICHMENT_RAW_ADDITION_PLAN.md) Phase 1
> **적용 범위:** `asset_type = 'apartment'` (v1). 연립·오피스텔·비주거는 범위 외.

---

## 0. 목적과 비범위

**목적:** 지역·면적·층·시점·규모를 통제한 **단지 단위 품질지수**를 산출하고, 그 지수를 단지특성(브랜드·시공사·세대수·구조)으로 설명해 **브랜드 프리미엄**과 **신규단지 예상시세**의 공통 기반을 만든다.

**비범위 (반드시 지킬 것):**

- **기존 건물 회귀·코호트 회귀 API·엔진을 수정하지 않는다.** `backend/app/collective/regression/engine.py`는 읽기 전용 참조. 응답 스키마·계수·경고 문구가 바뀌면 회귀(regression) 실패로 간주한다.
- 기존 mart(`collective_building_stats` 등)의 값도 바꾸지 않는다. 신규 테이블만 추가한다.
- 신규 기능은 **별도 엔드포인트·별도 mart**로 붙인다.

### 0.1 제품 원칙 — CH2 Macro는 AVM이 아니다

CH2 Macro는 **감정가를 뱉어주는 자동평가(AVM)가 아니라, 사용자가 통계를 보고 직접 회귀를 돌려 시장의 힘(macro force)과 인사이트를 도출하는 도구**다. 이 원칙이 아래 설계 제약으로 직결된다.

| 금지 | 대신 |
|---|---|
| 버튼 하나 → 「적정가 7.8억」 단일 정답 | 사용자가 **변수 블록·표본 범위·모형 스펙을 골라** 결과가 어떻게 변하는지 보게 한다 |
| 계수를 숨기고 결론만 노출 | **방정식·계수표(SE·t·p)·기준범주·표본수**를 항상 함께 노출 |
| 블랙박스 점수 | 왜 그 값인지 **기여도 분해**(지역 기준 + 규모 + 브랜드 + …)를 누적으로 표시 |
| 제외된 표본을 조용히 버림 | **제외 건수와 이유**(tier 미달·표본 부족·이상치)를 응답에 담는다 |
| 1단계를 감춘 채 2단계 결론만 | **1단계 품질지수 자체를 하나의 열람 가능한 통계**로 제공(분포·순위·단지별 값) |

**결과적으로 2단계 설계는 "정확한 예측값"이 목표가 아니라 "브랜드·규모의 효과를 사용자가 직접 확인·검증할 수 있는 도구"가 목표다.** 예상시세는 그 부산물이며, 항상 시나리오(입력을 바꿔보는 계산기) 형태로만 제시한다.

기존 제품이 이미 이 방식이다 — 건물 회귀 응답은 `equation`(사람이 읽는 방정식), `coefficients`(계수표), `warnings`(표본·외삽 경고), `model_candidates`(변수 블록 후보 비교)를 함께 반환한다. **신규 기능도 같은 4종을 반드시 반환한다.**

### 0.2 실험 단계 운영

이 트랙은 **실험 버전**으로 시작한다. 사용자가 UI를 직접 보며 점진적으로 다듬는다.

- 작업은 **별도 브랜치**에서 진행하고, **커밋은 사용자가 UI를 확인·정리한 뒤** 한다.
- 프런트 진입점은 **실험 라벨**을 달고 기본 노출을 최소화한다(기존 화면 흐름을 방해하지 않음).
- 수치·문구·차트는 확정본이 아니라 **검토용 초안**으로 취급한다.

**진행 상태 (2026-08-09):**

| 단계 | 산출물 | 상태 |
|---|---|---|
| P1 단지 속성 적재·매칭 | `db/049_collective_building_attributes.sql` · `pipeline/build_collective_building_attributes.py` | **완료** — 41,832행, tier A 5,149 / B 218 / C 12,574 / E 833, 거래가중 82.6%(A+B+C) |
| P2 사전·품질플래그 적용 | `db/052_…_dictionary_columns.sql` · `pipeline/collective/apply_danji_dictionary.py` · `pipeline/collective/danji_brand_dictionary.py` | **완료** — 시공사군 18,312단지(거래가중 83.8%), 브랜드 5,109단지(23.7%), 품질 플래그 742건 |
| P2.5 단지 정보 노출 | `backend/app/collective/danji_attributes.py` · `GET /api/collective/buildings/{key}/danji-attributes` · `BuildingDetailModal` 「단지 정보」 탭(실험 모드 전용) | **완료** — 값과 함께 출처·매칭 tier·신뢰도·회귀 제외 사유·이상값 사유를 반환 |
| P3 1단계 품질지수 | `db/050` · 빌드 스크립트 | 미착수 |
| P4 2단계 특성회귀 | `db/051` · 빌드 스크립트 | 미착수 |
| P5 API·UI | 신규 엔드포인트 3종 | 미착수 |

---

## 1. 왜 2단계인가

### 1.1 단일 회귀로는 브랜드 계수가 나오지 않는다

현재 코호트 회귀는 여러 단지를 pooling할 때 단지 고정효과(FE) 더미를 자동 추가한다(`_build_design_matrix`의 `cohort_mode`). 브랜드·세대수·구조·시공사는 **단지 안에서 값이 변하지 않으므로** 단지 FE와 완전공선이며 계수가 소멸한다. "코호트 회귀에 브랜드 더미 옵션 추가"는 작동하지 않는다.

### 1.2 거래 단위로 브랜드를 추정하면 표준오차가 거짓이 된다

단지 FE를 빼고 거래 단위로 브랜드 더미를 넣으면 계수는 나오지만, 같은 단지의 거래 수백 건이 독립 관측으로 취급되어 t값이 과대평가된다(단지 단위 클러스터 표준오차 없이는 필연). 2단계 설계는 **단지 1개 = 관측 1개**이므로 이 문제를 구조적으로 회피한다.

### 1.3 기존 회귀에서 발견한 사항 (신규 설계에서 반복 금지)

기존 회귀의 설명변수는 `전용면적·연식·층·동·권리구분`뿐이고 **계약시점 변수가 없다**(`CollectiveRegressionSpec`). 단지 내부에서 `building_age = 계약연도 − 준공연도`이므로, **현재 「연식」 계수는 사실상 시장 시간추세와 뒤섞여 있다.** 기존 경로는 호환성 때문에 그대로 두되, 신규 1단계에서는 다음 원칙을 지킨다.

> **1단계에는 계약연도 더미를 넣고 `building_age`는 넣지 않는다.**
> 단지 FE + 계약연도 더미 + 연식은 완전공선(연식 = 계약연도 − 단지별 고정 준공연도)이다.
> 준공연도(vintage) 효과는 **2단계**에서 단지 특성으로 추정한다.

---

## 2. 1단계 — 단지 품질지수

### 2.1 표본

| 항목 | 규칙 |
|---|---|
| 자산유형 | `asset_type = 'apartment'`, `is_valid = true` |
| 기간 | `as_of_month` 기준 **최근 5년 rolling** (기존 window 5와 정렬, SSOT: `backend/app/v2_stats_windows.py`) |
| 이상치 | 기존 규칙 재사용 — `unit_price` IQR 1.5배 (`_prepare_work`와 동일 정의) |
| 단지 최소 표본 | **거래 10건 이상** (기존 `MIN_BUILDING_FE_GROUP=5`보다 보수적 — FE 안정성 목적) |
| 추정 단위 | **시군구**(`sigungu_code` 5자리) |
| 시군구 최소 | 적격 단지 **10개 이상** AND 거래 **300건 이상** — 미달 시군구는 산출 제외(v1) |

### 2.2 모형

시군구 `r` 내에서:

```
ln(price_i) = Σ_j α_j · D_j(단지)  +  β · ln(exclusive_area_i)
              + Σ 상대층그룹 더미  +  Σ 계약연도 더미  +  ε_i
```

- 층은 기존 `relative_floor_group()`을 **그대로 재사용**한다(1층/최상층/저·중·고층부). 새 정의를 만들지 말 것.
- `ln(면적)`을 쓴다(선형 면적 아님) — 면적 탄력성 해석과 규모 왜곡 방지.
- 계약연도 더미가 시장추세를 흡수한다.
- 추정: 시군구 단위 OLS(더미 방식). 시군구당 단지 수는 수십~수백이라 설계행렬이 감당 가능하다. **전국 단일 회귀로 4만 단지 더미를 만들지 말 것.**

### 2.3 센터링과 기준수준 저장

`α_j`는 기준 단지 대비 상대값이므로 그대로 쓰면 시군구 간 비교가 불가능하다.

1. 시군구 내 **단지 단순평균이 0이 되도록 센터링**: `quality_index_j = α_j − mean_r(α)`
2. 센터링으로 사라진 지역 수준은 별도 저장한다 — **이것이 없으면 P5 예측이 절대금액으로 나오지 않는다.**
   `sigungu_base_ln_price` = 기준조건(면적 = 시군구 중위 전용면적, 층 = `floor_rel_mid`, 연도 = `as_of` 연도)에서의 적합값.
   기준조건 값 자체(`ref_area`, `ref_floor_group`, `ref_year`)도 함께 저장한다.

### 2.4 산출

단지별: `quality_index`, `quality_se`, `n_tx`, `first_year`, `last_year`
시군구별: `sigungu_base_ln_price`, `ref_area`, `ref_floor_group`, `ref_year`, `r_squared`, `n_buildings`, `n_tx`, `area_beta`

---

## 3. 2단계 — 단지특성 회귀

### 3.1 표본

| 항목 | 규칙 |
|---|---|
| 대상 | 1단계 `quality_index`가 있고 `collective_building_attributes`에 매칭된 단지 |
| 매칭 tier | **A·B·C만 사용**(hard). **E는 제외** — 적재 후 실측 결과 승인연도 완전일치 75.6%, 3년 초과 불일치 **12.6%**(A는 0.3%, C는 0.8%) |
| 단지분류 | `아파트`·`주상복합`만. 도시형생활주택·연립·다세대 제외 |
| 공급형태 | `분양형태 = '분양'` 기본. `임대`·`혼합`은 더미로 통제하거나 제외(§3.4 감도분석) |
| 원본 품질 | `attr_quality_flags`가 있는 단지는 **해당 변수만 결측 처리**(단지 자체를 버리지 않는다) — §3.1.1 |

**실측 표본 규모 (2026-08-09, P1·P2 적재 완료):** tier A·B·C + `households > 0` + 거래 10건 이상 = **17,361단지 / 거래 274만건**. 그중 품질 플래그 없는 단지 **16,713개(96.3%)**. 브랜드가 검출된 단지는 5,109개이며, 시군구 214곳의 **평균 브랜드 9.9개**(5개 이상 157곳)로 시군구 내 브랜드 식별이 가능하다.

### 3.1.1 K-apt 원본 이상값 — 지우지 말고 표시한다

P1 적재 후 실측에서 K-apt 원본에 물리적으로 불가능한 값이 확인됐다(세대수 14,700인데 10개동 15층, 세대당 주차 97.8대, 최고층수 200층). **값을 삭제하거나 보정하지 않고** `attr_quality_flags`(쉼표 구분 코드)로 표시한 뒤, 회귀에서 해당 변수만 결측 처리하고 **제외 사유를 응답·UI에 노출**한다(§0.1 원칙).

| 코드 | 판정 규칙 | 실측 건수 |
|---|---|---|
| `floor_implausible` | `max_floor < 3` 또는 `> 101`(엘시티 101층 기준). 층수·동수가 1인 자리표시자를 잡는다 | 541 |
| `scale_inconsistent` | 층당 세대수 = `households / (dong_count × max_floor)` > **20**. 층수 3 이상인 표본의 p99가 19.8이다 | 150 |
| `parking_implausible` | `parking_per_household > 5`(실측 최대 97.8 = 11세대·1,076면) | 50 |
| `hh_zero` | `households <= 0` | 15 |
| **합계** | 매칭 단지(41,832행)의 **1.77%** | 742 |

### 3.1.2 브랜드 커버리지는 매칭 tier에 종속되지 않는다

브랜드는 K-apt 단지명이 아니라 **실거래 원장의 `display_name`에서 추출**한다(`apply_danji_dictionary.py::_load_display_names`). 원장 단지명은 41,832행 전체에서 결측이 0건이므로, **K-apt에 매칭되지 않은 단지(tier D·F·Z)에도 브랜드가 존재한다 — 실측 653단지·거래 5.7만건.** 따라서:

- API는 `matched = false`여도 `brand`를 반환하고, 「K-apt 매칭과 무관하게 실거래 단지명에서 추출」임을 `notes`로 명시한다.
- 반대로 브랜드 프리미엄 **회귀 표본**은 tier A·B·C로 제한된다(규모·구조 변수가 K-apt에서만 오므로). 즉 **브랜드 표시 범위 > 브랜드 회귀 표본**이며, 이 비대칭을 UI에서 감추지 않는다.
- `brand`가 NULL인 것은 「브랜드 없음」이 아니라 **사전 미검출**이다. 기준범주 라벨(`BRAND_REFERENCE_LABEL`)도 이 구분을 유지한다.

`match_tier` D(`lot_multi`)·F(`contains_multi`)는 후보가 여러 개여서 `danji_code`가 NULL이고 속성 컬럼이 비어 있다. API는 `matched = (danji_code IS NOT NULL)`로 정의해 D·F를 미매칭으로 다루되, tier 라벨로 「다중후보」임을 전달한다 — 등록 대상 여부(tier Z의 사유)와 혼동시키지 않기 위해 D·F에는 Z용 사유 문장을 붙이지 않는다.

`scale_inconsistent`는 세대수·동수·층수 중 **어느 필드가 틀렸는지 특정할 수 없다.** 실측에서 상위 위반값은 대부분 `dong_count = 1`(275세대·1동·5층 = 층당 55세대)이었으므로, 세대수를 버리는 대신 **규모 변수 블록 전체를 결측**으로 처리한다. 판정 임계값은 `pipeline/collective/apply_danji_dictionary.py` 상단 상수가 SSOT다.

### 3.2 모형

```
quality_index_j = γ0
                + γ_brand[브랜드]            -- 기준: 「브랜드 없음」
                + b1 · ln(households)
                + b2 · 구조그룹              -- 기준: RC
                + b3 · vintage 구간더미      -- 기준: 2000-2009
                + b4 · max_floor
                + b5 · parking_per_household
                + b6 · danji_class(주상복합 더미)
                + u_j
```

- 종속변수가 log 스케일이므로 계수는 **근사 %**다. 표시는 `exp(γ) − 1`로 변환한다.
- 브랜드 기준을 「브랜드 없음」으로 두면 프리미엄이 **무브랜드 대비 %**로 해석된다.
- 개별 더미는 **단지 30개 이상** 브랜드/시공사군만. 미달은 `기타브랜드`로 묶는다.
- vintage 구간: `~1989 / 1990-1999 / 2000-2009 / 2010-2019 / 2020+`.

### 3.3 추정 방법

- **WLS** — 가중치 `w_j = 1 / (quality_se_j² + median(quality_se²))`.
  분모에 중위 분산을 더하는 것은 표본이 큰 단지가 가중치를 독점하지 않게 하는 shrinkage다(EIV 완화).
- 표준오차는 **HC3 robust**.
- 1단계 추정오차의 2단계 전파는 **부트스트랩(단지 리샘플 500회)**으로 CI를 병기한다. v1에서는 WLS + HC3를 기본 표시, 부트스트랩 CI를 검증용으로 산출한다.

### 3.4 스펙 분리 — 브랜드와 시공사를 동시에 넣지 않는다

브랜드와 시공사는 거의 1:1인 경우가 많다(래미안↔삼성물산). 동시 투입하면 공선으로 둘 다 무의미해진다.

| 스펙 | 구성 | 용도 |
|---|---|---|
| **A** | 브랜드 더미 + 규모·구조·vintage | **기본 표시**(브랜드 프리미엄) |
| **B** | 시공사군 더미 + 규모·구조·vintage | 시공사 관점(커버리지 더 넓음) |
| **C** | 브랜드 + 시공사군 동시 | **진단용** — VIF·조건수 병기, UI 기본 노출 금지 |

### 3.5 산출

스펙별: 계수, 변환 %(`exp(γ)−1`), robust SE, p, 95% CI, 부트스트랩 CI, `n_buildings`, `adj_r_squared`, 스펙 C는 VIF.

---

## 4. DDL (신규 파일)

`db/049_collective_building_attributes.sql` — P1 산출물(이 문서 범위 외, 참조용)
`db/050_collective_quality_index.sql`
`db/051_collective_attribute_effects.sql`

```sql
-- 050
CREATE TABLE IF NOT EXISTS collective_building_quality_index (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE         NOT NULL,
    window_years        SMALLINT     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    sigungu_code        CHAR(5)      NOT NULL,
    building_key        CHAR(64)     NOT NULL,
    quality_index       NUMERIC(10, 6) NOT NULL,
    quality_se          NUMERIC(10, 6),
    n_tx                INTEGER      NOT NULL,
    first_year          SMALLINT,
    last_year           SMALLINT,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uix_cbqi_grain
    ON collective_building_quality_index
       (as_of_month, window_years, asset_type, building_key);
CREATE INDEX IF NOT EXISTS ix_cbqi_sigungu
    ON collective_building_quality_index (as_of_month, sigungu_code);

CREATE TABLE IF NOT EXISTS collective_sigungu_base_level (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE         NOT NULL,
    window_years        SMALLINT     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    sigungu_code        CHAR(5)      NOT NULL,
    base_ln_price       NUMERIC(12, 6) NOT NULL,
    ref_area            NUMERIC(10, 3) NOT NULL,
    ref_floor_group     VARCHAR(20)  NOT NULL,
    ref_year            SMALLINT     NOT NULL,
    area_beta           NUMERIC(10, 6),
    r_squared           NUMERIC(8, 5),
    n_buildings         INTEGER      NOT NULL,
    n_tx                INTEGER      NOT NULL,
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uix_csbl_grain
    ON collective_sigungu_base_level
       (as_of_month, window_years, asset_type, sigungu_code);

-- 051
CREATE TABLE IF NOT EXISTS collective_attribute_effects (
    id                  BIGSERIAL PRIMARY KEY,
    as_of_month         DATE         NOT NULL,
    window_years        SMALLINT     NOT NULL,
    asset_type          VARCHAR(20)  NOT NULL,
    spec                CHAR(1)      NOT NULL,   -- A | B | C
    scope_level         VARCHAR(10)  NOT NULL,   -- national | sido
    scope_code          VARCHAR(5),              -- sido_code (national이면 NULL)
    term                VARCHAR(80)  NOT NULL,
    term_label          VARCHAR(120) NOT NULL,
    term_kind           VARCHAR(20)  NOT NULL,   -- brand | builder | scale | structure | vintage | other
    coef                NUMERIC(12, 6) NOT NULL,
    pct_effect          NUMERIC(10, 4),          -- exp(coef)-1, 100분율
    se                  NUMERIC(12, 6),
    p_value             NUMERIC(10, 6),
    ci_low              NUMERIC(12, 6),
    ci_high             NUMERIC(12, 6),
    boot_ci_low         NUMERIC(12, 6),
    boot_ci_high        NUMERIC(12, 6),
    n_buildings         INTEGER,
    vif                 NUMERIC(10, 4),
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uix_cae_grain
    ON collective_attribute_effects
       (as_of_month, window_years, asset_type, spec, scope_level, scope_code, term);
```

`scope_level`을 둔 이유는 전국 1개 값만으로는 "우리 지역에서도 그런가"에 답할 수 없기 때문이다. v1은 `national` 필수, `sido`는 단지 200개 이상인 시도만 산출한다.

---

## 5. 빌드 파이프라인

```
pipeline/build_collective_quality_index.py       # 1단계
pipeline/build_collective_attribute_effects.py   # 2단계
```

CLI는 기존 mart 스크립트 관례를 따른다.

```bash
py pipeline/build_collective_quality_index.py     --as-of 2026-07-01 --windows 5 --replace
py pipeline/build_collective_attribute_effects.py --as-of 2026-07-01 --windows 5 --specs A,B,C --replace
```

- 2단계는 1단계 산출을 읽는다(원장 재스캔 금지).
- 월 cycle 편입은 검증 통과 후 별건으로 결정한다(`COLLECTIVE_MONTHLY_UPDATE_SOP.md`).

---

## 6. API (신규, 기존 경로 불변)

### 6.1 엔드포인트

| 메서드 | 경로 | 성격 | 반환 |
|---|---|---|---|
| GET | `/analysis/quality-index` | 조회(mart) | 시군구 단지 품질지수 목록·분포·백분위 |
| GET | `/buildings/{building_key}/quality` | 조회(mart) | 해당 단지 지수, 시군구 내 백분위, 기여도 분해 |
| GET | `/analysis/attribute-effects` | 조회(mart) | 스펙별 계수표. 쿼리: `spec`·`scope_level`·`scope_code`·`term_kind` |
| **POST** | `/analysis/attribute-effects/run` | **사용자 실행** | 사용자가 옵션을 지정해 **2단계를 즉석 재추정** |
| POST | `/analysis/valuation/estimate` | 시나리오 | 특성 입력 → 예상 범위 + 기여도 분해 |

**`/run`이 있어야 하는 이유:** mart 스냅샷만 제공하면 "버튼 → 정답" 제품이 된다. 사용자가 변수 블록을 끄고 켜며 브랜드 계수가 얼마나 흔들리는지 직접 확인할 수 있어야 한다(§0.1).

`/run` 요청 옵션(전부 사용자 노출):

```
spec               : A | B | C
scope_level        : national | sido    (+ scope_code)
include_terms      : [brand, builder, scale, structure, vintage, parking, danji_class]
match_tiers        : [A, B, C] 기본 · E 포함 여부 선택 가능(경고 동반)
supply_types       : [분양] 기본 · 임대·혼합 포함 여부 선택
min_buildings_per_term : 기본 30
weighting          : wls | ols        (가중 유무 비교용)
```

1단계 재추정은 비용이 크므로 **`/run`은 2단계만** 대상으로 한다. 1단계 옵션(window·표본 규칙)을 바꾸려면 mart 재빌드다 — 이 제약을 응답 `notes`에 명시한다.

### 6.2 모든 응답에 필수로 포함할 것

기존 회귀 응답과 **같은 4종**을 반환한다. 하나라도 빠지면 사양 미충족이다.

| 필드 | 내용 |
|---|---|
| `equation` | 사람이 읽는 방정식 문자열(2단계 식, 기준범주 명시) |
| `coefficients[]` | `name·label·coef·pct_effect·se·t·p·n_buildings` |
| `warnings[]` | 표본 부족·공선·외삽·tier E 포함·임대 포함 등 |
| `model_candidates[]` | 변수 블록 조합 후보 비교(기존 `suggest_collective_regression` 발상 재사용) |
| `sample_breakdown` | **포함/제외 건수와 이유** — 전체 → tier 필터 → 단지분류 → 공급형태 → 최소표본 각 단계별 잔존 수 |
| `reference_categories` | 브랜드=「브랜드 없음」, 구조=RC, vintage=2000-2009 등 기준범주 |
| `controls_note` | "동일 시군구·면적·층·계약연도를 1단계에서 통제한 뒤의 효과"라는 정의문 |

### 6.3 시나리오 추정 (`estimate`)

```
ln(P̂) = base_ln_price(시군구)
         + area_beta · [ln(면적) − ln(ref_area)]
         + 층그룹 효과
         + Σ 특성 계수(선택 스펙)
예상시세 = exp(ln(P̂))
```

**출력 규칙:**

- 단일 숫자 금지 — 점추정 + 범위(2단계 잔차분산 + 계수 CI 전파) + 표본수를 함께.
- **기여도 분해를 필수로 반환**한다. 사용자가 "왜 이 금액인가"를 스스로 따라갈 수 있어야 한다.

```
시군구 기준수준          6.9억
+ 면적 효과 (84㎡)       +0.4억
+ 규모 효과 (1,200세대)  +0.15억
+ 브랜드 효과 (A브랜드)  +0.33억
+ 구조·연식 효과         −0.02억
= 예상 7.76억  (범위 7.3~8.2억, 근거 단지 n=…)
```

- 입력이 표본 범위를 벗어나면 **외삽 경고**를 낸다(기존 `_extrapolation_warnings` 발상 재사용).

---

## 6.5 UI 원칙 (실험 단계 초안 — 사용자가 다듬음)

화면은 **결론 → 근거** 순서가 아니라 **과정 → 결과** 순서로 쌓는다.

1. **단지 품질지수** — 시군구 내 단지 분포(히스토그램) + 순위표. "이 값은 면적·층·시점을 통제한 상대 가격수준"이라는 설명 병기. 여기까지는 회귀 결과가 아니라 **통계**다.
2. **특성 회귀** — 방정식 + 계수표 + 진단(adj R²·n·기준범주). 변수 블록 토글, 스펙 A/B/C 전환, 후보 모형 비교. **사용자가 직접 돌리는 영역.**
3. **시나리오 추정** — 입력 폼 + 기여도 분해 + 범위. **마지막에 배치**한다.

기존 컴포넌트 관례를 따른다 — 모달은 `DraggableModalShell`, 설명은 `AnalysisHelpPanel` 패턴, 회귀 표현은 `CollectiveRegressionEquation`·`RegressionEffectsTable`을 참고해 재사용 가능한 부분은 재사용한다(새 디자인 언어 도입 금지).

---

## 7. 검증 기준 (완료 판정)

**필수 통과 조건**

1. **기존 회귀 불변** — 임의 단지 5개 + 코호트 2건에 대해 신규 배포 전/후 `regression/run` 응답이 계수까지 동일.
2. 1단계: 산출 시군구 수, 평균 `r_squared` ≥ 0.6, `quality_index` 평균 ≈ 0(시군구별 |mean| < 1e-8).
3. **부호·크기 sanity**: `ln(households)` 계수 ≥ 0, 상위 브랜드 프리미엄이 0보다 크고 절대값 30% 미만. 30% 초과나 음수면 사양 오류로 간주하고 보고할 것(임의 수정 금지).
4. 스펙 C에서 브랜드·시공사 VIF를 보고(공선 확인이 목적, 통과 조건 아님).
5. `estimate`가 실제 거래가 있는 기존 단지 20개에 대해 MAPE 15% 이내(참고 지표).
6. **§6.2의 7개 필드가 모든 응답에 존재**한다. `equation`·`coefficients`·`sample_breakdown`·`reference_categories`가 비어 있으면 미충족.
7. **`/run`으로 변수 블록을 끄면 계수·진단이 실제로 달라진다**(옵션이 무시되지 않는지 확인).

**검증 쿼리 예시**

```sql
SELECT sigungu_code, COUNT(*) AS n, AVG(quality_index) AS m
FROM collective_building_quality_index
WHERE as_of_month = '2026-07-01' AND window_years = 5
GROUP BY sigungu_code HAVING ABS(AVG(quality_index)) > 1e-8;   -- 0행이어야 함

SELECT term_label, ROUND(pct_effect, 2) AS pct, n_buildings, p_value
FROM collective_attribute_effects
WHERE spec = 'A' AND scope_level = 'national' AND term_kind = 'brand'
ORDER BY pct_effect DESC;
```

---

## 8. 작업 분담

| 구분 | 담당 | 내용 |
|---|---|---|
| 설계·판정 | **상위 에이전트(리뷰)** | 이 문서 확정, 시공사 정규화 사전 최종 판정, §7 결과 해석 |
| 구현 | **위임 가능** | DDL, 1·2단계 빌드 스크립트, API 3개, 검증 쿼리 실행 |
| 사전 구축 | 위임 + 리뷰 | 브랜드 사전·시공사 정규화 사전 초안 생성 → 상위 200개 수작업 확인은 리뷰 |
| UI | 위임 가능 | 브랜드 프리미엄 표, 단지 품질 표시, 예상시세 폼 |

**위임 시 전달 원칙:** 이 문서 + 상위 검토 문서 링크만 주면 충분해야 한다. 임계값·기준범주·테이블명을 구현자가 새로 정하게 하지 말 것 — 임의 결정이 필요해지면 그 자체를 설계 결함으로 보고 문서를 고친다.

---

## 9. 미결정 (승인·후속 판단 필요)

| 항목 | 메모 |
|---|---|
| 시군구 미달 지역 | v1은 제외. 시도 pool 승격은 지역 통제가 느슨해지므로 v2에서 재검토 |
| window 5년 고정 | 3·7년 확장은 별도 논의(rolling 7년 트랙과 연동) |
| 부트스트랩 500회 비용 | 전국 + 시도 스펙 3종이면 실행시간 확인 후 조정 |
| 연립·오피스텔 확장 | K-apt는 공동주택 위주 — 연립 262단지뿐이라 v1 제외 |
| 무료/유료 경계 | 브랜드 프리미엄·예상시세는 유료 후보(freemium 설계와 함께 결정) |
| `임대`·`혼합` 단지 | 더미 통제 vs 제외 — 감도분석 후 확정 |
| **K-apt 단지 1개 ↔ building_key 2개 이상 (257건)** | 실거래 원장에서 같은 단지가 표기 차이로 갈라진 경우다. 2단계에서 동일 `danji_code`가 여러 관측치로 들어가면 단지특성이 중복 계상되므로, **`danji_code`를 클러스터로 묶어 robust SE**를 쓰거나 거래수 최대 키만 대표로 쓴다. 어느 쪽이든 응답에 중복 건수를 노출한다 |
| 시공사 판정 불가 약 440건 | `builder_raw`는 있으나 조합·신탁 등 시공사가 아닌 값이거나 「현대」처럼 실체 특정 불가. 임의 배정하지 않고 결측 유지 |
| 시공사가 아닌 법인이 기업집단에 남는 경우 | 예: 하남금호타운의 `builder_raw = 금호고속`(운수회사)이 `builder_group = 금호고속`으로 남는다. `_NON_BUILDER_RE`는 조합·신탁만 걸러내며, 업종 판정은 사전으로 하기 어렵다. **단지 30개 미만 기업집단은 회귀에서 「기타」로 묶이므로 계수를 오염시키지 않는다**(§3.2). 상위 그룹에 이런 값이 끼면 그때 개별 배제 |
| `brand.detected_from` 고정값 | 파이프라인이 원장 단지명을 우선 쓰고 비었을 때만 K-apt 단지명으로 대체하는데, 어느 쪽을 썼는지 컬럼에 남기지 않는다. 원장 단지명 결측이 **0건**이라 현재는 「실거래 단지명」이 사실이지만, 정확히 구분하려면 `brand_source` 컬럼이 필요하다 |
| `households_rent = 0` vs NULL | K-apt 원본이 임대세대 없음을 0으로 기록한다. 값을 바꾸지 않고 그대로 노출하므로 UI에 `0`으로 보인다(결측 `—`와 구분됨) |

---

## 10. 한 줄 요약

**1단계에서 시군구별로 단지 FE를 뽑아 「단지 품질지수」로 센터링하고(지역 기준수준은 별도 저장), 2단계에서 그 지수를 브랜드·세대수·구조에 WLS로 회귀한다. 기존 회귀는 손대지 않으며, 브랜드와 시공사는 공선 때문에 스펙을 분리한다.**
