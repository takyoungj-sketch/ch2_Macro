# CH2 Macro 중간점검 개선안

> **작성:** 2026-08-13  
> **성격:** 기능 추가 로드맵이 아님. **이미 구현된 동작의 검증·오류 실태·제품 정의 고정**이 목적.  
> **근거:** 2026-08-13 중간점검 보고 + 제품 방향(Twin Validation 폐쇄 루프) 합의.  
> **관련:** [CH2_CONSTITUTION.md](./CH2_CONSTITUTION.md) · [CH2_MACRO_VISION.md](./CH2_MACRO_VISION.md) · [CH2_MACRO_IMPLEMENTATION_ROADMAP.md](./CH2_MACRO_IMPLEMENTATION_ROADMAP.md) · [CH2_RECOMMENDATION_ENGINE_DESIGN.md](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) · [MONTHLY_UPDATE_SOP.md](./MONTHLY_UPDATE_SOP.md) · [RISK_REGISTER.md](./RISK_REGISTER.md)

---

## 0. 한 줄 결론

지금은 **기능을 더 만드는 단계가 아니라**, 토지·복합·집합에 이미 있는 통계·회귀·예측·추천을 **신뢰할 수 있는 구조로 고정하고**, Twin 추천이 **실제 회귀 성능을 개선하는지 검증하는 폐쇄 루프**를 완성하는 단계다.

- **빠른데 틀린 시스템**보다 **조금 느려도 검증 가능한 시스템**을 우선한다.
- P2 효율화(병렬 다운로드, DROP 범위 축소 등)는 **나중**이다. 현재 데이터·서버 규모에서 핵심 병목이 아니다.

---

## 1. 현재 단계 평가

| 단계 | 내용 | 상태 |
|------|------|------|
| 1 | 데이터·통계 기반 (원장·마트·as_of·3/5/7) | ✅ 상당 부분 완료 |
| 2 | 회귀·예측 엔진 | ✅ 상당 부분 구현 |
| 3 | 모형 추천 | 🟡 구현됐으나 **도메인별 깊이·평가 기준 불통일** (H3) |
| 4 | 지역 프로필 | 🟡 핵심 구조 진행 |
| 5 | 쌍둥이(Twin) 추천 | 🟡 핵심 로직 개발·실험 단계 |
| 6 | **Twin Validation** | 🔴 **핵심 미완성** — 차별화의 막힌 고리 |
| 7 | 월간 운영 자동화·안정화 | 🟡 구조는 있으나 **SOP/SSOT 고정** 필요 |

**중간점검 B3와의 연결:**  
「동일 추천·Validation OS」라고 말하면 **아직 거짓**이다.  
통계·회귀·예측·(부분)추천까지는 진행됐지만,

> *지역 A를 분석했을 때 지역 B가 정말 통계적으로 비슷한가?*  
> → Twin 추천 → **실제 회귀식 개선 여부로 검증**

하는 **폐쇄 루프가 없다.**

목표 루프(제품 차별점):

```
지역 프로필
  → 후보지역 필터링
  → 토지 유사성
  → 집합 유사성
  → 복합 유사성
  → Twin Score
  → 실제 회귀식 개선 여부 검증 (MAPE / CV-MAPE / Adj R² 등)
```

---

## 2. 우선순위 (재정렬)

중간점검의 P0 → P1 → P2 큰 틀은 유지하되, **P1 안 순서와 P2 비중**을 조정한다.

| 순위 | 초점 | 왜 지금인가 |
|------|------|-------------|
| **①** | 제품 정의 고정 | 통계 / 회귀 / 예측 / Twin 역할이 섞이면 이후 검증이 불가능 |
| **②** | 모형 추천 체계 고정 (H3) | 같은 「모형 추천」 라벨에 깊이 절벽 → 체감 패리티 붕괴 |
| **③** | Twin Validation 설계·측정 (B3) | CH2만의 핵심; 미완성 시 “추천 엔진”이 차별화되지 않음 |
| **④** | as_of / 3DB 동기화·월간 SSOT (B1·H1·H2) | Facts First; 원장 최신·화면 과거를 막음 |
| **⑤** | 효율화 (구 P2) | **보류** — 검증 가능한 시스템 이후에 |

