# 다음 작업 메모

마지막 정리일: 2026-05-17

> **큰 결정** 은 [`docs/DECISIONS.md`](docs/DECISIONS.md) 에, **운영 SOP** 는 [`docs/V2_OPERATOR_CHECKLIST.md`](docs/V2_OPERATOR_CHECKLIST.md) 에 둔다. 이 문서는 **지금 손대는 일 + 짧은 백로그** 만 유지한다.

---

## 0. 내일 첫 일 (이번 세션 마감 시점에 남은 검증)

이번 세션에서 백엔드(`main.py` lifespan + `/health.latest_as_of_month`, `paid.py` as_of/ref 노출, API_TOKEN 옵트인)와
프론트(매트릭스/연도별 표 캡션을 「YYYY년 M월 말 기준」으로 통일)를 모두 손봤지만, 실행 중인 백엔드 프로세스는 옛 코드 그대로다.
리허설(`pipeline/rehearse_v2_update.py`) 결과 → `logs/rehearse_v2_update.txt` 도 같이 참고.

| 순 | 액션 | 확인 |
|----|------|------|
| 0-1 | **백엔드 재시작** | `curl http://127.0.0.1:8000/health` → `latest_as_of_month: "2025-12-01"` 가 같이 와야 함 |
| 0-2 | **프론트 강제 새로고침** | 무료/유료 두 패널 우상단·매트릭스 캡션이 모두 「2025년 12월 말 기준」으로 동일한지 눈 확인 |
| 0-3 | (선택) **API_TOKEN 켜기** | `backend/.env` 의 `API_TOKEN` + `frontend/.env` 의 `VITE_API_TOKEN` 같은 값으로 채우고 양쪽 재시작 → 호출 통과 확인 |
| 0-4 | **리허설 재실행** | `py -3.13 pipeline/rehearse_v2_update.py --health-url http://127.0.0.1:8000/health` → errors=0 목표 (남은 errors 는 §1 P2 의 인구 시드 1건뿐이어야 함) |

위 4개 끝나면 본 세션의 모든 코드 변경분이 사용자 화면까지 닿은 것.

## 1. 지금 진행 중

| 우선 | 항목 | 메모 |
|------|------|------|
| P0-M | **월간 갱신 재현 SOP** | [`docs/MONTHLY_UPDATE_SOP.md`](docs/MONTHLY_UPDATE_SOP.md), `scripts/monthly/run_monthly_cycle.py` — 반자동 월배치. |
| P1 | **웹 배포 (프로덕션 / 준프로덕션)** | DECISIONS D-007 의 `API_TOKEN` 옵션을 활성한 채 배포. CORS·도메인·env 점검. |
| P2 | **`population_jusosagae` 전국 시드** | 리허설이 잡아낸 미적재 1건. SOP §B7: `py -3.13 pipeline/seed_population_csv.py --file ../data/population/<최신_CSV>` (DECISIONS D-004, prefix 미지정 = 전국). |
| P3 | **2026년 첫 월별 갱신 본 운영** | `docs/V2_OPERATOR_CHECKLIST.md` §B0 (리허설) → §B1~B12 그대로. `/health.latest_as_of_month` 가 직전 달 1일로 바뀌는지가 통과 기준. |
| P4 | **V1 라우터 폐기 일정 모니터링** | `docs/DECISIONS.md` D-001: 26-03-31 신규 호출 차단, 26-06-30 코드/테이블 제거. |

## 2. 짧은 백로그 (제품·코드)

브랜치 리뷰(2026-05-16)와 그 이후 추가 항목.

