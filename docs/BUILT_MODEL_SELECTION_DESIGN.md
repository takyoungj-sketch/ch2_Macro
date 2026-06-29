# 복합부동산 — 모형 추천·비교 (Group Model Selection) 설계

> **작성:** 2026-06-25  
> **상태:** **Phase 0 — 설계 SSOT** (코드 착수 전)  
> **내부 가칭:** ~~최적 회귀식~~ → **모형 추천 / 모형 비교** (UI·문서·AI에 「최적」 금지)  
> **범위:** `frontend-built` · `backend/app/built/regression` · `/api/built/regression/*`  
> **관련:** [`DECISIONS.md`](./DECISIONS.md) D-028 · [`CH2_AI_CONSTITUTION.md`](./CH2_AI_CONSTITUTION.md) · [`BUILT_RESEARCH_MVP.md`](./BUILT_RESEARCH_MVP.md) · 집합 `model_comparison` ([`collective/regression/engine.py`](../backend/app/collective/regression/engine.py))

---

## 1. 목표

| # | 목표 |
|---|------|
| G1 | 사용자가 **후보 변수 블록**을 고른 뒤, **통계 기준 추천·비교**를 받고 **직접 채택** |
| G2 | **변수 그룹 단위** ON/OFF — 범주 더미는 **블록 전체 포함 또는 전체 제외** |
| G3 | **제외·포함·후보 간 차이**를 Facts(JSON)로 제공 → AI·`?` 도움말이 **설명만** |
| G4 | 채택 후 **기존 OLS · 부분회귀도 · 예측** 파이프라인 재사용 |
| G5 | 집합과 동일하게 **linear vs log(금액) `model_comparison`** 제공 |

### CH2 차별화

> 회귀를 «잘 돌리는 것»이 아니라 **「왜 이 모형을 선택했는지 설명하는 것」**.

- **하나의 정답 제시 ✗** — 후보 A/B/C + 지표 + 사용자 선택 ✓  
- 감정·실무: Adj R²만큼 **설명 가능·납득 가능한 선택 과정**이 가치

---

## 2. 비목표

| 항목 | 이유 |
|------|------|
| **회귀식 사전통계 DB** | [`BUILT_MONTHLY_UPDATE_SOP.md`](./BUILT_MONTHLY_UPDATE_SOP.md) — 회귀는 **실시간 OLS**. 월간 배치는 `built_transactions` 원장만 |
| UI/API/AI **「최적」** 용어 | 「다른 모형은 틀림」으로 읽힘 · No Valuation·감정 실무와 충돌 |
| **개별 더미** 수준 탐색 | `road_8m`만 생존 등 — 해석 깨짐 |
| Brute Force (더미 조합) | 그룹 7개(2⁷=128)만 — **개별 컬럼** 2²⁰ 등은 금지 |
| LASSO **기본 UI** | λ·0 계수 설명 부담 — **고급/실험** 옵션만 (Phase D 이후) |
| LLM이 변수 선택 **대신 결정** | 헌법 **No Recalculation** · Facts First |

---

## 3. 현재 vs 목표

### 3.1 지금 (2026-06-25 프로덕션)

```
후보 ☑ → [통계분석] → OLS (response_scale 체크 1개) → 부분회귀도 · 예측
```

- **수동 모드만**
- log/linear: **체크박스 하나** — 집합형 `model_comparison` **없음**
- `/api/built/regression/run` · `/predict` — 실시간

### 3.2 목표

```
후보 변수 ☑
    │
    ├─ [수동 분석]              ← 현행 유지
    │
    ├─ [추천 모델 찾기]          ← Group Forward (+ early stop AIC/BIC)
    │       → 1안 + 제외 사유
    │
    └─ [모형 비교 보기]          ← Group Best Subset 상위 3~5
            → AIC / BIC / MAPE 탭 · linear/log 각각
            → [이 모형으로 분석] (사용자 채택)
    │
    ▼
VariableSpec 반영 → OLS → 부분회귀도 → 예측
```