효율화(land mart 중 built/collective 다운로드 병렬, promote DROP 축소 등)는 **⑤번 이후**에만 다룬다.

---

## 3. 제품 정의 고정 (①)

### 3.1 MVP 문장 (제안 SSOT)

**CH2 Macro MVP란:**

> 토지·복합·집합에서 **시장 통계·회귀·예측·한계 노출·AI 해석**을 같은 통계 언어로 제공하고,  
> **모형 추천은 “목적별 후보 제시”**이며, Twin은 **선택적 보조 pool**이다.  
> Twin이 Local만으로 한 회귀보다 **검증 지표상 개선**했는지 보여줄 수 있을 때, 비로소 Twin을 “제품 기본”으로 승격한다.

**아직 MVP에 넣지 않는 것:**

- 「동일 Validation OS가 3도메인에 완전 이식됨」
- Twin을 기본 on으로 두는 자동 채택
- 개별 물건 적정가·투자 조언

### 3.2 역할 분리 (UI·문서에 동일 문구)

| 기능 | 하는 일 | 하지 않는 일 |
|------|---------|--------------|
| **통계** | 수준·분포·추세·표본 n | 적정가 |
| **회귀** | 통제 후 패턴(계수·Adj R²·VIF) | 인과 단정 |
| **예측** | 한 점 ŷ + PI/CI · 한계 | 감정·투자 |
| **모형 추천** | 설명형 / 예측형(·균형) **목적별 후보** | “정답 식” 자동 확정 |
| **Twin** | 유사 지역 pool · **검증 전제** | 유사=동일 시장 선언 |
| **AI** | Facts·화면 설명 | 수치 invent · 가격 판단 |

### 3.3 문서 정리 과제 (개발보다 정의)

- 재구축·지목군·아키텍처 문서의 **「착수 대기 / 미구현」 헤더**를 코드 현실과 맞출 것 (중간점검 H5).
- `NEXT_STEPS.md`는 MVP SSOT로 쓰지 말 것 — 본 문서 + Constitution + Vision을 우선.

**완료 게이트 ①:** 위 MVP 문장·역할표가 Constitution/Vision/본 문서에 모순 없이 인용 가능.

---

## 4. 모형 추천 체계 고정 (② · H3)

### 4.0 실태표 (2026-08-13)

| 도메인 | API/UI | 깊이 배지 | 목적 분리 | Twin Validation |
|--------|--------|-----------|-----------|-----------------|
| 복합 | `/regression/recommend` · RecommendStagePanel | **확장** | 설명형/예측형 | Stage2 + `twin_validation` |
| 토지 | `/regression/suggest` · `ModelRecommendSection` | **표준** | AIC / MAPE 탭 | 없음 |
| 집합 | `model_candidates` · `ModelRecommendSection` | **표준+** | Adj R² / CV-MAPE 탭 | 없음 |

공유 골격: `shared/model-recommend` (목적 탭 · 최적화 한 문장 · 후보 · 한계). 깊이만 도메인별.

### 4.1 문제

| 도메인 | 현실 | 사용자 체감 위험 |
|--------|------|------------------|
| 복합 | 풀 엔진 (stage1/2, Twin 옵션, CV-MAPE 등) | — |
| 토지 | suggest (가벼움) | “왜 토지만 얕지?” |
| 집합 | 후보 / linear·log | “추천인지 비교인지 모호” |

같은 한글 라벨 **「모형 추천」**에 깊이가 다르면 제품 신뢰가 깨진다.

### 4.2 원칙

> **UI·개념은 통일하고, 내부 분석 깊이만 도메인별로 다르게.**

