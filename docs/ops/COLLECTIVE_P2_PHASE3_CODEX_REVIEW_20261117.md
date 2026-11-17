# 집합 P2 Phase 3 · main 병합 검수

검수 대상: `data/collective-p2`의 `762804e`(부모 `a00e06e`, `6633cf5`). 기준선은 병합 전 원격 main `6633cf5`. 2026-11-17 로컬 검수. 운영 접속·배포·push·운영 쓰기 없음. main 원본 폴더와 기존 P2 worktree도 수정하지 않았다.

## 반드시 수정 — 로컬 런북 수정 완료

1. **코드 선배포부터 낮 동결까지 배치·보강 금지 누락.** 기존 3.2는 낮 무거운 동기화 직전부터만 금지했다. 새 키 빌더가 그 사이 옛 DB를 바꾸면 코드만 복귀 가능한 전제가 깨진다. 3.2·4절 #1·신설 4-1에 선배포 직후부터 월간 배치·보강·그 결과 promote 금지를 명시했다. 5절의 승인된 P2 이전·보강만 런북 순서 안에서 허용한다.
2. **복귀 경계 누락.** 기존 762804e에는 별도 4-1과 `6633cf5` 코드 재배포 절차가 없다. 4-1에 코드 선배포, 구형 DB 확인, 운영 DB 반영 전 `6633cf5` 별도 worktree에서 `-Scope all -SkipPush` 재배포 조건을 추가했다. 일부 운영 DB라도 새 상태면 코드만 복귀 금지, 먼저 6.2·8절 DB 복원을 수행하도록 명시했다. 실제 복귀·배포는 하지 않았다.
3. **요약의 낮 순서 불일치.** 0절과 3.2의 「나누기」는 로컬 적용 후 동결로 적혀 있었지만 3.2 낮 상세 순서는 동결·동기화 후 적용이다. 두 요약을 상세 순서에 맞췄다. 밤 순서는 2 → 2a → 2b → 3을 유지했다.
4. **R5 시점 구분.** 4-1은 구형 DB 주요 API 확인만 수행한다. C-01 409·C-2 안내를 요구하는 R5는 세 DB promote 뒤 6.1 #12에서만 실행하도록 적었다.

수정 파일은 `docs/ops/COLLECTIVE_P2_RUNBOOK.md`. 이 문서 변경을 포함한 검수 브랜치를 실제 P2/main에 반영하기 전에는 원본 런북의 누락이 해소된 것이 아니다.

## 통과 — main 병합과 회귀

- `main.py`: P2 `KeyRemapMiddleware`와 D-085 `features.router` 등록이 함께 있다. 재매핑은 CORS 안쪽에 있어 409에도 CORS가 적용된다.
- `product_gate.py`: P2 집합 GET `key-status` 무료 허용과 D-085 기능 차단·QA 관리자 구독 통과·본문 `trait_enrich` 처리가 함께 있다. 임대 key-status는 기존 임대 구독 기준을 유지한다.
- `rent/router.py`: P2 `key-status`와 D-085 두 회귀 POST의 `require_feature(RENT_REGRESSION)` 의존성이 함께 있다. 기존 QueryDeadline도 유지된다.
- backend 전체 재실행: **1,381 passed · 12 failed · 1 skipped · 1 collection error**, 79.22초. main 기준선은 **1,360 passed · 12 failed · 1 skipped · 1 collection error**, 83.62초. JUnit에서 실패/오류의 `(classname, name, type)` 집합이 정확히 같다. 새 실패 0. D-085 테스트 54개와 P2 backend 테스트 20개 모두 통과한다.
- 기준선 실패: built 추천 deprecated 1, built 지역 all 3, Insight 번들 06/07/08/10/11/12 6, retired sido 1, yield compare 1. 수집 오류는 `test_profile_national_rank.py`. 전체 테스트가 녹색이라는 뜻은 아니다.

재실행 명령은 backend에서 `pytest tests --continue-on-collection-errors -q -rfE --junitxml=...`. 두 worktree에 동일한 로컬 환경을 프로세스 환경변수로 공급했다. 비밀을 worktree에 복사하거나 출력하지 않았다.

## 통과 — 결론 (가), 새 코드와 옛 DB

실제 로컬 `collective_stats`, `rent_stats`, `built_stats`에 `default_transaction_read_only=on`으로 연결했다. 접속 호스트는 localhost/루프백만 허용했다. 집합 key_map·c2_units, 임대 key_map의 `to_regclass`는 모두 NULL이다. 새 스키마를 만들지 않았다.

실제 FastAPI 앱과 재매핑 미들웨어를 통과시킨 **29회 요청 모두 HTTP 200**:

- 집합 주거: 메타·목록(실제 2행, display_name 존재·display_label NULL)·key-status·rolling·거래 목록.
- 집합 비주거: 메타·cluster 목록(실제 2행)·cluster rolling.
- 임대: 메타·목록(실제 254행)·key-status·rolling·거래 목록·sale-join.
- built: 메타·지역 목록·거래 목록(실제 2행)·기본통계 `/stats/scope`.
- `/api/features` 및 집합/임대 key-status 각각 반복 5회 포함.

구형 DB 호환 API 검증에서는 플랫폼 구독 조회만 `caller_access='macro'`로 대체했다. 기능 스위치 자체는 대체하지 않았으며 권한 차단은 별도 D-085 테스트로 검증했다. 임대·built 회귀의 실제 대규모 계산, 지도 좌표 쓰기, 운영 데이터 동일성은 이 스모크의 범위가 아니다. 모든 응답에서 `key_split_c2`는 없었다. sale-join은 200 응답 경로를 확인했으며 모든 키의 연결 성공률을 검증한 것은 아니다.

연결표 없음 처리: `_load_from_engine`이 `to_regclass` 한 번으로 빈 dict를 반환한다. 빈 결과도 앱별 TTL 600초 캐시에 남는다. 검증 요청 전체에서 집합/임대 존재 확인은 각각 1회, built는 0회였다. 캐시 cold 조회(이미 열린 로컬 DB 풀)는 집합 1.123ms·임대 0.739ms, warm 캐시 평균은 약 0.0003ms였다. key-status HTTP 반복은 약 3ms 수준이다. 표 부재는 SQL 예외를 만들지 않고, 조회 실패 시에도 통과하는 기존 테스트가 통과했다. 동시 cold 요청의 중복 로드나 DB 장애 시 최대 지연을 측정한 것은 아니다.

따라서 **코드 선배포 가능**이라는 결론 (가)는 위 구형 로컬 DB 표본에서 성립한다. 배포 후에도 배치·보강을 금지하는 조건이 붙는다. 서버 파일 상태와 운영 스모크는 실제 실행 단계에서 별도 확인해야 한다.

## 통과 — 프론트와 실행 주체

- 집합 프론트: `tsc` 오류 0, Vite production build 통과, 컴포넌트 **14/14**. `display_label` 누락 시 display_name, rolling 범례·AI 이름 fallback, `key_split_c2` 누락 시 children 유지가 포함된다.
- 임대 프론트: `tsc` 오류 0, Vite production build 통과, 컴포넌트 **7/7**. C-2 안내 부재·후보 전환·확인 오류 처리를 검증한다. 브라우저 수동 조작 대신 타입·빌드·정적 렌더 검증이다. 기존 SSR useLayoutEffect·번들 크기 경고는 남는다.
- `a00e06e`의 Cursor 실행 주체 변경은 요청한 **11개 위치**를 모두 확인했다: 문서 머리, 3.2 낮 실행, 3.2 설치 안내, 4절 #9, 5절 제목, 6절 built QA 기록, 6.0 제목, 6.0 설치 설명, viewer 경로 기록, 6.1 실행표, 6.2 manifest 수정 주체. 실제 diff는 실행표 여러 행을 포함해 20개 줄이다. 6.1 **2b도 Cursor**다. 남은 Codex는 검토·과거 실측 표기이고, Opus는 기존 보조/운영 확인 역할이다. 누락 없음.
- 2b는 요청 0 확인 시각부터 90초, 2a와 별도로 표시되며 #3에 `--confirmed-at`이 전달된다. 90초 미만 거절과 R5 로컬 주소 가드 등 추가 단위 검증 **71 passed · 1 deselected**. 제외 1개는 고정 임시 DB `ch2_statread_p2r`를 DROP/CREATE하는 실제 DB 테스트다. 최초 호출에서는 검수 worktree에 `.env`가 없어 실패했으며, 임시 DB 생성 검증은 이번에 실행하지 않았다.

## 권장

- **임대 목록·sale-join 지연 별도 추적.** 같은 표본의 main은 11.65초·13.49초, P2는 12.54초·13.04초였다. 초기 넓은 범위 조회는 검수용 15초 제한에도 걸렸다. 단일 측정으로 성능 회귀를 단정할 수 없고, 연결표 없는 재매핑 조회가 이 지연을 설명하지 않는다. 반복 측정·쿼리 계획은 별도 성능 작업으로 남긴다.
- 런북 제목 v6와 상태 v4, `CURSOR_P2_UNDERSTANDING.md`의 과거 실행 주체·시간식·2b 생략은 오래된 이해 기록이다. 향후 실행자는 현행 런북을 기준으로 삼고, 실제 배포 해시·시각·실측 S를 기록한다.

검증 원본은 검수 worktree의 무시된 `logs/collective_p2/phase3_codex/`에 보관한다: backend/main 기준선 로그·JUnit, 구형 DB JSON/스크립트, 프론트 빌드 로그, 가드 단위 테스트 로그. DB URL·키·원장 원본은 커밋하지 않는다.
