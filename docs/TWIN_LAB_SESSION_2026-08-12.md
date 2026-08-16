# 쌍둥이 로직 보강 — 2026-08-12 작업 기록 · 다음 계획

> **작업명:** 쌍둥이 로직 보강 (UI/코드명 Twin Experiment Lab)  
> **상태:** ⏸ 일시 중지 (chungbuk40 RT-price까지 기록)  
> **관련:** [`TWIN_EXPERIMENT_LAB_IMPLEMENTATION.md`](./TWIN_EXPERIMENT_LAB_IMPLEMENTATION.md) · [`TWIN_LAB_COMMERCIAL_V1_V2_NOTE.md`](./TWIN_LAB_COMMERCIAL_V1_V2_NOTE.md)  
> **재개 SSOT:** [`TWIN_LOGIC_AUGMENT_NEXT_PLAN.md`](./TWIN_LOGIC_AUGMENT_NEXT_PLAN.md) **§10 결과 · §11 차후 계획**  
> **화면:** `http://localhost:5174/built/?lab=twin`

---

## 0. 오늘의 한 줄

실험 **엔진·Lab·유형별 Twin 배치**가 동작함을 확인했다.  
이후 R0/T1/RT·chungbuk40에서 **Local 우세 · Twin 중앙값 손해 · land RT는 Twin 완화만**이 잠겼다.  
**모형추천(Local)은 유지 · Twin 기본화·V3는 보류.** 재개 시 §11.

> **후속 개정 (같은 날):** R1=식별불가 · 판정 R0/T1/RT ·  
> 주 mart `pilot-commercial-chungbuk40-r0-t1-rt-price` · 상세는 Next Plan §10.

---

## 1. 오늘 구현·산출물

### 1.1 Lab / 벤치 인프라
| 항목 | 내용 |
|------|------|
| Twin Experiment Lab | Overview · 지역별 비교 · 지역 상세 · CSV · `?lab=twin` |
| 마트 | `logs/twin_lab/*.json` · `kpis_by_sample_group` · `pool_ablation_v2` |
| Bench | `--compare` · `--v2x` · stage2 pool별 CV 기록 |
| 샘플러 | `pipeline/twin_lab/select_bench_eupmyeondong.py` |

### 1.2 Twin 프로필 (충북 eup, as_of 2026-06)
`general` · `built_commercial` · `built_factory` · `built_detached` · `built_all`(V2x)

### 1.3 실측 마트
| experiment_id | 요약 |
|---------------|------|
| `pilot-commercial-chungbuk12-v2x` | V0/V1/V2/V2x + pool ablation (주 해석 마트) |
| `pilot-commercial-chungbuk12` / `live` | 이전 V1/V2 |
| `pilot-factory-chungbuk8` | 공장 파일럿 |
| `pilot-detached-chungbuk8` / `24` | 단독 — 약한 양의 신호·holdout 유지 |

### 1.4 문서
- 프로토콜 SSOT · commercial 해석 노트 · **본 세션 기록(이 문서)**

---

## 2. 파일럿에서 확정된 관찰 (GPT 의견과 정합)

### 2.1 중앙값만 보면 commercial Twin은 “실패”
| | Median CV | Median lift_rel | Hit | Worsened |
|---|----------:|----------------:|----:|---------:|
| V0 | 53.8 | — | — | — |
| V1 | 59.1 | −0.19 | 16.7% | 75% |
| V2 | 58.6 | −0.16 | 16.7% | 75% |
| V2x | 58.3 | −0.21 | 16.7% | 83% |

→ **「상업에서 Twin은 효과가 없다」로 단정하지 말 것.** 표본 12·충북 한정 파일럿.

### 2.2 진짜 발견: 지역별 이질성
동일 프로토콜에서 어떤 읍면동은 V0→V2(→V2x)로 **큰 개선**, 다른 곳은 **큰 악화**.  
연구 질문 전환:

> Twin이 좋은가/나쁜가가 아니라, **어떤 지역에서 Twin이 작동하는가?**

장기적으로는 *「이 지역은 Twin 풀 후보 / 이 지역은 Local Only가 안전」* 게이팅까지.

### 2.3 V2x(`built_all`) → Target-specific 방향 지지
전 유형 블록 무차별 투입은 **해석 곤란 + 중앙 성능 악화**.  
유형 중심 Twin(상업 평가 시 상업 블록, …)이 주경로로 더 분명해짐.

