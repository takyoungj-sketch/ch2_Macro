# Twin Experiment Lab — 구현 계획 (SSOT)

> **작성:** 2026-08-11  
> **상태:** 구현 계획 (코딩 전 프로토콜 고정)  
> **성격:** 관리자·R&D 전용. **일반 사용자 `/built/` 모형추천 UI와 분리**  
> **상위·관련:**  
> [`TWIN_BUILT_RECOMMEND_COMPLEMENT_PLAN.md`](./TWIN_BUILT_RECOMMEND_COMPLEMENT_PLAN.md) (초기 상호보완 계획 — 본 문서가 **실험·Lab·버전 정의**를 승계·구체화) ·  
> [`CH2_RECOMMENDATION_ENGINE_DESIGN.md`](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) ·  
> [`PROFILE_TWIN_HYBRID.md`](./PROFILE_TWIN_HYBRID.md)

---

## 0. 한 줄 목적

> Twin을 **유사도 점수**로 평가하지 않는다.  
> **V0 Local 최적식 대비**, Twin pool 후 **동일 회귀 엔진·동일 CV**에서 나온 **CV-MAPE 개선(Lift)** 으로 V1/V2/V3를 고른다.  
> 그 과정을 **Experiment Lab UI**에서 지역·식·Twin 후보까지 눈으로 검증한다.

---

## 1. 의사결정 요약 (본 문서의 채택안)

GPT 제안·내부 논의를 참고하되, **아래를 채택 기준으로 한다.**

| 주제 | 채택 | 비고 (GPT 안과의 관계) |
|------|------|------------------------|
| 성공 지표 | Local(V0) 대비 **CV lift** | 동의 |
| V0 | **필수** Local Only baseline | 동의·강화 |
| 실험 단위 | **유형별 독립** (commercial / factory / detached) | 동의. 통합 회귀는 2차 메타만 |
| Twin scope (읍면동) | 제품과 동일 **`region`**. STEP1–2 앵커도 **한 권역** | 전국 앵커는 STEP2b+ |
| V1 | 현행 `general` (인구·토지·apt·mix) — **구축됨** | 동의 |
| **V2 (주경로)** | **Target 유형 시장 블록 추가** + 고정 가중 YAML | 예: 상가 실험 → `built_commercial` |
| **V2 ablation (부)** | `V2-all-built` — 상가·공장·단독 블록을 **한 벡터에 넣고 가중 고정** | GPT 주경로 안 → **내부 ablation으로 보존** |
| **V3** | Target-specific **가중 최적화** (dev 셋) → **holdout 검증** | GPT 동의. V1/V2 **이후**에만 정의·실행 |
| 표본 | 유형별 n 하한 + **층화 무작위** 읍면동 | 순수 national random ❌ |
| UI | **Twin Experiment Lab** 3화면, 비공개 | 동의·우선 구현 |
| 회귀 | 버전마다 **독립 재탐색** · 제품 stage2 `optimize` SSOT | 식 고정 diagnose ❌ |
| 토지·집합 | **별 트랙** (`twin_profile=land` 등). V2/V3에 끼워 넣지 않음 | 확장 원칙만 명시 |

### 왜 V2 주경로를 “유형 블록”으로 하는가

- 질문 단위가 **「이 asset_type 회귀를 Twin이 개선하는가」** 이므로, Twin 입력도 **그 유형 신호**를 먼저 넣는 편이 원인 해석이 깔끔하다.  
- GPT안(V2에 전 built 유형을 한꺼번에)은 의미가 분명하나, **한 번에 여러 블록이 들어가 lift 귀속이 어렵다.**  
- 따라서 **주 비교 = V0 / V1 / V2-target**.  
  **V2-all-built**는 같은 Lab·마트에 ablation 열로 남겨 “전 유형 동시 투입만으로도 되나?”를 본다.

### V3를 1차 동급으로 두지 않는 이유

V3는 가중 탐색이므로 **개발 표본에 과적합**하기 쉽다.  
순서: V1 vs V2-target 확정 → (선택) V2-all-built ablation → **dev에서 V3 가중 탐색** → **holdout에서만** V3 go/no-go.

---

## 2. 실험 프로토콜 (코딩 전 고정 6항목)

### 2.1 버전 정의

