# 토지 → 복합부동산 Land Signal 설계 (장기)

> **상태:** 구상·장기 계획 (2026-08-05) — **구현 전**  
> **범위:** 복합(built) 회귀 표본 부족 완화를 위해 **토지 도메인 데이터를 어떻게 활용할지**  
> **상위:** [CH2_MACRO_VISION.md](./CH2_MACRO_VISION.md) · [CANDIDATE_EVALUATION_DESIGN.md](./CANDIDATE_EVALUATION_DESIGN.md) · [CH2_MACRO_IMPLEMENTATION_ROADMAP.md](./CH2_MACRO_IMPLEMENTATION_ROADMAP.md)  
> **관련:** [REGIONAL_PROFILE_ARCHITECTURE.md](./REGIONAL_PROFILE_ARCHITECTURE.md) · [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md)

---

## 1. 배경·문제

CH2 Macro는 **토지 · 복합 · 집합** 세 앱이 **DB·API·UI 분리**로 운영된다 (`land_stats` / `built_stats` / `collective_stats`).

복합부동산(상업·공장·단독) 회귀는 **다중회귀(금액 ~ 연면적·대지·연식·더미)** 가 핵심이나, **scope별 표본 부족**이 지속적인 제약이다.

| 현상 | 예 |
|------|-----|
| 읍·면·동·유형 단위 n &lt; 30 | 공장 18건, 상가 25건 등 |
| 지역 더미·블록 탐색 불안 | n 대비 변수 과다 |
| Twin Pooling만으로는 부족 | **같은 유형·다른 지역** pool — 토지 구조 정보는 별도 |

**질문:** 같은 지역을 선택했을 때, **토지 거래 데이터**를 복합 회귀에 **어떻게** 활용할 수 있는가?

**본 문서의 답:** 토지를 **두 번째 표본으로 OLS에 합치지 않고**, **Land Signal Layer**로 두어 Feature·Prior·Constraint를 복합 후보에 공급한다.

---

## 2. 전제 — 왜 원시 UNION 회귀는 하지 않는가

토지 거래와 복합 거래는 **같은 “가격”이라도 설명 구조가 다르다.**

| | 토지 | 복합(공장·상가 등) |
|---|------|-------------------|
| **개념** | 가격 ≈ f(면적, 도로, 용도지역, 위치…) | 가격 ≈ **토지가치 + 건물가치** |
| **종속변수(현행)** | `unit_price_per_sqm` (만원/㎡) | `price` (총액, 만원) |
| **강한 IV** | 면적, 도로, (매트릭스 셀) | 연면적, 연식, 대지면적, 건물·용도 더미 |
| **없는 IV** | 연면적, 연식, 건축물용도 | (토지만 거래에 해당) |

`UNION(토지행, 복합행)` 후 단일 OLS를 돌리면:

- 토지 행: 건물 변수 **0 또는 결측** → OLS가 **건물 없는 수천 건**으로 계수를 학습
- Y 스케일·분산·잔차 구조 **이질**
- 계수 해석(특히 건물·토지 분리) **실무·감정 모두 어려움**

**결론:** 원시 데이터 통합 회귀는 **⭐☆☆☆☆ — 권장하지 않음** (구현도 하지 않는다).

---

## 3. 핵심 통찰 — 토지 회귀 R²가 낮아도 Signal은 쓸 수 있다

토지 통계 화면의 **셀 단위 회귀**는 종종 **설명력(R²)이 낮다.**

주된 이유는 **표본 부족보다 설명변수 부족**인 경우가 많다.

- 토지 가격: 위치·개별성·형상·고저·개발가능성 등 **CH2 원장에 없는 요인** 비중 큼
- CH2 토지 회귀 IV: 면적, 도로, 거래유형, 연도, (법정리 FE) 등 **제한적**

반면 복합부동산은 **연면적·연식·대지** 등 **강한 구조 변수**가 있어 회귀가 상대적으로 잘 되는 경우가 많다.

따라서:

