# main 누락 사항 순차 복원 결과 — 2026-11-08

후속 상태: main push 및 운영 배포 완료. [운영 배포·검증 보고서](reports/MAIN_OMISSION_DEPLOY_20261108.md)를 참고한다. 아래 배포 전 상태는 당시 복원 완료 시점의 기록이다.

검토 보고서 `MAIN_OMISSION_REVIEW_20261108.md`의 우선 복원 항목을 복합 → 토지 → 집합 → Insight → 장기추세 순서로 적용했다. 기존 main `d563d97`을 기준으로 `codex/release-20261108`에서 작업했다. 전체 작업 브랜치 병합은 하지 않았다.

## 완료한 변경과 커밋

1. `a15eabc` — 복합 추천 표본·Twin 조건·CV 순위
   - 추천 검색의 공통 숫자 결측 표본을 Local/Twin 재적합과 산점도에도 전달한다.
   - 원래 브랜치에서 빠져 있던 가격 추정 경로의 표본 고정도 보완했다. 추정 요청 역시 같은 `sample_lock_blocks`와 범주형 결측 정책을 적용한다.
   - Twin 조회에 현재 상세 필터와 IQR 조건을 전달한다. 재탐색은 통과한 선택 지역 전체를 사용한다.
   - 미완료 연도가 있는 CV를 예측형 순위에서 제외하고 대표모형 판단에 사유를 남긴다.
   - 서로 다른 Local/Twin 표본의 CV 차이를 원래 지역만의 예측 개선으로 단정하지 않도록 원래 설명도 복원했다.
2. `6500903` — 토지 회귀 정합성
   - 적합·추정의 범주 결측 처리, 추천 최소 표본, 빈 결과·상수 변수·비유한 통계량 처리를 복원했다.
   - 지분 표시가 비어 있는 전체거래를 문자열 결측 때문에 추천 표본에서 제외하지 않는다.
   - 공시지가 연결·기준연도 선택·원장 조회 SQL 정책은 변경하지 않았다.
3. `cdf8782` — 집합 주거·비주거 표본·효용지수·지역회귀
   - 희소 층·동·단지·도로명·반기 처리, 학습하지 않은 범주, 공선성 및 비교 지표의 공통 기준을 복원했다.
   - 효용지수 기준과 신뢰구간·p값의 대비를 맞추고, 조회 거래와 실제 분석 거래·산출 불가 사유를 함께 보여준다. 주거와 비주거가 공통 결과 컴포넌트를 사용한다.
   - 비주거 효용지수에 롤링 시작·종료 날짜를 전달한다.
   - 지역회귀의 부분 검증을 정상 검증과 구분하고 화면에도 제한 사유를 표시한다.
   - 구조 코드는 그대로 두고 기존 원래 브랜치의 한국어 표시 헬퍼를 복원했다.
4. `e9c716a` — Insight 13·14 AI 지원
   - 보고서별 Bundle, extractor, capability, 안내·후속 질문을 복원했다.
   - 네거티브 원칙과 기존 AI 이용량·구독 정책은 유지했다. 모델 호출 없이 등록과 핵심 수치·한계 전달을 검증했다.
5. `a7f2723` — 집합 장기추세의 누락 연도
   - 주거·비주거가 사용하는 단일·복수 대상 차트 모두 관측이 없는 연도를 보존한다.
   - 실제 거래 자료를 보충하지 않고 불연속 관측 구간의 선·사분위 띠를 끊는다.
   - 연도별 모드의 공통 차트 호출에도 annual 옵션을 연결했다.

## 검증

