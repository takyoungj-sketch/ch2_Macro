# 복합(Built) 회귀 분석 UI — 세로 흐름 설계

> **상태:** P0 구현 완료 (2026-08-09)  
> **범위:** `frontend-built` 회귀·Macro 탐색·상위지역 UX  
> **상위:** [CH2_RECOMMENDATION_ENGINE_DESIGN.md](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) · [CH2_CONSTITUTION.md](./CH2_CONSTITUTION.md)

---

## 1. 목적

복합 앱의 회귀 분석 화면을 **모달 중심**에서 **세로 분석 흐름**으로 전환한다.

- **Macro는 조언**, **채택·적용은 항상 사용자**
- 기본 통계(사용자 실험)와 Macro 탐색( SSOT 풀 )의 **역할 분리**를 UI에서 명확히
- 예측형·설명형을 **독립 실행** — 예측형을 먼저 할 필요 없음
- Twin(쌍둥이 지역 pool)은 **사용자 opt-in** — Macro가 비교 의견만 제시

---

## 2. 레이아웃 (불변 vs 변경)

### 2.1 왼쪽 사이드바 — **유지**

| 항목 | 위치 | 비고 |
|------|------|------|
| 변수 선택 (블록 체크) | 왼쪽 | 사용자 **기본 통계** 후보 |
| 회귀 모형 (linear / log / log-log) | 왼쪽 | 사용자 선택 |
| scope·필터·기간 | 왼쪽 | `analysis_scope` SSOT 입력 |
| 「통계분석」 버튼 | 왼쪽 | `POST /built/regression/run` |

> 왼쪽 변수 체크 ≠ Macro SSOT 탐색 풀. 이 차이는 **버그가 아니라 역할 분리**다.

### 2.2 오른쪽 본문 — **세로 카드 흐름**

```text
[단계 네비]  ① 회귀실험 · ② Macro 예측형 · ③ Macro 설명형 · ④ 상위지역

① 회귀 실험 (기존 FocusRegressionCard + 산점도)
   · 사용자가 왼쪽에서 고른 변수·스케일 결과
   · regM.data 있을 때만 표시

② Macro 예측형 (인라인 카드)
   · 「Macro 예측형 탐색」 버튼 — 사용자가 클릭 시 recommend API
   · CV-MAPE 1위 후보·예측형 랭킹·만족 등급
   · (선택) 「쌍둥이 지역 추가 검토」→ stage2 Twin (유사 지역 거래를 더해 **모형 재탐색**)

③ Macro 설명형 (인라인 카드)
   · 「Macro 설명형 탐색」 버튼 — ②와 **독립** (순서 강제 없음)
   · AIC 1위 후보·설명형 랭킹·계수 해석
   · 동일 recommend 응답의 alternate 슬라이스 표시

④ 상위 지역 분석 (인라인 카드)
   · ① 회귀 결과의 comparisons[] 기반
   · comparisons 없으면 안내 문구
   · 참고용 — 초점 vs 직계·상위 scope
```

**제거:** `RecommendationModal`, `UpperScopeCompareModal` 진입 버튼 (모달 자체는 deprecated, 점진 제거)

---

## 3. 단계별 동작 규칙

### 3.1 ① 회귀 실험

- 선행 조건: addr1 등 scope 최소 조건 + 「통계분석」 실행
- Macro ②③과 **독립** — ① 없이도 ②③ API 호출 가능 (동일 `regBody` / `analysis_scope`)
- ① 결과는 사용자 실험의 **기준선(baseline)** 으로 Macro 카드에서 참고 가능 (향후 CV 비교)

### 3.2 ② Macro 예측형 / ③ Macro 설명형

| 규칙 | 내용 |
|------|------|
| 실행 | 각 카드의 「탐색 실행」 — **필수 클릭**, 자동 실행 없음 |
| API | `POST /built/regression/recommend` — **한 번의 응답**에 primary(예측) + alternate(설명) |
| 표시 | **한 번에 하나만** — 사용자가 탐색한 모드(예측형 **또는** 설명형) 결과만 표시 |
| 순서 | **없음** — ③만 먼저 열어도 됨 |
| 재실행 | scope·필터 변경 후 「다시 탐색」 |
| 채택 | 「이 후보로 분석」→ 왼쪽 변수·스케일 갱신 + `regression/run` 재호출 |