| ID | Twin 후보 | 회귀 표본 |
|----|-----------|-----------|
| **V0** | 없음 | Local only |
| **V1** | algo 21 · `twin_profile=general` | Local + V1 pool |
| **V2** | algo 21 · `twin_profile=built_{asset}` (상가=`built_commercial`, 이후 factory/detached 형제) | Local + V2 pool |
| **V2x** (ablation) | `built_all` 또는 동등 — commercial+factory+detached 블록, **가중 고정** | Local + V2x pool |
| **V3** | V2(또는 V2x) 벡터 + **target별 가중 YAML** (dev 최적화본) | Local + V3 pool |

- Pool 규칙 **1차 고정:** recommend hard gate 통과 후 **`top3`만** (제품 UI의 top1/3/전체 동시와 분리).  
- Twin 배치: Profile window·`profile_version`·`as_of`·scope **실험 run마다 고정 기록**.

### 2.2 회귀 탐색 (전 버전 동일 엔진)

- 엔진: `POST /api/built/regression/recommend` 과 동일 SSOT (best-subset · `mode=optimize` 경로).  
- 고정: asset_type, contract window(5y 1차), 변수 후보 pool, subset cap, 이상치 정책, response_scale 후보.  
- **버전마다 독립 재탐색** (V1 식을 V2에 강제 ❌).  
- 평가: **CV-MAPE** (rolling-time). in-sample MAPE/R²로 버전 선정 ❌.

### 2.3 CV

| 층 | 내용 | 단계 |
|----|------|------|
| **Paired** | V0~V3 **동일 fold 연도 구조**로 점수 산출·마트 기록 | STEP1부터 필수 |
| **Leakage-aware** | Twin **재빌드**를 fold train만으로 — 최종 후보만 | STEP2 후반~STEP3 |
| Twin 입력 (기본) | **사전 배치 neighbor** (제품과 동일). fold마다 Twin 재선정 ❌ (연산·현행 아키텍처) |

### 2.4 KPI

마트·Lab에 **둘 다** 저장. 1차 랭킹은 `lift_rel`.

\[
\Delta_{pp} = \mathrm{CV}_{V0} - \mathrm{CV}_{Twin},\quad
\mathrm{lift}_{rel} = \frac{\mathrm{CV}_{V0} - \mathrm{CV}_{Twin}}{\mathrm{CV}_{V0}}
\]

| KPI | 용도 |
|-----|------|
| Median / mean CV-MAPE | 수준 |
| Median / mean `lift_rel`, `delta_pp` | 개선 |
| Hit rate (`lift_rel` ≥ δ, δ 예: 0.05) | 승률성 |
| Worsened rate (`lift_rel` < 0) | 위험 |
| MdAPE (보조) | MAPE 왜곡 보완 |
| Twin pool Jaccard (as_of·임계 민감) | 안정성 |
| Winner (argmin CV among V1..V3, **V0보다 나쁠 수 있음 → 표기**) | 참고만. 선정은 median lift 우선 |

R²·AIC는 **식 기록·설명용**. 버전 선정 KPI 아님.

### 2.5 표본 (읍면동)

1. grain = **읍면동**  
2. Twin scope = **`region`** (제품 기본)  
3. STEP1–2: 앵커 모집단 = **단일 권역** (예: 충청; fixture와 정합)  
4. 유형별 **최소 Local n** (초기안, 튜닝 가능):

| asset | 5년 Local n 하한 (초안) |
|-------|-------------------------|
| commercial | ≥ 30 |
| factory | ≥ 20 |
| detached | ≥ 40 |

5. 층화: 권역 내 시·군 규모 × 표본 분위(소/중/대) → 층별 랜덤  
6. 표본을 **dev / holdout** 분할 (예: 70/30). **V3 가중 탐색은 dev만.**  
7. Pilot: 기존 `pipeline/fixtures/twin_built_lift_bench.json` (~8) 유지

### 2.6 유형별 실험 → 통합은 메타만

```text
실험 A commercial  →  V0/V1/V2(/V2x)/V3 → 마트 A
실험 B factory     →  동일 프로토콜 · twin_profile=built_factory
실험 C detached    →  twin_profile=built_detached
        ↓
메타: property_type × volume × region × version 회귀/표
      (유형을 한 OLS에 더미로 넣어 Twin을 평가하지 않음)
```

데이터 규모(대략): 상가 7.4만/9.5만 · 공장 3.2만/4만 · 단독 23.7만/31.5만 (5y/7y).  
단독이 공장을 압도하므로 **통합 단일 실험은 금지.**