| 접근 | 적합성 |
|------|--------|
| 토지 **회귀식**을 그대로 복합에 이식 | △ — R² 낮으면 **필지 단위 예측** 신뢰 낮음 |
| 토지 **지역·용도 수준**(median, 분포, Profile) | ◎ — **개별 필지 정확도**보다 **수준·분포**가 목표 |
| 토지 거래를 **표본으로 pool** | △ — UNION과 유사한 해석 문제 |
| 토지 Signal을 **Prior / Feature** | ◎ — **CH2 강점**(전국 토지 DB·사전집계)과 정합 |

**Land Signal Layer**가 필요한 것은 **개별 필지 AVM**이 아니라,  
**「이 scope에서 토지 ㎡당 가격은 대략 어느 수준인가」** 를 안정적으로 추정하는 것이다.

---

## 4. CH2 Macro만의 강점 — Ensemble Land Price

일반 AVM과 달리 CH2는 **토지 도메인 자산**이 이미 풍부하다.

| 신호 원천 | 설명 | 상대적 신뢰 |
|-----------|------|-------------|
| **용도×지목 median** | `land_basic_stats_v2` 등 사전집계 | **높음** — 감정·무료 통계와 동일 언어 |
| **지목군 median** | 매트릭스 group 축 | 높음 |
| **토지 셀 회귀 predict** | `land_regression.py` | 보조 — n·R²에 따라 가중 ↓ |
| **Regional Profile** | `land_commercial` / `land_industrial` 등 | 읍·면 fallback |
| **Twin City** | 유사 지역 토지·시장 수준 | 표본 희소 시 |

**Ensemble Land PSM (㎡당 토지단가)** 개념:

```text
land_psqm_ensemble =
    w_matrix  · p_sqm_matrix      # 용도×지목(또는 지목군) median
  + w_reg     · p_sqm_regression   # 회귀 예측 (품질 낮으면 w_reg → 0)
  + w_profile · p_sqm_profile
  + w_twin    · p_sqm_twin
```

- 가중치 `w_*`는 **고정 상수로 시작** → 파일럿 CV로 보정 (장기)
- 회귀 R²가 낮아도 **matrix·Profile·Twin**이 backbone

---

## 5. 권장 아키텍처 — Land Signal Layer

```text
┌─────────────────────────────────────────────────────────┐
│  Land Signal Layer (토지 DB · Profile · Twin — 읽기 전용) │
│  matrix median · regression · profile · twin → ensemble  │
└──────────────────────────┬──────────────────────────────┘
                           │ 행별 lookup (beopjungri, zone, 기간)
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Feature Generator                                       │
│  land_psqm_ensemble                                      │
│  expected_land_value = land_psqm_ensemble × land_area    │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Built Regression (복합 — 기존 엔진 확장)               │
│  후보 A: Local-only (현행)                               │
│  후보 B: + expected_land_value (C8 Land-signal)          │
│  후보 C: ㎡단가 ~ land_psqm_ensemble + 건물 IV (장기)    │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Validation (동일 Contract)                              │
│  CV-MAPE · AIC/BIC · Local vs +Feature 승자              │
└─────────────────────────────────────────────────────────┘
```

**불변 원칙 (CH2 Vision 정합):**

1. **Profile·토지 Signal은 가설** — 최종 채택은 **Validation**(거래자료·CV)이 판단
2. Land-augmented 후보는 **Local-only와 동일 scope·기간·complete-case 규칙**으로 경쟁
3. UI에 **신호 출처·가중·fallback** 노출 (한계 숨기지 않음)
4. 토지·복합 **DB 분리 유지** — cross-DB는 **read-only lookup** 또는 **배치 feature mart**만

---

## 6. 방법론 우선순위 (합의)

| 순위 | 방법 | 요약 | 비고 |
|------|------|------|------|
| ⭐⭐⭐⭐⭐ | **Land Signal → Feature** | `expected_land_value` 등 1~2개 요약 변수를 복합 IV로 추가 | **1순위 구현 후보** |
| ⭐⭐⭐⭐☆ | **Ensemble Land PSM** | matrix + regression + Profile + Twin 가중 | CH2 차별화 |
| ⭐⭐⭐⭐☆ | **Prior / Constraint** | 지역 토지 수준으로 `β_land` shrinkage·하한 | 표본 극소; V3 Bayesian |
| ⭐⭐⭐⭐☆ | **잔차 2단계** | 토지 implied value 차감 후 건물 IV만 회귀 | Feature의 변형; 1단계 오차 고정 |
| ⭐⭐⭐☆☆ | **헤돈 분해 pool** | log(price)=토지항+D·건물항, 토지·복합 행 pool | 이론 OK; **오차 전파**·유지보수 |
| ⭐☆☆☆☆ | **원시 UNION** | 두 원장 행을 한 OLS에 | **금지** |

