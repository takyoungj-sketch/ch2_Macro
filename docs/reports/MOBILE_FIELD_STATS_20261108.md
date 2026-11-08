# 현장용 모바일 기본통계 수정 — 2026-11-08

## 요청과 구현

이전 e022bf1은 모바일 모달 축소 스타일만 복원하여 지역 선택 및 집합 대문 문제를 해결하지 못했다. 이번 변경은 PC 화면과 분리된 모바일 진입점을 제공한다.

- 상단: 토지 / 주거집합 / 비주거집합 직접 이동. 모바일 `/collective/`도 바로 주거 통계 화면을 연다.
- 지역 입력: 세 서비스가 같은 canonical 지역명 검색을 사용한다. 전국 전체 카탈로그 로딩 중 입력을 막지 않는다. 검색 결과를 선택하거나 유일하게 일치하는 지역을 Enter로 확정하면 즉시 통계를 조회한다.
- 지역은 한 개만 보관하고 새 선택은 이전 지역을 대체한다. 지도·복수지역·PC 칩 선택·고급 분석·로그인 안내를 모바일 화면에 표시하지 않는다.
- 토지: 5년 기본통계 용도×지목 매트릭스(평균 단가·거래수), 셀 선택 시 5년 롤링 그래프와 구간 수치.
- 집합: 주거 단지·건물별 / 비주거 도로명별 거래수·중앙값·평균, 이름 선택 시 5년 롤링 그래프와 구간 수치. 유형 변경은 한 가지 유형 또는 전체로 제공한다.
- 모달은 작은 제목·닫기 버튼과 스크롤 본문만 제공한다. ESC와 포커스 복귀를 지원한다.
- PC App 및 기존 통계 산식·유료 정책은 수정하지 않는다. 모바일은 기존 무료 5년 API만 호출한다.

## 확인한 기존 문제

집합 모바일은 PC의 시도·시군구/칩 선택 UI를 사용하고 있었고, `analysisUnits`를 모바일 effect에서 비우는 동작이 있었다. 토지 입력은 전국 카탈로그 로딩에 종속되어 비활성화될 수 있었다. 새 모바일 화면은 두 상태 흐름을 사용하지 않고 검색 결과의 canonical 코드로 통계를 요청한다. 집합 API의 필수 addr2도 함께 전달한다.

## 검증

- 토지·집합 TypeScript 검사 및 Vite production build 통과.
- `backend/tests/test_product_gate.py`: 6개 통과.
- 로컬 브라우저: 가경동 토지 매트릭스·셀 롤링, 주거 형석1 롤링, 비주거 2순환로 롤링, 흥덕구 Enter 확정 및 기존 단일 지역 교체, 집합 대문 없는 진입과 주거→비주거 직접 이동 확인.
- 390×844: 헤더 약 41px + 지역 입력 약 61px, 기본통계 영역 약 741px. 320×640에서 문서 가로 넘침 없음. 844×390에서 롤링 모달 헤더 47px·본문 343px. 라이트·다크, 닫기·ESC 확인.
- 운영 API: 사용자 JWT/쿠키 없이 지역 검색, 토지 기본통계·셀 롤링, 주거·비주거 목록 및 롤링 모두 200 확인. 7년 롤링·유료 분석은 401 유지. `pipeline/smoke_mobile_free.py`로 재현 가능. API_TOKEN은 기존 인프라 인증용이며 사용자 로그인과 무관하다.
- 실제 휴대폰의 Safari/Chrome 및 키보드는 직접 검사하지 못했다. 운영 브라우저 접근은 기존 HTTP Basic Auth 때문에 차단되므로 서버 빌드·정적 자산과 API를 검증한다. 기존 Basic Auth 설정은 변경하지 않는다.

## 변경 파일

- `frontend/src/main.tsx`, `frontend/src/MobileLandApp.tsx`
- `frontend-collective/src/main.tsx`, `frontend-collective/src/MobileCollectiveApp.tsx`
- `shared/macro-shell/mobile/{useMobileScreen.ts,MobileStatsShell.tsx,MobileRegionSearch.tsx,mobileStats.css}`
- `pipeline/smoke_mobile_free.py`, 본 보고서
