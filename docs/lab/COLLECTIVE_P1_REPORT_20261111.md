# 집합 1단계 수정 보고 (2026-11-11)

- 근거 지시: 「집합 1단계 수정 지시」(승인 T, 2026-11-11) · 0단계 보고: [`COLLECTIVE_PHASE0_REPORT_20261111.md`](COLLECTIVE_PHASE0_REPORT_20261111.md) (이 브랜치에 cherry-pick, `205cfd0`)
- 브랜치 `fix/collective-p1` (기준 `origin/main` 08aea31). merge·배포는 하지 않았다(Codex 몫).
- DB: **로컬 읽기만.** 측정 스크립트는 모두 `default_transaction_read_only=on`으로 접속했다. 원장·mart·지역코드표·새 테이블·마이그레이션 변경 없음.
- 개별 지번이 들어갈 수 있는 비교 산출물은 `logs/collective_p1/`(gitignore)에만 있다.

| Phase | 커밋 | 내용 |
|---|---|---|
| 0단계 문서 | `205cfd0` | 0단계 보고서·스크립트 cherry-pick(b84f691) |
| 1 | `ded1f53` | C-01 B안 — 지역 확장 코드 공식 읍면동명 거르기 |
| 2 | `875397f` | C-03 — 회귀 식별 불가 변수 자동 제외 |
| 3 | `fa5af18` | C-05 날짜 필터 누락·N-3·미지원 파라미터 경고 모드 |
| 4 | (이 커밋) | D-084 결정 기록 + 이 보고서 |

## 테스트

백엔드 전체 `pytest --continue-on-collection-errors`, Phase마다 그 Phase까지의 코드만 있는 상태에서 실행:

| 시점 | 통과 | 실패 | collection error |
|---|---|---|---|
| Phase 1 | 1,259 | 12 | 1 |
| Phase 2 | 1,268 | 12 | 1 |
| Phase 3 | 1,279 | 12 | 1 |

실패 12건·오류 1건은 모두 main 기준 기존 목록과 같다(test_insight_06~12 6건, test_built_region_all_asset 3건 — 「로그인이 필요합니다」, test_region_sido::test_retired_sido_addr2_returns_empty, test_yield_compare, test_built_recommend_deprecated 1건, test_profile_national_rank import 오류). **새 실패 0.** 지시 4번 「실패 0」과는 이 기존 실패 때문에 문자 그대로는 맞지 않는다. 이번 범위 밖이라 손대지 않았다.

프론트: `tsc --noEmit` 5앱(토지·복합·집합·임대·지역프로필) 통과.

---

## Phase 1 — C-01 B안: 지역 코드 확장 거르기

### 바꾼 것
- [`backend/app/region_scope.py`](../../backend/app/region_scope.py) `expand_beopjungri_codes()`가 반환 직전에 `filter_codes_by_official_emd_name()`로 거른다.
  - 기준: 코드 앞 8자리의 `region_codes` 읍면동명(활성·비활성 모두 = 옛 이름 포함), 읍↔면 변형은 `_leaf_name_variants` 재사용.
  - 공식명이 비었거나 `region_codes`에 없는 코드는 남긴다(거를 근거 없음 → 현행 유지).
  - 앞 8자리를 현행 코드와 비교하지 않는다(A안 금지).
  - 선택 읍면동명: addr4 목록(일반구 시의 동) → 없으면 addr3(시군구 직속 읍면동·세종). **리(addr5) 선택, 일반구 전체(addr3=구), 시군구 전체는 거르지 않는다.** 일반구 판정은 `region_codes.sigungu_name = '시 구'` 존재, 없으면 「시 + 구로 끝남」.
- 확장 쿼리가 `as_of_month`를 보지 않는 문제는 바꾸지 않았다(아래 영향만 측정).

### 발견해서 같이 처리한 것 — 세종 읍·면
첫 전국 비교에서 `collective_transactions` 세종 10개 읍면(조치원읍 2,017건 등)이 전부 빠졌다. 원인: 로컬 `region_codes`의 세종 읍·면 지역은 **열이 한 칸 밀려** `sigungu_name`=읍면명, `eupmyeondong_name`=리명이다. 0단계 시뮬레이션은 세종 addr2가 NULL이라 pandas groupby가 그 단위를 조용히 버려서 이 문제를 보지 못했다. `sigungu_name` 끝 토큰이 읍·면·동·가로 끝나면 공식명으로도 보도록 했고, 다시 돌린 전국 비교에서 원장 변화 0이 됐다. 고정 테스트에 세종 조치원읍을 추가했다.