### 6.1 Feature Generator (1순위) — 상세

**Step 1 — 토지 Signal (scope당 1회)**

- 입력: 복합 분석 scope (`beopjungri` ledger expand, `as_of_month`, `window_years`, `zone_type` 매핑)
- 출력: `land_psqm_ensemble` (+ optional P25/P75, n_tx, signal_quality)

**Step 2 — 복합 행별 Feature**

```text
expected_land_value_i = land_psqm_ensemble_i × land_area_i
```

- `land_area` SSOT: 복합 원장 `land_area` (단독·특수 케이스는 별도 규칙表 — 구현 시 확정)
- `zone_type` ↔ 토지 매트릭스 셀 **매핑 SSOT** 필요 (상업 built → `land_commercial` 대표 셀 등)

**Step 3 — 복합 회귀 후보**

```text
price = β0 + β1 · expected_land_value + β2 · gross_area + β3 · building_age + … + ε
```

- `β1`이 **1.0에서 벗어나도 OK** — 토지 Signal 품질·스케일을 데이터가 보정 (0.72, 0.84, 1.05 …)
- **Local-only** 와 **+Feature** 를 Candidate Factory에서 **동시 후보**

### 6.2 ㎡단가 종속변수 후보 (장기)

복합 종속변수를 **총액** 대신 **`price / gross_area`** 로 두고,  
IV에 `land_psqm_ensemble`(또는 matrix median)을 넣는 **별도 후보**.

- 토지 **사전집계**를 직접 활용 — 토지 회귀 R²에 덜 의존
- 총액 후보와 **CV-MAPE로 승자 선택** (강제 전환 아님)

### 6.3 Prior / Constraint (V3)

표본이 극소(예: 공장 18건)일 때:

- 토지 거래 80건으로 **OLS pool 하지 않음**
- `land_psqm_ensemble` 분포·median으로 **「토지 기여 최소 수준」** Prior
- Ridge / Bayesian / inequality constraint on `β1` 또는 `land_area` 계수
- **건물 효과는 복합 표본**이, **토지 계수만 전국 토지 DB**가 안정화

→ [CH2_MACRO_IMPLEMENTATION_ROADMAP.md](./CH2_MACRO_IMPLEMENTATION_ROADMAP.md) **V3 Mixed/Bayesian partial pooling** 과 동일 트랙.

### 6.4 헤돈 분해 — 후순위인 이유

```text
log(price) = 토지항 + D_build · (건물항)
```

- 토지·복합 **행을 pool**하는 변형 — 이론적으로 정돈됨
- **토지항 오차 → 건물항 오염** (error propagation)
- Feature 방식은 **한 계수(β1)가 Signal 오차를 흡수**하고 Validation이 **넣을 가치**를 판단

---

## 7. 기존 CH2 메커니즘과의 관계

| 기존 | Land Signal과의 관계 |
|------|----------------------|
| **Twin Pooling** (V2, 구현됨) | **지역 간** 복합 표본 확대 — **유지·병행**. Land Signal은 **동일 지역·토지 수준** |
| **Profile Twin** | Twin land median → Ensemble의 `w_twin` |
| **Candidate Factory** | 신규 후보 **C8: Land-signal augmented** (장기) |
| **Validation Contract** | Local vs C8 **동일 complete-case·Time Split CV** |
| **토지 앱 회귀** | Signal Layer 입력 중 하나; **복합 UI에 토지 회귀식 노출 불필요** |
| **집합(collective)** | **본 문서 범위 외** — 유형·원장 상이; 필요 시 별도 설계 |

**Cross-domain read 경로 (장기):**

- 런타임: `built` API → `land_stats` read-only lookup (또는 API 내부 service)
- 또는 배치: `built_land_signal_features` mart (beopjungri × zone × window grain)

