# 출시 포함 항목 선별 반영 결과 — 2026-11-08

작업 위치는 `D:\ch2\ch2_Macro\.release-worktree-20261108`, 브랜치는 `main`이다. AI3 원본 커밋을 항목별로 확인하고 main에서 cherry-pick했다. push·배포·서버 재시작·DB 보강 실행은 하지 않았다.

## 기준선 보고서 커밋

- `e022e34`: `docs/reports/TEST_BASELINE_20261108.md`만 커밋했다. 제품 소스는 포함하지 않았다.
- 비교 기준은 통과 1,116개, 실패 15개, 수집 오류 1개, 건너뜀 3개다.

## a) 같은 법정동 분양권 카탈로그 — 반영

- AI3 원본: `4aabdbfe616c789ea60899b9c25e001cb32181e3`.
- 최종 main 커밋: `fcbd9afdf1ac05b8c0e84e5d386bde055b4f1466`.
- `git cherry-pick -x 4aabdbf`로 반영했다. `/buildings/{building_key}/presale-catalog`, 주소 정규화·동일 법정동 필터, DTO·클라이언트·분양권 선택 UI·관련 테스트를 함께 가져왔다.
- 이름 유사도로 다른 동의 분양권을 추천하지 않고, 같은 법정동에 해당하는 카탈로그를 표시한다. 분양권은 주거 집합의 데이터이므로 비주거에 대응 카탈로그를 새로 만들지 않았다.
- 최초 전체 실행은 1,117 통과·18 실패·1 수집 오류였다. 원본 커밋에 카탈로그와 무관한 `ModelComparison.metric_basis`, `CohortAugmentation.metric_basis`, `CollectiveModelCandidate.cv_mape` 삭제가 포함돼 있었음을 확인했다.
- 기존 main의 위 세 필드를 보존하고 다시 전체 실행한 뒤 같은 a) 커밋에 정리했다. 테스트 기대값이나 회귀 계산 정책은 이 항목에서 변경하지 않았다.
- 최종 전체 결과: **1,120 통과·15 실패·1 수집 오류·3 건너뜀**. 기준선 대비 추가 실패·오류 집합은 모두 비어 있다. 관련 테스트 4개가 추가됐다.
- 집합 TypeScript 검사 및 Vite 프로덕션 빌드 통과.

## b) 지역명 검색 API — 조건에 따라 제외

- AI3 원본: `2be82ad`.
- main의 `MobileCollectiveApp.tsx`는 공통 `MobileRegionSearch`를 사용한다.
- `shared/macro-shell/mobile/MobileRegionSearch.tsx`의 실제 검색 경로는 **`/api/free/v2/regions?search=...&limit=400`**이다.
- 사용자 조건에 따라 기존 경로를 그대로 유지하고 이 커밋은 cherry-pick하지 않았다. `/regions/name-search` API와 AI3 모바일 화면·훅도 가져오지 않았다.
- `backend/app/collective/region_name_search.py`는 최종 main에도 없다.
- 이 항목은 제품 변경이 없으므로 별도의 전체 테스트 실행을 추가하지 않았다. a), c), 최종 검사에서 main 모바일 파일의 기준선 이후 diff가 없음을 확인했다.

## c) 빈 시공사 KB 보강 및 출처 안내 — 코드 반영, DB 실행 안 함

- AI3 원본: `05fa48fdc707e64f417fefdec2eb05fa96032745`.
- main 커밋: `a7295c3`.
- `git cherry-pick --no-commit 05fa48f` 후 필요한 출시 파일만 선별 커밋했다.
- 포함: `danji_attributes.py`, `BuildingDetailModal.tsx`, `pipeline/apply_kb_complex_fill.py`, 스크립트가 참조하는 입력 CSV 3개, 사전 검토 문서.
- 제외: 원본의 랩 계획표·일지·과거 실행 결과 JSON·관련 연구 계획 문서. 서비스 시작 경로에서 이 스크립트를 자동 실행하도록 하는 변경은 없다.
- 전체 결과: **1,120 통과·15 실패·1 수집 오류·3 건너뜀**. 기준선 대비 추가 실패·오류 집합은 비어 있다.
- 집합 TypeScript 검사 및 Vite 프로덕션 빌드 통과.
- **DB 보강 스크립트는 실행하지 않았다.** 이 스크립트는 `202607` 아파트 속성의 빈 시공사뿐 아니라 빈 주차도 갱신하고 commit한다. dry-run이나 자동 백업은 없다.
- 변경 범위와 실행 전 테이블 백업·변경 전 행 보존·복구 방법은 [KB 사전 검토](KB_COMPLEX_FILL_PREFLIGHT_20261108.md)에 보고했다. 실제 DB 대상 건수 산출이나 DB 백업도 이번에 실행하지 않았다.

## 공통 표본 6건·7건 조사 — 수정 없음

추가로 남는 행은 **0 기반 인덱스 5, 여섯 번째 행**이다. 연식 결측인 2번 행은 양쪽에서 제외된다. 5번 행은 `zone_type`만 결측이고 숫자 변수는 정상이라 현재의 ‘숫자 결측 제외·범주 결측 유지’ 정책에서는 남는다.

```text
기대: [0, 1, 3, 4,    6, 7]  (6건)
실제: [0, 1, 3, 4, 5, 6, 7]  (7건)
```

해당 함수와 테스트는 고치지 않았다. [행 단위 조사 보고서](COMPLETE_CASE_ROW_REVIEW_20261108.md)에 fixture 값과 제외 사유를 기록했다.

## 지하층 테스트 기대값 — 별도 커밋

- main 커밋: `364e8b4`.
- `test_basement_is_out_of_experiment_bins`에서 `relative_floor_group(-1, 15)`의 기대값 한 줄만 `floor_rel_mid` → `floor_rel_b`로 바꿨다.
- 실험 구간의 지하층 제외 기대나 제품 코드는 변경하지 않았다.
- 이후 최종 전체 결과: **1,121 통과·14 실패·1 수집 오류·3 건너뜀**.
- 기준선 대비 추가 실패·오류는 없으며, 기존 실패 목록에서 지하층 테스트 하나만 빠졌다. 전체 테스트가 모두 통과한 상태는 아니다.

## 검증 방법과 보관 위치

각 실제 반영 단계마다 main 워크트리에서 다음 명령을 실행했다:

```text
python -m pytest backend/tests -q --continue-on-collection-errors -p no:cacheprovider
```

동일한 Python 3.14.4·pytest 9.1.1과 각 단계의 workspace 내 `--basetemp`, `--junitxml`을 사용했다. Python의 `-B` 옵션과 `PYTHONPATH=<main-worktree>/backend`도 지정했다. 기존 수집 오류를 숨기지 않고 끝까지 실행해 집계했다. 세 단계 모두 남은 기존 실패·수집 오류 때문에 pytest 종료 코드는 1이다.

Git 제외 `logs/release-inclusions-20261108/`에 a) 최초·정리 후, c), 최종 전체 실행의 로그와 JUnit XML을 저장했다. 실패 개수만이 아니라 테스트 ID 집합도 최초 기준선과 비교했다. 배포나 유료 AI 호출, 운영 DB 변경은 수행하지 않았다.

기존 수집 오류와 잔여 실패의 원인·목록은 [기준선 보고서](TEST_BASELINE_20261108.md)에 있다. 기존 import 오류, Twin 1위만 기대하는 테스트, 인증·데이터 파일 관련 실패는 이번 요청에서 수정하지 않았다.
