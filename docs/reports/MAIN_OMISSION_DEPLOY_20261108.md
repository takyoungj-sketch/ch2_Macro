# main 누락 복원 운영 배포 — 2026-11-08

## main 반영 및 운영 상태

- 검증한 `codex/release-20261108`의 복원 커밋을 로컬 main에 fast-forward 병합했다.
- `origin/main`은 기존 `d563d97`에서 복원 소스 기준 `6f8ed2b`로 정상 push됐다. 이 보고서의 후속 커밋은 문서 변경만 포함한다.
- 복합·집합 공식 배포 스크립트 실행 및 VPS 프로덕션 빌드 완료. 토지 회귀와 공통 표본 판정·구조 표시 헬퍼도 함께 반영했다.
- 백엔드 `ch2-macro-backend` 재시작 및 `/health` 정상. 최종 확인 시 최근 10분의 서비스 로그에 Traceback 0건.
- 변경 대상 제품 소스 46개를 줄바꿈 정규화 SHA256으로 비교해 모두 로컬 main과 운영 일치를 확인했다.
- 운영 DB 구조·데이터는 변경하지 않았다. 회귀·효용지수 계산 검증은 READ ONLY 트랜잭션으로 수행했다. 실제 AI 모델 호출은 하지 않았다.

## 배포 방법과 백업

런북 `deploy/AGENT_DEPLOY_RUNBOOK.md`의 scp 배포 경로를 따랐다.

1. 배포 전 서버 내 코드·공유 모듈·복합/집합 소스 및 dist 백업:
   `/opt/ch2_release_backups/20261108-110719-main-restoration/code-and-static.tar.gz`.
2. 토지·공통 헬퍼 3개와 집합 backend 두 디렉터리를 먼저 전송해 의존 파일을 준비했다.
3. `deploy-from-windows.ps1 -Scope built -SkipPush`로 복합 코드 전송·빌드·재시작을 완료했다.
4. 기본 스모크의 유료 회귀 API 호출은 사용자 로그인 없이 실행되므로 정상 401로 중단됐다. 코드 오류가 아니라 로그인 제한임을 별도 확인했다.
5. `deploy-from-windows.ps1 -Scope collective -SkipPush -SkipVerify`로 집합 코드 전송·빌드·재시작을 완료하고, 아래 별도 스모크로 대체 검증했다.

프런트 JS 산출물:

- 복합: `/built/assets/index-CCema-IN.js`.
- 집합: `/collective/assets/index-BfOyZLU7.js`.

## 실제 운영 검증

- 토지 지역명 검색 정상.
- 비로그인 토지 5년 기본통계·용도×지목 매트릭스 롤링 5구간 정상.
- 비로그인 주거 집합 기본통계·5년 롤링 정상. 면적형별 롤링 3유형 정상.
- 비로그인 비주거 집합 기본통계·5년 롤링 정상. 면적형별 롤링 4유형 정상.
- 주거·비주거 7년 조회 401, 유료 분석 401 유지. 인증·접근 정책을 우회하도록 바꾸지 않았다.
- 서버 내부 복합 회귀: 가경동 초점 `eupmyeondong`, 상위 비교 `gu`·`sigungu`, 적합/추정 표본 67건 일치 및 모형 서명 확인 통과.
- 서버 내부 주거 효용지수: 조회/분석 264건, 5개 구간, `regression_semilog`, 응답 직렬화 정상.
- 비주거 효용지수: 최초 선택 대상의 해당 기간 표본 30건은 최소 50건 제한으로 정상 403이었다. 제한을 해제하지 않고 동일 기간의 충분한 표본을 선택해 조회 1,667건·분석 1,664건, 8개 구간의 `regression_semilog` 및 응답 직렬화를 확인했다.
- Insight 13·14 각각 보고서 전용 Bundle·한계·서비스 안내 등록 정상.
- 외부 운영 `/built/`, `/collective/residential/`, `/collective/commercial/`, `/insight/`는 기존 사이트 비밀번호 보호에 따라 401을 반환한다.

## 검증 한계

내장 브라우저의 운영 페이지 열기는 `ERR_INVALID_AUTH_CREDENTIALS`로 차단됐다. 따라서 이번 배포에서 비밀번호 인증 후 화면의 시각 검증이나 브라우저 전체 E2E 완료를 주장하지 않는다. 서버 빌드 산출물·소스 해시·실제 API 및 읽기 전용 계산 검증은 완료했다.

기존 번들 크기·Browserslist 경고는 배포를 막지 않았다. 사전 회귀 테스트 결과와 잔여 검토 후보는 [복원 보고서](../MAIN_OMISSION_RESTORATION_20261108.md)를 참고한다. 임대 탭 공개 여부 등 보류 항목은 이번 배포에 포함하지 않았다.

검증 스크립트·소스 해시 결과는 Git 제외 `logs/main-omission-audit-20261108/`에 보관했다. 사용자별 원자료나 인증정보를 보고서에 저장하지 않았다.
