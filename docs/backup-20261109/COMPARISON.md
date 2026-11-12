# 미커밋 작업 백업 및 origin/main 비교

확인일: 2026-11-12 (Asia/Seoul). 원본 작업 브랜치: `claude/ai-revision-20261109`.

## 백업 결과와 범위

- 백업: `D:/ch2/ch2_Macro-wip1109`, 브랜치 `wip/ai-revision-20261109`.
- 기준: `05fa48fdc707e64f417fefdec2eb05fa96032745`. 첫 백업 커밋: `bc5924cee74dd29705f713203d7b197051e056ff`. 원격 push 후 `ls-remote` SHA 일치를 확인했다.
- 대상 212개 = 추적 변경 64개 + 미추적 148개. 이 중 210개를 커밋·push했고 대용량 원본 2개는 별도 worktree 로컬에만 복사했다.
- `_tmp_*`·`_debug_*`·`.release-worktree-*`에 해당하는 145개 경로 항목은 `excluded-paths.txt`에만 기록했다. 중첩 release worktree의 내부 파일은 펼쳐 수집하지 않았다.
- 대용량 원본: `data/research/land_trait_slim/gauge_asof_2026-05-12.sqlite` 8,826,650,624 bytes, `pipeline/_land_annual.sql` 1,583,383,475 bytes. 원본과 복사본 SHA-256 일치. 저장소 지침에 따라 커밋하지 않았으므로 원격만으로 이 두 파일은 복원할 수 없다.
- 소스·문서·Office/HWPX XML의 비밀값 패턴 검사에서 검출 없음. 대용량 원본 2개 및 이미지/PDF 시각 내용은 검사 범위 밖이다. `.env`·키는 백업 후보에 포함되지 않았다. 사용된 OAuth client ID는 공개 식별자이며 client secret은 파일에 없었다.
- 명시 요청 범위에 따라 미추적 `.vite` 캐시도 보존했다. 이 브랜치는 보존용이며 운영 배포나 main 병합을 수행하지 않았다.
- 원본 파일 삭제·수정·브랜치 전환·reset·clean·stash는 수행하지 않았다. 공유 Git 메타데이터의 fetch/백업 브랜치/worktree 등록은 요청한 작업에 수반된다.

## 분류 기준과 결과

비교 main: `dfa308262b8f93a466226379b5cf0345ecdbe98b` (2026-11-12 00:09:31 +09:00). 비교 단위는 **변경 파일의 전체 현재 내용**이며, 파일의 일부 기능이 이미 반영돼도 전체가 다르면 ②다. 텍스트 CRLF/LF만 정규화하고 그 밖의 공백·내용은 유지했다. 바이너리는 바이트 비교했다.

- ① 같은 내용으로 반영: **34개**.
- ② main과 다르게 반영: **48개**. main 과거 파일과 정확히 일치하는 경우는 해당 과거 커밋을 기록했다. 그 밖에는 실제 차이를 읽고 main 후속분/WIP 독립 변경을 구분했다. 미커밋 파일에 커밋 날짜를 임의로 부여하지 않는다.
- ③ main에 파일 없음: **130개** (로컬 전용 대용량 원본 2개 포함).

이름이 같은 파일이 main에 없다는 것은 내용 자체가 다른 경로에도 전혀 없다는 뜻은 아니다. 이 보고서는 경로별 대조이며, WIP 전체가 최신이라는 결론도 아니다. 임시 제외 목록 145개는 이 212개 분류에서 제외했다.

## 주요 내용

### AI 화면 근거·모달 문맥

11-09 `820bb12`에서 화면 문맥·서버 숫자 검증·관리자 보호가 main에 반영됐다. 매트릭스 상위 120칸과 합계/연도표, 지역·기간·실행한 필터·기준월 전달, 모달 추이의 부분 연도/15건 미만 표시, 기저 화면 문맥, 세션의 분석 문맥 보존이 핵심이다. `schemas.py`, `sessions.py`, `screen_guides.py`, `panel_capabilities.py`, `aiClient.ts`는 현재 main과 동일하다.

WIP의 대화는 정상 LLM 1회, 위반 시 1회 재작성 후 위반 문장만 제거하며 `{{current.fN}}`와 서버 AST 산술을 사용한다. main에는 `46db76c`(11-10 02:24), `7ea9a86`(11-10 15:50) 등의 후속 변경이 있다. 빈 화면에서 이전 통계를 재사용하지 않기, 현재/이전 출처 표시, 기본 참조를 값과 단위로만 출력, 내부 용어 제거, 칸 전체 중앙값·분위수 계산, 짧은 일반 답변 등이 보강됐다. 따라서 WIP dialogue 전체를 main에 덮으면 후속 보호가 사라진다. 반대로 WIP의 회귀 추천/모바일 UI와 패널 라벨 추가분은 별도 보존 가치가 있다.