### 전후 비교 (전국 모든 읍면동, main 사본 vs 수정 후)
스크립트 [`scripts/lab/collective_p1/compare_region_scope.py`](../../scripts/lab/collective_p1/compare_region_scope.py) — 수정 전 함수는 main 사본 [`_region_scope_main.py`](../../scripts/lab/collective_p1/_region_scope_main.py). 같은 입력으로 두 함수를 호출하고 반환 코드로 단지·거래를 센다(집계 방식은 0단계 c01과 같음, 단지 수는 코드 그룹 합).

| 대상 | 선택 단위 | 변화 단위 | 단지 증감 | 거래 증감 | 새로 추가된 코드 |
|---|---|---|---|---|---|
| collective_building_stats (최신 as_of, 5년) | 3,902 | **116** | **−40,235** | **−389,186** | 0 |
| collective_transactions (5년 창) | 3,881 | 0 | 0 | 0 | 0 |
| collective_commercial_transactions | 3,204 | 0 | 0 | 0 | 0 |
| built_transactions | 5,526 | 0 | 0 | 0 | 0 |

0단계 기대값(116 / −40,235 / −389,186, 원장 0)과 **정확히 일치**한다.

대표 지역 (mart 단지 목록, 단지 / 거래):

| 지역 | 전 | 후 |
|---|---|---|
| 부천 원미구 춘의동 | 1,612 / 19,373 | **166 / 804** |
| 청주 청원구 우암동 | 50 / 1,671 | 27 / 497 (내수읍 코드 0) |
| 화성 효행구 봉담읍 | 243 / 6,389 | 199 / 6,213 (원장 6,219건 변화 0) |
| 청주 흥덕구 가경동 · 광산구 수완동 · 음성 대소읍 · 청주 내수읍 | 변화 없음 | 변화 없음 |

**토지:** `grep` 결과 토지 라우터(`free`·`free_v2`·`paid`·`upper_stats`)와 `ledger_region_sql.py`는 `region_scope`의 확장·적용 함수를 쓰지 않는다(쓰는 곳: 집합 filters·복합 transaction_scope·복합 회귀; 지역회귀·Twin은 `parse_region_addr_keys`만). 대표 지역 토지 API `GET /api/free/v2/stats/{code}?window_years=5`를 수정 전(로컬 8000, 08aea31)과 수정 후(같은 코드의 TestClient)로 비교: 4311425036·4311411100 둘 다 **응답 JSON 동일**.

**pytest 고정 사례** [`test_collective_p1_region_scope.py`](../../backend/tests/test_collective_p1_region_scope.py) (기준월 2026-10-01 스냅샷 고정, DB 없으면 skip): 우암동 내수읍 단지 0 · 춘의동 166곳/804건 · 봉담읍 원장 변화 0 · 세종 보람동·조치원읍 변화 0 · 음성 대소읍(읍·리 선택 둘 다) 변화 0 + 단위 테스트 5.

**as_of 무관 확장의 영향(변경 없음, 측정만):** mart 7개 기준월(2025-12~2026-10) 중 최신에 없는 (단위, 코드) 쌍 481개, 그런 단위 339개(3,909개 중). B 이후 남는 것은 같은 이름 코드뿐이라 영향은 「과거 스냅샷에만 있던 같은 읍면동 코드」로 한정된다(`asof_scope_impact.py`).

### 한계
- **반대 방향 혼입은 남는다.** 내수읍 선택 시 덕일한마음·삼일 같은 합성 주소 행은 코드가 정상 내수 코드라 B가 남긴다(응답 변경 없음). 2단계 키 이전(대표 행 한 건 주소)에서 해결.
- B는 mart에서 그 리의 **진짜 다른 읍면동 단지**뿐 아니라 「합성 주소 단지」(예: 우암동 이름 + 내수 코드) 2곳도 우암동 목록에서 뺀다. 이 단지들은 2단계에서 주소가 고쳐지면 제자리로 돌아온다.

---