### 2.4 Pool 크기 가정 폐기
고정 top3가 top1보다 나쁨(이 파일럿).  
「Twin을 많이 넣을수록 좋다」 가정을 버리고 **top1 / top3 / engine-best**를 명시 비교.

### 2.5 유형별 초동
| 유형 | 파일럿 인상 |
|------|-------------|
| commercial | 중앙 악화 · 지역 혼전 |
| factory | V2가 더 나쁜 쪽 (n 얇음) |
| detached | 약한 양의 lift · holdout 상대적으로 나음 |

→ **유형별 독립 벤치** 유지. 합쳐 뽑지 않음.

---

## 3. 버전 정의 (파일럿 이후 정리안)

| ID | 의미 | 비고 |
|----|------|------|
| **V0** | Local only | 불변 |
| **V1** | General Twin (인구·토지·apt·mix) | 현행 |
| **V2** | **Target-specific** Twin (인구·토지·apt + **대상 유형** 시장) | 주경로. V2x는 ablation만 |
| **V2-pool** | 동일 Twin 배치에서 **top1 / top3 / engine-best** | V2 하위 ablation (다음 벤치 필수) |
| **V3** | Target-specific **가중** (dev) → holdout | **전국 V2·pool 정리 후** |

V2x(`built_all`)는 계속 ablation 열로만 — 주 비교축 아님.

---

## 4. 회귀 확장 아이디어 (메모 — 다음 설계 트랙)

사용자 제안: Twin 풀링과 **별도/병행**으로, 회귀식에 **지역요인**을 넣는 방안 검토.

| 후보 소스 | 예 |
|-----------|-----|
| 지역 프로필 | 인구·시장 mix·대표시장·유형 P50 등 |
| 토지 통계 | 용도×지목군 단가·구조 지표 |

방향(초안, 미구현):
1. Twin = **표본 확장**(이웃 거래) vs 지역변수 = **식의 공변량** — 역할을 섞지 말 것.  
2. Lab에서 V0(+지역변수) vs V0 vs Twin 풀을 **분리 실험**.  
3. 전국 commercial 벤치와 **병행 설계 노트**만 먼저 쓰고, 구현은 V2-pool 벤치 이후에도 가능.

→ 상세 설계는 `LAND_BUILT_SIGNAL` / profile catalog와 맞춰 **별 트랙 문서**로 뺄 예정(다음 작업 §6).

---

## 5. Lab UI 개선 백로그 (다음 스프린트)

우선순위 높은 것:
1. **표본 구성** — Local n + Twin별 n + Total (표본 증가 vs 좋은 Twin 구분)
2. **회귀식 변화** — V0↔V* 추가/제거 변수 diff
3. 필터: 권역 · asset_type · 표본수 · 버전 MAPE/Lift · pool · 식 변화를 한 흐름으로

---

## 6. 다음 작업 계획

> **실행 SSOT (갱신):** [`TWIN_LOGIC_AUGMENT_NEXT_PLAN.md`](./TWIN_LOGIC_AUGMENT_NEXT_PLAN.md)

**원칙:** Twin 표본 확대와 지역특성 회귀를 **분리 비교** · V3는 RT 추가가치 확인 후 · 5년·유형별 독립.

```text
R0 Local
  → R1 Local + Region Profile   ← 먼저 (Twin 없이)
  → T1 Local + Twin
  → RT Local + Region + Twin
  → 해석 후 전국·공장·단독 · (조건부) Twin V2-pool / V3
```

### 의도적으로 미룸
- V3 가중 탐색 즉시 착수  
- Twin 거래에 앵커 지역특성 복사  
- 지역 코드 더미 회귀  
- 제품 Twin 기본 프로필 교체 (근거 부족)

---

## 7. 오늘 마무리 체크

- [x] 파일럿 실측·Lab·해석 노트 존재  
- [x] V2x / pool / 지역 이질성 관찰 기록  
- [x] V3 보류 · 다음 순서 문서화  
- [x] 지역변수 회귀 트랙을 백로그에 명시  
- [ ] 커밋/배포 — **요청 시** (오늘 자동 커밋 안 함)

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-08-12 | 파일럿 1차 마무리 · GPT 의견 반영 다음 계획 · 지역변수 트랙 메모 |
| 2026-08-12 | 다음 계획 승격 → R0/R1/T1/RT ([`TWIN_LOGIC_AUGMENT_NEXT_PLAN.md`](./TWIN_LOGIC_AUGMENT_NEXT_PLAN.md)) |
