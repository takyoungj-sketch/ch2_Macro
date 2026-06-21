# 회귀 실험 — 지역효과 vs Regional Profile (1단계)

작성: 2026-06-21 · 스크립트: `pipeline/collective_commercial/exp_region_vs_profile.py`

## 1. 배경·동기

복합부동산(상업·업무용/단독) 회귀에 **건물 구조(RC/철골/조적)** 변수가 빠져 있다.
원본 실거래의 **지번이 마스킹(`4**`)** 되어 건축물대장 조인이 어렵고(엑셀 테스트 매칭률 <30%),
구조를 확보하려면 비용이 크다. 그래서 **구조 확보에 투자하기 전에** 다음을 먼저 검증한다.

> "지역효과(특히 Regional Profile)가 구조보다 더 큰 설명변수가 아닌가?
>  그렇다면 매칭에 몇 달 쓰기 전에 지역 baseline부터 강화하는 게 ROI가 높다."

핵심 통찰: **Regional Profile = 연속형으로 일반화한 지역 고정효과(FE).**
지역 더미(청주=1/천안=0)보다 `토지 baseline 1.12`처럼 넣으면 지역 간 일반화가 가능 →
CH2 Macro만의 차별점이 될 수 있다.

## 2. 실험 설계

- **매칭 불필요** — 거래를 지역코드로 profile/더미만 붙임.
- **심판(KPI) = CV-MAPE / CV-R²(log)** (5-fold). in-sample adjR²·AIC는 참고만.
  - 이유: 읍면동 더미는 자유도를 빨아먹어 in-sample R²를 항상 올림 → 과적합. 공정 비교는 out-of-sample뿐.
- **누수(leakage) 점검 통과**: Regional Profile에는 *상업·업무용 건물 단가 피처가 없음*
  (인구·밀도·토지단가·아파트/연립/오피스텔 시장·용도지역 구성비뿐) → y(건물가)와 다른 자산군이라 안전.
- y: 집합상가 `log(unit_price)`, 복합부동산 `log(price)` (면적은 X로).
- base(헤도닉): `log_연면적 (+log_대지면적, 복합) + 연식 + 층대(지하/1층/고층) + 용도지역 + 건축용도 + 계약연도`.
- 모델: `base / 시군구더미 / 읍면동더미 / Profile시군구(전부) / Profile읍면동(전부)`
  + **블록 분해**: `Profile = 인구 / 토지시장 / 주거집합(아파트·연립·오피스텔) / 전부`.

## 3. 결과 (충북, 2021–2025)

### 집합상가 (collective_shop, n=5,731)
| 모델 | CV-MAPE | CV-R²log |
|---|---|---|
| base | 65.3% | 0.619 |
| 시군구 Dummy | 62.8% | 0.636 |
| **읍면동 Dummy** | **60.2%** | **0.660** |
| Profile 시군구(전부) | 63.5% | 0.628 |
| Profile 읍면동(전부) | 63.7% | 0.630 |

### 복합부동산 상업일반 (built/commercial, n=3,533, 지역코드 매칭 57%)
| 모델 | CV-MAPE | CV-R²log |
|---|---|---|
| base | 47.6% | 0.725 |
| 시군구 Dummy | 44.4% | 0.755 |
| **읍면동 Dummy** | **43.1%** | **0.765** |
| Profile 시군구(전부) | 45.1% | 0.746 |
| Profile 읍면동(전부) | 45.9% | 0.737 |
| └ 인구만 | 47.1% | 0.728 |
| └ **토지만** | **46.2%** | 0.734 |
| └ 주거집합만 | 47.1% | 0.728 |

