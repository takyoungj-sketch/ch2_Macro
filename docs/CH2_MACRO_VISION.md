# CH2 Macro Vision

> **불변 제품 철학.** 기능·UI·통계·AI 구현은 이 문서와 [CH2_CONSTITUTION.md](./CH2_CONSTITUTION.md)를 따른다.  
> 기술 모듈·API·알고리즘 세부는 [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md), [CANDIDATE_EVALUATION_DESIGN.md](./CANDIDATE_EVALUATION_DESIGN.md)를 본다.

---

## 한 줄 정의

**CH2 Macro는 지역 지식으로 후보모형을 만들고, 검증으로 고르고, AI로 설명하는 거시적 부동산 통계 플랫폼이다.**

---

## 목적

CH2 Macro는 **시장을 거시적으로 이해**하고, **시세 수준을 파악**하며, **미래를 읽기 위한 과거 데이터**를 분석하는 도구이다.

| 목표 | 설명 |
|------|------|
| **지역시장 이해** | 지역·자산군·시기별 수준·분산·추세·구조 |
| **통계적 설명** | 회귀·분포·코호트·매트릭스로 보이지 않던 차이를 드러냄 |
| **후보모형 생성** | Local·Twin Pooling·Region Group 등 **여러 후보**를 동시에 만든다 |
| **객관적 검증** | 동일 표본·동일 규칙으로 후보를 비교·순위화한다 |
| **AI 설명** | 검증된 결과와 한계를 근거 기반으로 해설한다 |

개별 물건에 “얼마”라고 숫자 하나를 붙이는 데 그치지 않는다.  
과거에 **크게 움직인 흐름**을 포착하고, **쉽게 보이지 않는 패턴·인사이트**를 드러내어, 사용자가 시장 맥락 속에서 판단할 수 있게 한다.

---

## 1차 사용자

| 층위 | 대상 | 비고 |
|------|------|------|
| **1차** | 감정평가사 | 설계·검증·워크플로의 기준 사용자 |
| **2차** | 일반 사용자 | 부동산에 관심 있는 누구나 — 전문 용어·통계를 **접근 가능하게** |

감정평가사만을 위한 폐쇄 도구가 아니다.  
전문성을 유지하면서도, **처음 온 사람도 시장 그림을 읽을 수 있는** 경험을 지향한다.

---

## AVM이 아닌 이유

| | 개별 AVM (전형) | CH2 Macro |
|---|-----------------|-----------|
| **초점** | 특정 물건 하나 | 지역·코호트·시장 구조 |
| **방법** | 유사 과거거래 비교 → 가치 산출 | 추세·분포·회귀·코호트·매트릭스 등 **집단 통계** |
| **결과** | “이 건은 X원”에 수렴 | “이 시장은 지금 어디에 있고, 무엇이 움직였는가” |
| **한계 인식** | 모형·표본 한계가 묻히기 쉬움 | 표본·기간·해상도 한계를 **화면과 설명에 노출** |

CH2 Macro는 **개별 적정가격 엔진을 대체하지 않는다.**  
과거 거래의 **큰 움직임**과 **구조적 차이**를 보여 주어, 감정·투자·기획 판단의 **배경 지식**을 제공한다.

---

## 하지 않는 것

- 개별 물건의 **감정·적정가격 대체**
- **투자 추천**, “오른다/내린다” 식의 **단정적 전망**
- AI가 가격을 **결정**하거나 모형을 **대신 선택**하는 것
- 표본·기간·모형 한계를 **숨기는** 단일 정답 제시

---

## 핵심 철학 (불변)

### Profile은 가설을 제안하고, Validation이 최종 판단한다

Regional Profile은 **회귀변수 목록**이 아니라 **지역 이해·후보 생성·설명**의 엔진이다.

- Profile → Twin·Region Group **후보 제안**
- Regression Engine → 거래자료 기반 **후보모형 적합**
- Validation Engine → **동일 규칙**으로 후보 비교·순위화
- AI → 검증 결과를 **근거 기반으로 해설**