---

## 3. Twin Experiment Lab UI

### 3.1 원칙

- **비공개 R&D.** 내비·허브에 일반 노출 ❌.  
- 접근: env 플래그 + API 토큰 (예: `VITE_TWIN_LAB=1`, 라우트 `/built/lab/twin-experiment`).  
- 제품 `RecommendationModal`과 **코드·카피 공유 최소화** (읽기 전용 조회 UI).  
- 데이터: 결과 마트 API만. 실험 실행은 **pipeline CLI** (UI에서 전국 재실험 버튼은 2차).

### 3.2 화면 3종

#### (1) Overview

- 필터: `asset_type` · `experiment_id` · 기간(5y/7y) · 권역 · sample_group(dev/holdout/all)  
- 버전 카드/표: Median Lift, Hit, Worsened, Median CV-MAPE (V0는 MAPE만)  
- CTA: 지역별 결과 · V1↔V2 · (V3 준비 시) V3 · Twin 상세

#### (2) Region Explorer (핵심)

선택 읍면동에 대해:

- 거래 건수 (해당 유형·창)  
- **V0:** 식(블록·scale) · CV-MAPE · (보조) adj R² · AIC  
- **V1/V2/V3:** Twin top3 (코드·라벨·similarity) · 식 · CV-MAPE · lift_rel / delta_pp  
- “무엇이 바뀌었나”: 선택 블록 diff · pool_n

숫자 요약만 보지 않고 **식 + Twin 후보**를 같이 보는 것이 Lab의 존재 이유다.

#### (3) Version Comparison

- 행 = 읍면동, 열 = V0..V3 MAPE · lift · winner  
- 행 클릭 → Region Explorer  
- CSV 내보내기 (연구 백업)

### 3.3 UI 구현 위치 (제안)

| 항목 | 제안 |
|------|------|
| 앱 | `frontend-built` 내부 lab 라우트 (빌드·토큰 공유) |
| API | `backend/app/recommendation/` 또는 `regional_profile` 옆 `GET /api/built/lab/twin-experiments*` |
| 권한 | `API_TOKEN` + (선택) `TWIN_LAB_ENABLED=1` |

와이어는 사용자 스케치(성능 요약 → 지역별 → 비교)를 그대로 따른다. 시각은 기존 built 톤 유지, **실험 배너**(`R&D · 비공개`) 고정.

---

## 4. 결과 마트 스키마 (최소)

구현은 Postgres(권장: `built_stats` 또는 실험 스키마) 또는 1차는 JSONL → 이후 DDL.

### 4.1 `twin_experiment_run`

| 컬럼 | 내용 |
|------|------|
| experiment_id | PK |
| asset_type | commercial / factory / detached |
| period_years | 5 / 7 |
| region_scope | Twin scope + 앵커 권역 코드 |
| profile_version · catalog_version | 재현 |
| cv_spec | fold 연도·규칙 JSON |
| pool_variant | `top3` |
| created_at · git_sha · notes | |

### 4.2 `twin_experiment_region`

| 컬럼 | 내용 |
|------|------|
| experiment_id · region_code · region_label | |
| sample_group | dev / holdout / pilot |
| strata | JSON |
| local_n · tx_count | |

### 4.3 `twin_experiment_version_result` (지역 × 버전)

| 컬럼 | 내용 |
|------|------|
| experiment_id · region_code · version | v0/v1/v2/v2x/v3 |
| twin_profile · weight_version | |
| twin_codes · similarity_scores | JSON |
| pool_n · twin_n_added | |
| formula / blocks / response_scale | |
| cv_mape · mdape · adj_r2 · aic | |
| delta_pp · lift_rel · hit · worsened | vs V0 |
| cv_fold_ids | 재현 |

### 4.4 `twin_experiment_kpi` (런 × 버전 집계)

median/mean lift, hit_rate, worsened_rate, median_cv_mape, n_regions, compute_seconds.

---

## 5. 파이프라인 · 엔진 연동

```text
[배치] build_twin_profile --twin-profile general|built_commercial|…
        ↓
[샘플] select_bench_eupmyeondong.py → fixture JSON (dev/holdout)
        ↓
[벤치] bench_twin_built_recommend_lift.py
        · 지역 × V0/V1/V2(/V2x)(/V3)
        · recommend SSOT · paired CV
        · → JSONL / COPY 마트
        ↓
[API]  lab read endpoints
        ↓
[UI]   Twin Experiment Lab
```

