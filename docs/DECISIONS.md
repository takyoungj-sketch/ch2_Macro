# 결정 기록 (DECISIONS)

이 문서는 **`ch2_Macro` 의 큰 방향 결정** 만 짧게 적습니다. 결정의 배경·상세 절차는 `README.md`, `docs/V2_*` 등 다른 문서에 두고, 여기에는 **무엇을 / 언제 / 왜** 만 둡니다.

| ID | 일자 | 결정 |
|----|------|------|
| D-001 | 2026-05-16 | 무료·유료 모두 **V2 시간 축(`as_of_month` + `window_years`)** 으로 단일화한다. V1 `land_basic_stats`·`/api/free/...`(V1) 라우터는 **2026-03-31 폐기**. |
| D-002 | 2026-05-16 | 데이터 신선도 **SLA**: "매월 1일~5일 사이에 직전 월 말까지의 거래를 반영해 갱신". 화면 우상단의 **「YYYY년 M월 말 기준」** 이 갱신 일자를 의미한다. |
| D-003 | 2026-05-16 | `run_pipeline.py` 실행 끝의 **응답 캐시 자동 비우기**(`analysis_cache` + `analysis_base_cache`)를 운영 SOP의 일부로 둔다. |
| D-004 | 2026-05-16 | `seed_population_csv.py` 의 **기본 동작은 전국 적재**. 시도 한정은 `--codes-prefix` 명시 시에만. |
| D-005 | 2026-05-16 | 백엔드 시간대는 모두 **UTC + timezone-aware** 로 통일 (`datetime.now(timezone.utc)`). |
| D-006 | 2026-05-16 | **유료 분석 응답에도 `as_of_month` + `stats_reference_date` 를 노출**한다. 무료/유료 화면이 가리키는 "데이터 기준 시점" 을 항상 같이 보여 준다. |
| D-007 | 2026-05-16 | 배포 직후 노출 보호: 환경변수 **`API_TOKEN`** 을 두면 백엔드가 모든 요청에서 `X-Api-Token` 헤더를 검사한다(없으면 미들웨어는 비활성). 결제·로그인 도입 전 1단 보호. |
| D-008 | 2026-05-16 | 갱신 절차의 단일 SOP 는 **`docs/V2_OPERATOR_CHECKLIST.md`** 1개. README/NEXT_STEPS 는 그쪽으로 포인터만 둔다. |
| D-009 | 2026-05-19 | **상위 행정구역 사전집계 도입**: 법정동/리 외에 읍면동·시군구·시도 레벨도 사전집계(`land_upper_stats_v2`)를 구축한다. 단, **한자 병기 beopjungri_code 오류 해소 및 원장 재정제 완료 후** 구축 시작. 설계: `docs/UPPER_STATS_DESIGN.md`. |
| D-010 | 2026-05-19 | **무료/유료 접근 경계 재정의**: 무료는 법정동/리 단건만. 유료는 단일 모든 레벨(법정동/리·읍면동·시군구·시도). 복수지역 실시간 집계는 유료에서 읍면동/동/리 최대 10개로 제한; 시군구·시도 복수지역 선택은 API·프론트에서 차단. |
| D-011 | 2026-05-19 | **쌍둥이 지역 찾기** 유료 기능 설계 확정: 시군구·읍면동 레벨, 가격 통계·거래량·인구·토지 구성 피처 벡터, 가중 유클리드 거리. 상세 설계: `docs/UPPER_STATS_DESIGN.md` §8. |
| D-012 | 2026-05-19 | **한자 병기·신설 분구 매핑 3단 방어** (`pipeline/clean.py`): ① 괄호 한자 정규화(`_normalize_admin_label`) + 리 주소 파싱(`_parse_address_structured`), ② 시도명 별칭(`전북특별자치도→전라북도` 등)·분구 토큰 drop(`화성시 만세구→화성시`) **fallback**, ③ **동명이리 한자 disambiguation** (정규화 이름이 같은 코드가 2 개 이상인 그룹에서 거래 원장의 괄호 한자와 `region_codes` 의 괄호 한자를 부분 포함 비교로 분기, `mapping_notes='disambiguated_hanja'`). 실측: ① + ② 로 `needs_review` 106,428 → 862 (-99.19%), ③ 으로 기암리·화산리 거래 241건 재분배. 적용 후 영향 단일 코드만 `land_basic_stats_v2` 재빌드 → `pipeline/remap_homonym_targets.py`. |
| D-013 | 2026-05-30 | **장기 연도별 추세(v1)**: `land_annual_stats` 사전 집계 + 유료 **필터분석 매트릭스 모달**「장기 추세」탭. **복수 지역은 합산하지 않고 지역별 시리즈**를 한 차트에 표시. 도로·면적·IQR 등 고급 필터 **미적용**. 설계: `docs/LONG_TERM_TREND_DESIGN.md`. |
| D-014 | 2026-06-10 | **Region · Property 아키텍처는 Post-MVP 장기 과제로 보류**. MVP(현 기능) 완성·6월 말 수정 반영 우선. Region/Resolution/Property/Transaction/Statistics 5층 모델·Property Registry SSOT는 **7월 업데이트 전** 재논의. 설계 초안: `docs/REGION_ARCHITECTURE_ROADMAP.md`. |
| D-015 | 2026-06-16 | **복합부동산 addr 정규화 — 리(法定里)를 항상 `addr5`로**: 구(區) 없는 시(市)에서 리가 `addr4`에 저장되어 `/regions/ri` 조회·3-way 회귀 비활성화되는 버그 확인. **import 레벨 정규화(방안 A)** 로 해결 예정. 상세: `docs/REGION_ARCHITECTURE_ROADMAP.md` §D-015. |
| D-016 | 2026-06-17 | **Regional Profile 중심 5-Layer Statistics 아키텍처**: Transactions → Object Stats → **Market Stats** (`upper_stats` 대체 개념) → **Regional Profile** (Feature Vector, 건물 미포함) → 회귀·쌍둥이·AI. 집합: `building_stats`(UI)와 `market_stats`(Profile) **분리**. 집합 모달 **Analysis Cohort**(다중 `building_key` 회귀·층·동 효용). 상세: [`docs/REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md). 브랜치: `feature/collective-work`. |
| D-017 | 2026-06-19 | **Regional Profile 설계 정련(검토 반영)**: ① **토지 domain은 대표시장 추출** — `ALL×ALL` 금지, `land_residential=2종주거×대`·`land_commercial=상업×대`·`land_industrial=공업×공장용지` (P0). ② **Profile A/B 검증은 다중 지역 pooling 필수** — 단일 지역은 절편과 공선이라 효과 0 (P0). ③ **Profile = 데이터 제품**: `regional_profile`에 `profile_version`·`window_years`·`feature_count`·`builder_version`·`validation_status` 추가, 고유 grain에 version·window 포함 (DDL `db/025_regional_profile.sql`). ④ **Twin·AI는 Profile을 소비**(계층 분리) — Feature 재생성 금지, `(profile_version, as_of, window)` 고정 조회. ⑤ **region_code 8/10자리 SSOT 통일**, DB 접속 **환경변수 일원화**. **문서가 설계 SSOT**(코드 선행 금지). 빌드 구현은 추후. 상세: [`docs/REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) §7.0. |

