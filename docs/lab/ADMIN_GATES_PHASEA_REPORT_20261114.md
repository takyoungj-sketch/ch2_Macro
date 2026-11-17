# 관리자 전용 기능 스위치 — Phase A 조사 보고 (2026-11-14)

- 기준: `origin/main` 55bb29c (임대 504 C안 포함). worktree `D:\ch2\ch2_Macro-gates`, 브랜치 `feature/admin-gates`.
- 코드 수정 없음. 이 보고서만 추가(미커밋).
- DB는 로컬 임대 DB에 읽기 전용 세션(`default_transaction_read_only=on` 확인)으로 SELECT만 했다.
- 근거 결정 D-085는 Phase B에서 기록한다. 번호는 `docs/lab/RENT_REGRESSION_504_20261112.md:54` 에 이미 「D-085 임대 회귀 공개 조건」으로 예약돼 있다. 다른 브랜치와 겹치지 않는다.

---

## 1. 관리자 판정

| 항목 | 현재 상태 |
|---|---|
| 역할 값 | `users.role` ∈ {`member`, `admin`} (`db/048_ch2_platform.sql:10-15` CHECK 제약). `staff` 같은 값은 없다. |
| `/api/auth/status` | 로그인 시 `role` 을 준다 (`platform/auth_router.py:490-501`). `/api/auth/me` 도 같다. |
| 서버 권한 함수 (있음) | `platform/deps.py` `require_admin`(FastAPI 의존성, 401/403) · `admin_auth.py` `caller_role()`, `admin_access_status()`, `require_admin_access()` (QA 토큰 또는 admin) |
| 구독 판정 | `product_gate.caller_access()` → anonymous/login/macro. `entitlements.apply_staff_entitlements` 가 admin 에게 macro 를 자동으로 준다. |
| 관리자 로그인 경로 | OAuth 로 로그인한 admin 계정, 또는 staff 비밀번호 로그인(`auth_router.py` staff-login: 첫 admin 계정으로 JWT 발급, 세션 짧음) |
| `/lab/` Basic Auth (D-061) | **별개다.** Nginx `auth_basic` 이 `/lab/` 정적 화면과 랩 API(`/api/admin/`, `/api/built/lab/`, `/api/regional-profile/lab/`)에만 걸린다 (`deploy/templates/nginx-ch2-lab-*.conf`). 제품 경로에는 없다. 앱 서버는 Basic Auth 를 모른다. 앱 안의 `/api/admin/*`·`/api/lab/*` 는 추가로 `admin_access_status` 로 막는다 (`product_gate.py` 맨 앞). |
| 로컬 개발 | `CH2_LOCAL_DEV_ACCESS` 설정만 남아 있다. `local_dev_access_enabled()` 를 부르는 곳이 없고 `/api/auth/status` 가 `local_dev_access` 를 주지 않는다. 그래서 프론트 `productAccess.tsx` 의 로컬 우회 분기는 실제로는 동작하지 않는다. |

**결론:** 스위치의 「관리자」 = `caller_role(request) == "admin"`. QA 토큰(`X-Qa-Audit-Token`)도 관리자로 볼지는 Phase B 에서 결정해야 한다. 권장은 **포함**이다. 검증 로봇이 비공개 기능도 점검해야 하기 때문이다.

참고 — 중복 조회: `caller_role`·`caller_access`·`get_optional_user` 가 요청마다 users 표를 따로 조회한다. Phase B 에서 role 을 `request.state` 에 한 번만 담으면 조회가 1회로 준다.

### 1-1. 프론트가 로그인 상태를 아는 곳

- 토지·집합: `shared/macro-shell/productAccess.tsx` `ProductAccessProvider` 가 `/api/auth/status` → `/api/billing/subscription/me` 를 부른다.
- 복합·임대·프로필·인사이트: Provider 가 없다. 로그인 상태를 모르고 서버 401/403 에만 기댄다.
- 그래서 Phase B 는 `shared/macro-shell/features.tsx`(`useFeatures()`)를 새로 만들어 5앱이 같이 쓰게 해야 한다(D-072 형식 패리티).

---

## 2. 대상 전수