**재사용:** 기존 `pipeline/bench_twin_built_recommend_lift.py`, fixture 8곳, stage2 `optimize`, `twin_validation` + pooling hard gates.

**신규:** 층화 샘플러, 마트 writer, lab API, lab FE, (V2) factory/detached weight YAML·catalog 블록, (V3) weight search + holdout eval 스크립트.

---

## 6. 구현 로드맵 (Lab 중심)

| Phase | 내용 | 산출 | 의존 |
|-------|------|------|------|
| **L0** | 본 문서 프로토콜 확정 · 구 계획서에 승계 링크 | SSOT | — |
| **L1** | 마트 DDL(또는 JSONL 스키마) · bench가 V0/V1/V2-commercial write | Pilot 적재 | V2 commercial **배치** |
| **L2** | Lab API + **Overview + Comparison 표** | 숫자 확인 | L1 |
| **L3** | **Region Explorer** (식·Twin 리스트·lift) | 연구실 UX | L2 |
| **L4** | 권역 내 층화 50~100 · commercial · dev/holdout | Benchmark | L1 |
| **L5** | V2x ablation (all-built) 선택 실행 | 비교 열 | catalog 확장 |
| **L6** | factory / detached `twin_profile` + 동일 Lab | 유형 확장 | L4 패턴 복제 |
| **L7** | V3 가중 탐색(dev) + holdout 검증 · Lab V3 열 | go/no-go | L4 |
| **L8** | 제2 권역 재현 · 메타 분석 노트 | 일반화 | L4+ |
| **L9** | 채택 프로필 → 제품 Twin/recommend 반영 | B9 | 검증 후 |

제품 모형추천 UX 개선은 Lab과 **병행 가능**하나, **알고리즘 선정 판단은 Lab KPI만** 사용한다.

---

## 7. 확장 원칙 (토지·집합)

```text
Target domain
  → twin_profile (general → domain market → target weights)
  → domain regression recommend (Local → Twin pool)
  → 동일 Lab 패턴 (별 experiment_id / asset 축)
```

| 도메인 | twin_profile (예) | 비고 |
|--------|-------------------|------|
| 복합 상가 | `built_commercial` | 1차 |
| 복합 공장/단독 | `built_factory` / `built_detached` | L6 |
| 토지 | `land` | L0 후속 — 복합 벡터에 혼합 ❌ |
| 집합 | collective_* | 별도 |

---

## 8. 비범위 / 금지

- Lab을 `/built/` 기본 내비에 노출  
- 유형 통합 OLS로 Twin 버전 선정  
- V3를 V1/V2와 **동시 1차 비교**에 넣기  
- Similarity 점수로 버전 승자 결정  
- Twin scope=`national`을 버전 선정 축과 교차 (ablation만)  
- holdout으로 V3 가중을 다시 튜닝

---

## 9. 수용 기준 (Definition of Done)

**Pilot (L1–L3)**

- [x] Lab Overview / Region Explorer / Comparison UI (`?lab=twin`) + demo mart  
- [x] Comparison CSV 내보내기  
- [x] 층화 샘플러 (`twin_lab/select_bench_eupmyeondong.py`) · 충북 commercial 40곳 fixture  
- [x] `built_commercial` Twin 배치 (충북 eup, as_of=2026-06-01)  
- [x] fixture 8곳 × V0/V1/V2 **실측** 마트 `logs/twin_lab/pilot-commercial-live.json`  
  - 유효 Local CV 4곳(표본 부족 4곳 SSOT 풀 빈 오류)  
  - **V2(`built_commercial`) median lift_rel +0.09 / hit 50%** vs V1(`general`) −0.12 / hit 25%  
  - `profile_compare.secondary_better_cases = 3/3` (비교 가능 케이스)  
  - beop: `built_commercial` 배치 미구축 → V2 beop 메타 error; SQL 컬럼은 `twin_region_code` 로 수정됨  
- [x] 충북 eup `n≥50` 12곳 실측 마트 `logs/twin_lab/pilot-commercial-chungbuk12.json`  
  - Local/Stage2 **12/12 성공** (error 0)  
  - V1 median lift_rel **−0.19** / V2 **−0.16** (둘 다 V0 대비 평균적으로 악화; hit 각 16.7%)  
  - winner 분할 **V1 6 : V2 6** — 소표본 pilot(+0.09)보다 보수적 신호  
