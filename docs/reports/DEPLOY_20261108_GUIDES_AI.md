# 서비스 안내·AI·구독 한도 배포 결과

작업일: 2026-11-08 (Asia/Seoul).

> 후속 정정: 아래에서 잔존 파일로 분류했던 `AllocationUi`, `builtTxAggregate`, `BuiltTransactionAggregate`는 폐기된 코드가 아니라 main 통합에서 누락된 기존 복합 기능이었다. 운영 백업과 작업 브랜치를 대조해 원인을 확인했으며 [간이 토지 배분단가 복원 기록](BUILT_ALLOCATION_RESTORE_20261108.md)에 따라 관련 진입점·계산·집계를 함께 복원했다. 아래 배포 중 정리 내용은 당시 조치의 기록으로만 해석한다.

## 반영 범위

- 대문과 유형별 안내, 임대·지역프로필 도움말, 토지 선택 지역 가독성, 토지·집합 모바일 롤링 헤더.
- 화면과 Insight 본문을 사용하는 AI 대화, 세션 소유권과 수치 검증, 계정별 요청·비용 장부.
- Macro 단독 AI 200회, 동시 구독 Macro 250회·사진 분석 500장·문구 작성 100회·주소표 보정 100회.
- 운영 플랫폼 DB에 `077_platform_ai_allowances.sql`의 신규 테이블 6개 적용. 기존 거래·결제·구독 원장 삭제나 소급 차감 없음.
- `AI_SUBSCRIPTION_QUOTA_ENABLED=true` 활성화. 구버전 Fieldnote의 작업 ID 누락은 서버 발급 ID로 호환한다.
- 기존 관리자 제품 접근을 배포 전 백업과 동일하게 보존. 로컬 개발 우회나 비로그인 유료 접근은 추가하지 않았다.

## 커밋·원격

최신 원격 main에 이번 변경만 통합했다. 원래 작업 브랜치의 다른 수정·임시 파일·개인 자료·결제 심사 산출물은 보존하고 제외했다.

- Macro 가이드: `c66fe99`.
- Macro AI·계정 한도: `df2e87c`.
- 운영 Insight 13개 보존·배포 호환성: `22cc203`.
- 기존 관리자 접근과 호환성 검증: `99c7c55`, `c8d855f`.
- Fieldnote 원격 main: `68b1534`.

웹 앱과 서버 배포는 완료했다. Fieldnote 소스와 서버 API도 반영했지만 **Android/iOS 바이너리 또는 앱스토어 등록은 수행하지 않았다.** 별도 문구 작성 버튼과 정확한 새 잔여량 표시는 새 Fieldnote 앱 업데이트에 포함된다. 구버전 사진·주소표 요청은 서버에서 계속 처리한다.

## 검증

- main 통합본의 AI·사용량·구독 관련 186개 테스트 통과.
- 구버전 Fieldnote 무작업ID 요청 처리 모의 테스트 1개 추가 확인, 관리자·웹 구독 테스트 4개 통과.
- 로컬 7개 앱 TypeScript·Vite 빌드 및 Fieldnote TypeScript 통과.
- 운영 서버 7개 앱의 기존 build 스크립트 전체 완료. nginx 설정 검사·reload 및 백엔드 재시작 완료.
- 운영 PostgreSQL의 격리 시험 스키마에서 마지막 1회 동시 요청 경쟁 및 사진 12장 실패 복원 PASS. 시험 스키마는 확인 후 제거했으며 모델 호출 없음.
- `/health` 정상, 토지 가경동 검색 1개, 집합 주거·비주거 필터 메타 정상.
- 기존 관리자 세션으로 `/api/ai/health` 200 (`grounded_dialogue`), 한도 조회 200, 관리자 계정 장부 200 (`enabled=true`), Fieldnote 한도 조회 200.
- Fieldnote vision/sheet/write 빈 입력은 공급자 호출 전에 HTTP 400으로 거절.
- 런북 복합 회귀: 가경동 초점 `eupmyeondong`, 흥덕구 비교 포함, 잔차 표본 67개 확인. 이 API는 새 권한 게이트에 맞춰 기존 관리자 세션으로 검증했다.
- 7개 앱의 index에 참조된 해시 자산 파일 모두 존재.
- 운영 HTTPS 인증서 연결 및 대문·각 제품 경로에서 기존 HTTP Basic 인증 401 확인. 인증 해제·비밀번호 변경 없음.
- 유료 OpenAI 추가 호출·비용 실측 없음.

## 배포 중 정리와 복원

현재 커밋에 없는 과거 오버레이 파일이 타입 검사에 섞였다. 광범위 파일 이동과 빌드 범위 변경은 자동 승인 검토에서 거절돼 실행하지 않았다. 기존 빌드 설정을 유지했다.

실제 앱 진입점의 읽기 전용 TypeScript 참조 그래프에서 의존성이 아님을 확인한 오류 파일만 개별 보관했다. 기존에 없어진 LandModelRecommend, AllocationUi, builtTxAggregate와 미사용 BuiltTransactionAggregate, AreaRollingView, UtilityIndexResults가 해당한다. 다른 잔존 소스의 일괄 이동·삭제는 하지 않았다.

- 배포 전 코드·정적 파일·환경·nginx 백업: `/opt/ch2_release_backups/20261107-152031` (폴더 시각은 UTC).
- 개별 잔존 소스 보관: `/opt/ch2_Macro/logs/release-quarantine-20261108`.
- 신규 AI 예약 복구 도구: `/opt/ch2_Macro/backend/scripts/reconcile_ai_allowance.py`.

운영 PostgreSQL 다중 요청 검증은 수행했으나 실제 유료 구독 결제 전환, Android/iOS 실기기 UI 및 앱스토어 새 버전 배포는 이번 결과에 포함하지 않는다.
