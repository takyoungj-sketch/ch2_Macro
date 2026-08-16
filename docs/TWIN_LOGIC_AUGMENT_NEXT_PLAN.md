# 쌍둥이 로직 보강 — 계획 · 구현 방안 (SSOT)

> **작성:** 2026-08-12 · **갱신:** 실험 결과 기록 · 작업 일시 중지 · 재개 계획 (§11)  
> **작업명:** 쌍둥이 로직 보강 (UI: Twin Experiment Lab · `?lab=twin`)  
> **선행:** [`TWIN_LAB_SESSION_2026-08-12.md`](./TWIN_LAB_SESSION_2026-08-12.md) · [`TWIN_EXPERIMENT_LAB_IMPLEMENTATION.md`](./TWIN_EXPERIMENT_LAB_IMPLEMENTATION.md)  
> **상태:** ⏸ **일시 중지** — chungbuk40 RT-price까지 기록 완료. 재개 시 §11부터.

---

## 0. 한 줄

지역특성은 **지역 간(또는 시점 간) 변이가 있을 때만** 회귀계수를 추정할 수 있다.  
단일 읍면동 Local + **고정** 프로필 → region_*는 상수 → **R1≡R0는 ‘효과 없음’이 아니라 ‘식별 불가’**.  
실험 중심은 **R0 → T1 → RT**. R1(고정 프로필)은 전국 확대 금지·참고축만.  
**제품:** Local 모형추천 유지 · Twin을 “더 좋은 추천”으로 기본화하지 않음 · V3 보류.

```text
                 Local (R0)
                     │
            ┌────────┴────────┐
            ↓                 ↓
     지역특성 (식별 조건)      Twin (T1)
     · 다지역 표본            │
     · 또는 시점별 프로필      │
            │                 │
            └────────┬────────┘
                     ↓
              Twin + 지역특성 (RT)  ← 지역변수 검증의 본무대
```

같은 지역 프로필 원천을 **Twin 선정**과 **회귀 공변량**에 써도 된다.  
다만 역할을 분리해 평가한다 (선정 품질 ≠ 식 기여).

---

## 1. 핵심 수정사항 (2026-08-12 smoke에서 확정)

### 1.1 문제

한 지역의 거래만 있고 지역 프로필이 **시점 불변 스냅샷**이면:

```text
행1…행n 전부 region_population = 동일값
→ intercept와 완전 공선
→ β_region 을 따로 추정할 수 없음
→ R0와 R1의 CV-MAPE가 같아지는 것이 통계적으로 정상
```

엔진 실패가 아니다. **실험 설계 정의 문제**다.  
이 정의를 모른 채 R1을 전국 100~200곳에 확대하면 “지역특성 무효과”로 **오해**할 위험이 있다 → **금지**.

### 1.2 지역변수가 식별되려면

| 조건 | 설명 | 현재 데이터 |
|------|------|------------|
| **다지역 표본** | 거래에 A/B/C… 프로필이 섞임 | Twin pool (RT) ✅ |
| **시점 변이** | 동일 지역이라도 연도별 인구·가격수준이 행마다 다름 | 고정 스냅샷이면 ❌ |

임의로 여러 지역을 합치면 Twin 효과와 다지역 효과가 섞인다 → **실험 축을 Twin on/off × region on/off로 분리**해 둔 이유가 이것.

---

## 2. 실험 축 (개정)

| ID | 표본 | 공변량 | 지위 |
|----|------|--------|------|
| **R0** | Local only | 물건만 | ✅ 기준선 |
| **R1** | Local only | 물건 + region_* | ⚠️ **참고만**. 고정 프로필이면 식별불가 → R0와 동치 기대. **전국 확대·승패 판정에 쓰지 않음** |
| **T1** | Local + Twin | 물건만 | ✅ Twin 표본 효과 |
| **RT** | Local + Twin | 물건 + **행 발생지** region_* | ✅ 지역특성 추가효과 검증의 본무대 |

### R1 정의 (개정)

```text
R1 = Local + region_*
  · 허용: 거래 시점별로 다른 지역특성 시계열이 있을 때
  · 금지(판정용): 고정 현재 프로필을 단일동 Local에만 붙인 뒤 R1 vs R0로
               “지역특성 효과”를 주장하는 것
  · Lab: R1≡R0 이면 “무효과”가 아니라 “상수 → 식별불가(정상)”로 표기
```

### RT 정의 (유지·강조)

```text
Target A
 ├─ Local A  → profile(A)
 ├─ Twin B   → profile(B)
 ├─ Twin C   → profile(C)
 └─ Twin D   → profile(D)
```