- 재현용 fixture: `twin_bench_commercial_pilot_eup4.json`, `twin_bench_commercial_chungbuk12.json`  

**Lab 열기:** `http://localhost:5174/built/?lab=twin` → `pilot-commercial-chungbuk12` 또는 `pilot-commercial-live`  





**Benchmark (L4)**

- [x] 층화 샘플 12곳(고n) + fixture 40곳 · mart에 **dev/holdout** (`kpis_by_sample_group`, Lab Overview 탭)  
- [x] V1 vs V2 해석 노트: [`TWIN_LAB_COMMERCIAL_V1_V2_NOTE.md`](./TWIN_LAB_COMMERCIAL_V1_V2_NOTE.md)  
- [x] L6: `built_factory` / `built_detached` weight·catalog·similarity  
  - 충북 Twin 배치 완료 (commercial/factory/detached/**built_all**)  
  - 실측: factory8 · detached8 · **detached24** (V2 median lift +0.015, holdout +0.16)  
  - V2x/pool 실측: `pilot-commercial-chungbuk12-v2x` — V2x −0.21, top3 고정 −0.32 (V2-target −0.16이 덜 나쁨)  



**V3 (L7)** — **보류** (2026-08-12: 전국 V2·pool 벤치 후 재개)

- [ ] dev 가중 ≠ holdout 재튜닝  
- [ ] `V3 lift > V2` (holdout) 또는 기각 문서화  
- [x] Lab/마트에 sample_group KPI 슬롯 (가중 탐색 전 인프라)  

**다음 실행 순서:** [`TWIN_LOGIC_AUGMENT_NEXT_PLAN.md`](./TWIN_LOGIC_AUGMENT_NEXT_PLAN.md)  
→ **R0 / R1 / T1 / RT** (지역특성 vs Twin 분리) → 전국·유형별 → (조건부) Twin V2-pool / V3.  
세션 기록: [`TWIN_LAB_SESSION_2026-08-12.md`](./TWIN_LAB_SESSION_2026-08-12.md)

---

## 10. 구 계획서와의 관계

| 구 `TWIN_BUILT_RECOMMEND_COMPLEMENT_PLAN` | 본 문서 |
|------------------------------------------|---------|
| Local = A조건 | **V0**으로 명시 |
| V3 = gate 미세조정 (모호) | **V3 = target 가중 + holdout** |
| B5 마트 | Lab 스키마 §4로 구체화 |
| B0–B10 | **L0–L9**가 실험·UI 실행 순서. 제품 B9는 L9 이후 |

구 계획서 §0~§4 정신(표본 확장·CV·벤치 우선)은 유지한다. **버전·Lab·유형별 실험의 SSOT는 본 문서**다.

---

## 11. 구현 현황 (코드)

| 항목 | 경로 |
|------|------|
| Lab mart 변환 | `pipeline/twin_lab/mart.py` |
| Bench → Lab | `bench_twin_built_recommend_lift.py --lab-out … --compare built_commercial` |
| Demo mart | `pipeline/fixtures/twin_lab_pilot_demo.json` · `logs/twin_lab/pilot-commercial-demo.json` |
| API | `GET /api/built/lab/twin-experiments` · `/{id}` · `/{id}/regions/{key}` |
| Store | `backend/app/built/lab_twin_store.py` |
| FE Lab | `frontend-built` → `http://localhost:5174/built/?lab=twin` |

실측 적재 예:

```bash
cd pipeline
python bench_twin_built_recommend_lift.py --compare built_commercial \
  --lab-out ../logs/twin_lab/pilot-commercial-live.json \
  --experiment-id pilot-commercial-live
```

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-08-11 | 초안 — Lab UI · V0~V3 채택안 · 유형별 실험 · 층화·권역 · 마트 · L0–L9 · GPT안은 V2x ablation으로 수용 |
| 2026-08-11 | L1–L3 초판 구현 — demo mart · lab API · FE Lab (`?lab=twin`) · bench `--lab-out` |
| 2026-08-12 | 충북 파일럿 실측·V2x/pool · V3 보류 · 다음 계획 → [`TWIN_LAB_SESSION_2026-08-12.md`](./TWIN_LAB_SESSION_2026-08-12.md) |