### 2-A. `rent_regression` (임대 단지 회귀)

| 구분 | 위치 |
|---|---|
| API | `POST /api/rent/buildings/{building_key}/regression/run` (단건) · `POST /api/rent/regression/run?building_key=…` (코호트) — `backend/app/rent/router.py:424, 454` |
| 서버 내부 | `_run_rent_regression` (`router.py:408`), `rent/land_price.prepare_rent_regression`, `rent/tx_query.fetch_regression_rows`, 집합 엔진 `collective/regression/engine.run_building_regression / run_cohort_regression` |
| 예측 | 임대 화면에는 예측 UI·엔드포인트가 **없다**. 회귀 응답 안의 계수·적합값만 있다. |
| 화면 | `frontend-rent/src/components/BuildingDetailModal.tsx:15,22` 탭 `regression`「회귀 분석」, `:521` `RentRegressionPanel` · `RentRegressionPanel.tsx` · `ZoneCaution.tsx` · `api/client.ts:222-306` (`runRentRegression`, `rentRegressionErrorMessage`) |
| 도움말 문구 | `frontend-rent/src/utils/rentHelpPresentation.ts:11, 60, 61` — 「회귀분석도 전체기간 자료 중 전세 거래를 사용합니다」 등. 사용자에게 보이고, AI 의 `ctx.explain` 으로도 들어간다. |
| AI | ① `RentBuildingDetail` 컨텍스트의 `detail_tab: "regression"` → `ai/screen_evidence.py:84 rent_detail` 이 「화면」 값으로 쓴다. 회귀 수치는 넘기지 않는다. ② 지식 문구: `ai/knowledge/product.py:20` APP_STRUCTURE 의 rent 설명에는 회귀가 없다. ③ AI2(랩)에는 `rent_rate` 도구만 있다 (`ai2/live_domains.py:305`). 회귀 도구는 없다. |
| 캐시 | 없다. `rent/db.py` 의 `lru_cache` 는 엔진 객체용이다. 프론트는 `useMutation` 이라 쿼리 캐시가 없다. |

### 2-B. `land_regression` (토지 회귀식 탭·실행)

| 구분 | 위치 |
|---|---|
| API | `POST /api/paid/matrix-cell-transactions/regression` · `…/regression/suggest` · `…/regression/predict` — `backend/app/routers/paid.py:2132, 2155, 2169` |
| 서버 내부 | `backend/app/land_regression.py` (`run_land_regression`, `suggest_land_regression`, `predict_land_regression`) |
| 화면 | `frontend/src/components/PaidMatrixYearlyModal.tsx:127,512` 탭 `regression`「회귀 분석」, `:1288-1490` 변수 선택·실행·추천·산점도·예측 · `LandRegressionResults.tsx` · `LandRegressionEquation.tsx` · `LandRegressionEffectsTable.tsx` · `LandRegressionScatterSection.tsx` · `LandPredictPanel.tsx` · `utils/landRegressionFormat.ts` · `LandMatrixTabsGuide.tsx`(탭 안내) · `constants/landStatsExplain.ts` · `utils/landHelpPresentation.ts` |
| 모바일 | `MobileLandApp.tsx` 에는 회귀 탭이 없다(롤링만, D-080). |
| AI | 컨텍스트: `frontend/src/api/aiContext.ts:16 buildLandRegressionContext`, `:55 buildLandScatterContext` (panel `LandRegressionTab`), `LandPredict`. 서버: `ai/dialogue.py:169-178`, `ai/panel_capabilities.py:256`, `ai/knowledge/planner.py:69`. 지식 문구: `ai/knowledge/product.py:17`「land: … 유료 필지 회귀」, `:757` land 설명 「매트릭스 셀 회귀」. `ai/knowledge/screen_guides.py:1044, 1059` 는 다른 화면에서 토지 회귀를 언급하는 추천 질문이다. |
| 캐시 | 없다. 회귀 요청은 매번 원거래를 다시 읽는다. |

### 2-C. `land_ledger_link` (토지 거래–대장 연결) — 응답 필드 단위