앵커 프로필을 Twin 행에 복사하지 않는다 (방법 C 금지).

### 결과 읽는 법 (개정)

| 관측 | 올바른 해석 | 잘못된 해석 |
|------|-------------|-------------|
| R1≡R0 (고정 프로필·단일동) | 식별불가 · 설계상 정상 | “지역특성 효과 없음” |
| T1≪R0 | Twin pooling/선정 문제 | 바로 V3 |
| RT &gt; T1 이지만 ≪R0 | region이 Twin 손상을 일부 완화 · 표본 혼합 리스크가 더 큼 | “인구 넣어서 성공” (소표본에서 단정 금지) |
| RT≫R0 (다수 지역) | Twin+region 가치 입증 → V3·전국 확대 검토 | — |

성공 지표는 계속 **R0 대비 CV-MAPE lift**.  
비교의 중심은 **T1 vs R0**, **RT vs T1**, **RT vs R0**.

---

## 3. 지역특성 두 종류 · 투입 순서

| 종류 | 예 | Twin에서 왜 중요한가 |
|------|-----|----------------------|
| **① 가격수준** | land / apt / commercial p50 | Twin이 가져오는 **가격수준 차이**를 식에서 흡수할 후보 |
| **② 규모·활성도** | population, 거래량(n) | 시장 규모·유동성. Twin 선정에도 쓰일 수 있음 |

### 단계적 투입 (다음 벤치)

```text
1차 (가격수준만):  region_land_p50, region_apt_p50, region_comm_p50*
2차 (+활성도):     + region_population, region_*_n
```

\* commercial y와 `region_comm_p50`는 부분 순환 가능 → 해석 주의·opt-in.  
공장/단독은 유형별 p50로 동일 패턴.

**가설:** Twin의 핵심 리스크가 “가격수준이 다른 지역의 거래를 섞는 것”이라면 ①이 ②보다 먼저 먹혀야 한다.  
현재 파일럿에서 `region_population`만 채택된 것은 **신호가 아니라 소읍 수·공선·키 품질** 이슈로 보고, 1차 세트 강제/우선 탐색을 다음 실험에 넣는다.

---

## 4. 하드 규칙

1. **행 단위 join:** `row.eupmyeondong_code` → 그 지역 프로필. 앵커 복사 금지.  
2. **예측 시:** 앵커 물건 + **앵커** 지역특성.  
3. **region 연속변수와 `region_leaf` 더미 동시 투입 자제.**  
4. **R1(고정 프로필)은 판정축이 아님** — 전국 실험·go/no-go에 넣지 않음.  
5. **RT 해석 최소 조건:** 앵커+Twin으로 **읍면동 ≥ 수 개**·케이스 **수십 개** 규모. 2지역 smoke로 RT 승패 단정 금지.  
6. **프로필 스냅샷**은 Twin 배치와 동일 `profile_version` / `window_years` / as_of.  
7. 제품 recommend 기본: `include_region_features=False` (R0). Lab/실험만 opt-in.

---

## 5. 지역 프로필의 이중 역할 (분리 평가)

```text
지역 프로필
     ├──→ Twin 선정 (유사도·가중치)     … T1/RT의 이웃 품질
     └──→ 회귀 공변량 (행별 join)       … RT의 식 기여
```

같은 숫자를 써도 된다. Lab에서는  
(a) Twin만 (T1) vs (b) Twin+식 (RT) 를 나눠 lift를 본다.

---

## 6. 구현 상태 (요약)

| 항목 | 상태 |
|------|------|
| `region_features.py` 행별 join · 상수 블록 제외 | ✅ |
| Stage2에서 region_* 재투입 (RT 식별 경로) | ✅ |
| land 키 폴백 (`land_top1_mean_manwon_per_sqm`) | ✅ |
| Lab 4축 mart · Local/Pool/Twin n | ✅ |
| R1 식별불가 라벨/문서 | ✅ 본 개정 |
| 가격수준 1차 강제 탐색 | ⬜ 다음 |
| 수십 지역 RT 본실험 | ⬜ 다음 (전국 R1 확대 아님) |

---

## 7. 파일럿·스모크 결과 (해석 잠금)

### 7.1 commercial 충북12 (`pilot-commercial-r0r1-t1-rt`)

| 축 | median CV | lift vs R0 | 해석 |
|----|-----------|------------|------|
| R0 | 53.84 | — | 기준 |
| R1 | 53.84 | 0 | **식별불가(정상)** · 효과검증 아님 |
| T1 | 58.63 | −0.16 | Twin pooling 손해 우세 |
| RT | 58.18 | −0.16 | T1 대비 일부 케이스 완화 · R0는 못 이김 · population만 채택 |

