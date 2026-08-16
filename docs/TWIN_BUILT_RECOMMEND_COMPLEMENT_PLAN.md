# 쌍둥이 도시 찾기 보완 · 복합 모형추천 · Twin 회귀 역평가 — 계획

> **작성:** 2026-08-10  
> **갱신:** 2026-08-11 — 실험 설계(B0–B10)·벤치 우선·결과 마트 SSOT 반영  
> **상태:** 계획 (복합 우선 · **전국 일괄 실험은 후순위**)  
> **제품 목적:** Twin = **통계분석용 데이터(표본) 확장**. 성공 기준 = **Local 대비 최종 회귀 CV-MAPE 개선**.  
> **실험·Lab·V0~V3 구현 SSOT (승계):** [`TWIN_EXPERIMENT_LAB_IMPLEMENTATION.md`](./TWIN_EXPERIMENT_LAB_IMPLEMENTATION.md) — Twin Experiment Lab UI · 유형별 실험 · V2-target / V2x ablation · V3 holdout.  
> **관련:**  
> [`REGIONAL_PROFILE_ARCHITECTURE.md`](./REGIONAL_PROFILE_ARCHITECTURE.md) §12 ·  
> [`REGIONAL_PROFILE_POST_MVP_BACKLOG.md`](./REGIONAL_PROFILE_POST_MVP_BACKLOG.md) (E3) ·  
> [`CH2_RECOMMENDATION_ENGINE_DESIGN.md`](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) ·  
> [`CANDIDATE_EVALUATION_DESIGN.md`](./CANDIDATE_EVALUATION_DESIGN.md) ·  
> [`PROFILE_TWIN_HYBRID.md`](./PROFILE_TWIN_HYBRID.md) (Profile-native algo 21)

---

## 0. 합의 요지

1. Twin의 제품 목적은 **분석 표본 확장**이다. Similarity 점수 자체가 성공 지표가 아니다.  
2. **핵심 실험 질문:** v1/v2/v3 중 어떤 Twin 로직이 **Local만으로 만든 최적모형보다 더 좋은 최종 회귀모형**을 만드는가?  
3. 비교 방식: 지역별 **Local 재탐색 최적식** vs **Twin Pool 추가 후 독립 재탐색 최적식** → **CV-MAPE** (in-sample MAPE 비교 금지).  
4. **75,000건(5년) 전국 데이터**는 사용자 축적을 기다리지 않고 **선제 실험(80~90%)**에 쓴다. 사용자 로그는 **외부 검증(10~20%)**.  
5. **전국 75,000건을 한 번에 돌리는 것이 목표가 아니다.** 순서: **대표 벤치(50~200) → 알고리즘 수정 → 전국 배치/실험**.  
6. Twin v1/v2/v3는 **한 번에 한 축씩** 차별화해, “무엇이 lift에 기여했는지” 해석 가능하게 한다.  
7. 실험 결과는 **결과 마트(Result Mart)** 로 축적해 Twin v4+ 및 Similarity↔Lift 역분석의 장기 자산으로 삼는다.

---

## 1. 핵심 실험 질문 (정확한 표현)

| ❌ 하지 않는 질문 | ✅ 하는 질문 |
|-----------------|-------------|
| v3 Similarity가 v1보다 높은가? | v1/v2/v3 중 어떤 Twin이 **Local baseline 대비 CV-MAPE를 개선**하는가? |
| Twin 후보가 많이 나오는가? | **같은 지역·asset·window**에서 Pool 재탐색 후 **예측성이 나아지는가?** |
| 사용자가 Twin을 채택했는가? | (운영 후) 사전 실험 결과가 **실사용에서 재현**되는가? |

이 실험이 곧 **Twin 회귀 역평가**다: Profile Similarity → Pool → 재탐색 최적식 → CV-MAPE 변화.

---

## 2. Twin 버전 정의 (v1 / v2 / v3)