### AI 한도·사용량

`rate_limit.py`와 `usage_log.py`는 main과 동일하다. 로그인은 검증된 JWT user ID, 비로그인은 IP를 키로 쓰고, 신뢰 프록시의 X-Real-IP만 허용한다. 분당 제한 저장소는 단일 워커 전제의 메모리다. 기존 계정별 구독 질문 한도는 유지하며 월 전체 호출/비용 상한, JSONL 월 누계 캐시, 질문별 LLM 호출 수·원가·지연·검증 결과, 개인 질문 수와 전체 LLM 호출 수 단위의 한도 충돌 경고를 추가했다. 관리자 사용량 API/화면은 WIP가 `820bb12` 시점과 일치하고 main에 후속 수정이 있어 main이 최신이다. 실제 운영 환경변수 값이나 현재 사용량은 이번 백업에서 조회하지 않았다.

### admin_auth.py

관리자 세션의 DB role=admin 또는 비어 있지 않은 설정 QA 토큰의 상수시간 비교만 허용하며, 미로그인 401/비관리자 403/DB 장애 시 거부한다. AI2는 기본 비활성·관리자 전용이다. 이 보호 자체는 main에 있다. WIP에는 `require_admin_access`와 제품 게이트에서 local_dev_access_enabled이면 조기 통과하는 예외가 별도로 있다. 이것은 main에 없는 접근 정책 차이이며 무심코 재적용하지 않아야 한다.

### 토지 회귀·표본 및 기준월

`land_regression.py`의 `exclude_outliers_iqr and not req.exclude_outlier`는 원장 셀에서 이미 적용한 IQR을 회귀에서 다시 계산하지 않게 한다. 이 파일은 main과 동일하다. 기본통계 셀/필터 분석의 미지정·기타 라벨 매칭, 기간·표본 조건 정합성, 필터 요청과 UI 상태 분리, 완료 집계월 선택 및 캐시 발행 버전 반영도 main과 동일하며 관련 표본/평가 테스트도 동일하다. 주 반영 커밋은 `af5d93f`(11-09 22:04)다.

모달 UI는 혼합 상태다. WIP에 연도추세 기본 해제, 후보 선택 후 즉시 회귀 실행, 지연 응답 무시, 접힌 산점도/추천 UI가 있다. main에는 칸 전체 통계를 AI에 넘기는 후속 코드가 있다. 통계 계산 패치와 UI 변경을 분리해 검토해야 한다.

### db/083_land_stats_v2_publications.sql

main과 완전히 동일하다. 완료된 월간 집계만 기록하는 `land_stats_v2_publications`를 `IF NOT EXISTS`로 만든다. 월 1일만 허용하는 date 기본키 `as_of_month`, 기본값 `clock_timestamp()`인 `published_at` 두 열이다. `land_stats_snapshot.py`가 최신 완료월을 읽고, 기본통계·상위통계·유료 분석이 이를 기준으로 사용하며 발행 시각으로 캐시를 갱신한다. 월간 러너의 검증 후 발행 흐름 역시 main에 후속 반영돼 있다. 이번 작업은 SQL을 실행하지 않았고 실제 DB 적용 상태는 확인하지 않았다.

## 검증과 원본 정리

파일 보존 작업이므로 앱 코드 수정/빌드/DB 마이그레이션을 수행하지 않았다. 대신 파일 SHA-256 대조, 스테이징 경로 집합 일치, 커밋 부모 기준점, 원격 SHA, 원본 변경 목록/내용 유지 여부를 검증한다. 백업 브랜치에는 기존 미커밋 실험과 생성물이 함께 있으므로 실행 검증 완료본으로 간주하지 않는다.

원본을 main으로 전환하거나 정리하려면 사용자의 별도 승인이 필요하다. 현재는 원본 보존 상태를 유지한다.

## 파일별 전체 목록


### ① 이미 main과 동일 (34개)