## D-001 V1·V2 단일화 — 폐기 일정

| 시점 | 상태 |
|------|------|
| 2026-05-16 (현재) | V2(`/api/free/v2/...`) 가 무료의 표준. 유료 `/api/paid/...` 는 V2 시간 축(`as_of_month`/`stats_reference_date`)을 응답에 노출. V1 `/api/free/...`(이름·기본통계·bulk) 는 **deprecated** 로 마킹되어 OpenAPI·응답 헤더(`Sunset: Wed, 31 Mar 2026 ...`)에 표시. |
| 2026-03-31 | V1 라우터·`build_stats.py`·`land_basic_stats` 의 **신규 호출·갱신 중단**. (테이블 자체는 한 분기 더 보존 후 백업 정리.) |
| 2026-06-30 (예정) | V1 테이블·코드 제거. 유료 매트릭스 캐시 키도 V2 단일 컨텍스트로 정리. |

## D-002 신선도 SLA — 사용자 약속

- **표시**: 모든 무료/유료 화면 우상단 「YYYY년 M월 말 기준」.
- **갱신 창**: 매월 **1일 09:00 KST 시작 ~ 5일 자정 까지**. 5일을 넘기는 지연은 운영자가 별도 공지.
- **API**: `/health` 응답이 `latest_as_of_month` 를 포함. 외부 모니터·배지에 활용.