---

## 4. 용어

| 용어 | 정의 |
|------|------|
| **변수 블록 (block)** | 사용자 토글 1개 = OLS 설계행렬의 **연속 1컬럼 또는 더미 묶음 전체** |
| **Group Forward** | 빈 모델에서 **블록 단위** forward add · AIC/BIC 개선 없으면 중단 |
| **Group Best Subset** | 후보 블록 부분집합 **전수(≤128)** · 지표별 상위 k개 |
| **추천** | Forward 1안 + `excluded[]` 사유 — **채택은 사용자** |
| **모형 비교** | Best Subset **3~5 후보** 나란히 — **정답 아님** |
| **`model_comparison`** | 동일 블록 집합에 대해 **linear vs log** 지표 비교 (집합 패리티) |

---

## 5. 변수 블록 SSOT

`RegressionVariableSpec` 토글 → **블록 ID** 매핑:

| 블록 ID | UI 토글 | OLS 내용 |
|---------|---------|----------|
| `gross_area` | 연면적 | 연속 1컬럼 |
| `land_area` | 대지면적 | 연속 1컬럼 |
| `building_age` | 연식 | 연속 1컬럼 |
| `road_width` | 도로조건 더미 | `road_*` **전부** |
| `zone_type` | 용도지역 더미 | `zone_*` **전부** (단독·통합 시 detached 제외 규칙 유지) |
| `building_use` | 건축물용도/주택유형 더미 | `use_*` **전부** |
| `asset_type` | 유형 더미 (통합만) | `atype_*` **전부** |
| `region_leaf` | 지역(읍·면·동) 더미 | `loc_*` **전부** |

**탐색 입력:** 사용자가 ☑ 한 블록만 **후보 풀**.  
**최대 후보 블록 수:** 8 → **2⁸ = 256** fit (linear+log 병행 시 512 — 여전히 실시간 가능).

**고정 블록:** 없음 — intercept(const)만 항상.

---

## 6. 알고리즘

### 6.1 추천 — Pareto Archetypes (설명형 · 균형형 · 예측형)

> **2026-06 변경:** AIC Forward **단일 1안 ✗** → Best Subset pool에서 **목적별 3후보 ✓**  
> Forward는 **제외 사유 참고**만 (AIC greedy — 정답 아님).

1. 후보 블록 `C`의 부분집합 Best Subset (≤128) 적합
2. **baseline** = 현재 사용자 ☑ 변수 블록 (동일 scope·IQR)
3. pool에서 3종 pick (블록집합 중복 최소화):
   - **설명형** — Adj R²(log) 최대
   - **예측형** — 금액 MAPE 최소
   - **균형형** — Adj R²·MAPE·AIC·변수 수 **균형 점수** 최대
4. 각 후보: **추천 신뢰도**(높음/보통/낮음) + **reasons[]** (baseline 대비 Δ)
5. **정답 제시 ✗** — AI·UI는 목적(예측/설명/균형)에 따른 **선택 가이드**만

**우선순위 (출시):** 3후보 + trade-off → AI 설명 → (장기) CV-MAPE

**MAPE 분해 스크립트:** `pipeline/built/verify_mape_decomposition.py` — 구간별 MAPE·worst 거래·common-n 공정 비교.

```powershell
py pipeline/built/verify_mape_decomposition.py `
  --addr1 "서울특별시" --addr3-list "강북구" --addr4-list "비산동" --leaf-level addr4 `
  --asset-type commercial --scale log --iqr `
  --blocks gross_area,land_area,building_age,road_width,zone_type,building_use `
  --compare-blocks gross_area,land_area,building_age,road_width
```

**legacy Forward:** `forward_steps` · `excluded` — API 유지, UI 접힘 참고.

### 6.2 모형 비교 — Group Best Subset

