# 복합(Built) 회귀 분석 UI — 세로 흐름 설계

> **상태:** 2026-08-17 — Macro는 작업 창(탭) · 기본 통계 비대체  
> **범위:** `frontend-built` 회귀·Macro 탐색·상위지역 UX  
> **상위:** [CH2_RECOMMENDATION_ENGINE_DESIGN.md](./CH2_RECOMMENDATION_ENGINE_DESIGN.md) · [CH2_CONSTITUTION.md](./CH2_CONSTITUTION.md)

---

## 1. 목적

기본 통계(①)는 사용자가 만든 식. Macro는 **별도 창에서만** 보는 조언이다.

- **Macro 결과는 기본 통계 식·변수·지역을 대체하지 않는다**
- 예측형·설명형은 **한 번 탐색**으로 함께 채워진다 (탭으로 읽기)
- Twin(쌍둥이 지역 pool)은 **사용자 opt-in** — 창 안에서만 비교, 본문 `/run`에 적용하지 않음

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
[단계 네비]  ① 회귀실험 · ② Macro 모형 탐색(창) · ③ 상위지역

① 회귀 실험 (기존 FocusRegressionCard + 산점도)
   · 사용자가 왼쪽에서 고른 변수·스케일 결과
   · regM.data 있을 때만 표시

② Macro 모형 탐색 (진입 카드 → 큰 작업 창)
   · 본문 「창 열기 / 결과 보기」 한 버튼
   · 창 안 탭 [예측형 (CV-MAPE)] [설명형 (AIC)]
   · 한 번 탐색 = 두 탭 동시 채움
   · 「예측 미리보기」·Twin은 창 안에서만
   · 기본 통계 식 대체 없음 (「이 후보로 분석」 없음)

③ 상위 지역 분석 (인라인 카드)
   · ① 회귀 결과의 comparisons[] 기반
   · 참고용 — 초점 vs 직계·상위 scope
```

**창:** `RecommendationModal` (`DraggableModalShell`). 채택으로 본문 `/run`을 덮어쓰지 않는다.

---

## 3. 단계별 동작 규칙

### 3.1 ① 회귀 실험

- 선행 조건: addr1 등 scope 최소 조건 + 「통계분석」 실행
- Macro 창과 **독립** — ① 결과가 있어야 추가분석 블록이 뜬다 (`regM.data`)
- ① 결과는 사용자 실험의 **기준선(baseline)** — Macro 창의 「내 식 vs Macro」에서 참고

### 3.2 ② Macro 모형 탐색 (창)

| 규칙 | 내용 |
|------|------|
| 진입 | 본문 「창 열기」 — 결과 없으면 창이 열리며 한 번 탐색 |
| API | `POST /built/regression/recommend` — **한 번의 응답**에 primary(예측) + alternate(설명) |
| 표시 | 창 탭 **예측형 / 설명형** — 같은 응답의 슬라이스 |
| 본문 | 기본 통계 식·왼쪽 변수·선택 지역을 **덮어쓰지 않음** |
| 확인 | 「예측 미리보기」는 창 안 embedded PredictPanel |
| 재실행 | 창 안 「다시 탐색」. scope·필터 변경 시 Macro 리셋 |

**배치:** ① 회귀 실험 **예측창 아래**에 Macro 진입 카드 + 상위지역 (`regM.data` 있을 때만).

### 3.3 Twin (쌍둥이 지역)

- **예측형 탭**에만 「쌍둥이 지역 추가 검토」 노출
- Macro `conclusion.twin_recommended` 일 때 안내; **자동 pool 적용 금지**
- 사용자 클릭 → `run_stage2: true` 재요청 → pool별 **재탐색 변수·CV-MAPE** 를 **창 안에서만** 표시
- 「이 pool로 분석」으로 본문 `/run`에 region_codes를 넣지 않음
- gate/validation 탈락은 decision_reason 한 줄로만 요약 (선택)
- 설명형 탭은 Twin 결과 **요약 참조**만 (pool UI 중복 없음)

### 3.4 ③ 상위 지역

- **opt-in** — 「상위지역 분석」 클릭 시에만 비교·예측 UI 표시 (통계분석만으로 자동 노출 안 함)
- ① `regression/run` 응답의 `comparisons` 사용 (별도 API 없음)
- 시·군 단일 선택 등 비교 불가 시 empty state
- PredictPanel embedded — 초점·상위 scope 예측 참고

---

## 4. 컴ponent 구조 (P0)

```text
frontend-built/src/components/
├── BuiltRegressionAnalysisPanel.tsx  # 진입 카드 + 창 open + 상위지역
├── RecommendationModal.tsx        # Macro 작업 창 (탭·탐색·미리보기)
├── UpperScopeAnalysisCard.tsx     # ③ 인라인
└── RecommendStagePanel.tsx        # mode: predictive | explanatory | full
```

`App.tsx`:

- 왼쪽 사이드바: 변경 없음 (Macro 채택으로 덮어쓰지 않음)
- ① 섹션: `id="built-step-regression"`
- ① 아래: `<BuiltRegressionAnalysisPanel />`

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
- [x] `App.tsx` Macro 창 연결 (본문 식 비대체)
- [x] `CH2_RECOMMENDATION_ENGINE_DESIGN.md` §10 갱신

### P1 (후속)

- [ ] ① 사용자 실험 vs Macro 후보 CV-MAPE 나란히 비교
- [ ] AI Assistant를 ②③ 카드별 context 분리
- [ ] 토지·집합 동일 패턴 adapter

---

## 7. UX 카피 (고정)

| 위치 | 문구 |
|------|------|
| ② 제목 | Macro 모형 탐색 |
| ② 부제 | 예측형·설명형 한 탐색 — 창 안에서만 확인 |
| 탭 | 예측형 (CV-MAPE) / 설명형 (AIC) |
| Twin CTA | 유사 지역 거래를 더해 이 창에서 모형을 다시 찾습니다 |
| Twin 설명 | 기본 통계 식은 바꾸지 않습니다 |
| ③ 제목 | 상위 지역 분석 |
| ③ 부제 | 분석 초점 vs 상위 행정 scope — 참고용 |

---

## 8. 관련 결정

- D-032~D-037: [DECISIONS.md](./DECISIONS.md) — recommend 엔진·Twin opt-in
- 본 UI는 D-037 「Twin 사용자 opt-in」의 **프론트 반영**