Profile이 후보를 만들 수는 있지만, Profile 자체가 회귀 성능을 **판정해서는 안 된다.**  
거래자료와 Validation이 최종 판단한다.

### AI는 판사가 아니라 해설자

- AI는 **Facts First** — CH2가 계산·저장한 수치·Bundle만 인용
- AI는 모형을 **선택하지 않고**, 사용자가 채택한 결과와 후보 비교를 **설명**
- AI는 한계(limitations)를 **먼저** 말한다

상세: [CH2_AI_CONSTITUTION.md](./CH2_AI_CONSTITUTION.md)

### 하나의 정답이 아니라 후보 경쟁

회귀를 “잘 돌리는 것”이 아니라 **왜 이 모형을 선택했는지 설명 가능한 과정**이 가치이다.

- 후보 A/B/C + 지표 + 사용자 선택 ✓
- “최적 모형” 단정 ✗

---

## 제품 흐름 (한 페이지 그림)

```
거래 원장 (Transactions)
        │
        ▼
Regional Profile Engine ──→ 지역 이해 · Twin · Region Group 후보
        │
        ▼
Candidate Factory ──→ Local · Twin Pool · Region Group · Province · National Prior …
        │
        ▼
Validation Engine (OS) ──→ 동일 표본 · Time Split · Spatial Validation · Holdout
        │
        ▼
Model Ranking · Decision Confidence
        │
        ▼
AI Explanation (Facts · Limitations · Evidence)
```

**현재 구현:** 거래 원장 → 실시간 OLS 회귀·모형 추천(복합·집합) → 부분회귀도·예측.  
Profile·Twin·Validation OS·Candidate Factory는 **단계적 도입** ([CH2_MACRO_IMPLEMENTATION_ROADMAP.md](./CH2_MACRO_IMPLEMENTATION_ROADMAP.md)).

---

## 제품·기술 원칙 (요약)

| 원칙 | 요약 |
|------|------|
| **Facts First** | 수치·표본·계수는 CH2가 계산·저장한 결과만 (AI 포함) |
| **한계 노출** | n, 기간, 해상도, 모형 가정을 숨기지 않음 |
| **해상도 일관** | 토지·주거 집합·비주거 집합·복합 — 같은 통계 언어·UI 패턴 |
| **전문가 + 대중** | 감정평가 워크플로에 맞으면서, 설명·라벨은 비전문가도 따라올 수 있게 |
| **Validation Contract** | 모든 후보는 동일 검증 규칙을 통과해야 비교 가능 |

---

## 관련 문서

| 문서 | 역할 |
|------|------|
| [CH2_CONSTITUTION.md](./CH2_CONSTITUTION.md) | 제품 헌법 (존재 이유·사용자·AVM 비교) |
| [CH2_AI_CONSTITUTION.md](./CH2_AI_CONSTITUTION.md) | AI 6대 조항·Router·Bundle |
| [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) | 모듈 경계·인프라·API |
| [CANDIDATE_EVALUATION_DESIGN.md](./CANDIDATE_EVALUATION_DESIGN.md) | 후보·표본·검증·Confidence 상세 |
| [CH2_MACRO_IMPLEMENTATION_ROADMAP.md](./CH2_MACRO_IMPLEMENTATION_ROADMAP.md) | V1~V3 구현 순서·완료 게이트 |
| [REGIONAL_PROFILE_ARCHITECTURE.md](./REGIONAL_PROFILE_ARCHITECTURE.md) | Profile·Market Stats 도메인 SSOT |
| [DECISIONS.md](./DECISIONS.md) | 구체적 설계 결정 기록 |

---

**한 줄 (재확인):** CH2 Macro는 **지역 지식으로 후보모형을 만들고, 검증으로 고르고, AI로 설명하는** 거시적 부동산 통계 플랫폼이다 — AVM이 아니다.