## D-003 캐시 자동 무효화 (`analysis_cache` + `analysis_base_cache`)

원장·사전집계가 갱신되면 두 캐시 모두 stale.

- `analysis_cache` (응답 캐시, 24h TTL): 24h 안에 같은 페이로드가 들어오면 옛 매트릭스를 보여 줌 → 갱신 직후 **TRUNCATE**.
- `analysis_base_cache` (row_ids 캐시, 4h TTL): `clean.py --reprocess-all` 등으로 `transaction_hash` 가 바뀌면 `id` 가 바뀌어 **다른 거래의 id 를 가리킬 위험** → 갱신 직후 **TRUNCATE**.
- 구현: `pipeline/run_pipeline.py` 끝에서 두 테이블 모두 비움. 실패해도 파이프라인은 정상 종료(로그만 남김).

## D-006 유료 응답의 시간 축 노출

- `PaidAnalysisResponse` 가 `as_of_month` 와 `stats_reference_date` 를 같이 내려준다.
- 프론트 화면 우상단·매트릭스 캡션에서 **무료/유료 동일 표기** 「YYYY년 M월 말 기준」 사용.
- 사용자의 「연도 칩(years)」 선택은 그대로 유지. as_of_month 는 "이 데이터가 언제까지 반영됐는지" 정보용이고, 칩은 "어느 해 거래만 볼지" 필터.

## D-007 API_TOKEN 옵트인 보호

- `.env` 의 `API_TOKEN=` 값이 비어 있으면 미들웨어는 통과 (개발·로컬).
- 값이 있으면 모든 비-`/health` 요청이 `X-Api-Token: <값>` 헤더를 가져야 200, 아니면 401.
- 프론트는 빌드 시 `VITE_API_TOKEN` 으로 주입. 결제·로그인 도입 후에는 사용자 토큰으로 대체할 자리.

## D-009 상위 행정구역 사전집계 (`land_upper_stats_v2`)

- **신규 테이블**: `land_upper_stats_v2` (`db/010_land_upper_stats_v2.sql`)
  - `region_level`: `'sido'` | `'sigungu'` | `'eupmyeondong'`
  - `region_code`: 레벨에 맞는 코드 (2/5/8자리)
  - 나머지 컬럼은 `land_basic_stats_v2`와 동일 (`as_of_month`, `window_years`, 통계 필드)
- **집계 원칙**: `land_transactions` 원장에서 직접 집계 (하위 단계 사전집계 값 합산 금지).
- **신규 파이프라인**: `pipeline/build_upper_stats_v2.py` → `run_pipeline.py`에 통합.
- **선행 조건**: 한자 병기 beopjungri_code 매핑 오류 해소 + 원장 재정제 완료.

## D-010 복수지역 제한 정책

| 요청 레벨 | 무료 | 유료 |
|-----------|------|------|
| 법정동/리 (10자리) | 단건 1개 | 최대 10개 (실시간 집계) |
| 읍면동 (8자리) | 불가 | 단건 1개 (사전집계) |
| 시군구 (5자리) | 불가 | 단건 1개 (사전집계) |
| 시도 (2자리) | 불가 | 단건 1개 (사전집계) |

- `_MAX_STATS_REGIONS`: 무료 1 / 유료 10 (법정동/리 한정).
- 시군구·시도 복수 선택은 API 422로 차단 (프론트에서도 선택 자체 비활성화).

## D-012 한자 병기·신설 분구 매핑 3단 방어

원장(`land_transactions`) 의 `beopjungri_code` 매핑 손실을 다층 방어로 회복.

### 1단 — 정규화 (이미 반영, 커밋 `a220caf`)

- `_normalize_admin_label`: 읍·면·동·리명의 전각·반각 괄호(`(岐岩)`, `（花山）`) 제거.
- `_parse_address_structured`: 마지막 토큰이 `기암리(岐岩)` 처럼 괄호 병기여도 정규화 후 `endswith("리")` 로 법정리 분기.

### 2단 — Fallback (커밋 `e76e167`)