대장 연결 값이 나오는 곳은 `land_transaction_trait_link` 를 읽는 **`routers/paid.py` + `land_trait_link.py` 두 파일뿐이다**(백엔드 전체 grep). 복합·집합·임대의 공시지가 변수는 다른 표(`LAND_PRICE_TABLE`·복합 enrichment)에서 오므로 이 스위치 범위 밖이다. 인사이트·프로필에는 없다.

| API | 요청 신호 | 응답·출력 칸 | 화면 |
|---|---|---|---|
| `POST /api/paid/matrix-cell-transactions` (`paid.py:2040`) | `trait_enrich: true` | `trait_enrich_applied` + 항목별 `trait_link_status`, `trait_link_label`, `trait_price_status`, `official_price_won`, `official_price_year`, `trait_asof`, `trait_unverified`, `recovered_lot` (`schemas.py:645-654`, `land_trait_link.TRAIT_ITEM_KEYS`) | 거래목록 「공시지가 표시」 체크·동의 모달(`PaidMatrixYearlyModal.tsx:1190-1220, 1490`, `LandTraitConsentModal.tsx`, `utils/landTraitConsent.ts`) · 표 열 「공시지가」(`MatrixCellTransactionTable.tsx:52 TRAIT_COLS`) · 지번 칸 툴팁 `recovered_lot`(복원 지번, `:728`, `landTxDisplay.ts:121`) · 공시지가 칸 툴팁 「YYYY년 공시지가」(`:780`) |
| 같은 목록 — 정렬·필터 | 클라이언트 정렬/필터 | 정렬 `official_price`(sort-only), 필터 키 `trait_status`·`trait_asof` (`landTxDisplay.ts:67-69, 100-105`, `MatrixCellTransactionTable.tsx:86`) | 서버 정렬·필터 파라미터는 없다. 전부 받은 행을 브라우저에서 정렬한다. |
| `POST /api/paid/matrix-cell-transactions/export` (`paid.py:2096`) | `trait_enrich: true` | CSV 열 「연결상태, 공시지가(원/㎡), 공시기준연도, 공시지가구분, 특성기준일」(`TRAIT_CSV_HEADER`, `csv_cells`) | 「CSV 내보내기」 |
| `POST …/regression` · `…/regression/predict` (`paid.py:2132, 2169`) | `variables.assessed_land_price: true` | 계수 `log_assessed_land_price` · `analysis.sample_groups[].structural_excluded_n / linked_n / unlinked_n`(**연결률**, `land_regression.py:527-534`) · `analysis` 단계표 「공시지가 연결값 확인 후」(`:546`) · `analysis.assessed_years` · 예측 요청 `assessed_land_price`(입력값) | 변수 체크 「개별공시지가」(`PaidMatrixYearlyModal.tsx:1301, 1317`) · 연결 건수(`LandRegressionResults.tsx:16-20`) · `shared/regression-ui/AnalysisSummary.tsx:64, 86`(공시지가 기준연도·「비지분 공시지가 연결 n건 / 미연결 n건」) · 예측 입력 칸(`LandPredictPanel.tsx:142-150, 271-280`) · 식 표기(`landRegressionFormat.ts:46, 107`) |
| `POST …/regression/suggest` (`paid.py:2155`) | — | 대장을 읽지 않는다. 후보에서 `assessed_land_price` 를 빼고 `excluded_blocks: ["assessed_land_price"]` 를 준다 (`land_regression.py:579-583`) | `PaidMatrixYearlyModal.tsx:1453` 안내 |
| 지도 툴팁 | — | 대장 값 없음(`map/`, `RegionMapHub.tsx` grep 0건) | — |
| AI | 회귀 컨텍스트가 `regData` 전체를 펼쳐 보낸다 (`aiContext.ts:44-45`). 그래서 `log_assessed_land_price` 계수·`linked_n` 이 AI 로 간다. 거래목록 탭은 AI 컨텍스트가 없다(`PaidMatrixYearlyModal.tsx:315-340`). 서버 라벨: `ai/dialogue.py:386, 520` 「개별공시지가」. |
| 관리자 전용(이미) | `/api/admin/parcel/*`(parcel_lab), `/api/admin/land-twin` — 이미 admin 게이트 안 | `/lab/` 의 Cheongju*Ledger* 랩 화면 |