승자: R0 9 · T1 2 · RT 1.  
→ **V3 근거 없음.** Twin 선정/pool 개선 또는 역할 축소 신호.

### 7.2 factory 2케이스 스모크 (`pilot-factory-r0r1-t1-rt-smoke`)

| 축 | median CV | lift |
|----|-----------|------|
| R0 | 56.6 | — |
| R1 | 56.6 | 0 (식별불가) |
| T1 | 63.4 | −0.13 |
| RT | 62.0 | −0.10 |

T1이 두 곳 모두 Local 악화. RT가 T1을 소폭 완화해도 Local보다 나쁨.  
**결론 범위:** “현재 Twin 5 pooling은 공장 smoke에서 문제” — RT/인구 효과 단정·전국 확대 근거로 쓰지 않음.

### 7.3 키 진단 (참고)

- land_*_median 미적재 → top1 폴백으로 coverage 회복, 채택은 여전히 population 치우침.  
- Twin 읍 2~4개에서 region 변수 상호 공선 → 가격수준 1차 실험이 필요.

---

## 8. 확정된 실험 구조 (잠금)

| 축 | 역할 | 판정 |
|----|------|------|
| **R0** | Local only 기준선 | ✅ |
| **R1** | 참고 — 단일지역·고정 프로필에서 지역변수 식별불가 | ❌ 승패·전국 확대 금지 |
| **T1** | Local + Twin → 표본 보강 효과 | ✅ |
| **RT** | Local + Twin + 지역특성 → 결합 효과 | ✅ |

**검증 중심:** `R0 → T1 → RT`  
**지역변수 순서:** ① 가격수준(토지·아파트·대상유형) → ② 거래량(토지·아파트·대상유형 n) · 인구는 2차  
**RT 성공 단정:** 2지역 smoke(T1 63.4→RT 62.0 등)로 하지 않음. **최소 수십 읍면동**에서 R0→T1, T1→RT 패턴이 반복될 때만.

한 줄 방향:

> R1은 참고용. 진짜 실험은 Local → Twin → Twin+지역 가격수준을 여러 읍면동에서 반복하고,  
> 성능 숫자만이 아니라 **최적 회귀식 + 실제 채택 지역변수 + Twin pool + CV-MAPE + Lift**를 한 세트로 저장한다.  
> V2/V3를 미리 정하지 않고, 그 결과에서 다음 Twin 버전(가중치)을 도출한다.

```text
                 Local (R0)
                   │
              ┌────┴────┐
              ↓         ↓
         지역특성*     Twin (T1)
              │         │
              └────┬────┘
                   ↓
             Twin + 지역특성 (RT)

* 고정 프로필 → Local alone에서 판정용으로 쓰지 않음
```

---

## 9. 차기 구현 계획 (다음 세션 · 코드 착수 체크리스트)

> 본 절만 보고 이어서 작업하면 된다. **지금은 문서만.** 전국 벤치는 mart 스키마·1차 블록 플래그 준비 후.

### 9.1 Lab / Mart — 채택 변수 세트 저장 (우선)

케이스마다 최소 아래를 mart에 **구조화 저장** (문자열 notes 금지).

| 필드 | 설명 |
|------|------|
| `cv_mape` / `lift_rel` / `delta_pp` | 기존 |
| `blocks` | **최종 최적식** 블록 전체 (물건+region) |
| `region_blocks_selected` | `blocks` ∩ region_* 만 (식에 들어간 것만) |
| `region_blocks_candidate` | Twin pool 탐색 풀에 들어온 region_* (탈락 포함) |
| `region_tier` | `"price"` \| `"price+activity"` — 해당 런의 후보 세트 |
| `n_local` / `n_pool` / `n_twins` / `pool_id` | 표본 구성 |
| `twins[]` | Twin 코드·sim (기존) |

비교표(CSV·Lab) 열 예:

```text
지역 | R0 CV | T1 CV | RT CV | RT Lift | region 채택 | RT 식 블록 | pool_id | n_local | n_pool
```

나중에 집계:

- “RT가 좋아진 케이스에서 어떤 region_*가 반복 채택되는가?”  
- 유형별(commercial/factory/detached) 채택 빈도 → **Twin 가중치 설계 입력**

Lab UI: 이미 “식에 들어간 region만 채택 표시” — mart·CSV·overview 표를 동일 SSOT로 맞춤.

### 9.2 엔진 — 가격수준 1차 후보 세트