1. 후보 블록 `C`의 **모든 부분집합** (공집합 제외 — intercept-only는 **참고**로만)
2. 각 subset × `{linear, log}` OLS
3. 지표 계산: **AIC, BIC, Adj R², in-sample MAPE** (집합 [`_build_model_comparison`](../backend/app/collective/regression/engine.py) 재사용)
4. **랭킹 탭별 상위 3~5** (중복 제거)

**동일 subset이 AIC 1위·BIC 3위** → **교육·비교 가치** — UI에 **「기준별 1위가 다름」** 표시.

### 6.3 LASSO (Phase D — 고급)

- 설정: `engine: forward | best_subset | lasso_experimental`
- **Group LASSO** 또는 블록 단위 only — **기본 UI 비노출**
- Post-LASSO OLS는 **실험실** 문서만

---

## 7. 제외·포함 사유 (Facts)

`reasons[]` 항목 — AI·`?` 패널 SSOT:

| code | 의미 | 예시 |
|------|------|------|
| `p_value` | full 또는 nested model에서 비유의 | p=0.42 |
| `aic` | 추가 시 AIC 악화 | ΔAIC=+2.1 |
| `bic` | BIC 악화 | ΔBIC=+3.0 |
| `adj_r2` | Adj R² 개선 없음 | ΔAdjR²=+0.001 |
| `mape` | MAPE 개선 없음 | 18.2%→18.1% |
| `vif` | VIF≥10 (연속 블록) | VIF=12.3 |
| `sample_size` | n 대비 파라미터 과다 | n=28, p=14 |
| `forward_stop` | Forward early stop | AIC 개선 중단 |
| `user_candidate` | 후보 풀에 없었음 | — |

**예시 UI (연식 제외):**

```
연식 — 제외
  ✓ p=0.42
  ✓ Adj R² 증가 없음 (Δ<0.001)
  ✓ MAPE 개선 없음
```

---

## 8. log / linear — `model_comparison`

집합 [`ModelComparison`](../backend/app/collective/schemas.py) 스키마 **재사용**:

- `log` · `linear` · `recommended` · `metric_basis` · `confidence_stars`
- 추천·비교 **모든 후보**에 `model_comparison` 부附
- UI: [`ModelComparisonCard`](../frontend-collective/src/components/CommercialRegressionPanel.tsx) 패턴 이식

**채택 시:** `response_scale` + `VariableSpec` → `/regression/run` body.

### 8.1 지표 산출·비교 (감사 SSOT, 2026-06)

모형 추천 UI에서 **기존 회귀 vs 추천 후보**를 나란히 해석할 때 아래를 전제로 한다.

#### MAPE — 동일 함수, 비교 시 주의

| 항목 | 기존 `/regression/run` | 추천 `/regression/suggest` |
|------|------------------------|----------------------------|
| 함수 | `_insample_mape_pct` | 동일 |
| 역변환 (log) | Duan smearing | 동일 |
| IQR 이상치 | `req.exclude_outliers_iqr` | 동일 body (`regBody`) |
| 표본 n | `_build_design_matrix` mask | **변수 블록마다 다를 수 있음** (결측·log≤0) |

→ **계산식·필터·역변환은 동일**하나, 블록 구성이 다르면 **적합 행(n)이 달라질 수 있다.**  
공정 비교가 필요하면 **동일 변수·동일 n** 기준으로 재적합하거나, UI **「현재 모형 vs 추천」** delta 카드(Phase E)에서 같은 mask로 맞춘다.

#### Adj R² — 척도 혼동 금지

| 출처 | 척도 |
|------|------|
| 메인 카드·추천 `metrics.adj_r_squared` | **적합 척도** (`model.rsquared_adj` — log면 **log(금액)** ) |
| `ModelComparisonCard` (linear/log 탭) | **원척도 금액** 기준 adj R² (`_orig_scale_metrics`) |

→ **Adj R² 0.92 (log) + MAPE 300% (금액)** 조합은 “버그”만은 아니다. **지표 척도가 다르다.**  
다만 금액 MAPE가 300%대면 **저가 거래·꼬리 표본** 영향을 반드시 의심한다 (아래).