`land_regression` 을 숨기면 회귀 쪽 대장 노출도 같이 사라진다. `land_ledger_link` 만 켜고 `land_regression` 은 끈 조합은 거래목록·CSV 만 남는다. 반대 조합(회귀 공개·대장 비공개)이면 `assessed_land_price` 변수만 거절하면 된다.

---

## 3. 캐시 위험

| 캐시 | 키에 권한? | 대상 기능 응답이 들어가나 | 위험 |
|---|---|---|---|
| `analysis_cache` (`paid.py:95 _make_cache_key`, `/api/paid/analyze` 만) | 없음(요청 본문+as_of+published_at) | **아니오.** `PaidAnalysisResponse` 에 대장 칸이 없다 | 지금은 없다. Phase B 에서 이 응답에 권한별 칸을 넣으면 키에 `gate_profile`(켜진 스위치 집합의 해시)을 넣어야 한다. |
| `analysis_base_cache` | 없음 | 거래 id 목록만 | 없다. 권한과 무관한 값이다. |
| 거래목록·CSV·토지/임대 회귀 | 서버 캐시 없음 | — | 없다. |
| 집합 라우터 `lru_cache`·`_CACHE` | 없음 | 대상 아님 | 없다. |
| Nginx | `/api/` 에 `proxy_cache` 없음. Cache-Control 은 정적 HTML 에만 있다 | — | 없다. `GET /api/features` 는 새로 `Cache-Control: no-store` + `Vary: Cookie` 를 붙여야 한다. 그래야 브라우저·중간 캐시가 관리자 응답을 다른 사람에게 주지 않는다. |
| 프론트 상태 | React state(`txData`, `regResult`, `traitEnrich`) · react-query(토지·집합 QueryClient, 메모리) | 화면에 남는다 | **같은 탭에서 권한이 바뀌면** 남는다. 예: staff 로그인 → 로그아웃. 관리자 때 받은 대장 값·회귀 결과가 로그아웃 뒤에도 그대로 보인다. Phase B: 기능 목록이 바뀌면 `queryClient.clear()` 와 모달 상태 초기화, 또는 로그인·로그아웃 시 새로고침. |
| AI 세션 (`ai/sessions.py`, 메모리) | owner=`user:{id}` 또는 익명 쿠키 | `context_snapshots`·`analysis_history` 에 회귀 facts 가 쌓인다 | 사용자가 바뀌면 owner 가 달라 새 세션이 된다. 그래서 관리자 → 사용자 누출은 없다. 남는 위험은 **클라이언트가 보낸 facts** 다. 비관리자가 숨긴 패널 이름(`LandRegressionTab`, `LandPredict`, rent `detail_tab=regression`)이나 `log_assessed_land_price` 를 직접 보내도 지금은 그대로 근거로 쓴다. Phase B 에서 서버가 걸러야 한다. |

**결론:** 지금 서버 응답 캐시에는 관리자 응답이 사용자에게 가는 경로가 **없다**. 대상 API 가 모두 캐시 없이 매번 계산한다. 위험은 ① 앞으로 `analysis_cache` 에 권한별 칸을 넣는 경우 ② 새 `/api/features` 의 HTTP 캐시 ③ 프론트 메모리 상태 ④ AI 가 클라이언트 facts 를 그대로 믿는 경우, 네 가지다.

---

## 4. 임대 → 집합 링크

### 4-1. 지금 집합 화면이 URL 로 열 수 있는 것

- `?region_level=…&region_code=…` → 지역 선택까지만 된다 (`useCollectiveDeepLink.ts`, `shared/macro-shell/regionDeepLink.ts`).
- `?view=regression&building_key=…&display_name=…&asset_type=…` → 레거시 별도 창(`pages/BuildingRegressionPage.tsx`). **단지 회귀 패널만** 열고 모달·효용지수 탭은 없다.
- 단지 모달(`BuildingDetailModal`)은 목록 행(`BuildingStatsRow`)이 있어야 열린다. 처음 탭을 고르는 prop 도 없다. 효용지수 탭 id 는 `floor_index` 이다(`BuildingDetailModal.tsx:84`).
- `GET /api/collective/buildings` 에는 `building_key` 필터가 없다(페이지 100행). 단지 한 곳의 행을 주는 API 도 없다. 효용지수 API 는 있다: `GET /api/collective/buildings/{key}/floor-index` (`collective/router.py:1019`).