## Phase 2 — C-03: 회귀 식별 불가 변수 자동 제외

### 바꾼 것
- 공통 함수 [`backend/app/regression_identifiability.py`](../../backend/app/regression_identifiability.py): 복합의 p×p SVD `_scaled_design_svd`·`design_rank`·`nonidentifiable_columns`를 옮기고 `lstsq_r_squared` 추가. 복합 엔진은 같은 이름으로 다시 내보낸다 → 복합 테스트(`test_built_p1_audit_fixes`, `test_built_p5_codex_fixes` 포함 monkeypatch 경로) 그대로 통과.
- 집합 엔진 [`collective/regression/engine.py`](../../backend/app/collective/regression/engine.py) `auto_exclude_nonidentifiable()`: `_fit_regression` 안에서 적합 직전에 실행 → 단일 단지·코호트 회귀·예측(`predict_regression`) 모두 같은 경로. 식별 불가 열 중 우선순위(연식 → 동 미상 → 동 수준 → 층 수준 → 반기 → 면적)가 가장 높은 그룹의 열 **하나**를 빼고 rank를 다시 본다. 우선순위 밖 열(단지 FE·속성)만 남으면 멈추고 기존 「모형 식별」 경고를 유지한다.
- 응답: `excluded_variables[{variable, label, reason_code, message, column}]`, `identifiability{rank_before, rank_after, cols_before, cols_after, r_squared_before, r_squared_after}`. R² 차이가 1e-6을 넘으면 경고 문구를 붙인다. 사유 문구는 0단계 §C-03 초안.
- 예측: 제외된 연식·면적에 입력값이 있으면 「반영하지 않았습니다 — 사유」, 제외된 동·반기 수준을 고르면 「기준 범주로 계산」 경고.
- 화면(집합 주거): 결과 요약 첫 줄에 「제외한 변수: 연식 — 사유」. 조건별 추정의 연식·면적 입력칸 비활성 + 사유 툴팁, 제외된 동·반기 옵션에 「(제외: 기준과 같게 계산)」. 「모형 식별: 설계 열 25개…」 경고는 제외 후에도 남을 때만 뜬다(적합 설계로 판정하므로 자동).
- **임대는 적용하지 않았다.** 임대 라우터가 집합 엔진(`run_building_regression`·`run_cohort_regression`)을 쓰는데, 범위 밖이라 `auto_exclusion_disabled()`로 현행을 유지했다.
- 층 효용지수(`floor_index_regression.py`)·비주거 cluster 회귀는 바꾸지 않았다.

### 검증
- 단위 테스트 [`test_collective_p1_identifiability.py`](../../backend/tests/test_collective_p1_identifiability.py): 연식↔시점(연식 제외·반기 3개 유지) · 면적 단일(`area_single`) · 동 미상↔최근 반기(동 미상 제외, 2026H2 유지) · 식별 가능(계수·R² 변화 없음) · 층 효용지수와 같은 단지에서 둘 다 연식 제외 · 예측이 연식 입력을 무시 · 임대 경로 현행 유지.
- **0단계 표본 51곳** (제품 기본 변수 면적·연식·층(상대)·동·반기, 선형, 5년 창; `c03_product_check.py`):

| 지표 | 결과 |
|---|---|
| 제품 설계에서도 식별 불가 | 51 / 51 |
| 제외 후 식별 가능 | **51 / 51** |
| R² 변화(>1e-6) | **0곳** (중앙값 0.7959 → 0.7959) |
| CV-MAPE 변화(>0.05%p) | **0곳** (중앙값 4.71% → 4.71%) |
| 「모형 식별」 경고 | 51 → 0 |
| 제외 변수 | 연식 22 · 연식+면적 14 · 연식+동 미상+면적 6 · 연식+동 수준 4 · 연식+동 미상 3 · 연식+동 미상+층 1 · 동 미상+면적 1 |

  제품 설계(층 상대 구간·면적 원값)는 0단계 최소 설계보다 열이 많아 연식이 함께 빠지는 곳이 늘었다(0단계 「면적 단일」 21곳 대부분이 제품에서는 연식+면적).