#### MAPE 300% — 점검 체크리스트

1. **저가 거래:** 분모 `|y|`가 작으면 % 오차 폭주. 복합부동산(소형 상가 등)에서 흔함.  
2. **IQR:** 켜져 있어도 fence 안의 저가는 남음.  
3. **y=0만 제외:** 최소 금액 floor 없음.  
4. **in-sample only:** 복합 selection 경로는 **CV 미구현** (집합 `CV_MIN_N=40`과 다름). Train/Test MAPE로 **과적합 단정 금지**.

#### 해석·UI 원칙 (CH2)

- 추천 = **정답 ✗** · **후보 1안 + trade-off ✓**
- **과적합** → “가능성” (n 대비 변수·CV 부재 명시)
- Adj R² **0.92→0.69** → “약간 하락” ✗ · **“설명력 상당 감소(Δ≈0.23)”** ✓
- 추천 카드에 **ΔMAPE · ΔAdj R² · ΔAIC · 변수 수** + 목적별 안내:

```
✓ MAPE 188%p 개선   △ Adj R² 0.23 감소   ✓ AIC 감소   ✓ 변수 4개 감소
예측 목적 → 이 후보 검토 · 설명 목적 → 현재 모형도 검토
```

- (Phase E) 차원별 ★ — 예측력 / 설명력 / 단순성 / 안정성 (CV 도입 전까지 안정성은 보수적)

---

## 9. API (초안)

### 9.1 기존 (유지)

| Method | Path | 역할 |
|--------|------|------|
| POST | `/api/built/regression/run` | 수동 OLS + 산점도 + explain |
| POST | `/api/built/regression/predict` | 예측 |

### 9.2 신규

| Method | Path | 역할 |
|--------|------|------|
| POST | `/api/built/regression/suggest` | **Group Forward** → 추천 1안 + excluded |
| POST | `/api/built/regression/compare` | **Group Best Subset** → candidates[] (3~5) |

**공통 Request** — `RegressionRunRequest` 확장 또는 동일 body +:

```python
class RegressionSelectionRequest(RegressionRunRequest):
    candidate_blocks: list[str]  # block_id; 생략 시 variables=True 인 블록 전부
    max_candidates: int = 5      # compare 전용
    ranking_metric: Literal["aic", "bic", "mape", "adj_r2"] = "aic"
```

**`RegressionSuggestResponse` (초안):**

```python
class BlockReason(BaseModel):
    code: str
    detail: str

class ExcludedBlock(BaseModel):
    block_id: str
    label: str
    reasons: list[BlockReason]

class RegressionSuggestResponse(BaseModel):
    recommended_blocks: list[str]          # block_id
    recommended_variables: RegressionVariableSpec
    response_scale: ResponseScale
    model_comparison: ModelComparison | None
    metrics: ModelMetrics                  # 추천 모형 1개
    excluded: list[ExcludedBlock]
    forward_steps: list[ForwardStep]       # optional
    n: int
    scope_label: str | None
    warnings: list[str]
    explain: AnalysisExplain | None
```

**`RegressionCompareResponse` (초안):**

```python
class ModelCandidate(BaseModel):
    rank: int
    blocks: list[str]
    variables: RegressionVariableSpec
    response_scale: ResponseScale
    metrics: ModelMetrics
    model_comparison: ModelComparison | None
    aic: float | None
    bic: float | None

class RegressionCompareResponse(BaseModel):
    candidates_by_aic: list[ModelCandidate]
    candidates_by_bic: list[ModelCandidate]
    candidates_by_mape: list[ModelCandidate]
    n: int
    scope_label: str | None
    warnings: list[str]
    explain: AnalysisExplain | None
```

**채택:** 프론트가 `recommended_variables` / 선택 candidate → **`/regression/run`** 호출 (별도 persist 없음).

---

## 10. UI

### 10.1 버튼 (회귀 카드)