- 공통 UX: **설명형 / 예측형** (필요 시 균형형) 분리 — 이미 복합에서 쓰는 언어를 SSOT로.
- 공통 표기: 후보 카드에 **평가 지표·표본 n(거래/탐색/적합)·한계 한 줄**.
- 도메인 depth 배지(또는 도움말): 예) `표준` / `확장(Twin pool)` — 깊이가 달라도 **같은 골격**.

### 4.3 평가 기준 (검증용 — 확정 대상)

추천·Twin을 논하려면 **먼저** 지표 의미를 고정한다.

| 목적 | 1차 지표 | 보조 | 비고 |
|------|----------|------|------|
| 설명형 | Adj R² (또는 AIC) | 유의 변수·VIF | in-sample 설명력 |
| 예측형 | **CV-MAPE** (가능 시) | in-sample MAPE | CV 없으면 MAPE + 명시적 한계 |
| Twin 효과 | Local 대비 ΔCV-MAPE / ΔAdj R² | selection_n, fit_n | **개선 없으면 Twin 미채택 권고** |

**완료 게이트 ②:**

1. 토지·복합·집합 추천 UI가 **같은 섹션 골격**(목적 탭 · 후보 · 지표 · 한계). → ✅
2. “이 추천이 무엇을 최적화했는지”가 화면에 **한 문장**으로 보임. → ✅
3. 평가 지표 표가 본 문서 §4.3과 일치 (코드 변경은 게이트 통과용 후속). → ✅ 탭별 1차 지표 분리

---

## 5. Twin Validation 설계 (③ · B3) — 핵심

### 5.1 목적

Twin Score로 고른 지역을 넣었을 때, **Local-only 회귀보다 검증 지표가 나아지는지**를 측정·기록한다.  
나아지지 않으면 Twin은 제품 기본이 아니라 **실험·조건부**로 남긴다 (기존 Lab 취지와 정합).

### 5.2 최소 폐쇄 루프 (설계 산출물)

```
[입력] Anchor scope + 목적(설명형|예측형) + 창(as_of, window_years)
   ↓
[Profile] 후보 필터 (인구·시장 mix 등 — 기존 Profile)
   ↓
[유사성] 토지 / 집합 / 복합 블록 점수 → Twin Score
   ↓
[회귀 A] Local only (동일 변수 계약·공통 표본 규칙)
[회귀 B] Local + Twin pool (동일 계약)
   ↓
[검증] ΔCV-MAPE, ΔAdj R², n, 한계 플래그
   ↓
[판정] 개선 | 동등 | 악화 → UI·로그에 남김
```

### 5.3 검증 과제 (구현 전 · 실태 파악)

코드 대량 추가 전에 **현재 구현으로 무엇을 이미 재현할 수 있는지** 조사한다.

| # | 질문 | 산출 |
|---|------|------|
| V1 | 복합 `/recommend` stage2 Twin이 Local 대비 지표를 **어디에 저장·표시**하는가? | 파일·API 필드 목록 |
| V2 | Twin Lab / Experiment가 Validation과 **같은 지표**를 쓰는가, 다른가? | 불일치 표 |
| V3 | 토지·집합에 Twin pool 회귀 경로가 **있는가 / 없는가**? | 도메인별 Y/N |
| V4 | “개선”의 운영 정의(임계값)가 문서·코드에 **있는가**? | 있으면 인용, 없으면 초안 |

**완료 게이트 ③a (설계):** §5.2 루프 + 판정 규칙 초안이 문서화됨.  
→ [`TWIN_VALIDATION_STATUS.md`](./TWIN_VALIDATION_STATUS.md) (2026-08-13).  
**완료 게이트 ③b (실측):** 복합 golden Local vs Twin 표 — ✅ 동 문서 §3 (옥천·봉명 개선 / 진천 악화→local).

기능 확장(전국 Twin, 새 점수식)은 **③b 이후** — 다음 P1은 verdict API/UI.

---

## 6. 월간·Facts 안정화 (④ · B1·H1·H2)

### 6.1 표준 사이클 (제안)