---

## 8. 매핑·계약 (구현 전 확정 필요)

| 항목 | 이슈 | 장기 SSOT 방향 |
|------|------|----------------|
| `zone_type` (built) ↔ 토지 matrix 셀 | 명칭·분류 불일치 | 유형별 매핑表 (commercial/factory/detached) |
| 지목·지목군 | built에 land_category 없음 | asset_type → jimok_group 대표 |
| canonical / ledger code | land·built 동기화 | `region_canonical.expand_to_ledger_codes` 재사용 |
| 기간 | rolling window | `as_of_month`, `window_years` **동일 파라미터** |
| Signal 결측 | matrix 셀 n=0 | 상위 scope fallback (읍·면 → 시군구); UI에 fallback 표시 |
| complete-case | `expected_land_value` 결측 | `land_area` NULL 행 — 기존 built 규칙과 동일 |

---

## 9. 검증·성공 기준 (파일럿)

구현 착수 전 **P0 파일럿**으로 GO/NO-GO.

| 지표 | 비교 |
|------|------|
| **CV-MAPE** (Time Split) | Local-only vs +Feature vs +Ensemble |
| **Adj R²** | in-sample 참고만 (예측형과 분리 표기) |
| **β1 안정성** | bootstrap / fold 간 분산 |
| **잔차 패턴** | 극단 외삽·면적 leverage |

**성공:** 표본 n &lt; 30 scope에서 CV-MAPE **유의미 개선** 또는 **β_land·land_area 계수 안정화**  
**실패:** Feature 추가가 CV 악화만 반복 → Ensemble 가중·매핑 재검토, Prior 트랙으로 이동

---

## 10. 구현 로드맵 (장기)

| Phase | 내용 | 산출 | 로드맵 대응 |
|-------|------|------|-------------|
| **P0** | 파일럿 3~5 scope (n&lt;30) | 리포트: matrix vs ensemble vs none | 선행 — 코드 최소 |
| **P1** | `land_psqm_matrix` + `expected_land_value` | built 회귀 실험 토글; Local vs C8 | V2~V3 사이 |
| **P2** | Full Ensemble + ㎡단가 후보 | Candidate C8, UI 신호 출처 | V3 |
| **P3** | Prior / ridge / Bayesian land 계수 | 극소 n 전용 후보 | V3 Mixed/Bayesian |

**현재 (2026-08):** 구상·문서화만. **MVP 회귀·Twin Pooling·log-log 등 선행 작업을 깨지 않음.**

---

## 11. 하지 않을 것

- 토지·복합 **원장 UNION OLS**
- 토지 회귀 R²만으로 Feature 채택 여부 **단독 결정**
- AI가 Land Signal 가중·후보 **최종 선택**
- 집합 앱과 **무분별한 동일 API** (분석 단위 다름)
- Signal 품질·fallback **UI 숨김**

---

## 12. 관련 문서·코드 (현행 baseline)

| 구분 | 경로 |
|------|------|
| 복합 회귀 엔진 | `backend/app/built/regression/engine.py` |
| Twin Pooling | `backend/app/built/regression/selection/pooling.py` |
| 토지 회귀 | `backend/app/land_regression.py` |
| 토지 사전집계 | `db/007_land_basic_stats_v2.sql`, `land_annual_upper_stats` |
| Profile land 도메인 | `pipeline/build_regional_profile.py` (`land_commercial` 등) |
| 지역 canonical | `pipeline/region_canonical.py` |
| 후보·검증 OS | [CANDIDATE_EVALUATION_DESIGN.md](./CANDIDATE_EVALUATION_DESIGN.md) |

---

## 13. Decision Log 후보 (착수 시)

구현 GO 시 [DECISIONS.md](./DECISIONS.md)에 별도 D-xxx로 기록할 항목:

- Land Signal을 **Feature**로만 복합에 주입 (UNION 금지)
- Ensemble backbone = **matrix median 우선**, regression = 보조
- 채택 기준 = **Validation CV-MAPE**, 토지 R² 아님

---

*초안: 2026-08-05 — Cursor·제품 논의 반영 (구상 단계, 구현 보류)*