| # | 영역 | 항목 | 비고 |
|---|------|------|------|
| 1 | ~~backend/frontend~~ | ~~`paid.py` 매트릭스 응답에 `as_of_month`/`stats_reference_date` 노출 + 프론트 캡션 「YYYY년 M월 말 기준」 통일~~ | **2026-05-17 완료 — DECISIONS D-002/D-006**. archive 참조. |
| 2 | backend | `free_v2._combined_bundle_v2_from_transactions` 메모리 합산 → SQL `GROUPING SETS` 로 이전 | 시군구 다중 합산 시 성능 |
| 3 | pipeline | `clean.py --reprocess-all` 에 `--yes-i-am-sure` 또는 stdin 확인 도입 | 전 테이블 삭제 가드 |
| 4 | backend | `free_v2.get_basic_stats_v2` 단건 — 사전집계 미적재 시 안내 메시지에 `build_stats_v2.py --as-of …` 명시 | UX |
| 5 | backend | `free.py`(V1) 라우터 deprecated 마킹 후 **2026-03-31 제거** | DECISIONS D-001 |
| 6 | backend | 갱신 실패 알림 (Slack/SMTP) — `build_stats_v2.py` 종료 코드를 받는 wrapper | 외부 webhook 정해지면 |
| 7 | ops | DB 일일 백업 자동화 (`pg_dump` 또는 PITR) + 복구 리허설 | 결제 도입 전이라도 |
| 8 | tests | `clean.py` 강한 키 매핑·`compute_stats`·`period_bounds_for_window` 단위 테스트 | 26년 코드 변경 회귀 방지 |
| 9 | ops | Selenium/Playwright 자동 수집 | 현재는 수동 다운로드 → `--excel-dir` |
| 10 | ui | 신규 연도 첫 분기 "참고용" 워터마크 (count<15 강조 외 보조) | 26년 1Q UX |
| 11 | docs | README 분할 (`docs/SETUP.md`, `docs/PRODUCT.md`, `docs/PIPELINE.md`) | 현재 README 270+ 줄 |
| 12 | backend | `region_codes` 활성/비활성(`is_active`) 갱신 절차 — 행정 개편 대응 | 신규 법정동 코드 자동 반영 |

## 3. 상위단계 사전집계 + 쌍둥이 지역 (DECISIONS D-009~D-011)

> 상세 설계: [`docs/UPPER_STATS_DESIGN.md`](docs/UPPER_STATS_DESIGN.md)
> **선행 조건**: §3-0의 한자 병기 이슈 해소 완료 후 진행.

### 3-0. 선행 — 한자 병기 beopjungri_code 오류 해소 (P0) ✅ **완료 (2026-05-19)**

3단 방어 적용. 상세는 `docs/DECISIONS.md` **D-012**, `docs/FOLLOW_UP_LAND_TX_MAPPING.md` §1 참고.

| # | 액션 | 결과 |
|---|------|------|
| 0-a | `clean.py` 괄호 병기 리 주소 파싱 (`_parse_address_structured`) | ✅ 코드 + 테스트 (`a220caf`) |
| 0-b | `clean.py` 2단 fallback — 시도 별칭 + 분구 토큰 drop | ✅ `e76e167` — `needs_review` 106,428 → 862 (-99.19%) |
| 0-c | `clean.py` 3단 — 동명이리 한자 disambiguation | ✅ `86ce77f` — 3쌍 중 거래 영향 2쌍 (241건) 부분 재매핑 |
| 0-d | `land_transactions` 전체 재정제 (`--reprocess-all`) + `land_basic_stats_v2` 전체 재구축 | ✅ 2026-05-19 (`logs/rebuild_local_20260519_164409.txt`) |
| 0-e | 동명이리 영향 코드 `land_basic_stats_v2` 부분 재빌드 | ✅ `pipeline/remap_homonym_targets.py` — 216행 삭제 후 재빌드 |

### 3-1. DB 마이그레이션

| # | 항목 | 파일 |
|---|------|------|
| 1 | `land_upper_stats_v2` 테이블 생성 DDL | `db/010_land_upper_stats_v2.sql` |

### 3-2. 파이프라인

| # | 항목 | 비고 |
|---|------|------|
| 2 | `pipeline/build_upper_stats_v2.py` 구현 | `build_stats_v2.py` 구조 참고, `--level` 인수 |
| 3 | `run_pipeline.py`에 upper stats 빌드 단계 연동 | `build_stats_v2` 완료 직후 |

### 3-3. 백엔드 API

| # | 항목 | 비고 |
|---|------|------|
| 4 | `GET /api/paid/upper-stats/{level}/{code}` 엔드포인트 | 사전집계 단건 조회 |
| 5 | 복수지역 레벨 검증 미들웨어/의존성 추가 | 무료=단건, 유료=법정동/리 최대 10개, 상위=단건 강제 |
| 6 | `population_stats` 상위 레벨 집계 뷰 (`v_population_sigungu`, `v_population_eupmyeondong`) | `region_codes JOIN population_stats` |
| 7 | `POST /api/paid/twin-regions` 엔드포인트 | 피처 벡터·z-score·거리 계산 |

