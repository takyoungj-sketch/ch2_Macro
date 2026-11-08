# 공통 표본 6건·7건 차이 조사 — 2026-11-08

대상: `backend/tests/test_built_archetypes.py::test_complete_case_is_shared_across_candidate_union`.

## 차이가 나는 행

추가로 남는 행은 **0부터 시작하는 인덱스 5, 즉 여섯 번째 행**이다.

```text
테스트 기대 인덱스: [0, 1, 3, 4,    6, 7]  → 6건
실제 표본 인덱스:   [0, 1, 3, 4, 5, 6, 7]  → 7건
추가 행:            [5]
```

fixture의 5번 행:

```text
price:             3420
gross_area:        60
land_area:         35
building_age:      10
road_width_label:  12m
zone_type:         결측 (테스트에서 None 대입)
building_use:      근린
asset_type:        commercial
```

테스트는 `_make_df(8)`을 만든 다음 `df.loc[2, 'building_age'] = None`, `df.loc[5, 'zone_type'] = None`을 실행한다.

## 왜 남는가

`with_complete_case`의 현재 정책은 숫자 변수 결측을 후보 풀 전체 기준으로 제외하고 범주형 결측은 유지하는 것이다. 함수 설명에도 ‘범주 빈칸은 빼지 않고, 적합 때 미상으로 남긴다’고 명시돼 있다.

- 인덱스 2의 `building_age`는 숫자 결측이므로 제외된다.
- 인덱스 5의 `zone_type`은 범주형 결측이다. `_BLOCK_SOURCE_COLUMNS`에는 있어 `sample_columns`에 포함되지만, `_NUMERIC_SOURCE_COLUMNS`에는 없으므로 숫자 결측 제외 대상이 아니다.
- 실행 결과의 `numeric_drop_notes`는 `연식 결측 1건` 하나였다.
- 테스트 기대는 숫자 결측 행과 범주 결측 행을 모두 제외하는 예전 complete-case 기대다.

따라서 6건과 7건의 차이는 거래 추가 조회·중복 집계가 아니라, **동일한 8행 fixture에서 범주 결측 행을 유지하는지 여부**다. 운영 거래 원자료를 읽지 않고 테스트 fixture를 그대로 호출해 확인했다.

## 변경하지 않은 사항

이 요청에서는 원인 보고만 수행했다. `backend/app/built/regression/selection/context.py`와 `backend/tests/test_built_archetypes.py`는 기준선 보고서 커밋 `e022e34` 이후 변경이 없음을 확인했다. 기대값을 7로 바꾸거나 범주 결측 행을 다시 제거하는 수정은 하지 않았다. 이 테스트는 기존 실패 목록에 그대로 남는다.

재현 결과는 Git 제외 `logs/release-inclusions-20261108/complete-case-probe.json`에 저장했다. 이 파일의 자료는 합성 fixture이며 운영 데이터가 아니다.
