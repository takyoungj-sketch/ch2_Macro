# CH2 Macro 헌법 (Constitution)

> CH2 Macro가 **왜 존재하는지**, **무엇을 지향하는지**에 대한 변하지 않는 원칙.  
> 기능·UI·통계·AI 구현은 이 문서를 따른다.  
> AI 세부 조항: [CH2_AI_CONSTITUTION.md](./CH2_AI_CONSTITUTION.md)  
> 물음표·AI 설명 체계: [CH2_EXPLAIN_CONSTITUTION.md](./CH2_EXPLAIN_CONSTITUTION.md)

---

## 1. 존재 이유

CH2 Macro는 **시장을 거시적으로 이해**하고, **시세 수준을 파악**하며, **미래를 읽기 위한 과거 데이터**를 분석하는 도구이다.

개별 물건에 “얼마”라고 숫자 하나를 붙이는 데 그치지 않는다.  
과거에 **크게 움직인 흐름**을 포착하고, **쉽게 보이지 않는 패턴·인사이트**를 드러내어, 사용자가 시장 맥락 속에서 판단할 수 있게 한다.

---

## 2. 사용자

| 층위 | 대상 | 비고 |
|------|------|------|
| **1차** | 감정평가사 | 설계·검증·워크플로의 기준 사용자 |
| **2차** | 일반 사용자 | 부동산에 관심 있는 누구나 — 전문 용어·통계를 **접근 가능하게** |

감정평가사만을 위한 폐쇄 도구가 아니다.  
전문성을 유지하면서도, **처음 온 사람도 시장 그림을 읽을 수 있는** 경험을 지향한다.

---

## 3. 개별 AVM이 아닌 이유

| | 개별 AVM (전형) | CH2 Macro |
|---|-----------------|-----------|
| **초점** | 특정 물건 하나 | 지역·코호트·시장 구조 |
| **방법** | 유사 과거거래 비교 → 가치 산출 | 추세·분포·회귀·코호트·매트릭스 등 **집단 통계** |
| **결과** | “이 건은 X원”에 수렴 | “이 시장은 지금 어디에 있고, 무엇이 움직였는가” |
| **한계 인식** | 모형·표본 한계가 묻히기 쉬움 | 표본·기간·해상도 한계를 **화면과 설명에 노출** |

CH2 Macro는 **개별 적정가격 엔진을 대체하지 않는다.**  
과거 거래의 **큰 움직임**과 **구조적 차이**를 보여 주어, 감정·투자·기획 판단의 **배경 지식**을 제공한다.

---

## 4. 지향하는 분석

다음을 우선한다. (토지·집합·복합 공통)

1. **거시적 시장 이해** — 지역·용도·시기별 수준·분산·추세
2. **과거 데이터의 구조적 해석** — 연도·코호트·변수 간 관계, 이상·전환 구간
3. **미래에 대한 힌트** — 예측은 “확정 전망”이 아니라 **통계적 패턴의 연장·한계**와 함께 제시
4. **숨은 인사이트** — 단순 평균·최근 거래 나열을 넘어, 회귀·분포·비교·코호트로 **보이지 않던 차이**를 드러냄

**하지 않는 것:** 개별 물건의 감정·적정가격 대체, 투자 추천, “오른다/내린다” 식의 단정적 전망.

---

## 5. 제품·기술 원칙 (요약)

| 원칙 | 요약 |
|------|------|
| **Facts First** | 수치·표본·계수는 CH2가 계산·저장한 결과만 (AI 포함) |
| **한계 노출** | n, 기간, 해상도, 모형 가정을 숨기지 않음 |
| **해상도 일관** | 토지·주거 집합·비주거 집합·복합 — 같은 통계 언어·UI 패턴 (분석 단위만 도메인별로 다름) |
| **전문가 + 대중** | 감정평가 워크플로에 맞으면서, 설명·라벨은 비전문가도 따라올 수 있게 |

---

## 5-1. MVP 범위 (2026-08 중간점검 고정)

**CH2 Macro MVP란:**

> 토지·복합·집합에서 **시장 통계·회귀·예측·한계 노출·AI 해석**을 같은 통계 언어로 제공하고,  
> **모형 추천은 “목적별 후보 제시”**이며, Twin은 **선택적 보조 pool**이다.  
> Twin이 Local만으로 한 회귀보다 **검증 지표상 개선**했는지 보여줄 수 있을 때, 비로소 Twin을 “제품 기본”으로 승격한다.