→ **지금은 URL 로 단지 모달 + 효용지수 탭을 바로 열 수 없다.**

### 4-2. `rent_sale_building_map` 연결률 (로컬 DB, 읽기 전용, 2026-11-14)

- 맵: exact 만 있다. apartment 40,634 · officetel 11,841 · rowhouse 161,072. `built_on` = 2026-09-02.
- 대상: 임대 마트 `rent_building_stats` 의 as_of 2026-10, 5년 창.
- 키 규칙: 맵은 「양쪽 원장에 같은 `building_key` 해시가 있으면 연결」이다(`pipeline/rent/build_sale_building_map.py`). 그래서 매매 키 = 임대 키다.

| 유형 | 임대 단지 | 연결 | 단지 연결률 | 전세 거래 가중 | 회귀 가능 단지(전세 5년 ≥8건) 연결률 |
|---|---|---|---|---|---|
| 아파트 | 42,930 | 39,034 | **90.9%** | 93.2% | 96.0% (22,445/23,373) |
| 오피스텔 | 17,474 | 11,427 | **65.4%** | 90.9% | 83.1% (5,205/6,261) |
| 연립·다세대 | 193,343 | 145,897 | **75.5%** | 78.6% | 72.0% (11,823/16,428) |
| 단독·다가구 | 124,983 | 0 | 대상 아님(`JOIN_ASSETS` 밖) | — | — |
| **3유형 합계** | 253,747 | 196,358 | **77.4%** | — | **85.7%** (39,473/46,062) |

주의:
- 「회귀 가능」은 5년 창 전세 건수로 잡은 근사치다. 회귀는 실제로 전체기간 전세를 쓴다.
- 연결이 있어도 집합 쪽 효용지수가 계산 가능한지(층·면적 표본)는 따로 판정된다.
- 집합 2단계(P2)가 키를 옮기면 이 맵도 다시 만들어진다. P2 리허설 실측 c7: 연결 213,547 → 216,348, 분할 키 연결 1,474 중 일부만 이어짐 400·끊김 6, 다중 연결 0. 그래서 **링크는 P2 반영 후 키 기준으로 검증해야 한다.**

### 4-3. 구현 방안 (2개)

**안 1 (권장) — 집합 단지 딥링크 확장.**
- 링크 예: `/collective/residential/?region_level=…&region_code=…&building_key=<sale_key>&asset_type=…&detail_tab=floor_index`
- 백엔드: 단지 한 곳의 목록 행을 주는 `GET /api/collective/buildings/{key}/row`(또는 목록 API 의 `building_key` 필터)를 추가한다.
- 프론트: `useCollectiveDeepLink` 가 지역을 고른 뒤 그 행으로 `BuildingDetailModal` 을 연다. 모달에 `initialPanel` prop 을 추가한다. 상업·업무 쪽(`CommercialApp`·`CommercialClusterDetailModal`)도 같은 방식으로 맞춘다(주거·비주거 패리티).
- 임대 쪽: 회귀 탭 자리에 안내문을 둔다. 연결이 있으면 버튼 「같은 단지 매매 효용지수 보기」, 없으면 버튼 없이 안내만. 키는 `lookup_rent_key` 의 역방향(rent→sale) 조회를 쓴다. 목록 행에는 `sale_building_key` 가 없으므로 상세 열 때 조회하거나 목록 응답에 칸을 추가한다.
- C-05 허용 목록(`api_param_warn`)에 새 파라미터를 등록해야 한다.
- P2 의 `BuildingKeySplitGuard` 가 모달을 감싸므로, 옛 키·분할 키는 그쪽 안내를 그대로 탄다.
- 단점: P2 와 `frontend-collective/src/App.tsx`·`api/client.ts` 가 겹친다(§7).