### 3-4. 프론트엔드

| # | 항목 | 비고 |
|---|------|------|
| 8 | 상위 행정구역 단건 분석 패널 (유료 탭) | 읍면동·시군구·시도 선택 시 사전집계 조회 |
| 9 | 시군구·시도 선택 시 복수 선택 비활성화 UI | D-010 정책 반영 |
| 10 | 쌍둥이 지역 카드 UI | 기준 지역 vs 유사 지역 비교 테이블, 가중치 모드 선택 |
| 11 | 쌍둥이 지역명 클릭 → 해당 지역 분석 화면 이동 | 딥링크 |

---

## 4. 유료 매트릭스 모달 확장 (상시 백로그)

매트릭스 셀 모달(`PaidMatrixYearlyModal`) 에 단계적으로 확장.

### 4-1. 히스토그램 (분포·정규성 확인용)

| 고려사항 | 내용 |
|----------|------|
| 데이터 정의 | 모달과 **동일한 유료 필터** + 선택한 **용도지역·지목** 의 `unit_price_per_sqm` 표본. |
| 연도 범위 | "특정 연도 한 해" 분포 vs "모달이 다루는 연도 전체 합산" 분포 — 탭 또는 셀렉터. |
| 왜곡 | 단가는 꼬리가 길 수 있음 → **선형 히스토그램 + log 스케일** 병행. 정규성은 모양·대칭 위주 안내. |
| 구현 위치 | **서버에서 bin 경계·빈도·`n` 만 반환**. 최대 표본 상한 정책. |
| UI | 표본 수 `n`, bin 수, (선택) 정규 근사 곡선. 추세선과 같은 이상치 옵션 적용 여부 명시. |

### 4-2. 원데이터 보기 (거래 목록)