`map_beopjungri_codes` 의 기본 강한 키 lookup 이 실패할 때만:

| Fallback | 조건 | 예 | `mapping_notes` |
|---|---|---|---|
| `sido_alias` | 신설 시·도 별칭(`_SIDO_NAME_ALIASES`) | `전북특별자치도 → 전라북도` | `sido_alias` |
| `subgu_dropped` | 마스터에 없는 분구가 시군구 토큰에 붙은 경우 — 마지막 토큰을 하나씩 떼며 재시도 | `화성시 만세구 → 화성시` | `subgu_dropped` |

실측: 전국 로컬 재정제 결과 `needs_review` **106,428 → 862 (-99.19%)**. 로그: `logs/rebuild_local_20260519_164409.txt`.

### 3단 — 동명이리 (同名異里) Disambiguation (커밋 `86ce77f`)

`region_codes` 의 정규화 이름이 같은 코드가 2 개 이상인 그룹(전국 **3쌍**: 기암리, 화산리, 양리)에서 일반 lookup 은 등록 순서상 첫 코드만 살아남아 거래가 한쪽으로 몰린다.

- `build_region_lookup` 이 `disamb_by_name` / `disamb_by_code` (정규화 키 → `[(code, 괄호한자, 원본명), …]`) 인덱스를 반환.
- `map_beopjungri_codes` 가 일반 lookup **이전에** 한자 부분 포함 비교로 분기, `mapping_notes='disambiguated_hanja'` 기록.

| 그룹 | 코드·한자 | 원장 영향 |
|---|---|---|
| 충북 상당구 미원면 기암리 | `4311132026` (岐岩) / `4311132033` (基岩) | 77건이 `2026 → 2033` 으로 이동 |
| 충북 흥덕구 오창읍 화산리 | `4311425322` (华山) / `4311425350` (花山) | 65건이 `5322 → 5350` 으로 이동 |
| 강원 양양 현남면 양리 | `4729025331` / `4729025332` | 거래 0건 — 변경 없음 |

### 적용 도구

- 전체 재정제: `pipeline/clean.py --reprocess-all` (수 시간) — 1·2단을 한 번에 흡수하는 표준 절차.
- 동명이리만 영향이라면 **부분 적용**: `pipeline/remap_homonym_targets.py --as-of YYYY-MM-01 --windows 3,5`.
  - 영향 6개 코드 범위 raw 만 재매핑 → `land_basic_stats_v2` 의 해당 행 삭제 → `build_stats_v2.py --region <code>` 로 영향 코드만 재빌드.
  - `land_upper_stats_v2` 는 동일 시군구·읍면 내 재분배라 합계가 동일하므로 **재빌드 불요**.

### 테스트

`pipeline/tests/test_clean_address.py` — 17건 통과. `_extract_paren_content` 4건, `subgu_dropped`/`sido_alias` 3건, `disambiguated_hanja` 3건 포함.

## D-011 쌍둥이 지역 찾기

- **대상 레벨**: 시군구, 읍면동.
- **피처 그룹**: 가격 통계(mean/median/p25/p75/std), 거래량(log count), 인구(log 총인구·밀도), 토지 구성(주거·상업·농림 비율, 대지·농경지·임야 비율).
- **알고리즘**: z-score 정규화 → 가중 유클리드 거리 → top-N 반환.
- **가중치 모드**: `uniform`(기본) | `price` | `population` | `composition`.
- **인구 데이터 보강**: 현재 `population_stats`는 beopjungri 레벨만 보유 → `region_codes JOIN population_stats` 집계 뷰로 시군구·읍면동 레벨 인구 확보.
- **API**: `POST /api/paid/twin-regions`.
- 상세 설계: `docs/UPPER_STATS_DESIGN.md` §8.

---

## 관련 문서

- 운영 SOP: `docs/V2_OPERATOR_CHECKLIST.md`
- 갱신 흐름: `docs/V2_STATS_PRODUCTION.md`
- 통계 설계 (V2): `docs/V2_STATS_DESIGN.md`
- 상위단계·쌍둥이 설계: `docs/UPPER_STATS_DESIGN.md`
- 정제 정책: `LAND_CLEANING.md`
- 다음 작업: `NEXT_STEPS.md`