**안 2 — 효용지수 단독 창.**
- `?view=floor_index&building_key=…&asset_type=…` 로 `BuildingRegressionPage` 같은 단독 페이지를 열고 `FloorIndexPanel` 만 띄운다.
- 장점: 목록 행·지역 선택이 필요 없다. `App.tsx` 를 건드리지 않아 P2 충돌이 적다(`main.tsx` 에 분기 한 줄 + 새 페이지).
- 단점: 모달·탭 UX 가 아니다. 「레거시 별도 창」 형식이 하나 더 생긴다. 사용자가 단지 다른 탭(롤링·거래)으로 넘어갈 수 없다.

권장: **안 1**. 단, 머지 순서는 P2 → admin-gates 로 하고, 안 1 의 `App.tsx` 수정은 P2 머지 후 그 위에서 한다.

---

## 5. 토지 회귀 대체 안내문 (초안)

- 2026-11-10 T 결정: 최종 공개 여부는 출시 전에 정한다. 기본값은 admin.
- 숨김 방식: 탭 버튼 자체를 숨긴다(빈 탭 + 안내문을 두지 않는다).
- 안내문을 둘 곳: 모달 탭 바 아래의 짧은 한 줄과, `LandMatrixTabsGuide` 의 탭 설명.

> **회귀 분석은 준비 중입니다.**
> 같은 칸의 거래로 면적·도로·연도 효과를 추정하는 기능을 검증하고 있습니다. 지금은 추이·장기추세·분포·거래목록으로 이 칸을 확인해 주세요.

공시지가(`land_ledger_link`)를 숨길 때 거래목록 「공시지가 표시」 자리:
- 권장은 **아무것도 두지 않는 것**이다(체크·열·CSV 열 미노출).
- 안내가 꼭 필요하면 한 줄: 「공시지가 연결은 자료 검증 중이라 지금은 표시하지 않습니다.」
- 주의: 이 문구도 「값이 있다」는 신호다. 그래서 출시 전 결정과 같이 정하는 것을 권한다.

임대 회귀 자리 안내문(참고, `rent_regression`):

> **전세 보증금 회귀는 준비 중입니다.**
> 같은 단지의 매매 거래로 본 층·면적 효용지수는 집합 분석에서 볼 수 있습니다. [같은 단지 매매 효용지수 보기]
> (연결이 없을 때) 이 건물은 집합 매매 자료와 연결되지 않았습니다.

---

## 6. 임대 504 메모 — 스위치를 걸 자리

현재 경로:
- `rent/router.py:424` / `:454` 엔드포인트
- `deadline: QueryDeadline = Depends(request_query_deadline)` → 90초 예산이 시작된다
- `heavy_query(...)` → `fetch_regression_rows`
- 시간 초과 시 503 + `REGRESSION_TIMEOUT_MESSAGE`(`rent/query_guard.py:21`)

스위치 자리:
1. **라우트 데코레이터 의존성**: `@router.post(..., dependencies=[Depends(require_feature("rent_regression"))])`
   - 데코레이터 `dependencies` 는 엔드포인트 인자 의존성(`request_query_deadline`, `get_rent_db`)보다 먼저 풀린다.
   - 그래서 비관리자는 **DB 세션을 열기 전에, 90초 예산을 쓰기 전에** 403 을 받는다.
2. **미들웨어 이중 방어**(권장): `product_gate.product_gate_response` 에 경로 규칙을 하나 넣는다. 대상은 `/api/rent/buildings/*/regression/run` 과 `/api/rent/regression/run`.
   - 이 미들웨어는 P2 `KeyRemapMiddleware` 보다 바깥에서 돈다(Starlette 은 나중에 등록한 미들웨어가 바깥).
   - 그래서 비관리자가 분할 옛 키로 요청하면 409 후보 목록 대신 403 이 먼저 나간다.
   - 의존성만 쓰면 KeyRemap 이 먼저 돌아 409(후보 목록)가 403 보다 먼저 나간다.
- 503 문구 수정과 A안(계산 키 전체 스캔 개선)은 이번에 하지 않는다(지시대로). 스위치를 넣은 뒤 관리자 실험 기능 개선 때 한다.

---

