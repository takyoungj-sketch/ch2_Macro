# Twin Lab — Commercial V1 vs V2 해석 노트

> 기준 마트: `logs/twin_lab/pilot-commercial-chungbuk12.json`  
> 비교: V0 Local · V1 `general` · V2 `built_commercial`  
> 표본: 충북 eup · ledger `n≥50` · 8dev + 4holdout · 2019–2025 · window 3 · profile `v2.1-national`

## 한 줄 결론

**현 설정에서 Twin pool(V1/V2)은 Local(V0)보다 중앙값 CV-MAPE를 개선하지 못한다.**  
V2는 V1보다 **약간 덜 나쁘거나 동률**이며, case winner는 6:6으로 갈린다.  
→ 제품 기본 Twin을 `built_commercial`로 바꾸기 **시기상조**. Lab에서 pool/게이트/가중을 더 조인 뒤 재판정.

## KPI (all)

| | V0 | V1 general | V2 built_commercial |
|---|---:|---:|---:|
| n regions | 12 | 12 | 12 |
| median CV-MAPE | 53.8 | 59.1 | 58.6 |
| median lift_rel vs V0 | — | **−0.19** | **−0.16** |
| hit (≥5% rel) | — | 16.7% | 16.7% |
| worsened | — | 75% | 75% |

`profile_compare.secondary_better_cases = 6/12` (V2 lift_pp > V1).

### 참고: 소표본 pilot (8곳 중 유효 4곳)

| | V1 | V2 |
|---|---:|---:|
| median lift_rel | −0.12 | **+0.09** |

소표본 낙관 신호는 **고n 12곳 벤치에서 사라짐**. 해석은 chungbuk12를 우선.

## 해석

1. **Local이 이미 강한 케이스**에서는 Twin 합류가 variance·이질성을 키워 CV가 악화되는 경우가 많다 (worsened 75%).
2. V2의 상가 블록은 Twin **순위**를 바꾸지만, recommend hard gate + top3 pool 경로에서 **일관된 lift로 이어지지 않았다**.
3. winner 6:6 → “유형 블록 Twin이 항상 낫다”는 기각. 지역·표본 구조 의존.
4. holdout(4)에서도 동일 패턴(대체로 음수 lift) — 과적합 의심보다 **풀링 정책 자체**가 병목일 가능성.

## Go / No-go (현 시점)

| 결정 | 상태 |
|------|------|
| 제품 Twin 기본을 `built_commercial`로 교체 | **No-go** |
| Lab에서 V2를 주 비교열로 유지 | **Go** (해석·ablation용) |
| V3 가중 탐색 착수 | **조건부** — 먼저 pool variant(top1/top3)·게이트 완화 ablation 후 |

## 유형 확장 파일럿

### Factory (`pilot-factory-chungbuk8`, V2=`built_factory`)

| | V1 | V2 |
|---|---:|---:|
| median lift_rel | −0.01 | **−0.13** |
| hit | 12.5% | 25% |

→ Local 대비 개선 실패. 제품 전환 **No-go**.

### Detached — 확장 재검증

**소표본 8** (`pilot-detached-chungbuk8`)

| | V1 | V2 |
|---|---:|---:|
| median lift_rel | +0.02 | **+0.12** |
| hit | 37.5% | **62.5%** |

**층화 24** (`pilot-detached-chungbuk24`) — 우선 해석

| | V1 | V2 |
|---|---:|---:|
| median lift_rel | 0.00 | **+0.015** |
| hit | 33.3% | **45.8%** |
| worsened | 33.3% | **20.8%** |
| holdout median lift | +0.05 | **+0.16** |
| winner (cases) | 13 | 11 |

확장 후 V2 중앙 lift는 약해졌지만 **여전히 non-negative**, hit↑ / worsened↓, **holdout +0.16 유지**.  
commercial/factory와 달리 단독만 Twin 유형 블록이 Local을 해치지 않는 축.  
→ 제품 전면 전환은 보류, **detached V3(dev 가중→holdout) 1순위 후보**.

## Commercial V2x + pool ablation (`pilot-commercial-chungbuk12-v2x`)

| | V1 | V2 | V2x `built_all` |
|---|---:|---:|---:|
| median lift_rel | −0.19 | **−0.16** | −0.21 |
| hit | 16.7% | 16.7% | 16.7% |
| worsened | 75% | 75% | **83%** |

고정 pool (V2 케이스, V0 대비):

| pool | median lift | hit |
|------|------------:|----:|
| twin_pool_n1 | −0.19 | 0% |
| twin_pool_n3 | **−0.32** | 8% |

- **V2x No-go**: all-built 동시 투입이 V2-target보다 나쁨.  
- **top3 고정이 top1보다 나쁨** (commercial 12곳) — Lab 프로토콜의 “top3 선호”를 commercial에서는 재검토.  
- 엔진 best(V2 −0.16)가 고정 pool보다 덜 나쁜 이유: 케이스별로 n1/n3/n5를 고름.

## 다음 실험

> **세션 기록·실행 순서 SSOT:** [`TWIN_LAB_SESSION_2026-08-12.md`](./TWIN_LAB_SESSION_2026-08-12.md)  
> V3는 보류. 먼저 지역별 성공/실패 패턴 → 전국 commercial V2-top1/top3/engine-best.

1. commercial 12곳 **개선·악화 지역 특성** 분석  
2. 전국 commercial 50~200 · V2 pool ablation  
3. factory / detached 독립 벤치  
4. (병행 메모) 회귀식 **지역변수**(프로필·토지 통계) 트랙 — Twin 풀링과 역할 분리  
5. V3는 위 결과에 따라 착수 여부·형태 결정

## 재현

```bash
cd pipeline
python bench_twin_built_recommend_lift.py \
  --fixture fixtures/twin_bench_commercial_chungbuk12.json \
  --compare built_commercial \
  --lab-out ../logs/twin_lab/pilot-commercial-chungbuk12.json \
  --experiment-id pilot-commercial-chungbuk12
```

Lab: `http://localhost:5174/built/?lab=twin` → `pilot-commercial-chungbuk12` · Overview에서 `dev` / `holdout` 탭.
