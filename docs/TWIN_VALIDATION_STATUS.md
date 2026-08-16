# Twin Validation — 현황 조사 · 설계 초안

> **작성:** 2026-08-13  
> **목적:** 중간점검 ③(B3) — 코드 대량 추가 전 **무엇을 이미 재현할 수 있는지** 고정.  
> **상위:** [CH2_MIDCHECK_IMPROVEMENT_PLAN.md](./CH2_MIDCHECK_IMPROVEMENT_PLAN.md) §5  
> **관련:** [CH2_RECOMMENDATION_ENGINE_DESIGN.md](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) · Twin Lab 문서

---

## 1. 제품 목표 (폐쇄 루프)

```
Profile 필터 → 도메인 유사성(Twin Score) → Twin 후보
  → [A] Local-only 회귀
  → [B] Local + Twin pool 회귀 (동일 변수 계약·표본 규칙)
  → Δ지표 검증 → 개선 | 동등 | 악화 판정 → UI·로그
```

**원칙:** Twin Score로 고른 지역이 Local보다 **검증 지표상 나아질 때만** Twin을 제품 기본으로 승격.

**포지션 (2026-08-16):** Twin은 **지역시장 비교 엔진**이다. 가격예측 변수로 쓰지 않고, Stage2 pool도 검증 없이 자동 투입하지 않는다. 일부 지역에서는 pool이 개선되고(옥천읍), 중앙값 Lab에서는 악화하는 경우가 많다. 둘 다 제품 설계에 반영한다.

---

## 2. 실태 조사 (V1–V4)

### V1 — 복합 `/regression/recommend` Stage2가 Local 대비 지표를 어디에 두는가?

| 구분 | 위치 | 필드·의미 |
|------|------|-----------|
| Orchestration | `backend/app/recommendation/stages.py` | `run_stage2` 시 `run_stage2_twin` |
| Stage2 | `backend/app/recommendation/stage2.py` | `local_cv_mape`, `pools[].cv_mape`, `cv_mape_delta` (= local − pool), `decision`, `decision_reason` |
| Neighbor 사전검증 | `backend/app/recommendation/twin_validation.py` | Profile Twin normalize + 표본·계약 `generate_candidates` 게이트 → `twin_codes` |
| Pool 실측 비교 | `backend/app/built/regression/selection/pooling.py` | `evaluate_pooling_candidates(..., mode="optimize")` — Local vs Twin 조합 적합·순위 |
| Hard gate | 동 파일 + `TwinGateResult` | 가격수준·인접성 등으로 Twin 제외 |
| UI | `frontend-built/.../RecommendStagePanel.tsx` | Twin pool 카드 · ΔCV-MAPE · decision 문구 |

**이미 있는 것:** Local vs Twin pool의 **CV-MAPE(또는 AIC) 비교**와 `decision` 문자열.  
**아직 약한 것:** “개선/동등/악화” **명시 enum·임계값**이 API 스키마에 없고, 판정이 UI 배지·로그 SSOT로 고정되지 않음. Adj R² Δ는 pool 카드에 있으나 Twin 채택의 1차 순위는 CV-MAPE/AIC.

### V2 — Twin Lab / Experiment vs Recommend Validation

| 축 | Recommend Stage2 | Twin Lab (실험) |
|----|------------------|-----------------|
| 목적 | 제품 추천 흐름 안 pool 채택 보조 | 가중·알고리즘 실험 |
| 이웃 검증 | `twin_validation.validate_recommend_twin_neighbors` | Lab store/router 별도 경로 |
| 지표 | pooling `cv_mape` / AIC + `cv_mape_delta` | Lab 세션·노트 문서 기준 (제품 Stage2와 **동일 SSOT 아님**) |
| 판정 | `pooling.decision` (후보 id, 보통 local 또는 twin pool id) | 실험 로그 |

**결론:** Lab과 Recommend는 **같은 Twin Score 입력 계열을 쓸 수 있으나**, Validation 지표·판정 문구는 **아직 단일 OS가 아님**. 제품 Validation SSOT는 Recommend Stage2 + pooling 쪽으로 수렴시키는 것이 맞다.

### V3 — 토지·집합 Twin pool 회귀 경로

| 도메인 | Twin pool 회귀 | 비고 |
|--------|----------------|------|
| 복합 | **Y** — Stage2 + pooling | 깊이: 확장 |
| 토지 | **N** — `/regression/suggest` AIC 후보만 | 깊이: 표준 |
| 집합 | **N** — `model_candidates` 비교 | 깊이: 표준+ · Twin Validation 루프 없음 |

### V4 — “개선” 운영 정의

| 출처 | 내용 | 상태 |
|------|------|------|
| Midcheck §4.3 | Twin 효과: Local 대비 ΔCV-MAPE / ΔAdj R² | 문서 초안 |
| `pooling._decision_reason` | CV-MAPE(또는 AIC) 1위 후보 선택 | **코드에 존재** — 임계값 없는 “더 작으면 승” |
| `pooling._decision_confidence` | 1·2위 상대 격차 별점 (휴리스틱) | 채택 여부 아님 · 신뢰도 표시용 |
| API enum `improved \| tie \| worse` | — | **없음** |

**판정 규칙 초안 (③a — 문서 고정, 코드는 후속):**

| 판정 | 예측형 (1차) | 설명형 (보조) |
|------|--------------|---------------|
| **개선** | Twin pool CV-MAPE ≤ Local − ε (ε 초안 0.5%p) | Adj R² ≥ Local + 0.01 이고 VIF 악화 없음 |
| **동등** | \|ΔCV-MAPE\| < ε | Adj R² 변화 미미 |
| **악화** | Twin CV-MAPE > Local + ε | 또는 gate 전부 탈락 → Local 유지 |