계획만 유지. **거래 목록 열 확대(예: 계약일 yyyy-MM-dd, 지번, 지분구분 원문, 거래유형 등)** 는 `db`·`pipeline/clean`·API·모달 변경이 따라붙으며, **`운영자가 명시적으로 지시하기 전까지 진행하지 않는다**(서버 이전 타이밍이나 월별 업데이트에 자동으로 묶어 일정 고정 안 함)**.

예상 노출 형태(실행 지시 후 참고용): 계약일·지번·면적·금액·단가·도로·지분구분·거래유형. 현재 UI는 재범위를 줄여 **계약연월·면적·금액·단가·도로** 만 노출.

| 고려사항 | 내용 |
|----------|------|
| 데이터 출처 | `land_transactions` 정제 행. 히스토그램과 동일 필터 + 용도·지목. |
| API | `PaidAnalysisRequest` + `zone_type`, `land_category` + 페이지네이션. |
| DB·정합 | 지시 시점에 확정한다. 참고 시 `contract_date`(또는 동일 정보)·`db/011` 표시 컬럼 등과 `pipeline/clean` 동기화 검토. |
| 규모 | 셀당 수천 건 가능 → 한 페이지 건수 상한, 총 건수 표시. |
| 캐시 | `analysis_base_cache` 키 재사용으로 같은 후보 행 집합 위에서 목록 조회. |

(현재 위 두 기능 일부는 이미 `MatrixCellHistogramRequest`/`MatrixCellTransactionsRequest` 로 백엔드에 도입돼 있고, 프론트 합류는 단계적으로.)

---

## 부록 A. 끝난 단계 (Archive)

> 다음 항목들은 종료 상태. 다음 정리에서 별도 파일(`docs/archive/`) 로 이동 예정.

### 정제 정책 확정 (2026-05-10)

- 신고 행 단위 보존 + 해제 행만 통계 제외 정책 확정.
- `참고/7.토지 통합 정제.ipynb` 의 핵심 정제 기준을 `pipeline/clean.py` 에 반영.
- 단가 = `거래금액(만원) / 계약면적(㎡)` 로 저장.
- DB 백업: `backup_land_transactions_20260510_152743`, `backup_land_basic_stats_20260510_152743`.
- 호암동 2022~2025 검증: 원장 433 건, 통계 대상 406 건, `land_basic_stats` ALL 통계 406 건.

### 전국 base DB — 시도별 적재 (2026-05-15 시점 진행, V2 사전집계는 전국 완료)

- `pipeline/seed_region_codes.py` + `pipeline/run_pipeline.py --excel-dir ...` 패턴으로 시도별 적재.
- `pipeline/run_remaining_sidos.py` 가 잔여 13개 시도 일괄 처리(시드 → 토지 파이프라인 → 인구 연도별).
- 인구 CSV 는 `data/population/` 의 행안부 「지역별(법정동) 성별 연령별 주민등록 인구수」 사용.

이후 신규 시도 적재가 발생하면 위 SOP 동일 적용. 운영 진입 후에는 시도별 폴더보다 **평면 한 폴더 + `--skip-build-stats` + 마지막 1회 `build_stats_v2.py`** 권장 (`docs/V2_OPERATOR_CHECKLIST.md`).

### 매트릭스 ↔ 모달 일관성 (2026-05-16 패치)

- 무료 V2 응답의 `kept` 코드를 `paidBulkBeopjungriCodes` 로 동기화 → 유료 분석/매트릭스/모달이 같은 행 집합.
- `runPaidFilteredAnalysis` race / 로딩 표시 누락 수정.
- 파이프라인 끝에서 `analysis_cache` + `analysis_base_cache` 자동 무효화.
- `setViewMode("free")` 시 다중 선택 잔재 정리.
- `PaidAnalysisRequest` `extra="forbid"` 로 오타 방어.

### 캡션 통일 + 리허설 도구 (2026-05-17 패치)

- 무료/유료 패널 모두 「YYYY년 M월 말 기준」으로 표기 통일 (`statsAsOfLabel` 유틸).
  - `frontend/src/utils/freeStatsV2.ts`, `FreeStatsPanel.tsx`, `PaidAnalysisPanel.tsx`.
- 백엔드 `paid.py` 의 매트릭스 응답에도 `as_of_month`/`stats_reference_date` 노출 (DECISIONS D-006).
- `backend/app/main.py` lifespan 전환 + `/health.latest_as_of_month` 노출 + `API_TOKEN` 옵트인 미들웨어 + V1 라우터 `Sunset` 헤더.
- SOP §B 앞에 **B0 (리허설)** 단계 추가: `pipeline/rehearse_v2_update.py` (읽기 전용; 환경/DB/마이그레이션/SOP `--help`/`/health` 일괄 점검).
  - 산출물: `logs/rehearse_v2_update.txt` (UTF-8). PowerShell 콘솔이 cp949 라 화면이 깨질 수 있어 항상 파일을 본다.

### 통합 브랜치 `feature/land-integration-export` 종료 및 main 병합 (2026-05-25)

- **거래 목록 고도화(계약 일자·지번·지분·거래유형 등)**: `NEXT_STEPS` §4-2 로 계획만 남김.**운영자 명시 지시 전 미진행.**
- 당분간 모달 거래 목록은 **연·월 기준 간소 목록**(면적·금액·단가·도로); `matrix-cell-transactions` 는 `land_transactions`+`region_codes` 만 조회.
- 롤링 매트릭스 구간·차트 레이블: `backend/app/matrix_rolling_buckets.py`, `frontend/src/utils/matrixYearlyLabels.ts`.
- 유료/무료 패널·필터·모달 리팩터, `paid`·`schemas` 확장, `free_v2`·`upper_stats` 보강, `analysis_base_cache`·페이로드 유틸 정리.
- 정제 준비: `pipeline/clean` 표시 필드 채우기, `db/001_init.sql` 및 `db/011_land_transactions_display_columns.sql`(향후 DDL용).
- 월간 스크립트·SOP 및 `.env.example` 보완.

---

## 관련 문서

- 결정 기록: [`docs/DECISIONS.md`](docs/DECISIONS.md)
- 운영 SOP: [`docs/V2_OPERATOR_CHECKLIST.md`](docs/V2_OPERATOR_CHECKLIST.md)
- **월간 로컬 재현 SOP**: [`docs/MONTHLY_UPDATE_SOP.md`](docs/MONTHLY_UPDATE_SOP.md)
- 갱신 흐름: [`docs/V2_STATS_PRODUCTION.md`](docs/V2_STATS_PRODUCTION.md)
- 통계 설계: [`docs/V2_STATS_DESIGN.md`](docs/V2_STATS_DESIGN.md)
- 정제 정책: [`LAND_CLEANING.md`](LAND_CLEANING.md)
- 제품 기준: [`README.md`](README.md)