| 단계 | region 후보 | 비고 |
|------|-------------|------|
| **RT-price (1차)** | `region_land_p50`, `region_apt_p50`, (+ 유형) `region_comm_p50` / factory·detached 대응 | population·`*_n` **제외** |
| **RT-full (2차)** | 1차 + `region_population` + `region_*_n` | 1차에서 신호 있을 때만 |

구현 스케치:

- `region_blocks_for_asset(asset, tier="price"|"full")`  
- bench/`include_region_features`에 `region_feature_tier` 전달  
- 기존 land top1 폴백 유지 · 정규 `land_*_median` 적재는 별도 파이프라인 이슈로 추적

### 9.3 Bench — 수십 읍면동 × R0/T1/RT

```text
1. fixture: commercial (및/또는 factory) 읍면동 ≥ ~40–80 (충청→전국 점진)
2. axes: r0, t1, rt   (± r1은 부록·소량만, 판정 제외)
3. RT 런: region_tier=price 고정
4. twin profile: 유형별 built_* 유지 (가중치는 이번엔 안 건드림)
5. 산출: experiment_id + raw + lab mart + comparison CSV
6. KPI: median lift R0→T1, T1→RT, R0→RT · hit/worsen · region 채택률(블록별)
```

**성공 선언 금지 조건 재확인:** n_cases 작거나 Twin 읍 수가 극소(예: 대부분 top1=2읍)이면 RT lift를 “지역변수 성공”으로 쓰지 않음.

### 9.4 분석 → Twin 버전 도출 (벤치 이후 · V3 아님)

채택 빈도 표가 쌓이면:

| 관찰 예 | Twin 설계에의 함의 |
|---------|-------------------|
| commercial: land·comm p50 자주 채택, population 드묾 | 유사도에서 가격수준 축 강화 후보 |
| factory: land·factory p50, apt 드묾 | 유형 전용 가격축 유지·강화 |
| detached: apt·population | 주거권 가격·규모 축 |

→ **임의 % 가중치를 선험적으로 박지 않고**, 회귀 채택 패턴으로 V_next weight profile을 설계.  
이 단계 전까지 V3 탐색 착수하지 않음.

### 9.5 착수 순서 (다음 세션)

```text
[x] R1 식별불가 문서·Lab 라벨 (완료)
[x] 9.1 mart 스키마 + CSV/비교표 열 (region 채택·식 블록·tier·adoption)
[x] 9.2 region_feature_tier=price|full (엔진·Stage2·bench --region-tier)
[x] 9.3 commercial chungbuk40 × R0/T1/RT-price 벤치
[x] 채택빈도 요약 — **RT 성공 단정 아님** → 상세 §10
[ ] (후속) §11 재개 계획으로 이관
```

**구현 메모:** `region_feature_tier` · mart 1.1/CSV/adoption · bench `--region-tier price` · `--skip-axes r1`

---

## 10. 실험 결과 기록 (2026-08-12 체크포인트)

### 10.1 산출물 경로

| 종류 | 경로 / ID |
|------|-----------|
| **주 해석 mart** | `logs/twin_lab/pilot-commercial-chungbuk40-r0-t1-rt-price.json` |
| CSV | `logs/twin_lab/pilot-commercial-chungbuk40-r0-t1-rt-price.csv` |
| raw | `logs/twin_lab/pilot-commercial-chungbuk40-r0-t1-rt-price.raw.json` |
| Lab | `http://localhost:5174/built/?lab=twin` → 위 experiment_id |
| 선행 12축 | `pilot-commercial-r0r1-t1-rt` (R1≡R0·Stage2 region 재투입 검증) |
| factory smoke | `pilot-factory-r0r1-t1-rt-smoke` (2케이스, Twin 악화 패턴 동일) |
| price smoke | `smoke-commercial-r0-t1-rt-price` (land 채택 확인) |

### 10.2 chungbuk40 × R0/T1/RT-price (본실험)

설정: commercial · 충북 eup 40 · Twin `built_commercial` · `region_feature_tier=price` · R1 skip.

| 축 | median CV-MAPE | median lift vs R0 |
|----|----------------|-------------------|
| **R0** Local | 50.5 | — |
| **T1** +Twin | 58.4 | **−0.14** |
| **RT** +Twin+가격수준 | 57.7 | **−0.11** |

| 지표 | 값 |
|------|-----|
| 승자 | R0 **28** · RT 7 · T1 5 |
| T1이 R0 이김 | 10/40 |
| RT가 R0 이김 | 12/40 |
| RT vs T1 | 나음 **24** · 같음 16 · 나쁨 **0** |
| median T1→RT lift | ≈ +0.007 (상대) |
| region 후보 진입 | 38/40 |
| region **식 채택** | **23/40** — 전부 `region_land_p50` |
| apt_p50 / comm_p50 채택 | **0** |
| RT&gt;T1 중 land 채택 | 23/24 |
| land 있을 때 median T1→RT | +0.024 · 없을 때 0 (대개 RT≡T1) |
| land 있을 때 median R0→RT | **−0.16** (전체 −0.11보다 나쁨) |