## 7. 집합 2단계(`data/collective-p2`)와 겹치는 파일

`git diff origin/main...data/collective-p2 --stat`(읽기만): 92파일. 그중 Phase B 와 닿는 것:

| 파일 | P2 변경 | Phase B 예정 | 충돌 |
|---|---|---|---|
| `backend/app/main.py` | `KeyRemapMiddleware` 등록 4줄(CORS 앞, 73행 부근) | `/api/features` 라우터 등록. 미들웨어는 추가하지 않고 `product_gate` 안에서 처리 | 다른 위치라 문자 충돌은 낮다. **순서 의미는 중요**하다(§6: gate 가 KeyRemap 보다 바깥) |
| `backend/app/collective/key_remap.py` (신규) | `/api/rent/buildings/{key}/…` 와 `/api/rent/…?building_key=` 를 다시 쓴다. 임대 회귀 두 경로도 포함 | 건드리지 않는다 | 동작 상호작용만 있다: 관리자 옛 키 → remap 후 회귀, 분할 → 409 |
| `backend/app/collective/router.py` | `GET /buildings/{key}/key-status` 추가(674행 부근) | 안 1 이면 `/buildings/{key}/row` 추가 | 근처 위치라 **중간** 위험. P2 다음에 추가하면 해소된다 |
| `backend/app/ai2/planner.py`, `ai2/live_floor.py` | `KEY_SPLIT` 사유·후보 표시 | AI2 는 랩 전용·운영에서 꺼져 있다 → **건드리지 않기를 권장** | 건드리면 `_REASON_KO` 같은 덩어리에서 충돌 |
| `frontend-collective/src/App.tsx` | `BuildingKeySplitGuard` 로 모달 감쌈(858-876행) | 안 1: 딥링크로 모달 열기·`initialPanel` | **높음**(같은 블록) |
| `frontend-collective/src/api/client.ts` | +29(key-status 등) | 안 1: 단지 행 조회 함수 | 중간 |
| `frontend-collective/src/pages/BuildingRegressionPage.tsx` | 분할 가드 반영 | 안 2 를 고르면 비슷한 새 페이지 | 낮음(새 파일) |
| `docs/ops/DEPLOY_PATHS.md` | +12 | 건드리지 않는다. 공개 절차는 새 문서 `docs/ops/FEATURE_GATES.md` | 없음 |
| 임대 DB `rent_sale_building_map`·`rent_building_key_map` | P2 마이그레이션이 다시 만든다 | 링크 키 조회만 한다 | 데이터 상호작용: 링크 검증은 P2 반영 후 |

`frontend-rent/`, `frontend/src/`, `backend/app/rent/`, `routers/paid.py`, `product_gate.py`, `admin_auth.py`, `shared/` 는 **P2 와 겹치지 않는다**(0파일).

---

## 8. Phase B 범위·예상 변경 파일

### 백엔드
- `backend/app/feature_gates.py` (신규)
  - 레지스트리 `{rent_regression, land_regression, land_ledger_link}`, 기본 `admin`
  - 환경변수 `FEATURE_<NAME>=public|admin|off` 로 덮어쓴다
  - `is_admin(request)`(role 또는 QA 토큰, `request.state` 에 1회 저장), `enabled(request, name)`, `require_feature(name)` 의존성(403 「관리자만 이용할 수 있습니다.」), `gate_profile(request)`(캐시 키용)
- `backend/app/routers/features.py` (신규) — `GET /api/features` → `{"features": [켜진 이름]}` + `Cache-Control: no-store`, `Vary: Cookie`. `product_gate._ALWAYS_OPEN_PREFIXES` 에 등록. `main.py` 에 include.
- `backend/app/product_gate.py` — 임대·토지 회귀 경로 403 규칙(§6).
- `backend/app/rent/router.py` — 회귀 두 라우트에 `dependencies=[require_feature("rent_regression")]`.
- `backend/app/routers/paid.py`
  - 회귀·suggest·predict 3개에 `require_feature("land_regression")`
  - 비관리자 `trait_enrich=true` → `land_ledger_link` 가 꺼져 있으면 403(목록·CSV)
  - `variables.assessed_land_price=true` → 403. 조용히 무시하지 않는다. 결과가 달라지기 때문이다.
  - 응답 만들 때 `TRAIT_ITEM_KEYS` 를 비관리자에게 넣지 않는다(이중 방어)
  - `_make_cache_key` 에 `gate_profile` 을 넣는다(지금 해당 칸은 없지만 예방)
  - C-05 경고 모드(`api_param_warn`)와는 별개 경로로 둔다