- **가경자이**(청주 흥덕구, 5년 228건, 선형): 제외 전 연식 +1,693만원/년·p 없음, 「설계 열 25개, 독립 계수 24개」 → 제외 후 연식 제외(사유 「한 단지 안에서는 연식이…」), 반기 계수 전부 유지, R² 0.88165 동일, CV-MAPE 2.8% 동일, 식별 경고 없음. 로그 모형도 같다. 테스트로 고정.
- 주거 코호트 10개(같은 읍면동 아파트 2~5곳): 제품 코호트는 기본으로 **단지 고정효과**를 쓴다 → 7개에서 연식 자동 제외(준공연도 2~5개여도 FE와 시점에 흡수), 3개는 식별 가능. 10/10 제외 후 식별 가능. 지시의 「단지 고정효과가 있는 코호트는 단일 단지 규칙」과 같다.
- 기존 테스트 변경 1건: `test_collinear_age_refuses_only_the_unseen_combination`은 옛 동작(연식 계수 빈칸 + 학습 밖 조합 예측 거절)을 고정하던 테스트라 새 계약(연식 자동 제외·예측은 연식 무시·경고)으로 바꿨다(`test_collinear_age_is_auto_excluded_and_ignored_in_predict`). 삭제·skip 없음.

### 비주거 cluster 회귀 — 측정만(10곳, 적용 안 함)
기본 변수, 5년 창. 적합 9곳 중 **7곳이 식별 불가**(모형 식별 경고), 2곳 식별 가능, 1곳은 반기 표본 부족으로 적합 안 됨. 식별 불가 열은 연식(5곳), 반기, 건축물용도·용도지역·도로폭·상가 층 더미가 섞여 있다. n이 11~53으로 작은 cluster에서 범주 더미가 많아 생기는 경우가 대부분이다. 주거보다 빈도가 높으므로 3단계에서 우선순위(범주 더미 그룹 포함)를 따로 정해 적용할 것을 권한다.

---

## Phase 3 — C-05 날짜 필터 누락 + N-3 + 경고·집계 모드

### 3-1 필터 누락
- 비주거 `GET /clusters/{key}/addresses`·`/histogram`·`/stats/by-year`가 `contract_date_from/to`를 받아 `_tx_where`에 넘긴다(주거 짝과 같은 방식). by-year는 날짜가 있으면 mart 대신 live 집계(주거와 같음).
- **대농로(청주 흥덕구 복대동) 5년 창:** 번지별 합계 371 → **223**, 히스토그램 n **223**, 연도별 합 223. 테스트 [`test_collective_p1_param_fixes.py`](../../backend/tests/test_collective_p1_param_fixes.py).
- `/analysis/cohort/regression/predict`(비주거)의 `asset_type`: **필요 없음.** 로컬 원장에서 cluster당 유형은 1개뿐(여러 유형 cluster 0 / 25,624)이고, 예측·실행 라우트는 거래 행의 최빈 유형으로 상가/공장을 정한다. 화면(`predictCommercialCohortRegression`)이 보내지 않게 했다.

### 3-2 N-3
`/api/collective/analysis/cohort/regression/run`이 `CohortRegressionRunRequest`(= 코호트 요청 + `categorical_missing`)를 받아 단일 단지 회귀와 같이 적용한다. 가경동 아파트 2곳 코호트에서 `drop`의 n < `keep_unknown`의 n, `n_excluded_missing > 0` 테스트. 예측 요청은 원래 받았으므로 이제 실행·예측 모형 서명이 맞는다.