한 번에 여러 축을 바꾸지 않는다. 차이를 명확히 해 **원인 해석**이 가능해야 한다.

| 버전 | 내용 | 코드/설정 대응 (현재·예정) |
|------|------|---------------------------|
| **v1** | 현행 Profile-native **algo 21** · `general` weight | `profile_weight.yaml` · population·mix·land·apt |
| **v2** | v1 + **복합 상가 가격 블록** · `built_commercial` weight | `commercial_p50` · `profile_weight_built_commercial.yaml` |
| **v3** | v2 + **gate·top_k·가중 미세조정** (1회 iteration) | pooling gate · pool 규칙 · weight bump |

- v4+는 v3 벤치 결과를 본 뒤 정의.  
- `/profile/` UI용 **general** Twin은 v1과 동일 축으로 유지·분리 가능.

---

## 3. 실험 단위 (지역 × 조건)

각 **벤치 지역**에 대해 아래를 **독립** 수행한다.

### 3.1 조건 (A–D)

| 조건 | 표본 | 탐색 |
|------|------|------|
| **A. Local baseline** | 해당 지역 5년 자료만 | 변수·response_scale **재탐색** → 최적모형 → CV-MAPE |
| **B. Local + Twin v1** | v1 gate 통과 Twin pool (top1/top3/전체 규칙 **고정**) | **독립** 재탐색 → 최적모형 → CV-MAPE |
| **C. Local + Twin v2** | v2 pool | 동일 |
| **D. Local + Twin v3** | v3 pool | 동일 |

**중요:** v1에서 고른 변수·스케일을 v2/v3에 **강제 적용하지 않는다.**  
Twin 추가로 최적 변수·함수형이 바뀌는 것까지 Twin 효과에 포함한다 (최종 목적 = 예측성능).

### 3.2 지역별 결과 예시 (1행 × 버전)

| | Local | v1 | v2 | v3 |
|--|-------|----|----|-----|
| 표본수 (pool_n) | 18 | 61 | 54 | 47 |
| CV-MAPE | 42.1 | 35.8 | 31.4 | 28.7 |
| ΔCV-MAPE (%p) | — | −6.3 | −10.7 | −13.4 |
| 선택식 (예) | log-log | semi-log | log-log | log-log |

수백~수천 지역 × 버전이 쌓이면 Twin 알고리즘을 **회귀 성능으로** 평가할 수 있다.

### 3.3 CV 비교 필수 조건

반드시 동일해야 한다.

- **같은 지역** · **같은 asset_slice** · **같은 regression_window** (예: contract 5년 vs Profile window 3년 — 실험마다 고정)  
- **같은 CV fold 분할** — Local·v1·v2·v3가 **동일 rolling-time CV seed/구조**로 평가 (fold가 다르면 ΔCV 해석 불가)  
- **같은 SSOT candidate pool** · **같은 subset cap** (`MAX_COMPARE_SUBSETS`)  
- **같은 pool 크기 규칙** (top1 / top3 / 전체 — 버전 간 동일)

in-sample MAPE/AIC만으로 “Twin이 좋다”고 말하지 않는다.

---

## 4. 두 가지 성공 수준 (구분 기록)

결과 마트에 **지역 단위**와 **알고리즘 단위** KPI를 분리한다.

| 수준 | 의미 | 예 |
|------|------|-----|
| **Pool 유용성** (지역) | 이 지역에서 v3 pool이 Local보다 CV-MAPE 개선 | A동: 35% → 25% |
| **알고리즘 우수성** (전국) | v3가 벤치/전국에서 **개선 비율·median lift**가 v1/v2보다 우수 | 1,000지역 중 700개 개선, median Δ 5.2%p |

전국 집계 KPI (버전별):