ε·별점 임계는 운영 데이터로 재보정. **개선이 아니면 Twin 미채택 권고** (사용자 강제 채택은 가능하되 라벨로 구분).

---

## 3. Golden 실측 (③b · 2026-08-13)

**방법:** `pipeline/bench_twin_built_recommend_lift.py` → 제품 `run_recommendation` (Stage1 Local + Stage2 Twin, `mode=optimize`).  
**픽스처:** `pipeline/fixtures/twin_bench_commercial_pilot_eup4.json`  
**프로필:** `built_commercial` · algo 21 · batch `pt_eup_reg_v21n_bc_2606_w3_caf986`  
**계약:** commercial · eupmyeondong · 2019–2025 · profile window 3y · ε=`lift_delta_pp` 0.5  
**원본 JSON:** `logs/twin_lab/golden_validation_2026-08-13.json` · `logs/twin_lab/golden_validation_jincheon_2026-08-13.json`

### 3.1 표 (제품 Validation 관점)

| case | Anchor | Local n / CV-MAPE | Stage2 decision | Best Twin pool | Pool n / CV-MAPE | ΔCV-MAPE (local−pool) | 판정 (ε=0.5) |
|------|--------|-------------------|-----------------|----------------|------------------|------------------------|--------------|
| okcheon_eup | 옥천읍 `43730250` | 91 / **88.63** | `twin_pool_n1` | n1 (+진천읍) | 188 / **67.16** | **+21.47** | **개선** |
| bongmyeong_eup | 봉명동 `43112111` | 13 / **27.42** | `twin_pool_n1` | n1 | 20 / **21.49** | **+5.93** | **개선** |
| jincheon_eup (대조) | 진천읍 `43750250` | 97 / **59.46** | **`local`** | (best 후보 n3라도) 63.42 | 267 / 63.42 | **−3.96** | **악화 → Local 유지** |

Local primary blocks (요약):

| case | Local blocks | scale |
|------|--------------|-------|
| 옥천읍 | gross_area · land_area · building_age · road_width · zone_type | log |
| 봉명동 | gross_area · land_area · building_age · zone_type | log |
| 진천읍 | land_area · building_age · road_width · zone_type · building_use | log |

### 3.2 재현 명령

```bash
cd pipeline
python bench_twin_built_recommend_lift.py \
  --fixture fixtures/twin_bench_commercial_pilot_eup4.json \
  --case okcheon_eup --case bongmyeong_eup \
  --twin-profile built_commercial \
  --out ../logs/twin_lab/golden_validation_2026-08-13.json

python bench_twin_built_recommend_lift.py \
  --fixture fixtures/twin_bench_commercial_pilot_eup4.json \
  --case jincheon_eup \
  --twin-profile built_commercial \
  --out ../logs/twin_lab/golden_validation_jincheon_2026-08-13.json
```

### 3.3 실측에서 확인된 제품 함의

1. **폐쇄 루프는 이미 동작한다** — Stage2가 Local vs Twin pool CV-MAPE를 비교하고, 악화면 `decision=local`로 남긴다 (진천읍).
2. **개선 ≠ 절대 성능 충분** — 옥천읍은 Δ+21%p여도 Local 등급 `poor`(CV 88). Twin 채택 시에도 **한계·등급을 함께 노출**해야 한다.
3. **pool 크기 ≠ 개선** — 옥천읍 n3/n5는 Local보다 악화. top-1 Twin만 나을 수 있음 → “이웃 많을수록 좋다”는 거짓.
4. **소표본** — 봉명동 Local n=13 → Twin n=20. 개선이어도 **표본 한계 배지** 필요.
5. **API/UI** — `stage2.twin_validation` + RecommendStagePanel 배지 ✅ (§3.5 스모크)

### 3.4 UI 일치 여부

| 기대 | 실제 (RecommendStagePanel) |
|------|----------------------------|
| Local vs Twin Δ 표시 | ✅ `twin_validation` 배지 + ΔCV-MAPE |
| 악화 시 Local 권고 | ✅ `twin_adopt_recommended=false` ·「Local 유지 권고」 |
| 개선 시에도 한계 | Stage1 grade/warnings 병행 (절대 CV 높을 수 있음) |

### 3.5 실응답 스모크 (2026-08-13)

```bash
py scripts/monthly/_smoke_twin_validation_okcheon.py
```

| 항목 | 값 |
|------|-----|
| case | okcheon_eup |
| decision | `twin_pool_n1` |
| twin_validation.verdict | **improved** |
| ΔCV-MAPE | +21.47 (88.63 → 67.16) |
| twin_adopt_recommended | true |
| 결과 | **SMOKE_OK** |

---

## 4. 다음 구현 순서 (③ 후속 · P1)

1. ~~API에 `twin_validation_verdict`~~ → `stage2.twin_validation` ✅  
2. ~~UI 배지~~ → RecommendStagePanel `TwinValidationBanner` ✅  
3. ~~Golden / 실응답 스모크~~ → §3 + §3.5 ✅  
4. 토지·집합 Twin pool 엔진 이식은 Validation OS 안정 후 (현재 개념·골격만)

---

## 5. 완료 게이트

| 게이트 | 상태 (2026-08-13) |
|--------|-------------------|
| ③a 루프 + 판정 초안 문서화 | ✅ 본 문서 §1–2 |
| ③b golden 실측 표 | ✅ §3 (개선 2 + 악화 대조 1) |
| P1 verdict API/UI | ✅ `twin_validation` + Banner |
| Twin = 비교 엔진, 회귀 자동투입 금지 | ✅ 판정 SSOT `TWIN_VALIDATION_EPSILON_PP=0.5` · 채택은 `improved`만 |