```
CSV 갱신
  → 검증 (integrity · count · as_of 매핑 확인)
  → mart 갱신 (windows 3,5,7 · 토지 §7.1 group 포함)
  → analysis cache 초기화/재생성   ★ H2 — Facts First
  → Promote (도메인별 DB)
  → as_of / 3DB 스모크
```

**원칙:** git/deploy만으로 “월이 바뀌었다”고 보지 않는다.

### 6.2 P0 운영 고정 (문서·체크리스트)

1. **월간 SSOT 러너:** `run_land_cycle_csv` / `run_built_cycle_csv` / `run_collective_cycle_csv`  
   - xlsx · `run_monthly_cycle` → 복구·레거시로 강등 표기
2. **1페이지 체크리스트:** cycle_id → as_of → land → built → collective → 각 health·「N월 말 기준」
3. **CSV land 후 cache TRUNCATE 필수** — `run_land_cycle_csv.py` 종료 전 자동 (`--skip-cache-clear` 비권장)
4. SOP·PIPELINE 문서의 windows 표기 **3,5,7 통일**
5. **1페이지:** [`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md)
6. **사전 점검:** `py scripts/monthly/verify_monthly_checklist_ready.py` (2026-08-13 PASS)

**완료 게이트 ④:** 체크리스트 문서 존재 + 사전 점검 스크립트 PASS.  
다음 월간 1회에 체크리스트로 **수집→promote→3DB as_of** 완주·이슈 로그.

### 6.3 as_of / 3DB 스모크

Promote 후 한 표로 확인:

| DB | latest as_of | UI 문구 | /health | 비고 |
|----|--------------|---------|---------|------|
| land_stats | | | | |
| built_stats | | | | |
| collective_stats | | | | |

**완료 게이트 ④:** 체크리스트 + `verify_monthly_checklist_ready.py` PASS.  
실월 완주(수집→promote→3DB)는 다음 cycle 운영 시.

---

## 7. 「검증·오류 실태」작업 백로그 (기능 추가 아님)

우선 **관측·기록**. 수정은 이슈 확정 후.

### 7.1 도메인 공통 스모크 (로컬 → 가능 시 VPS)

| ID | 항목 | 통과 기준 |
|----|------|-----------|
| S1 | 동일 지역·창에서 통계 n과 회귀 fit_n 관계 설명 가능 | 화면·help와 모순 없음 |
| S2 | 회귀 실행 → Adj R²·MAPE·계수 부호가 재실행 시 동일 | 결정적(동일 입력) |
| S3 | 예측 PI ≥ CI (해당 시) | 위반 시 로그 |
| S4 | 모형 추천 후보 지표가 카드와 API 일치 | drift 없음 |
| S5 | AI(기본 모드)가 화면 수치를 invent하지 않음 | Open Mode는 별도 |

### 7.2 도메인별 실태 표 (작성 템플릿)

각 행을 채우며 **오류/모호함만** 적는다.

| 도메인 | 화면 | 기대 | 실제 | 심각도 | 비고 |
|--------|------|------|------|--------|------|
| 토지 | 매트릭스 셀 회귀 | | | | |
| 토지 | 모형 추천 | | | | H3 |
| 복합 | recommend stage1/2 | | | | Twin 경로 |
| 복합 | 상위 scope | | | | |
| 집합 주거 | 회귀·효용지수 | | | | grain |
| 집합 비주거 | cluster 회귀 | | | | |

### 7.3 월간·캐시

| ID | 항목 |
|----|------|
| M1 | CSV 경로 후 `analysis_base_cache` / `analysis_cache` 잔존 여부 |
| M2 | promote 직후 land/built/collective as_of 불일치 사례 |
| M3 | 지목군(group) 404 — xlsx 레거시 경로 사용 여부 |

---

## 8. 의도적 후순위 (하지 않을 것 · 지금)

- land mart 중 built/collective 다운로드 병렬화
- Promote를 mart-only로 축소하는 대규모 인프라 변경
- Twin 전국 확장·새 점수식 대공사 (③b 전)
- 건축물대장·개별 AVM성 기능
- 「기능 추가」로 포장된 UI 장식

---

## 9. 실행 순서 요약

```
① 제품 정의 고정 (MVP 문장 · 역할표 · 문서 헤더 정리)
    ↓
② 모형 추천 개념·UI 골격·평가 지표 통일안 (H3) + 실태표
    ↓
③ Twin Validation 설계 + 복합 golden 실측 (B3)
    ↓
④ 월간 SSOT 체크리스트 · cache · 3DB as_of 스모크 (H1·H2·B1)
    ↓
⑤ (후) 효율화 P2
```

### 2026-08-13 진행 (본 라운드)

| 단계 | 상태 | 산출 |
|------|------|------|
| ① | ✅ | Constitution §5-1 · Vision MVP 문장 |
| ④ 문서 | ✅ | `MONTHLY_UPDATE_CHECKLIST.md` · SOP SSOT 표기 |
| H2 | ✅ | `run_land_cycle_csv.py` 종료 전 cache TRUNCATE |
| ② | ✅ | `shared/model-recommend` + 토지/집합 목적 탭 · 복합은 확장 패널 |
| ③a | ✅ | `TWIN_VALIDATION_STATUS.md` |
| ③b | ✅ | 옥천읍·봉명동 **개선**, 진천읍 **악화→local** (`logs/twin_lab/golden_validation_*.json`) |
| P1 verdict | ✅ | `stage2.twin_validation` + RecommendStagePanel 배지 |
| 월간 준비도 | ✅ | `verify_monthly_checklist_ready.py` PASS (2026-08-13) |
| Twin 실응답 | ✅ | okcheon `SMOKE_OK improved` |
| 원장 핫패스 지연 | ✅ | [`LAND_LEDGER_QUERY_PERF.md`](./LAND_LEDGER_QUERY_PERF.md) · `ledger_region_sql` · R-014 |
| ⑤ | 보류 | P2 효율화 |

각 단계 **완료 게이트**를 넘기기 전에는 다음 단계의 “새 기능”에 착수하지 않는다.  
게이트 통과에 필요한 **최소 코드 수정**만 허용한다 (본 문서는 설계·검증 우선).

---

## 10. 성공 정의 (3개월 시야)

1. 운영자·개발자가 **같은 MVP 문장**을 말한다.  
2. 사용자가 토지·복합·집합에서 **같은 「모형 추천」 골격**을 보고, 깊이 차이를 오해가 아니라 **배지/도움말**로 이해한다.  
3. Twin에 대해 **「Local 대비 개선했는지」**를 숫자로 답할 수 있다 (악화면 악화라고 말한다).  
4. 월간 1회를 **단일 체크리스트**로 완주하고, 원장·화면 as_of가 3 DB에서 맞는다.  
5. Facts First: CSV 갱신 후 **캐시 stale로 과거 결과가 보이지 않는다.**

---

## 11. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-08-13 | 초안 — 중간점검 + Twin Validation·검증 우선 재정렬 |
| 2026-08-13 | ①④H2②③a 실행: Constitution/Vision · 월간 체크리스트 · land CSV cache clear · 추천 depth 배지 · TWIN_VALIDATION_STATUS |
| 2026-08-13 | ③b golden 실측: commercial eup 옥천·봉명 개선 / 진천 Local 유지 |
| 2026-08-13 | P1: `stage2.twin_validation` API + RecommendStagePanel Twin Validation 배지 |
| 2026-08-13 | ② H3: `ModelRecommendSection` 공유 골격 · 토지 AIC/MAPE · 집합 AdjR²/CV 탭 |
| 2026-08-13 | 월간 preflight PASS · okcheon twin_validation 실응답 SMOKE_OK |
| 2026-09-01 | SOP·PIPELINE·scripts/monthly README를 CSV 러너·windows 3,5,7에 맞춤. 체크리스트 0.6(전월세·K-apt·검증로봇은 1페이지 밖) |