- `lift_hit_rate` — ΔCV > δ (예: 0.5%p) 비율  
- `cv_lift_mean` / **`cv_lift_median`** (median 중요 — 극단값 완화)  
- `n_gain` — pool 표본 증가  
- `gate_pass_rate` — Twin top-k gate 통과율  
- `worsened_rate` — Local보다 악화된 지역 비율 (정상 — 큰 n 지역)

---

## 5. 데이터 역할: 선제 실험 vs 사용자

| | 선제 실험 (주) | 사용자 데이터 (보조) |
|--|----------------|---------------------|
| 비율 | 80~90% | 10~20% |
| 데이터 | built 5년 ~75k · 벤치/전국 설계 | 실제 분석·채택 로그 |
| 목적 | v1/v2/v3 비교 · 가중·gate 튜닝 | 운영 환경 **외부 검증** |
| 편향 | 지역·자산 **층화 샘플링** 가능 | 관심 지역·상가 위주 편향 |

사용자 데이터는 Twin **학습용**이 아니라 **“사전 실험이 재현되는가?”** 검증용.

---

## 6. 실험 단계 (전국 일괄 ❌ → 벤치 우선 ✅)

```text
① Twin v1/v2/v3 설계 (축별 차별화)
        ↓
② 대표 벤치 50~200지역 선정 (층화 — §6.1)
        ↓
③ 지역별 Local / v1 / v2 / v3 독립 재탐색 + CV-MAPE
        ↓
④ 결과 마트 적재 + KPI 집계
        ↓
⑤ v2 commercial·gate 등 **데이터 기반** 수정
        ↓
⑥ (선택) 벤치 확대 · v3 재실험
        ↓
⑦ 전국 Twin 배치 + 전국 회귀 벤치 (변경 영향 지역만 재실험 가능 구조)
        ↓
⑧ Similarity ↔ CV-Lift 산점도 · 역평가
        ↓
⑨ 서비스 반영 (B9)
        ↓
⑩ 사용자 로그 외부 검증 (B10)
```

**목표가 아닌 것:** 75,000건 전체를 v1/v2/v3로 **처음부터 한 번에** 돌리는 것.

### 6.1 벤치 지역 선정 (50~200, 층화)

단순 랜덤이 아니라 골고루:

- 소표본 / 중간 / 대표본 지역  
- 상업·공장·단독 **asset_slice** 중심 (1차 commercial)  
- Twin lift **기대** 지역 (소표본·Fair) + **어려울 것으로 예상** 지역 (대표본·gate 실패多)  
- eup / beop grain 혼합  
- 기존 실측 앵커 포함 (예: 옥천읍·가경동 등)

초기 fixture: `pipeline/fixtures/twin_built_lift_bench.json` (8곳) → **50~200으로 확장**이 B1 목표.

### 6.2 연산 절약 · 재실험

전국 1차 배치 후 **결과 마트를 버리지 않는다.**  
Twin v4에서 Pool 정의만 바뀐 경우 → **영향 지역만 재실험** 가능.

```text
Twin Algorithm → Candidate/Pool → Regression Benchmark → Result Mart
                                                      ↓
                                              Algorithm 개선
                                                      ↓
                                              변경 지역만 재실험
```

---

## 7. 결과 마트 (Result Mart) 스키마 SSOT

지역 × Twin 버전 × pool variant마다 최소 컬럼:

| 컬럼 | 내용 |
|------|------|
| `region_code` | 대상 지역 |
| `region_label` | 표시명 |
| `asset_slice` | commercial / factory / detached |
| `admin_level` | eupmyeondong / beopjungri |
| `regression_window` | contract_year_from/to 또는 window_years |
| `twin_version` | v1 / v2 / v3 |
| `twin_profile` | general / built_commercial |
| `profile_version` | v2.1-national 등 |
| `weight_version` · `catalog_version` | 재현성 |
| `experiment_id` · `run_at` | 배치 run |
| `condition` | local / twin_v1 / twin_v2 / twin_v3 |
| `local_n` | Local complete-case n |
| `twin_n_added` | Twin에서 추가된 표본 |
| `pool_n` | pool 적합 n |
| `gate_pass_rate` | top-k gate 통과율 |
| `local_cv_mape` | Local baseline |
| `twin_cv_mape` | Pool 재탐색 후 |
| `delta_cv_mape` | local − twin (%p, 양수=개선) |
| `local_aic` · `twin_aic` | 보조 |
| `local_model_blocks` · `twin_model_blocks` | 선택 변수 블록 |
| `local_response_scale` · `twin_response_scale` | linear / log |
| `selected_twins` | 실제 pool에 포함된 Twin 코드 |
| `similarity_scores` | Twin별 similarity (역분석용) |
| `pool_variant` | twin_pool_n1 / n3 / n* |
| `stage1_truncated` | subset cap 적용 여부 |
| `cv_seed` · `cv_folds` | fold 재현성 |

**선택 저장:** 전 지역 full 계수 JSON은 상·하위 N% 샘플만 (용량).

### 7.1 역평가 (Similarity ↔ Lift)

마트가 쌓이면:

- Similarity vs ΔCV-MAPE **산점도**  
- **경우 A:** similarity ↑ → lift ↑ → 현 로직 유효  
- **경우 B:** 무상관 → Similarity 로직 개선 필요  
- **경우 C:** similarity 낮지만 특정 asset에서 lift 큼 → asset-specific Twin

“Similarity 90+ 인데 lift 48%” vs “75~85 + 가격 유사 → lift 72%” 같은 **가중·gate 재설계** 근거가 된다.

---

## 8. 제품·엔진 현황 (요약)

### 8.1 Twin 엔진 (Profile-native algo 21)

- 경로: `/api/regional-profile/twins*`  
- v1 = `general` · v2 = `built_commercial` (commercial_p50 + weight 파일)  
- Legacy Twin 스택 제거 방향 유지

### 8.2 복합 모형추천 (사용자 경로)

- stage2 = Twin pool gate → **pool 위 best-subset 재탐색** (식 고정은 `mode=diagnose` 내부용)  
- CTA: 「유사 지역 거래를 더해 모형을 다시 찾습니다」  
- 자동 pool 적용 없음 — 사용자 채택

### 8.3 초기 벤치 도구 (WIP)

- `pipeline/fixtures/twin_built_lift_bench.json`  
- `pipeline/bench_twin_built_recommend_lift.py` — Local → stage2 → KPI JSON  
- **확장 예정:** v1/v2/v3 동시 compare · 결과 마트 적재 · CV seed 고정

---

## 9. 로드맵 B0–B10

| Phase | 내용 | 산출 |
|-------|------|------|
| **B0** | Twin algo 21(v1) 안정화 · legacy 제거 · 실험 전제 정리 | v1 baseline 고정 |
| **B1** | **대표 벤치 50~200** 층화 선정 · fixture·runbook | go/no-go용 지역군 |
| **B2** | Twin **v1 / v2 / v3** 정의·배치 (축별 차별) | 버전별 neighbor 테이블 |
| **B3** | Pool마다 **변수·함수형 독립 재탐색** (recommend stage2 optimize와 동일 SSOT) | 지역×버전 최적식 |
| **B4** | **CV-MAPE** Local vs Twin 비교 · **동일 CV split** · in-sample 금지 | 지역별 Δ표 |
| **B5** | **결과 마트** 구축 (§7 스키마) · 집계 KPI | Twin 실험 dataset |
| **B6** | 벤치 결과로 v2/v3 **데이터 기반** 수정 · (필요 시) 벤치 재실행 | v3 go/no-go |
| **B7** | **전국** Twin 배치 + (선택) 전국 회귀 벤치 · 변경 지역만 재실험 | scale-up |
| **B8** | Similarity ↔ Regression Lift 분석 · 역평가 리포트 | v4 방향 |
| **B9** | 검증된 Twin·추천 경로 **서비스 반영** | 제품 |
| **B10** | 사용자 채택·성능 **외부 검증** 로그 축적 | 운영 KPI |
| **L0** (후속) | `twin_profile=land` · 토지 회귀 | 복합 패턴 이식 |