- `backend/app/ai/router.py` 또는 `ai/dialogue.py`
  - 비관리자 컨텍스트에서 숨김 패널(`LandRegressionTab`, `LandPredict`, rent `detail_tab=regression`)과 대장 facts(`log_assessed_land_price`, `linked_n` 등)를 버린다
  - `ai/knowledge/product.py`·`screen_guides.py`·`panel_capabilities.py` 의 회귀 안내 문구를 기능 상태에 따라 뺀다. AI 가 비공개 기능을 안내하거나 근거로 쓰지 않게 한다.
- 테스트(신규): `backend/tests/test_feature_gates.py`
  - 403/200 × 역할(익명·member·macro member·admin·QA 토큰)
  - 환경변수 덮어쓰기
  - `/api/features` 응답·헤더
  - 대장 칸 미포함
  - `assessed_land_price` 거절
  - AI facts 필터
  - 캐시 키 분리
  - 임대 회귀가 DB 세션 전에 403

### 프론트(5앱 패리티, 랩 제외)
- `shared/macro-shell/features.tsx` (신규) — `FeaturesProvider`·`useFeature(name)`. `/api/features` 1회 조회. 바뀌면 상태 초기화. 관리자 「비공개」 배지 컴포넌트.
- 토지 `frontend/src`
  - `main.tsx`(Provider)
  - `PaidMatrixYearlyModal.tsx`: 탭·공시지가 체크·동의 모달·CSV 옵션·회귀 변수 「개별공시지가」
  - `MatrixCellTransactionTable.tsx`, `LandPredictPanel.tsx`, `LandRegressionResults.tsx`, `LandMatrixTabsGuide.tsx`
  - `utils/landHelpPresentation.ts`, `constants/landStatsExplain.ts`
  - `api/aiContext.ts`: 숨김이면 컨텍스트를 만들지 않는다
- 임대 `frontend-rent/src`
  - `main.tsx`, `components/BuildingDetailModal.tsx`(탭 자리 안내문 + 집합 링크)
  - `utils/rentHelpPresentation.ts`(회귀 문구 분기), `api/client.ts`
- 집합 `frontend-collective/src` (안 1)
  - `hooks/useCollectiveDeepLink.ts`, `App.tsx`, `CommercialApp.tsx`
  - `components/BuildingDetailModal.tsx`·`CommercialClusterDetailModal.tsx`(`initialPanel`)
  - `api/client.ts`
- `shared/regression-ui/AnalysisSummary.tsx` — 대장 연결 줄은 서버가 칸을 안 주면 자동으로 사라진다(값이 없으면 렌더링 안 함). 확인만 한다.
- 복합·프로필·인사이트 — 대상 기능이 없다. Provider·배지 컴포넌트만 공통으로 붙인다(형식 패리티).

### 문서
- `docs/DECISIONS.md` D-085 (+ `docs/lab/decisions/D-085.json`)
- `docs/ops/FEATURE_GATES.md` — 공개 절차: 환경변수 → 재시작 → `/api/features` 확인 → 스모크
- `docs/CH2_ENTITLEMENT.md` 에 관리자 전용 줄 추가

### 순서·위험
- 머지 순서 권장: **P2 → admin-gates**. 안 1 의 집합 프론트는 P2 위에서 작업한다.
- 운영 로그인 관리자 = staff 로그인 또는 admin OAuth 계정이다. staff 세션이 짧으니 관리자 검증 시 세션 만료 → 기능이 사라지는 동작을 확인해야 한다.
- 로컬 개발: 로그인 없이 개발하면 기능이 숨는다. `.env` 에 `FEATURE_*=public` 로 켜는 방법을 문서화한다(`local_dev_access` 는 지금 동작하지 않음, §1).