### 3-3 미지원 파라미터 경고·집계 모드
- 미들웨어 [`backend/app/api_param_warn.py`](../../backend/app/api_param_warn.py) (순수 ASGI, `main.py`에 등록). 라우팅 뒤 `scope["route"]`로 라우트를 찾아 **query 키**(하위 의존성 포함)와 **JSON body 키**(Pydantic 모델이 버리는 키, 중첩 모델은 `variables.foo` 점 경로)를 비교한다. body까지 구현했다. 핸들러가 `Request`를 직접 받는 라우트는 query를 수동으로 읽을 수 있어 query 판정을 건너뛴다(오탐 방지). axios 배열 표기 `x[]`도 같은 이름으로 본다.
- **요청은 그대로 통과**(테스트: 미지원 파라미터 1개 → 200, 집계 +1). 거절 모드 없음.
- 집계 키: (경로 템플릿, method, 화면 식별자, 위치 query/body, 파라미터 이름) → 빈도. 프로세스 메모리 → 기본 1시간마다·종료 시 JSONL 한 줄씩 추가. 앱 로그에는 날이 바뀔 때 하루 요약 1줄.
- **기록하지 않는 것:** 값, 쿼리 문자열, 사용자 ID, IP, 토큰, **Referer 원문**(경로 앞부분으로 앱만 분류: referer:land·built·collective/residential·collective/commercial·rent·profile, 그 밖 referer:other), **허용 목록 밖 화면 헤더 값**(other로 기록; 목록은 `api_param_warn.ALLOWED_SCREENS`, 프론트 값과 대조 테스트 있음). 경로 변수는 템플릿(`{cluster_key}`). 테스트가 값·경로 변수 값이 파일에 없는지 확인한다.
- **키 폭증 방지(검수 보완):** 파라미터 이름은 영문·숫자·`_-.[]`만 남기고 64자로 자른다(남는 문자가 없으면 버림). 한 집계 창(그리고 하루 요약)에서 고유 키가 1,000개에 닿으면 이후 새 키는 route별 `_overflow` 한 키로 합친다(창당 최대 1,000키 + route별 `_overflow`).
- 설정: `API_PARAM_WARN_ENABLED`(기본 true), `API_PARAM_WARN_PATH`(기본 `logs/api_param_warn.jsonl`, 상대 경로는 저장소 루트), `API_PARAM_WARN_FLUSH_SECONDS`(기본 3600). 테스트는 conftest가 임시 경로로 돌린다.
- 화면 식별자: [`shared/macro-shell/apiScreen.ts`](../../shared/macro-shell/apiScreen.ts) `attachApiScreenHeader()`를 5앱의 axios 인스턴스 12개에 붙였다. 값 `앱/화면`(land/main·land/map·built/main·built/twin·collective/residential·collective/commercial·rent/main·profile/main 등). 집합 상세 모달은 열려 있는 동안 `collective/residential-detail/{패널}`·`collective/commercial-detail/{패널}`. 헤더가 없으면 Referer의 경로만(`referer:/collective/`).
- CORS: `allow_headers=["*"]`. 운영 nginx(`deploy/templates/nginx-ch2-macro.conf`)는 `/api/` 프록시에서 요청 헤더를 기본 전달하며(`proxy_pass_request_headers` 미변경), 헤더 이름에 밑줄이 없어 `underscores_in_headers`와 무관하다 → 막히지 않는다.
- 조회 도구 [`scripts/ops/api_param_warn_summary.py`](../../scripts/ops/api_param_warn_summary.py): JSONL을 읽어 API·화면·파라미터별 빈도표(`--since`, `--by`, `--top`).
- **정적 대조 회귀 방지:** 0단계 `c05_param_audit.py`·`c05_frontend_params.cjs`를 `scripts/lab/collective_p1/`로 가져와 실행 → **137호출 중 무시 파라미터 0건**(수정 전 5건: 필터 누락 4 + 옵션 무시 1). 라우트 미일치 2건(경로 변수 조립 `/api/${path}`)은 0단계와 같다. CI에는 넣지 않았다.

**운영 JSONL 위치·회전(제안, 결정은 Codex 배포 때):** 기본값이면 `/opt/ch2_Macro/logs/api_param_warn.jsonl`(백엔드 실행 사용자 쓰기 권한 필요). 1시간마다 (API·파라미터) 조합당 한 줄이라 하루 수십~수백 줄 수준으로 예상된다. `logrotate`로 주 1회 회전·8주 보관(`copytruncate` 불필요 — 매 기록마다 append로 열고 닫는다)을 권한다. 워커가 여러 개면 프로세스마다 따로 집계해 같은 파일에 append하므로 요약 도구는 합산한다.

---

## Phase 4 — 결정 기록
- `docs/DECISIONS.md`에 **D-084** 표 행과 본문을 추가했다(지시 문구 그대로 7항목 + 1단계 반영 사항: C-01 B안은 조회 측 거르기, 임대는 C-03 미적용).
- 기존 결정과 충돌 없음 확인: D-083(쌍둥이 지역 더미)과 같은 방향, 직거래·일괄거래·C-05 관련 기존 결정 없음.

---