### 복합부동산 단독·다가구 (built/detached, n=18,354, 지역코드 매칭 64%)
| 모델 | CV-MAPE | CV-R²log |
|---|---|---|
| base | 47.8% | 0.594 |
| 시군구 Dummy | 43.3% | 0.657 |
| **읍면동 Dummy** | **41.1%** | **0.688** |
| Profile 시군구(전부) | 43.8% | 0.650 |
| Profile 읍면동(전부) | 46.2% | 0.617 |
| └ 인구만 | 47.2% | 0.601 |
| └ **토지만** | **46.4%** | 0.614 |
| └ 주거집합만 | 47.3% | 0.601 |

## 4. 핵심 결론

1. **지역효과는 크고 확실하다.** base→읍면동 더미 CV-MAPE 개선: 집합 −5.1%p, 복합상업 −4.5%p,
   복합단독 **−6.7%p**(R²log +0.094). → **지역을 안 넣는 회귀는 손해**. 거의 확정.
2. **복합부동산은 base MAPE가 훨씬 낮다(47% vs 집합 60%).** 토지+건물 면적 덕에 본질적으로 더 설명가능 — CH2 핵심 자산에 유리.
3. **현재 Profile은 "시군구 더미 수준"까지만 대체.** Profile(시군구·전부)이 시군구 더미를 거의 따라잡으나
   (복합상업 45.1 vs 44.4, 단독 43.8 vs 43.3), **읍면동 더미에는 진다** = 시군구 아래 변동을 못 담음.
4. **블록 분해: 지금 작동하는 건 '토지시장' 블록뿐.** 인구·주거집합 블록은 base와 동일.
   → 현재 Profile은 *복합부동산 특화 피처가 아니다*. **토지지가 baseline만 실질 신호.**
5. **읍면동 Profile이 시군구 Profile보다 나쁘다** → 현재 읍면동 프로필이 결측·희박해 노이즈. 품질 개선 필요.
6. 즉 결론은 **"Profile 실패"가 아니라 "현재 Profile은 시군구까지만 더미를 대체, 읍면동·복합 특화 신호는 미보유"**.

## 5. 주의·한계

- **built 지역코드 충전율 57~64%** — 나머지는 미상 처리 → 지역효과가 과소평가됐을 수 있음(별도 보강 과제).
- **VIF 높음**: `land_residential_median`(상업 19, 단독 11), `ratio_commercial_zone`(17/11) → 변수 선택/LASSO 필요.
- 충북 단일 시도 결과. 전국/권역 일반화는 미검증.
- k-fold는 *전송(transfer)* 을 검증하지 못함(모든 지역이 train에 등장). Profile의 진짜 강점(미등장/희박 지역 외삽)은 LOSO/시간분할에서만 드러남.

## 6. 다음 실험 (우선순위)

1. **시간 외삽(Time Split, 2021–24 학습 → 2025 예측)** — CH2는 미래 예측 프로그램이라 가장 실무적.
   ⚠️ 프로필 스냅샷도 ≤2024 윈도우로 맞춰 **미래누수 차단**.
2. **전국/권역 LOSO** — 더미는 미등장 지역을 못 맞춤 → Profile의 일반화 가치 분수령. (이긴다는 보장 없음, "아직 모름".)
3. **Profile 피처 확장** — 블록 분해가 시사: 복합부동산엔 **상권·유동인구·기업·산업단지·역세권** 피처가 필요.
4. **구조 incremental(계층형 매칭 POC 후)** — 단 복합 base MAPE가 이미 낮아 구조 기여 상한은 제한적일 수 있음.
   계층형 매칭(법정동+연면적±2%+연식 → 도로명+층 …) + 미상 범주 + 매칭/미매칭 균형표로 선택편향 진단.

## 7. 재현

```bash
# 복합부동산 (built_stats.built_transactions)
python collective_commercial/exp_region_vs_profile.py --source built --asset commercial --sido 충청북도
python collective_commercial/exp_region_vs_profile.py --source built --asset detached  --sido 충청북도
# 집합상가 (collective_stats.collective_commercial_transactions)
python collective_commercial/exp_region_vs_profile.py --source collective_shop --sido 충청북도
```
리포트: `pipeline/collective_commercial/exp_region_vs_profile_*.json`