**구현 PR 분할 (참고):** B0–B4 제품·벤치 파이프라인 / B5 마트 / B6–B8 분석·튜닝 / B9–B10 운영.

---

## 10. Part A — Twin 벡터·가중 보완 (v2/v3 입력)

§2 v2/v3 정의와 동일. 요약:

- **A1** commercial_p50 + `built_commercial` weight  
- **A2** twin_profile 분기 (general / built_commercial / 후속 factory·land)  
- **A3** mask 재정규화 · represent_market · top_k 통일  
- **A4** 8대 mix만으로 상가 가격대 대체 시도 ❌

---

## 11. Part B — 복합 모형추천 (사용자 UX)

§8.2와 동일. 실험(B3–B4)과 **동일 엔진**을 쓰면 “벤치에서 검증한 것 = 사용자가 보는 것”이 된다.

---

## 12. 원칙 · 리스크

### 12.1 원칙 (P1–P7)

| ID | 원칙 |
|----|------|
| P1 | Twin = 표본 공급기 · 성공 = CV-MAPE 등 **최종 모형 성능** |
| P2 | Twin 유의성 UI 전면 비강조 · lift는 내부 QA |
| P3 | Catalog → Vector → Weight → Similarity · YAML version bump |
| P4 | 분석유형별 twin_profile |
| P5 | Pool 확정 후 **재탐색** (조건별 독립) |
| P6 | Hard gate = 불량 Twin 차단 |
| P7 | Similarity만 올리고 lift 없으면 **실패** |
| **P8** | **벤치 → 수정 → 전국** 순서. 전국 일괄 선행 ❌ |
| **P9** | Local·v1·v2·v3 **동일 CV split** |

### 12.2 리스크

| 리스크 | 완화 |
|--------|------|
| commercial mask 多 | mask 재정규화 · mask_min_count |
| 전국 연산 폭발 | 50~200 벤치 우선 · 영향 지역만 재실험 |
| 재탐색 과적합 | CV-only · complete-case · cap 유지 |
| fold 불일치 | cv_seed/folds 마트 기록 · fit.py CV 고정 |
| lift 없음 | worsened_rate·median 보고 · gate/scope 조정 |

---

## 13. 한 줄 전략

> **Twin v1/v2/v3를 대표 bench에서 Local 대비 CV-MAPE로 검증하고, 결과 마트로 역평가한 뒤, 전국·서비스에 단계적으로 반영한다. 75k는 기다릴 데이터가 아니라 실험 재료다.**

---

## 14. 코드·브랜치 (WIP)

- 실험·stage2 재탐색·built_commercial 등 **진행 중 구현**은 브랜치 `experiment/twin-regression-benchmark` 에 두고, **본 계획(B5 마트·B6 이후)과 정합 검토 후** merge 한다.  
- main에는 계획 문서 갱신만 반영하거나, WIP 브랜치에서 일괄 PR한다 (팀 정책에 따름).

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-08-10 | 초안 — Twin 보완 / 복합 활용·재탐색 UX / 상호보완 KPI |
| 2026-08-11 | **실험 설계 확정** — 핵심 질문·v1/v2/v3·독립 재탐색·동일 CV split·벤치 우선·결과 마트·B0–B10 로드맵 |
| 2026-08-11 | 전국 75k 일괄 실험 ❌ 명시 · 선제 80~90% / 사용자 10~20% · Similarity 역평가 |
| 2026-08-11 | 실험·Lab SSOT를 [`TWIN_EXPERIMENT_LAB_IMPLEMENTATION.md`](./TWIN_EXPERIMENT_LAB_IMPLEMENTATION.md)로 승계 |
