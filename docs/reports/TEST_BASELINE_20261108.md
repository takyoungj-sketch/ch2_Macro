# 백엔드 전체 테스트 기준선 조사 — 2026-11-08

## 결론

`db_utils.get_engine` 수집 오류는 복원 전 main `d563d97`에서도 동일하게 재현된다. 이번 복원으로 새로 생긴 import 오류가 아니다. 서로 다른 디렉터리의 `db_utils.py`를 같은 최상위 모듈명으로 import하면서 생기는 수집 순서 의존 문제다.

현재 main 전체 테스트는 **1,116개 통과, 15개 실패, 3개 건너뜀, 수집 오류 1개**다. 복원 전 main도 전체 실행해 비교했으며 **1,069개 통과, 14개 실패, 3개 건너뜀, 수집 오류 1개**였다. 두 버전에서 공통으로 실패하는 테스트는 13개, 현재 버전에서만 실패하는 테스트는 2개다.

조사만 수행했다. 제품 코드·테스트 코드를 수정하지 않았고 재배포·서비스 재시작도 하지 않았다. 요청받은 서버 배포 해시 파일 기록만 수행했다.

## 실행 위치와 조건

- 현재 main 워크트리: `D:\ch2\ch2_Macro\.release-worktree-20261108`.
- 브랜치: `main`.
- 조사 기준 HEAD: `6c62404e010d2408d868f8f7d48eb72922256815`.
- 이미 운영에 배포한 소스 기준: `6f8ed2b`.
- 이전 기준: `d563d97`.
- 이전 기준은 현재 main을 checkout하거나 덮어쓰지 않고 다음 별도 detached 워크트리에서 조사했다:
  `D:\ch2\ch2_Macro\.release-worktree-20261108\logs\test-baseline-20261108\baseline-d563d97`.
- 두 버전 모두 같은 인터프리터 `D:\ch2\ch2_Macro\backend\.venv\Scripts\python.exe`, Python 3.14.4, pytest 9.1.1을 사용했다.
- 각 워크트리의 `backend`를 `PYTHONPATH`로 지정했다. 현재 워크트리의 `backend/.env`는 없다.
- 전체 실행에는 Windows 임시 디렉터리 권한 문제를 피하도록 workspace 내 `--basetemp`를 지정하고, 비교 가능한 집계를 위해 `--junitxml`과 로그를 저장했다. 테스트나 애플리케이션 동작을 바꾸는 패치는 적용하지 않았다.
- Windows 샌드박스의 asyncio socketpair 정지 문제가 앞서 확인돼, 전체 실행은 승인된 셸 도구의 샌드박스 밖에서 수행했다.

## 1. 현재 main의 수집 오류

요청 명령의 PowerShell 동등 실행:

```powershell
python -m pytest backend/tests --collect-only -q 2>&1 | Select-Object -Last 30
```

결과: `1134 tests collected, 1 error`.

오류 파일:

```text
backend/tests/test_profile_national_rank.py
```

호출 경로:

```text
backend/tests/test_profile_national_rank.py:11
  -> pipeline/build_regional_profile_rank.py:28
  -> pipeline/build_stats_v2.py:39
  -> from db_utils import get_engine
```

실제로 선택된 모듈과 오류:

```text
pipeline/built/db_utils.py
ImportError: cannot import name 'get_engine' from 'db_utils'
```

`pipeline/db_utils.py:20`에는 `get_engine`이 있지만, `pipeline/built/db_utils.py`는 `get_built_engine` 등을 제공한다.

추가 재현:

- `python -m pytest backend/tests/test_profile_national_rank.py --collect-only -q`: **12개 정상 수집**.
- `python -m pytest backend/tests/test_mape_decomposition.py backend/tests/test_profile_national_rank.py --collect-only -q`: **동일 ImportError 재현**, 1개 수집·수집 오류 1개.
- `test_mape_decomposition.py`는 `pipeline/built`를 `sys.path` 앞에 넣고 `verify_mape_decomposition`을 import한다.
- `pipeline/built/verify_mape_decomposition.py`는 `from db_utils import get_built_engine`을 실행한다. 이후 전국 순위 테스트에서 경로를 바꾸더라도 이미 `sys.modules['db_utils']`에 들어간 모듈명이 재사용된다.
- 관련 import 경로 파일들은 `git diff d563d97 HEAD -- ...`에서 변경이 없음을 확인했다. 수집 순서에 따른 모듈 이름 충돌이라는 판단은 단독·두 파일·전체 수집 재현으로 뒷받침된다.

## 2. 저장소의 db_utils.py 전체 경로

`git ls-files | findstr db_utils` 결과:

```text
pipeline/built/db_utils.py
pipeline/collective/db_utils.py
pipeline/db_utils.py
pipeline/parcel_master/db_utils.py
pipeline/rent/db_utils.py
```

이 목록은 Git 추적 파일 기준이며, 조사용 이전 워크트리의 중복 복사본이나 가상환경 패키지는 포함하지 않는다.

## 3. 복원 전 main 재현 여부

`d563d97`에서 같은 조건으로 실행한 수집 결과:

```text
1086 tests collected, 1 error
ERROR backend/tests/test_profile_national_rank.py
ImportError: cannot import name 'get_engine' from 'db_utils'
실제 모듈: pipeline/built/db_utils.py
```

따라서 **이 수집 오류는 복원 이전부터 존재했다.** 이 판단을 전체 실패 항목 모두가 기존 문제라는 뜻으로 확대하지 않는다. 실패 항목별 전후 차이는 아래와 같다.

## 4. 전체 실행 결과

요청한 전체 실행 명령:

```powershell
python -m pytest backend/tests -q --continue-on-collection-errors -p no:cacheprovider
```

실제 실행에서는 결과 보존을 위해 다음 옵션도 추가했다:

```text
-B (python 옵션)
--basetemp=logs/test-baseline-20261108/tmp
--junitxml=logs/test-baseline-20261108/results.xml
```

현재 main 결과:

```text
15 failed, 1116 passed, 3 skipped, 19 warnings, 1 error in 55.30s
exit code: 1
```

복원 전 main `d563d97` 결과:

```text
14 failed, 1069 passed, 3 skipped, 26 warnings, 1 error in 48.10s
exit code: 1
```

현재 1,134개 수집 항목은 통과·실패·건너뜀의 합계다. 수집 오류 1개는 별도다. 오류가 난 전국 순위 파일의 12개 테스트는 이 전체 실행에서 실행되지 않았다. 두 버전의 수집 수가 48개 다르고 일부 테스트 내용도 변경됐으므로, 통과 수 증가만으로 기존 코드의 오류 해결 수를 산정하지 않는다.

### 현재 main 실패 테스트 15개

```text
backend/tests/test_apt_floor_utility_lab.py::test_basement_is_out_of_experiment_bins
backend/tests/test_built_archetypes.py::test_complete_case_is_shared_across_candidate_union
backend/tests/test_built_recommend_deprecated.py::test_suggest_compare_deprecation_headers
backend/tests/test_built_region_all_asset.py::test_gyeongbuk_addr2_with_all
backend/tests/test_built_region_all_asset.py::test_gyeongbuk_pohang_structure_with_all
backend/tests/test_built_region_all_asset.py::test_gyeongbuk_leaf_with_all
backend/tests/test_flat_sido_addr2_list.py::test_list_addr2_sejong_commercial_flat_token
backend/tests/test_insight_06.py::test_insight_06_bundle_not_01
backend/tests/test_insight_07.py::test_insight_07_bundle_not_01
backend/tests/test_insight_08.py::test_insight_08_bundle_not_01
backend/tests/test_insight_10.py::test_insight_10_bundle_not_08
backend/tests/test_insight_11.py::test_insight_11_bundle_not_01
backend/tests/test_insight_12.py::test_insight_12_bundle_not_11
backend/tests/test_stage2_region_search_pool.py::test_research_uses_only_rank1_passed_twin
backend/tests/test_yield_compare.py::test_apartment_december_matches_table
```

수집 오류:

```text
backend/tests/test_profile_national_rank.py
```

### 전후 비교와 관측 내용

현재에서만 실패한 두 항목:

- `test_basement_is_out_of_experiment_bins`: 이전 기대는 지하를 `floor_rel_mid`로 분류하는 것이지만, 복원 후 결과는 별도 지하 범주 `floor_rel_b`다. 기존 랩 테스트 기대와 복원된 분류 정책이 다르다.
- `test_research_uses_only_rank1_passed_twin`: 이전 기대는 통과한 Twin 1위만 포함하는 것이지만, 복원 후 결과는 통과한 선택 지역 `t1, t2, t3` 전체다. 기존 테스트의 ‘1위만’ 기대와 복원한 선택 지역 전체 정책이 다르다.

이 두 실패는 이번 복원과 함께 나타난 차이다. 테스트가 오래됐는지 정책 복원이 부적절한지 결론을 내려 테스트 또는 제품 코드를 수정하지 않았다.

두 버전 모두 실패한 13개는 위 15개 목록에서 이 두 항목을 제외한 전부다. 관측된 실패 양상:

- 복합 공통 표본 테스트: 기대 6건과 실제 7건의 차이.
- 복합 deprecated/지역 API 테스트: 로그인 없는 요청의 401 응답과 테스트 기대의 차이.
- 세종 비주거 지역 목록 테스트: `None` 연결 객체의 `.connect` 호출 실패.
- Insight 06·07·08·10·11·12: 안내문의 표시 번호와 테스트 기대 번호의 차이.
- 수익률 비교 테스트: 워크트리에 없는 `data/아파트_전국 매매가격지수.pdf` 파일 참조 실패.

복원 전에는 실패했지만 현재 통과하는 항목:

```text
backend/tests/test_collective_model_search.py::test_pool_is_not_the_checked_variables
```

이 테스트는 복원 과정에서 후보 풀 정책에 맞춘 기대 변경도 포함됐으므로, 단순히 제품 버그 하나를 해결한 것으로 집계하지 않는다.

## 5. 서버 배포 해시 기록

요청한 파일에 다음 내용을 기록하고 확인했다:

```text
파일: /opt/ch2_Macro/DEPLOYED_COMMIT
내용: 6f8ed2b
크기: 8 bytes (개행 포함)
```

서버 코드 전송, 빌드, 서비스 재시작, DB 변경은 하지 않았다.

## 원본 결과 보관 위치

Git 제외 폴더 `logs/test-baseline-20261108/`에 다음을 보관했다:

- `full-output.log`, `results.xml`: 현재 main 전체 실행.
- `baseline-collect-output.log`: 이전 main 수집 결과.
- `baseline-full-output.log`, `baseline-results.xml`: 이전 main 전체 실행.
- `import-order-repro.log`: 두 파일로 import 충돌 재현.
- `comparison.json`: JUnit에서 추출한 집계·실패 목록·전후 차이.
- `baseline-d563d97/`: 조사에 사용한 detached 이전 기준 워크트리.

이 보고서는 조사 결과만 기록한다. 전체 테스트는 아직 통과 상태가 아니며, 실패를 없애기 위한 코드·테스트 수정은 수행하지 않았다.