| 기능 | 하는 일 | 하지 않는 일 |
|------|---------|--------------|
| **통계** | 수준·분포·추세·표본 n | 적정가 |
| **회귀** | 통제 후 패턴(계수·Adj R²·VIF) | 인과 단정 |
| **예측** | 한 점 ŷ + PI/CI · 한계 | 감정·투자 |
| **모형 추천** | 설명형 / 예측형(·균형) **목적별 후보** | “정답 식” 자동 확정 |
| **Twin** | 유사 지역 pool · **검증 전제** | 유사=동일 시장 선언 |
| **AI** | Facts·화면 설명 | 수치 invent · 가격 판단 |

상세·실행 순서: [CH2_MIDCHECK_IMPROVEMENT_PLAN.md](./CH2_MIDCHECK_IMPROVEMENT_PLAN.md)

---

## 6. AI와의 관계

CH2 AI는 [CH2_AI_CONSTITUTION.md](./CH2_AI_CONSTITUTION.md)에 따라 **통계 분석 어시스턴트**로 동작한다.

- 본 헌법 §3·§4의 **거시·패턴·한계 중심** 정체성과 일치해야 한다.
- AI는 가격을 **결정**하지 않고, 화면·Bundle에 있는 **시장 통계**를 설명한다.

---

## 7. 관련 문서

| 문서 | 역할 |
|------|------|
| [CH2_MACRO_VISION.md](./CH2_MACRO_VISION.md) | **제품 비전** — Profile 제안 · Validation 판단 · AI 해설 |
| [CH2_EXPLAIN_CONSTITUTION.md](./CH2_EXPLAIN_CONSTITUTION.md) | 물음표 1차 · AI 2차 설명 체계 |
| [CH2_AI_CONSTITUTION.md](./CH2_AI_CONSTITUTION.md) | AI 6대 조항·Router·Bundle |
| [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) | Candidate Factory · Validation Engine · 모듈 경계 |
| [CANDIDATE_EVALUATION_DESIGN.md](./CANDIDATE_EVALUATION_DESIGN.md) | 후보·표본·검증·Confidence 상세 |
| [CH2_MACRO_IMPLEMENTATION_ROADMAP.md](./CH2_MACRO_IMPLEMENTATION_ROADMAP.md) | V1~V3 구현 순서·완료 게이트 |
| [DECISIONS.md](./DECISIONS.md) | 구체적 설계 결정 기록 |
| [CH2_ENTITLEMENT.md](./CH2_ENTITLEMENT.md) | 무료/유료 권한 — 5앱 통일 · 토지 전용 무료 탭 없음 (D-043) |
| [REGIONAL_PROFILE_ARCHITECTURE.md](./REGIONAL_PROFILE_ARCHITECTURE.md) | Regional Profile·거시 분석 로드맵 |
| [CH2_MIDCHECK_IMPROVEMENT_PLAN.md](./CH2_MIDCHECK_IMPROVEMENT_PLAN.md) | 중간점검 개선안 — 검증·Twin Validation·월간 SSOT |
| [TWIN_VALIDATION_STATUS.md](./TWIN_VALIDATION_STATUS.md) | Twin Validation 실태·판정 초안 |
| [TWIN_ENGINE_V2.md](./TWIN_ENGINE_V2.md) | Twin 거리 엔진 V2 — 비교/풀 분리 (D-044) |
| [MONTHLY_UPDATE_CHECKLIST.md](./MONTHLY_UPDATE_CHECKLIST.md) | 월간 1페이지 체크리스트 |
| [RENT_CONVERSION_EXPERIMENT.md](./RENT_CONVERSION_EXPERIMENT.md) | 주거 전월세 전환율 실험 종료 · `mean_simple` 확정 (D-040) |

---

**한 줄:** CH2 Macro는 개별 AVM이 아니라, **과거의 큰 움직임으로 시장을 읽고 숨은 인사이트를 얻는** 거시적 부동산 통계 플랫폼이다 — 감정평가사를 중심으로, 일반 사용자도 함께 쓸 수 있게.