- 복합 추천 관련 6개 테스트 파일: **40개 통과**. 추가한 가격 추정 표본 고정 테스트 포함.
- 토지 회귀·공시지가 회귀·공통 표본 판정: **25개 통과**.
- 집합 주거·비주거·효용지수·지역회귀·재현성 등 14개 파일: **151개 통과**.
- Insight 등록·AI 화면 계약·대화 원칙·사용량 정책 4개 파일: **57개 통과**.
- 위 backend 그룹 합계는 서로 다른 **273개 테스트 통과**다.
- 최초 누락 진단에 사용한 원본 스냅샷 75개를 그대로 재실행: **75개 모두 통과**. 이 75개는 위 테스트와 중복되는 재확인이므로 합계에 다시 더하지 않는다. 결과 XML은 `logs/main-omission-audit-20261108/restored-tests.xml`.
- 장기추세 유틸리티 Node 테스트: **4개 통과**. 이 중 2개는 비교 자료 로딩 헬퍼의 단위 검증이다. 현재 모달의 비교 조회 연결 전체를 검증한 결과로 보지 않는다.
- 복합·집합 TypeScript 검사 및 Vite 프로덕션 빌드 통과. 기존 번들 크기·Browserslist 데이터 경고는 남아 있다.
- 일부 통계 합성 표본에서 statsmodels 경고, 사용량 SQLite 테스트에서 datetime adapter 경고가 있었으나 테스트 실패는 없었다.
- 최초 AI 실행은 임시 폴더 권한 문제, 이후 Windows 샌드박스의 asyncio 로컬 socketpair 생성 정지로 완료하지 못했다. workspace 내 임시 경로를 지정하고, HTTP·모델 호출을 모의 처리한 동일 테스트를 샌드박스 밖에서 실행해 57개 통과를 확인했다. 제품 코드를 테스트 환경에 맞춰 우회하지 않았다.

## 유지한 범위와 남은 검토

모바일 지역 선택·헤더·기본통계·롤링 전용 흐름, 로그인·권한·결제 정책, 모형추천2 제거, AI2 숨김은 변경하지 않았다. 랩/AI3 실험 파일도 복원하지 않았다.

다음은 이번 우선 복원과 별개로 남겨 둔다.

- 임대 회귀 탭 공개 여부: 원래 브랜치는 비공개, main은 공개다. 마지막 공개 의도가 확인되지 않아 상태를 임의 변경하지 않았다.
- 토지 새 모형추천 UI 및 후보 채택 편의: 기존 추천 기능은 남아 있으며, 계산 정합성 복구와 별도로 화면 개선분을 검토한다.
- 집합 분양권 비교 선택 UI·카탈로그 변경과 비교 조회 일부 실패의 모달 처리: 이번에는 API 경로와 기존 선택 UI를 바꾸지 않았다. 장기추세의 축·연결 표시만 복원했다.
- 나머지 랩·주변 소스 차이를 전부 반영한 것은 아니다. 검토 단계의 190개 파일 차이가 모두 제품 결함이라는 의미도 아니다.

운영 DB 데이터 변경, 실제 유료 AI 호출, 브라우저 화면의 PC·모바일/다크·라이트 시각 검증, 전체 E2E는 수행하지 않았다. 로컬 복원 커밋까지 완료했으며 **원격 main push와 운영 배포는 아직 하지 않았다**.

## 주요 수정 파일 위치

- 복합: `backend/app/built/regression/`, `backend/app/built/schemas.py`, `backend/app/recommendation/`의 결론·순위·stage2·종료·Twin 검증, `frontend-built/src/components/RecommendationModal.tsx`, `frontend-built/src/types.ts`.
- 토지·공통: `backend/app/land_regression.py`, `backend/app/regression_sample_judge.py`.
- 집합: `backend/app/collective/regression/`, `regional_regression/engine.py`, `regional_regression/schemas.py`, `floor_index_regression.py`, `analysis_explain.py`, 양쪽 schemas, 비주거 회귀 엔진과 router.
- 집합 화면: `FloorIndexPanel`, `CommercialFloorIndexPanel`, `UtilityIndexResults`, 양쪽 UtilityIndexHelp, `FloorIndexMethodGuide`, `RegionalRegressionModal`, 관련 타입·AI 컨텍스트·지역회귀 응답 타입·표시 유틸리티.
- 추세: `YearlyTrendChart`, `MultiBuildingTrendChart`, `CohortTrendPanel`, `utils/trendComparison.ts`.
- AI: `backend/app/ai/bundles/{registry,extractors}.py`, `panel_capabilities.py`, `knowledge/screen_guides.py`.
- 회귀 테스트는 관련 원래 브랜치 테스트와 필요한 fixture·기대 표시를 함께 복원했고, 복합 가격 추정 및 Insight 등록 검증을 추가했다. 수정 파일의 정확한 전체 목록은 `git diff --name-only d563d97 HEAD`로 확인한다.
