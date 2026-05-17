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

---

## 관련 문서

- 운영 SOP: `docs/V2_OPERATOR_CHECKLIST.md`
- 갱신 흐름: `docs/V2_STATS_PRODUCTION.md`
- 통계 설계: `docs/V2_STATS_DESIGN.md`
- 정제 정책: `LAND_CLEANING.md`
- 다음 작업: `NEXT_STEPS.md`