- `backend/app/ai/knowledge/screen_guides.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/ai/panel_capabilities.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/ai/rate_limit.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/ai/schemas.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/ai/sessions.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/ai/usage_log.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/ai2/router.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/land_lab/twin_router.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/land_regression.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/land_stats_snapshot.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/routers/free_v2.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/routers/paid.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/routers/upper_stats.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/app/schemas.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/tests/test_ai2_protocol.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/tests/test_land_paid_sample_alignment.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `backend/tests/test_regression_evaluation_identity.py` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `db/083_land_stats_v2_publications.sql` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `docs/AI_SCREEN_EXPLANATION_FOLLOWUP.md` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `docs/BUILT_REGRESSION_ANALYSIS_UI.md` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `docs/BUILT_REGRESSION_UX_IMPROVEMENT_PLAN.md` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `docs/LOCAL_DEVELOPMENT_ACCESS.md` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `docs/V2_STATS_DESIGN.md` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `docs/archive/CH2_AI_CONSTITUTION_v2.1_2026-11-04.md` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `frontend/src/components/PaidFilterTable.tsx` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `frontend/src/constants/paidFilters.ts` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `frontend/src/store.ts` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `frontend/src/types.ts` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `frontend/src/utils/freeStatsV2.ts` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `frontend/src/utils/paidAnalysisPayload.ts` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `frontend/tests/paidFilterState.test.cjs` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `scripts/local/start-built.ps1` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `scripts/local/use-env.ps1` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.
- `shared/ai-assistant/aiClient.ts` — 현재 WIP 내용과 origin/main 파일 내용 동일. 줄바꿈 CRLF/LF 차이는 무시.

### ② main과 다름 (48개)

- `backend/app/admin_auth.py` — 관리자 세션/설정된 QA 토큰 보호는 main 반영. WIP에만 require_admin_access의 local_dev_access_enabled 조기 허용 4줄이 있음. 기능 추가라는 의미에서는 WIP가 앞서지만 main의 관리자 접근 제한보다 느슨하므로 자동 덮어쓰기 금지.
  - main 최종 파일 변경: `820bb12` · 2026-11-09T23:51:03+09:00 · feat(ai): 화면 문맥 전달, 1회 호출 대화, 서버 숫자 검증과 관리자 API 보호
- `backend/app/ai/constitution.py` — main에 11-11 음수 추정금액 단정 금지 문구가 추가됨. WIP는 AI3도 레거시 경로라는 주석이 별도 유지됨. 운영 정책은 main 후속본.
  - main 최종 파일 변경: `c9275cd` · 2026-11-11T17:23:43+09:00 · fix(built): 점검 4단계 — 표시·안내 정리, Twin 판단 기준(T-5), D-073 갱신·D-083 확정
- `backend/app/ai/dialogue.py` — main에 11-10 이후 빈 화면 이전 분석 재사용 방지·출처 구분·기본 참조 값만 표시·내부 용어 제거·칸 전체 통계 계산·분위범위 보완·유형별 주의문구·자리수 개선이 있음. WIP에는 모든 매트릭스 칸 p25/p75 전달처럼 다른 구현도 있어 정확한 과거 파일 일치가 아닌 혼합 상태. 운영 AI 기준은 main 후속본이며 WIP 전체 복원 금지.
  - main 최종 파일 변경: `c9275cd` · 2026-11-11T17:23:43+09:00 · fix(built): 점검 4단계 — 표시·안내 정리, Twin 판단 기준(T-5), D-073 갱신·D-083 확정
- `backend/app/ai/usage_router.py` — WIP 파일이 main 이력의 820bb12과 일치. main에 그 뒤 수정이 있으므로 main이 최신.
  - main 최종 파일 변경: `46db76c` · 2026-11-10T02:24:40+09:00 · fix(ai): 빈 화면에서 이전 분석 재사용을 막고 참조를 값만 넣으며 칸 전체 통계로 계산한다
  - WIP와 일치하는 main 과거 파일: `820bb12ea8610c0ea132cb872bb9ae303beaf7f5`
- `backend/app/config.py` — main은 AI_REASONING_EFFORT와 C-05 파라미터 경고 설정을 보유. WIP는 AI3 설정 4개를 별도 보유. 양쪽 독립 변경.
  - main 최종 파일 변경: `fa5af18` · 2026-11-11T23:23:05+09:00 · fix(collective): 1단계 Phase 3 — 비주거 날짜 필터·코호트 미상 제외·미지원 파라미터 경고 모드 (C-05, N-3)
- `backend/app/main.py` — main은 C-05 경고 미들웨어/종료 처리와 health.configured_land_as_of_month를 보유. WIP만 AI3 라우터 등록. 양쪽 독립 변경.
  - main 최종 파일 변경: `fa5af18` · 2026-11-11T23:23:05+09:00 · fix(collective): 1단계 Phase 3 — 비주거 날짜 필터·코호트 미상 제외·미지원 파라미터 경고 모드 (C-05, N-3)
- `backend/app/product_gate.py` — WIP에만 /api/ai3/ 제품 경로와 로컬 개발 시 게이트 전체 조기 통과가 있음. main과 다른 접근 정책이므로 단순 최신 교체 대상 아님.
  - main 최종 파일 변경: `15a6d49` · 2026-11-10T00:22:13+09:00 · fix(ai): 랩 관리자 API에 QA 토큰을 보내고 AI3 잔여 설정과 누락된 AI 문맥을 정리한다
- `backend/tests/conftest.py` — WIP 파일이 main 이력의 820bb12과 일치. main에 그 뒤 수정이 있으므로 main이 최신.
  - main 최종 파일 변경: `fa5af18` · 2026-11-11T23:23:05+09:00 · fix(collective): 1단계 Phase 3 — 비주거 날짜 필터·코호트 미상 제외·미지원 파라미터 경고 모드 (C-05, N-3)
  - WIP와 일치하는 main 과거 파일: `820bb12ea8610c0ea132cb872bb9ae303beaf7f5`
- `backend/tests/test_ai_gateway.py` — WIP 파일이 main 이력의 820bb12과 일치. main에 그 뒤 수정이 있으므로 main이 최신.
  - main 최종 파일 변경: `46db76c` · 2026-11-10T02:24:40+09:00 · fix(ai): 빈 화면에서 이전 분석 재사용을 막고 참조를 값만 넣으며 칸 전체 통계로 계산한다
  - WIP와 일치하는 main 과거 파일: `820bb12ea8610c0ea132cb872bb9ae303beaf7f5`
- `backend/tests/test_land_ai_dialogue.py` — main의 11-10 이후 참조·빈 화면·산술·유형별 보호 후속 테스트와 WIP의 검증 예제가 다름. 운영 후속 정책은 main 기준. 테스트 파일을 덮어쓰기보다 필요한 WIP 사례만 검토.
  - main 최종 파일 변경: `7ea9a86` · 2026-11-10T15:50:49+09:00 · fix(ai): 답변의 내부 용어를 빼고 중앙값 계산에 분위 범위를 붙이며 일반 답을 짧게 한다
- `deploy/hub/index.html` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `ff92339` · 2026-10-18T12:11:06+09:00 · 토스 빌링 심사에 맞춰 홈에서 월 구독 상품을 열고, 회신 초안에 빌링 MID와 단건 가입비 환불 요청을 반영.
- `deploy/hub/refund/index.html` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `ff92339` · 2026-10-18T12:11:06+09:00 · 토스 빌링 심사에 맞춰 홈에서 월 구독 상품을 열고, 회신 초안에 빌링 MID와 단건 가입비 환불 요청을 반영.
- `deploy/hub/subscribe/index.html` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `dcccf85` · 2026-10-09T15:57:55+09:00 · fix(hub): 빌링 미계약 시 심사용 단건 결제창 fallback
- `deploy/hub/subscription/index.html` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `6547798` · 2026-10-09T15:18:52+09:00 · feat(billing): 토스 빌링키 월 구독과 해지 예약을 연동한다
- `deploy/hub/toss-review/CH2DATA_payment_path.pptx` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `667dfe2` · 2026-10-09T16:05:02+09:00 · docs(toss): 심사용 결제창 캡처로 결제경로 PPT를 갱신한다
- `deploy/hub/toss-review/CH2DATA_결제경로.pptx` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `667dfe2` · 2026-10-09T16:05:02+09:00 · docs(toss): 심사용 결제창 캡처로 결제경로 PPT를 갱신한다
- `deploy/hub/toss-review/screenshots/02_footer.png` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `7d2bd01` · 2026-10-01T11:02:58+09:00 · feat(hub): 사용자 캡처로 토스 결제경로 PPT를 다시 만든다
- `deploy/hub/toss-review/screenshots/03_refund.png` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `7d2bd01` · 2026-10-01T11:02:58+09:00 · feat(hub): 사용자 캡처로 토스 결제경로 PPT를 다시 만든다
- `deploy/hub/toss-review/screenshots/06_subscribe.png` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `667dfe2` · 2026-10-09T16:05:02+09:00 · docs(toss): 심사용 결제창 캡처로 결제경로 PPT를 갱신한다
- `deploy/hub/toss-review/screenshots/07_payment_window.png` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `667dfe2` · 2026-10-09T16:05:02+09:00 · docs(toss): 심사용 결제창 캡처로 결제경로 PPT를 갱신한다
- `deploy/scripts/apply_toss_test_keys_from_local.ps1` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `1f483b9` · 2026-10-09T15:46:07+09:00 · fix(toss): VPS 키 병합 스크립트와 심사 스모크 쿠키 도메인 수정
- `deploy/scripts/build_toss_payment_path_ppt_manual.py` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `667dfe2` · 2026-10-09T16:05:02+09:00 · docs(toss): 심사용 결제창 캡처로 결제경로 PPT를 갱신한다
- `deploy/scripts/dump_built_stats_local.ps1` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `b329136` · 2026-06-03T20:43:09+09:00 · Add built-stats MVP, macro gateway, and VPS deploy tooling.
- `deploy/scripts/promote_restore.sh` — WIP 파일이 main 이력의 af5d93f과 일치. main에 그 뒤 수정이 있으므로 main이 최신.
  - main 최종 파일 변경: `2fc85a1` · 2026-11-11T03:07:13+09:00 · fix(promote): verify backend readiness and document recovery
  - WIP와 일치하는 main 과거 파일: `af5d93f8ee38db011297f5f4715c115fc647a32a`
- `docs/BUILT_MONTHLY_UPDATE_SOP.md` — main은 신규 해시 ENGINE_V2 공급 기본, WIP는 skip-enrich 기본과 D: 경로. 공급 정책은 main 후속본, 경로는 로컬 조정.
  - main 최종 파일 변경: `0a773c4` · 2026-11-10T17:22:45+09:00 · feat(monthly): 신규 대장 공급과 계약월 연결률을 기본 실행한다
- `docs/CH2_AI_CONSTITUTION.md` — main은 11-10 참조 기본값·이전 분석 출처·빈 화면 정책·추론 강도와 11-11 음수 추정금액 지침까지 반영. WIP는 11-09 v3 초안 중심이므로 운영 정책은 main이 최신.
  - main 최종 파일 변경: `c9275cd` · 2026-11-11T17:23:43+09:00 · fix(built): 점검 4단계 — 표시·안내 정리, Twin 판단 기준(T-5), D-073 갱신·D-083 확정
- `docs/CH2_LAB_HUB.md` — WIP에 회귀 표본 확장·분양권 연결·동일 지번 조사와 Insight 12/13 기록 등 추가 연구 이력이 있음. 문서 연구 목록은 WIP 추가분이며 제품 구현 최신 여부와는 별개.
  - main 최종 파일 변경: `9432fc1` · 2026-10-08T23:46:38+09:00 · 청주 대장 실험과 전국 특성 수신 상태를 문서와 로컬 로더로 남긴다.
- `docs/COLLECTIVE_COMMERCIAL_REGRESSION_UX_IMPROVEMENT_PLAN.md` — WIP에 11-01 회귀 UI 정리·추천 후보 선택 후 즉시 재분석 기록이 추가됨. 해당 문서 내용은 WIP 추가분. 본 작업에서는 실제 운영 적용 여부를 새로 검증하지 않음.
  - main 최종 파일 변경: `73b3cef` · 2026-10-29T23:29:07+09:00 · docs(regression): 유형별 개선 이력과 최종 UX 작업 범위 정리
- `docs/COLLECTIVE_MONTHLY_UPDATE_SOP.md` — main은 주거 신규 키 공시지가 공급 기본, WIP는 skip-enrich 기본과 D: 경로. 운영 공급 정책은 main 후속본.
  - main 최종 파일 변경: `0a773c4` · 2026-11-10T17:22:45+09:00 · feat(monthly): 신규 대장 공급과 계약월 연결률을 기본 실행한다
- `docs/COLLECTIVE_REGIONAL_REGRESSION_UX_IMPROVEMENT_PLAN.md` — WIP에 11-01 회귀 UI 정리·추천 후보 선택 후 즉시 재분석 기록이 추가됨. 해당 문서 내용은 WIP 추가분. 본 작업에서는 실제 운영 적용 여부를 새로 검증하지 않음.
  - main 최종 파일 변경: `73b3cef` · 2026-10-29T23:29:07+09:00 · docs(regression): 유형별 개선 이력과 최종 UX 작업 범위 정리
- `docs/COLLECTIVE_RESIDENTIAL_REGRESSION_UX_IMPROVEMENT_PLAN.md` — WIP에 11-01 회귀 UI 정리·추천 후보 선택 후 즉시 재분석 기록이 추가됨. 해당 문서 내용은 WIP 추가분. 본 작업에서는 실제 운영 적용 여부를 새로 검증하지 않음.
  - main 최종 파일 변경: `73b3cef` · 2026-10-29T23:29:07+09:00 · docs(regression): 유형별 개선 이력과 최종 UX 작업 범위 정리
- `docs/LAND_REGRESSION_UX_IMPROVEMENT_PLAN.md` — WIP에 11-01 회귀 UI 정리·추천 후보 선택 후 즉시 재분석 기록이 추가됨. 해당 문서 내용은 WIP 추가분. 본 작업에서는 실제 운영 적용 여부를 새로 검증하지 않음.
  - main 최종 파일 변경: `73b3cef` · 2026-10-29T23:29:07+09:00 · docs(regression): 유형별 개선 이력과 최종 UX 작업 범위 정리
- `docs/MONTHLY_UPDATE_SOP.md` — main은 신규 대장 공급·광주전남 V2 대응표·Promote 기준월 헬스·202612 점검 절차까지 있음. WIP는 D: 경로와 옛 skip-enrich 문구. 운영 절차는 main 후속본.
  - main 최종 파일 변경: `2fc85a1` · 2026-11-11T03:07:13+09:00 · fix(promote): verify backend readiness and document recovery
- `docs/QA_REGION_AUDIT_PLAN.md` — main에는 이력 마이그레이션 권한/읽기쓰기 구분 안내가 있고 WIP는 D: 경로를 보유. 운영 안내 main 후속, 경로는 로컬 조정.
  - main 최종 파일 변경: `2435e0d` · 2026-11-10T16:44:50+09:00 · fix(qa): 이력 스키마 준비를 소유자 마이그레이션으로 분리한다
- `docs/REGRESSION_IMPROVEMENT_STATUS.md` — main은 10-29 통합·운영 반영 이력을 보유. WIP는 미배포 상태 문구이므로 배포 상태 설명은 main이 최신.
  - main 최종 파일 변경: `73b3cef` · 2026-10-29T23:29:07+09:00 · docs(regression): 유형별 개선 이력과 최종 UX 작업 범위 정리
- `docs/REGRESSION_UNIFIED_IMPLEMENTATION_PLAN.md` — main에는 10-29 최종 UX 범위·통합 반영·검증 §14가 있음. WIP에는 이 후속 정리가 없어 main 문서가 최신.
  - main 최종 파일 변경: `73b3cef` · 2026-10-29T23:29:07+09:00 · docs(regression): 유형별 개선 이력과 최종 UX 작업 범위 정리
- `docs/lab/MACRO_TS_RAW_MONTH_MART.md` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `5d2077a` · 2026-09-22T15:13:45+09:00 · feat(insight): 연 거래액과 GDP·M2·주식을 비교하는 5번 글을 올린다
- `frontend-lab/src/api/aiUsageClient.ts` — WIP 파일이 main 이력의 820bb12과 일치. main에 그 뒤 수정이 있으므로 main이 최신.
  - main 최종 파일 변경: `15a6d49` · 2026-11-10T00:22:13+09:00 · fix(ai): 랩 관리자 API에 QA 토큰을 보내고 AI3 잔여 설정과 누락된 AI 문맥을 정리한다
  - WIP와 일치하는 main 과거 파일: `820bb12ea8610c0ea132cb872bb9ae303beaf7f5`
- `frontend-lab/src/components/AiUsagePanel.tsx` — WIP 파일이 main 이력의 820bb12과 일치. main에 그 뒤 수정이 있으므로 main이 최신.
  - main 최종 파일 변경: `46db76c` · 2026-11-10T02:24:40+09:00 · fix(ai): 빈 화면에서 이전 분석 재사용을 막고 참조를 값만 넣으며 칸 전체 통계로 계산한다
  - WIP와 일치하는 main 과거 파일: `820bb12ea8610c0ea132cb872bb9ae303beaf7f5`
- `frontend/src/api/aiContext.ts` — main만 buildLandScatterContext와 셀 전체 cell_total을 보유. WIP는 장기추세 trend_metric을 별도로 전달. main의 후속 AI 계산 근거와 WIP의 별도 지표 전달을 구분해야 함.
  - main 최종 파일 변경: `46db76c` · 2026-11-10T02:24:40+09:00 · fix(ai): 빈 화면에서 이전 분석 재사용을 막고 참조를 값만 넣으며 칸 전체 통계로 계산한다
- `frontend/src/components/FreeStatsPanel.tsx` — WIP의 좁은 화면 배치·표 설명 연결과 main의 후속 AI 문맥/셀 전체 통계 전달이 공존. 한쪽 전체 교체로 정리 불가.
  - main 최종 파일 변경: `46db76c` · 2026-11-10T02:24:40+09:00 · fix(ai): 빈 화면에서 이전 분석 재사용을 막고 참조를 값만 넣으며 칸 전체 통계로 계산한다
- `frontend/src/components/PaidAnalysisPanel.tsx` — WIP 파일이 main 이력의 820bb12과 일치. main에 그 뒤 수정이 있으므로 main이 최신.
  - main 최종 파일 변경: `46db76c` · 2026-11-10T02:24:40+09:00 · fix(ai): 빈 화면에서 이전 분석 재사용을 막고 참조를 값만 넣으며 칸 전체 통계로 계산한다
  - WIP와 일치하는 main 과거 파일: `820bb12ea8610c0ea132cb872bb9ae303beaf7f5`
- `frontend/src/components/PaidMatrixYearlyModal.tsx` — WIP만 연도추세 기본 해제·추천 후보 즉시 적용·접힌 산점도·응답 세대번호 방어·모바일 배치가 있음. main만 aiCellStats 전달 및 후속 산점도 문맥 연결이 있음. 회귀 UX는 WIP 추가분, AI 계산 근거는 main 후속분.
  - main 최종 파일 변경: `46db76c` · 2026-11-10T02:24:40+09:00 · fix(ai): 빈 화면에서 이전 분석 재사용을 막고 참조를 값만 넣으며 칸 전체 통계로 계산한다
- `frontend/src/constants/landStatsExplain.ts` — WIP의 단순 설명 생성과 main의 구조화된 도움말 구현이 다름. 통계 표본 로직은 동일 계열이나 도움말 구성은 분기 상태.
  - main 최종 파일 변경: `80272a3` · 2026-11-10T16:23:24+09:00 · fix(land): 토지 통계와 회귀 도움말을 복원한다
- `logs/rehearse_v2_update.txt` — WIP에만 추가 변경 (main은 기준 내용 유지); 기록된 main 최종 변경 커밋 참조.
  - main 최종 파일 변경: `e76e167` · 2026-05-20T01:45:50+09:00 · fix(pipeline): 시도 별칭·분구 토큰 fallback 으로 beopjungri 매핑 회복
- `scripts/monthly/dump_land_for_promote.py` — main은 cycle-id/output 인자를 받는 공통 덤프 도우미를 사용. WIP는 202608 출력 경로/PG18 실행파일을 고정하고 일부 GUC 줄을 제거하는 이전 방식. 재사용 가능한 운영판은 main 후속본.
  - main 최종 파일 변경: `874c74d` · 2026-11-10T16:23:24+09:00 · fix(ops): 토지 덤프 작업월과 출력 경로를 지정한다
- `scripts/monthly/run_land_cycle_csv.py` — WIP 파일이 main 이력의 af5d93f과 일치. main에 그 뒤 수정이 있으므로 main이 최신.
  - main 최종 파일 변경: `0a773c4` · 2026-11-10T17:22:45+09:00 · feat(monthly): 신규 대장 공급과 계약월 연결률을 기본 실행한다
  - WIP와 일치하는 main 과거 파일: `af5d93f8ee38db011297f5f4715c115fc647a32a`
- `shared/ai-assistant/AiAssistantPanel.tsx` — WIP는 더 많은 패널 이름 매핑을 보유. main은 응답 문맥 라벨 생성에 reply 플래그를 넣는 후속 처리 보유. 양쪽 독립 UI 변경.
  - main 최종 파일 변경: `15a6d49` · 2026-11-10T00:22:13+09:00 · fix(ai): 랩 관리자 API에 QA 토큰을 보내고 AI3 잔여 설정과 누락된 AI 문맥을 정리한다

### ③ main에 없음 (130개)

- `backend/app/collective/regional_regression/complex_gap_lab.py` — main에 없음 (새 파일)
- `backend/app/collective_commercial/factory_floor_lab.py` — main에 없음 (새 파일)
- `backend/app/land_lab/regression_augment.py` — main에 없음 (새 파일)
- `backend/app/land_lab/regression_augment_run.py` — main에 없음 (새 파일)
- `backend/tests/test_land_regression_augment.py` — main에 없음 (새 파일)
- `data/research/land_trait_slim/gauge_asof_2026-05-12.sqlite` — main에 없음 (새 파일) · 대용량 원본으로 로컬 복사만, 원격 미포함.
- `data/단독_전국 매매가격지수.pdf` — main에 없음 (새 파일)
- `data/아파트_전국 매매가격지수.pdf` — main에 없음 (새 파일)
- `data/연립다세대_전국 매매가격지수.pdf` — main에 없음 (새 파일)
- `data/오피스텔_전국 매매가격지수.pdf` — main에 없음 (새 파일)
- `deploy/hub/toss-review/screenshots/08_identity.png` — main에 없음 (새 파일)
- `deploy/scripts/_vps_built_chungbuk_audit.sh` — main에 없음 (새 파일)
- `deploy/scripts/_vps_built_daeso_detail.sh` — main에 없음 (새 파일)
- `deploy/scripts/_vps_compare_daeso_hashes.sh` — main에 없음 (새 파일)
- `deploy/scripts/_vps_oauth_smoke.sh` — main에 없음 (새 파일)
- `deploy/scripts/_vps_platform_setup_once.sh` — main에 없음 (새 파일)
- `deploy/scripts/_vps_sync_history_and_smoke.sh` — main에 없음 (새 파일)
- `deploy/scripts/_vps_verify_oauth_env.sh` — main에 없음 (새 파일)
- `docs/BUILT_RECOMMEND2.md` — main에 없음 (기준 브랜치에는 있음: main에서 삭제/미수용 여부 확인)
- `docs/CH2_AI3_IMPLEMENTATION_PLAN.md` — main에 없음 (새 파일)
- `docs/CH2_AI_ASSISTANT_DIALOGUE_PLAN.md` — main에 없음 (새 파일)
- `docs/CH2_AI_REVISION_PLAN_20261109.md` — main에 없음 (새 파일)
- `docs/built/replacement_cost_review_2025.csv` — main에 없음 (새 파일)
- `docs/built/간이신축원가표.csv` — main에 없음 (새 파일)
- `docs/built/간이신축원가표_집계.csv` — main에 없음 (새 파일)
- `docs/lab/COLLECTIVE_COMPLEX_GAP_LAB.md` — main에 없음 (새 파일)
- `docs/lab/LAND_REGRESSION_AUGMENT_LAB.md` — main에 없음 (새 파일)
- `docs/lab/PRESALE_APARTMENT_MATCH_PLAN.md` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_gyeonggi.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/받은결과/A_확인군_입력.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/받은결과/A_확인군_입력2.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/받은결과/B_답이있는행.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/받은결과/B_실험군_입력.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/받은결과/네이버건설사_8곳.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/받은결과/사람판정_8곳.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/받은결과/사람확인_목록.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/받은결과/여기에_세_파일을_넣으세요.txt` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/올리지말것/A_정답.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/올리지말것/B_연결키.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/올릴파일/A_확인군_입력.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/올릴파일/B_실험군_입력.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/올릴파일/참고_시공사명.csv` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/올릴파일/프롬프트_목록없음.txt` — main에 없음 (새 파일)
- `docs/lab/builder_gemini_trial_20261105/올릴파일/프롬프트_목록있음.txt` — main에 없음 (새 파일)
- `docs/lab/collective_complex_gap_pilot.json` — main에 없음 (새 파일)
- `docs/lab/collective_factory_floor_lab.json` — main에 없음 (새 파일)
- `docs/lab/journal/2026-10-24.md` — main에 없음 (새 파일)
- `docs/lab/journal/2026-10-29.md` — main에 없음 (새 파일)
- `docs/lab/journal/2026-10-30.md` — main에 없음 (새 파일)
- `docs/lab/land_regression_augment_assessed.json` — main에 없음 (새 파일)
- `docs/lab/land_regression_augment_round1.json` — main에 없음 (새 파일)
- `docs/lab/presale_apartment_gemini_sample.md` — main에 없음 (새 파일)
- `docs/lab/presale_apartment_gemini_sample_동남구.md` — main에 없음 (새 파일)
- `docs/lab/presale_apartment_gemini_sample_상당구.md` — main에 없음 (새 파일)
- `docs/reports/BUILT_ALLOCATION_REVIEW_20261103.md` — main에 없음 (새 파일)
- `docs/reports/CH2_AI3_HEADER_ENTRY.png` — main에 없음 (새 파일)
- `docs/reports/CH2_AI3_MODAL_DEMO.png` — main에 없음 (새 파일)
- `docs/reports/CH2_AI3_TRIAL_REPORT.md` — main에 없음 (새 파일)
- `docs/reports/CH2_AI3_TRIAL_UI.png` — main에 없음 (새 파일)
- `docs/reports/LOCAL_MIGRATION_LAND_SMOKE_20261010.json` — main에 없음 (새 파일)
- `docs/reports/LOCAL_MIGRATION_REVIEW_20261010.md` — main에 없음 (새 파일)
- `docs/reports/RENT_BASIC_STATS_REVIEW_20261102.md` — main에 없음 (새 파일)
- `docs/reports/RENT_CONVERSION_MODAL_REVIEW_20261102.md` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/@tanstack_react-query.js` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/@tanstack_react-query.js.map` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/_metadata.json` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/axios.js` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/axios.js.map` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/chunk-4MBMRILA.js` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/chunk-4MBMRILA.js.map` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/chunk-E55NSNTN.js` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/chunk-E55NSNTN.js.map` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/clsx.js` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/clsx.js.map` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/package.json` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/react-dom_client.js` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/react-dom_client.js.map` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/react.js` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/react.js.map` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/react_jsx-dev-runtime.js` — main에 없음 (새 파일)
- `frontend-lab/.vite/deps/react_jsx-dev-runtime.js.map` — main에 없음 (새 파일)
- `frontend-profile/.vite/deps_temp_af090201/package.json` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@tanstack_react-query.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@tanstack_react-query.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_bbox.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_bbox.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_boolean-disjoint.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_boolean-disjoint.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_boolean-intersects.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_boolean-intersects.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_boolean-touches.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_boolean-touches.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_helpers.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/@turf_helpers.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/_metadata.json` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/axios.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/axios.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-2UO76BCB.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-2UO76BCB.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-4MBMRILA.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-4MBMRILA.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-5U2ID3AT.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-5U2ID3AT.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-E55NSNTN.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-E55NSNTN.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-EGSHJPUB.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-EGSHJPUB.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-GH4D7NQT.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-GH4D7NQT.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-QPRHBWFJ.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/chunk-QPRHBWFJ.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/clsx.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/clsx.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/maplibre-gl.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/maplibre-gl.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/package.json` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react-dom.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react-dom.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react-dom_client.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react-dom_client.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react-map-gl_maplibre.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react-map-gl_maplibre.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react.js.map` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react_jsx-dev-runtime.js` — main에 없음 (새 파일)
- `frontend-rent/.vite/deps/react_jsx-dev-runtime.js.map` — main에 없음 (새 파일)
- `pipeline/_land_annual.sql` — main에 없음 (새 파일) · 대용량 원본으로 로컬 복사만, 원격 미포함.
- `scripts/local/check-land.py` — main에 없음 (새 파일)
- `scripts/local/start-land.ps1` — main에 없음 (새 파일)
- `참고/지도구현.hwpx` — main에 없음 (새 파일)