| 버튼 | 동작 |
|------|------|
| **통계분석** | 수동 — **현행** |
| **추천 모델 찾기** | `/suggest` |
| **모형 비교** | `/compare` |

### 10.2 추천 결과 패널

- 포함 블록 ✓ / 제외 블록 + 사유
- `ModelComparisonCard` (log vs linear)
- **[이 모형으로 분석]** → VariableSpec 체크 반영 + `/run`

### 10.3 비교 결과 패널

- 탭: **AIC | BIC | MAPE**
- 카드 3~5개: Adj R² · MAPE · 변수 목록 · scale
- 기준별 1위 불일치 시 배너: *「AIC·BIC 1위가 다릅니다 — 기준을 선택하세요」*

### 10.4 도움말 · AI

- `?` — [`built_explain`](../backend/app/ai/built_explain.py) 확장 · `model_selection_explain`
- AI panel: `ModelSelectionCard` · bundle `model_selection_diagnostic`
- 추천 질문: 「왜 도로조건이 빠졌나?」「AIC와 BIC 차이는?」

---

## 11. 표본·게이트

| 조건 | 동작 |
|------|------|
| n < 30 | suggest/compare **비활성** 또는 `warnings: ["참고용"]` |
| n < 10 × (선택 블록 수) | `sample_size` reason · BIC 가중 안내 |
| region_leaf + loc 더미 ≥ 15 | compare 기본 **region 블록 후보 off** 또는 scope 축소 UI |
| price ≤ 0 & log | log 후보 **skip** (집합 동일) |

---

## 12. AI · 헌법

| Facts | AI 역할 |
|-------|---------|
| `excluded[].reasons` | 제외 설명 |
| `candidates[]` diff | A/B/C 차이 |
| `chosen_by_user` | 「사용자가 B 채택」 — 정답 주장 금지 |

- **No Recalculation** — 선택 알고리즘은 **백엔드 only**
- **No Valuation** — 「최적 가격」 금지 · 「통계적 모형 선택」만

---

## 13. 구현 Phase

| Phase | 내용 | 산출 |
|-------|------|------|
| **0** | **본 문서 · D-028** | SSOT ✅ |
| **1** | `selection/blocks.py` — block_id ↔ design matrix | 단위 테스트 |
| **2** | Group Forward + `/suggest` + excluded reasons | API + 테스트 |
| **3** | UI 「추천 모델 찾기」+ 채택 → run | frontend-built |
| **4** | Group Best Subset + `/compare` + `model_comparison` | API |
| **5** | UI 「모형 비교」+ ModelComparisonCard | frontend-built |
| **6** | explain · AI `ModelSelectionCard` · `?` | ai module |
| **7** | (선택) LASSO experimental · Stepwise 재탐색 | settings |

**Phase 1 착수 순서:** `backend/app/built/regression/selection/` → `test_built_model_selection.py`

---

## 14. 파일·모듈 (예정)

```
backend/app/built/regression/
  engine.py              # 기존 OLS (유지)
  selection/
    blocks.py            # block_id ↔ VariableSpec ↔ X columns
    forward.py           # Group Forward
    best_subset.py       # 2^k enumeration
    metrics.py           # AIC/BIC/MAPE — collective 공유 추출 검토
    reasons.py           # excluded reason builder
  router.py              # /suggest · /compare

frontend-built/src/
  components/
    ModelSelectionPanel.tsx
    ModelComparePanel.tsx
    ModelComparisonCard.tsx   # collective에서 이식 또는 shared
```

---

## 15. 관련 결정·문서

- **D-028** — 본 설계 채택
- 회귀 실시간 — D-024 built Phase A · `BUILT_MONTHLY_UPDATE_SOP`
- 부분회귀도 — 배포됨 (탐색/분석 탭)
- 원장 백필 — D-027 (본 작업과 **독립**)

---

## 16. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-25 | 초안 — Group Forward + Best Subset, 3경로 UI, model_comparison, 제외 사유, API 초안 |