**해석 잠금**

1. Twin 표본 보강(T1)은 중앙값·다수결에서 Local보다 나쁘다.  
2. 가격수준(land) RT는 Twin 손상을 **완화·유지**하며 T1보다 나빠지지 않는다. Local 대체는 못 함.  
3. land 채택은 「T1→RT 개선」에 가깝고, 「R0 대비 성공」이 아니다 (이미 Twin이 깨진 케이스 되돌림).  
4. R1≡R0는 식별불가(정상) — 효과 없음으로 읽지 말 것.  
5. **RT 성공·V3 착수 선언 금지.**

### 10.3 제품(복합 모형추천)에의 함의

| 함의 | 조치 |
|------|------|
| Local 추천(R0)은 근거 있음 | **기능 유지** — 제거하지 않음 |
| Twin을 “더 정확”으로 기본화하면 위험 | Stage2 Twin **opt-in·조건부** · Local 미개선 시 비추천 |
| region 공변량 제품 기본 | **보류** (`include_region_features=False` 유지) |
| Twin 유사도 | land 가격수준 축 강화는 **후보** (문서만, 코드 후순위) |

### 10.4 같은 날 구현·설계 완료분 (재개 시 전제)

- R1 식별불가 Lab 라벨 · 판정에서 R1 제외  
- Stage2 region_* 재투입 (Local 상수 제외 후 RT 식별 경로)  
- land 키 폴백 `land_top1_mean_manwon_per_sqm`  
- `region_feature_tier=price|full` · mart 1.1 · CSV · `region_adoption`  
- bench: `pipeline/bench_region_twin_axes.py` (`--region-tier price`, `--skip-axes r1`)

---

## 11. 차후 작업 계획 (재개 시)

> 나중에 이 문서 §11만 보고 이어가면 된다. **지금 코드 착수하지 않음.**

### 11.1 제품 경로 (우선순위 높음)

```text
[ ] Twin 채택 게이트: Stage2 결과가 Local CV를 이기지 않으면 추천식에 올리지 않음 (참고만)
[ ] UX/카피: Twin = 표본 부족 시 검토 옵션 · “넣으면 더 정확” 문구 제거·완화
[ ] include_region_features 제품 기본 False 유지 확인
[ ] (하지 않음) 모형추천 기능 제거 · Twin 전면 삭제
```

### 11.2 Twin 품질 (실험 병목)

```text
[ ] T1 worsen 원인: top1 vs n3/n5 · 가격수준 gate · 유사도 축 (land 반영 후보)
[ ] land 강제 투입 vs 자유 선택 ablation (chungbuk40 일부)
[ ] 정규 land_*_median 프로필 적재 여부 파이프라인 점검
```

### 11.3 Lab / 분석 (후순위)

```text
[ ] 채택패턴 → Twin weight 개정안 **문서만** (commercial: land 축 강화 초안)
[ ] (선택) factory/detached 동일 R0/T1/RT-price 수십동
[ ] V3 가중치 탐색: RT≫R0가 다수 지역에서 나온 뒤에만
```

### 11.4 재개 체크리스트

```text
1. 본 문서 §10 결과·함의 재확인
2. Lab에서 pilot-commercial-chungbuk40-r0-t1-rt-price 열기
3. §11.1 제품 게이트부터 (실험 확대보다 제품 안전이 먼저)
```

---

## 12. 비범위 (유지)

- 고정 프로필 R1 전국 확대·승패 판정  
- 소표본/smoke로 RT 성공 선언  
- V3 즉시 · 지역 더미 · 앵커 특성 복사 · 상대지수 1차  
- 제품 기본 풀에 region 강제  
- Twin 가중치 임의 재설정 · 모형추천 기능 제거  

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-08-12 | 초안 R0/R1/T1/RT |
| 2026-08-12 | 방법 A~E · Local-only 상수 이슈 언급 |
| 2026-08-12 | P2/P3 파일럿·land 폴백·factory 스모크 |
| 2026-08-12 | R1 정의 개정: 식별불가 · RT 중심 · 가격수준 1차 |
| 2026-08-12 | region_feature_tier · mart 1.1/CSV · chungbuk40 RT-price |
| 2026-08-12 | **체크포인트:** §10 결과 기록 · §11 재개 계획 · 제품=Local 유지·Twin 조건부 · 작업 일시 중지 |