**배치:** ① 회귀 실험 **예측창 아래**에 ②③④ 배치 (`regM.data` 있을 때만).

### 3.3 Twin (쌍둥이 지역)

- **② 예측형 카드**에만 「쌍둥이 지역 추가 검토」 노출
- Macro `conclusion.twin_recommended` 일 때 안내; **자동 pool 적용 금지**
- 사용자 클릭 → `run_stage2: true` 재요청 → pool별 **재탐색 변수·CV-MAPE** · 「이 pool로 분석」
- pool 채택 시 해당 pool의 **변수·response_scale·region_codes**가 `/run`에 반영
- gate/validation 탈락은 decision_reason 한 줄로만 요약 (선택)
- ③ 설명형은 Twin 결과 **요약 참조**만 (pool UI 중복 없음)

### 3.4 ④ 상위 지역

- **opt-in** — 「상위지역 분석」 클릭 시에만 비교·예측 UI 표시 (통계분석만으로 자동 노출 안 함)
- ① `regression/run` 응답의 `comparisons` 사용 (별도 API 없음)
- 시·군 단일 선택 등 비교 불가 시 empty state
- PredictPanel embedded — 초점·상위 scope 예측 참고

---

## 4. 컴ponent 구조 (P0)

```text
frontend-built/src/components/
├── BuiltAnalysisStepNav.tsx       # ①~④ 앵커 네비
├── BuiltRegressionAnalysisPanel.tsx  # recommend·Twin·predict 상태 orchestration
├── MacroModelExploreCard.tsx      # ② 또는 ③ 단일 모드 카드
├── UpperScopeAnalysisCard.tsx     # ④ 인라인
├── RecommendStagePanel.tsx        # mode: predictive | explanatory | full
└── (deprecated) RecommendationModal.tsx
```

`App.tsx`:

- 왼쪽 사이드바: 변경 없음
- ① 섹션: `id="built-step-regression"`
- ① 아래: `<BuiltRegressionAnalysisPanel />`
- `modelExploreOpen` / `upperCompareOpen` state 제거

---

## 5. API·데이터 (변경 없음)

| API | 용도 |
|-----|------|
| `POST /built/regression/run` | ① 사용자 실험 |
| `POST /built/regression/recommend` | ②③ Macro 탐색 |
| Profile Twin neighbors | stage2 입력 enrichment |

응답 필드·termination·dual rank — [CH2_RECOMMENDATION_ENGINE_DESIGN.md §11](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) SSOT.

---

## 6. 구현 체크리스트

### P0 (본 문서 착수)

- [x] `BUILT_REGRESSION_ANALYSIS_UI.md` 작성
- [x] `BuiltRegressionAnalysisPanel` + 카드 3종
- [x] `RecommendStagePanel` mode 분기
- [x] `App.tsx` 모달 제거·인라인 연결
- [x] `CH2_RECOMMENDATION_ENGINE_DESIGN.md` §10 갱신

### P1 (후속)

- [ ] ① 사용자 실험 vs Macro 후보 CV-MAPE 나란히 비교
- [ ] AI Assistant를 ②③ 카드별 context 분리
- [ ] 토지·집합 동일 패턴 adapter

---

## 7. UX 카피 (고정)

| 위치 | 문구 |
|------|------|
| ② 제목 | Macro 예측형 |
| ② 부제 | CV-MAPE 기준 — SSOT 변수 풀에서 최적 조합 탐색 |
| ③ 제목 | Macro 설명형 |
| ③ 부제 | AIC 기준 — 계수 해석·설명력 중심 |
| Twin CTA | 유사 지역 거래를 더해 모형을 다시 찾습니다 |
| Twin 설명 | 표본 확대 후 최종 모형 제안 — pool 채택은 사용자 결정 |
| ④ 제목 | 상위 지역 분석 |
| ④ 부제 | 분석 초점 vs 상위 행정 scope — 참고용 |

---

## 8. 관련 결정

- D-032~D-037: [DECISIONS.md](./DECISIONS.md) — recommend 엔진·Twin opt-in
- 본 UI는 D-037 「Twin 사용자 opt-in」의 **프론트 반영**