## 발견 사항 (범위 밖, 손대지 않음)
1. **`region_codes` 세종 읍·면 열 밀림**: `sigungu_name`=읍면명, `eupmyeondong_name`=리명, `beopjungri_name`=리명. 세종 동 지역은 이름 공란. `apply_admin_code_scope(level=beopjungri)`의 이름 보조 매칭(`sigungu_name = addr2`, `beopjungri_name = addr5`)도 세종에서는 맞지 않을 수 있다. 지역코드표 보강은 별도 결정.
2. 0단계 c01 시뮬레이션은 addr2 NULL(세종) 단위를 pandas groupby가 버려 세종을 측정하지 않았다. 1단계 비교 스크립트는 세종을 포함한다.
3. 주거 코호트 회귀 실행(`cohort_regression`)은 `contract_date_from/to`를 데이터 조회에는 쓰지만 `CollectiveRegressionRequest`에는 넘기지 않는다(설명·분석 문맥의 기간 표시용). 결과 수치에는 영향 없음으로 보이나 확인 필요.
4. 비주거 코호트 실행 요청(`CommercialCohortAnalysisRequest`)의 `asset_type`도 실행 라우트에서 쓰이지 않는다(예측과 같은 이유로 무해). 스키마 필드라 경고 모드에는 잡히지 않는다.
5. 비주거 cluster 회귀 식별 불가 빈도가 높다(10곳 중 7곳, 위 Phase 2).
6. 집합 주거 코호트는 기본이 단지 FE라 연식이 대부분 빠진다. 「준공연도가 다르면 연식 유지」를 원하면 FE 없는 코호트 옵션이 필요하다(현 제품 동작은 지시의 FE 규칙과 일치).

## 2단계 인계
- **단지 키 이전(C-01·C-02):** mart 주소를 「대표 거래 한 건의 주소·코드 세트」로 바꾸면 Phase 1 거르기에서 빠진 합성 주소 단지가 제자리로 돌아오고, 반대 방향 혼입(내수읍 선택 시 덕일한마음)이 사라진다. 그 뒤 `filter_codes_by_official_emd_name`은 안전망으로 남겨도 된다.
- 전후 검증은 `compare_region_scope.py`를 그대로 다시 돌리면 된다(main 사본 교체).
- C-03: 비주거 적용(범주 더미 우선순위), 임대 적용 여부 결정.
- C-05: 운영 JSONL 2주 관찰 → 거절 모드 전환 조건(0단계 §6-3) 검토.

## Codex 검수용 체크리스트
- [ ] **원장 변화 0**: `logs/collective_p1/compare_region_scope.md` 또는 `python scripts/lab/collective_p1/compare_region_scope.py` — collective·commercial·built 변화 단위 0, building_stats 116 / −40,235 / −389,186.
- [ ] **복합 테스트 그대로 통과**: `pytest tests -k built` — 복합 `nonidentifiable_columns`·`design_rank`는 공통 모듈 재수출, `test_built_p1_audit_fixes`·`test_built_p5_codex_fixes` 통과(기존 실패 test_built_region_all_asset 3건·test_built_recommend_deprecated 1건은 main과 동일).
- [ ] **경고 모드에서 값이 기록되지 않음**: `tests/test_api_param_warn.py`(값·경로 변수 값이 JSONL에 없음, 필드는 8개 키만).
- [ ] **키 폭증 방지**: 이름 64자·문자 `[A-Za-z0-9_-.[]]`만, 창당 고유 키 1,000 초과분은 `(route, _overflow)`로 합침 — `test_long_and_odd_param_names_are_cleaned`·`test_unique_keys_capped_with_overflow`·`test_overflow_via_http_keeps_requests_passing`.
- [ ] **거절 모드 없음**: 미들웨어는 응답을 바꾸지 않는다(`test_main_app_has_middleware_and_no_reject_mode`, 미지원 파라미터 요청 200).
- [ ] **DB 변경 없음**: 제품 코드는 SELECT만 추가(`region_codes` 이름 조회). 측정 스크립트는 읽기 전용 접속. 마이그레이션·새 테이블 없음.
- [ ] 배포 시: `API_PARAM_WARN_PATH` 운영 경로·쓰기 권한·logrotate 결정, 프론트 5앱 재빌드(헤더), 집합 화면 「제외한 변수」 표시 확인.
