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
| D-010 | 2026-05-19 | **유료 복수지역 한도**: 유료는 단일 모든 레벨(법정동/리·읍면동·시군구·시도). 복수지역 실시간 집계는 읍면동/동/리 최대 10개; 시군구·시도 복수는 API·프론트에서 차단. ~~무료=법정동/리 단건~~ 은 **D-043에서 폐기**. |
| D-011 | 2026-05-19 | **쌍둥이 지역 찾기** 유료 기능 설계 확정: 시군구·읍면동 레벨, 가격 통계·거래량·인구·토지 구성 피처 벡터, 가중 유클리드 거리. 상세 설계: `docs/UPPER_STATS_DESIGN.md` §8. |
| D-012 | 2026-05-19 | **한자 병기·신설 분구 매핑 3단 방어** (`pipeline/clean.py`): ① 괄호 한자 정규화(`_normalize_admin_label`) + 리 주소 파싱(`_parse_address_structured`), ② 시도명 별칭(`전북특별자치도→전라북도` 등)·분구 토큰 drop(`화성시 만세구→화성시`) **fallback**, ③ **동명이리 한자 disambiguation** (정규화 이름이 같은 코드가 2 개 이상인 그룹에서 거래 원장의 괄호 한자와 `region_codes` 의 괄호 한자를 부분 포함 비교로 분기, `mapping_notes='disambiguated_hanja'`). 실측: ① + ② 로 `needs_review` 106,428 → 862 (-99.19%), ③ 으로 기암리·화산리 거래 241건 재분배. 적용 후 영향 단일 코드만 `land_basic_stats_v2` 재빌드 → `pipeline/remap_homonym_targets.py`. |
| D-013 | 2026-05-30 | **장기 연도별 추세(v1)**: `land_annual_stats` 사전 집계 + 유료 **필터분석 매트릭스 모달**「장기 추세」탭. **복수 지역은 지역별 시리즈**를 한 차트에 표시. **평균 모드**에서는 거래수 가중 통합선(Σn·평균/Σn)을 추가로 표시; **중앙값 모드는 통합선 없음**. 도로·면적·IQR 등 고급 필터 **미적용**. 설계: `docs/LONG_TERM_TREND_DESIGN.md`. |
| D-014 | 2026-06-10 | **Region · Property 아키텍처는 Post-MVP 장기 과제로 보류**. MVP(현 기능) 완성·6월 말 수정 반영 우선. Region/Resolution/Property/Transaction/Statistics 5층 모델·Property Registry SSOT는 **7월 업데이트 전** 재논의. 설계 초안: `docs/REGION_ARCHITECTURE_ROADMAP.md`. |
| D-015 | 2026-06-16 | **복합부동산 addr 정규화 — 리(法定里)를 항상 `addr5`로**: 구(區) 없는 시(市)에서 리가 `addr4`에 저장되어 `/regions/ri` 조회·3-way 회귀 비활성화되는 버그 확인. **import 레벨 정규화(방안 A)** 로 해결 예정. 상세: `docs/REGION_ARCHITECTURE_ROADMAP.md` §D-015. |
| D-016 | 2026-06-17 | **Regional Profile 중심 5-Layer Statistics 아키텍처**: Transactions → Object Stats → **Market Stats** (`upper_stats` 대체 개념) → **Regional Profile** (Feature Vector, 건물 미포함) → 회귀·쌍둥이·AI. 집합: `building_stats`(UI)와 `market_stats`(Profile) **분리**. 집합 모달 **Analysis Cohort**(다중 `building_key` 회귀·층·동 효용). 상세: [`docs/REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md). 브랜치: `feature/collective-work`. |
| D-017 | 2026-06-19 | **Regional Profile 설계 정련(검토 반영)**: ① **토지 domain은 대표시장 추출** — `ALL×ALL` 금지, `land_residential=2종주거×대`·`land_commercial=상업×대`·`land_industrial=공업×공장용지` (P0). ② **Profile A/B 검증은 다중 지역 pooling 필수** — 단일 지역은 절편과 공선이라 효과 0 (P0). ③ **Profile = 데이터 제품**: `regional_profile`에 `profile_version`·`window_years`·`feature_count`·`builder_version`·`validation_status` 추가, 고유 grain에 version·window 포함 (DDL `db/025_regional_profile.sql`). ④ **Twin·AI는 Profile을 소비**(계층 분리) — Feature 재생성 금지, `(profile_version, as_of, window)` 고정 조회. ⑤ **region_code 8/10자리 SSOT 통일**, DB 접속 **환경변수 일원화**. **문서가 설계 SSOT**(코드 선행 금지). 빌드 구현은 추후. 상세: [`docs/REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) §7.0. |
| D-018 | 2026-06-19 | **비주거 집합부동산 재구축 착수(Phase 0)**: ① **입력 SSOT** = `raw/raw base/{상업업무\|공장창고}_2021_2026` MOLIT CSV, **`유형=집합`만** (`일반`→built). ② **분석 grain** = **도로명 cluster** (`cluster_key`) only. ③ 주거 재구축 패턴 따름: ingest → meta → cluster mart. ④ Legacy GUKTO xlsx는 `--source gukto` fallback, default **`molit`**. ⑤ Phase 3에서 주거 회귀·효용지수 개선 commercial 이식. 상세: [`docs/COLLECTIVE_COMMERCIAL_REBUILD_PLAN.md`](COLLECTIVE_COMMERCIAL_REBUILD_PLAN.md). |
| D-019 | 2026-06-20 | **비주거 집합 재구축 Phase 0~4 완료**: ① **장기 추세** — `raw/raw long term` 집합만 → `collective_cluster_annual_stats` (2010~2020) + transactions (2021~). ② API `stats/by-year` mart-first·`data_source`. ③ UI 코호트(롤링·분포·거래·회귀·장기)·회귀 PI. ④ `finish_collective_commercial.py` Promote 게이트. VPS Promote는 운영자 지시 시. |
| D-020 | 2026-06-20 | **비주거 집합 — 건물 grain 계획 제외**: MOLIT 마스킹 번지·표본 부족으로 **`building_key` / `building_key_v2` 기반 건물 단위 분석은 구현·로드맵에서 제거**. 분석 해상도 = **도로 cluster만** (`COLLECTIVE_COMMERCIAL_DESIGN.md`). DB `building_key` nullable 컬럼은 스키마 호환용 유지. |
| D-021 | 2026-06-20 | **Regional Profile 충북 파일럿**: 전국 확장 전 **시도 43 End-to-End** 반복. `profile_version=v1.0-chungbuk`, land domain 추출 SSOT=`pipeline/config/land_domain_extraction.yaml`, 빌드=`rebuild_regional_profile_chungbuk.py`. 물리 토지 GIS·고용 등 **추가 외부 데이터는 v2 후보** — v1은 거래 통계+인구+거래비중 파생. |
| D-022 | 2026-06-20 | **Regional Profile 전국 Phase 1**: 충북 단독 회귀 A/B로 Profile 효과 결론 내리지 않음. **`v1.1-national`** 전국 Profile → **`build_twin_from_profile.py`**(Profile 소비, algorithm_version=5) → 복합 회귀 pooling(1안 AI 제안·2안 원격 유사)은 **Twin 이후**. orchestrator=`rebuild_regional_profile_national.py`. |
| D-023 | 2026-06-20 | **Twin 하이브리드(v1.2)**: Profile-only Twin(v5)은 API·SSOT 검증용. **제품 Twin** = 토지 legacy **50%** + 집합 market **30%** + Profile **20%** (composition 중복 회피). 장기: 블록을 Profile feature로 흡수 후 Twin은 Profile-only 복귀. 상세: [`docs/PROFILE_TWIN_HYBRID.md`](PROFILE_TWIN_HYBRID.md). |
| D-023b | 2026-06-21 | **Hybrid Twin v2 정련**(리뷰 반영): 전 블록 [0,1] 통일, 집합=구성비 cosine+아파트가 pairwise log-sim(z-score 폐기), Profile 가격 제거(인구·밀도만, 가격 3중 counting 회피), 결측=시장없음(평균 대체 금지), 집합 신뢰도 기반 적응형 가중치(남는 비중 토지·Profile 재분배), reason_codes 설명성, 스모크 후보풀=anchor+인접 시도. `detail.algorithm=hybrid_v2`. |
| D-025 | 2026-06-29 | **불변 Master + Exception Queue + Correction Rule Engine**: `land_transactions`(Master)는 절대 수정하지 않는다. MOLIT CSV 동일 거래에 용도지역·지목이 다른 duplicate 발생 시 → `land_exception_queue`에 격리 → 운영자가 확인 후 `land_correction_rules`에 Rule 등록 → `land_transactions_resolved` VIEW에서 자동 반영. 이 경로를 통해서만 분석·mart 기준값을 보정하며, Rule 삭제 시 즉시 원본 복원. `build_stats_v2`·`build_upper_stats_v2`는 `land_transactions_resolved` 기반으로 전환. 기존 `detect_land_exceptions.py --execute`로 전국 1,235건(zone 427 + land_category 808) 초기 적재 완료. DDL: `db/034`, `035`, `036`. |
| D-026 | 2026-06-30 | **토지 지목군(`jimok_group`) 7분류**: 농경지·산림지·개발지·기반시설·수면·특수용도·기타. **원장 Master 불변** — `land_jimok_group_map` + VIEW + **원장 단가 재집계** mart. **UI:** 기본=**용도×지목**, 옵션=**용도×지목군**(대체 아님). Profile·Twin Feature 연결은 후속. 광천지·염전→⑥; **(2026-07-17) 양어장·목장용지→① 농경지**. SSOT: [`LAND_JIMOK_GROUP_DESIGN.md`](LAND_JIMOK_GROUP_DESIGN.md). |
| D-024 | 2026-06-21 | **복합부동산(일반 3유형) 원장 재구축(Phase A)**: ① **SSOT** = `raw/raw base/{상업업무\|공장창고\|단독다가구}_2021_2026` MOLIT CSV, **GUKTO 무시**. ② 상업·공장 **`유형=일반`**, 단독 전량. ③ **해제 제외**, **semantic hash dedupe** 유지. ④ **`road_width_label`** 원문 저장, **`road_code` 정수 변환 폐기**. ⑤ 주소 표시 ingest 규칙 **B** (리·번지 마스킹·도로명). ⑥ **`region_codes`** = land sync (집합·토지 재구축 동일). ⑦ **Phase A = 원장만**; 회귀는 **총액 linear 기본**(집합 회귀 미참조), log·통합·UI는 Phase B. ⑧ **`as_of_month`+3·5년** = Macro 공통(D-001), mart는 Phase B. 상세: [`docs/BUILT_LEDGER_REBUILD_PLAN.md`](BUILT_LEDGER_REBUILD_PLAN.md). |
| D-028 | 2026-07-21 | **지역코드 3계층 (raw / historical / canonical)**: ① 원장·raw 원본코드(또는 주소)는 보존. ② 분석·사전집계·GIS 정규화·Profile·Twin은 **현행 canonical만**. ③ 읍·면 승격 시 **이름만 바꾸고 폐지 코드를 활성 canonical로 남기는 수리 금지** (`repair_eup_myeon_promotion` 패턴 폐기). ④ 마스터 존재/폐지 불일치는 **구→현행 건별 매핑**(`region_code_history`); 1:N `split`은 자동 치환 금지. ⑤ Profile·Twin 착수 **전** Phase 1(분류→history→seed→stats 재빌드→GIS resolve) 완료. ⑥ **토지 Land finish(2026-07-21)**: basic+upper+annual canonical, 공통 모듈 `pipeline/region_canonical.py`(Built/Collective 공유). unresolved 2건 제외. Phase 1a: [`docs/reports/REGION_CODE_PHASE1A_CLASSIFICATION.md`](reports/REGION_CODE_PHASE1A_CLASSIFICATION.md). ⑦ **Resolver 완성(2026-08-04)**: Stateless pure core(`resolve_to_canonical`·`expand_to_ledger_codes`·`normalize_result_codes`·`is_canonical`); user-facing raw historical 반환 금지; 8자리 eup prefix remap; property/API contract tests + `verify_canonical_resolver_migration.py`. 상세: [`docs/REGION_CODE_LAYERS.md`](REGION_CODE_LAYERS.md). |
| D-027 | 2026-07-25 | **Regional Profile v2 제품화(소급 기록)**: ① 독립 SPA `frontend-profile` (`/profile/`) — 토지 앱 내장 ProfilePanel·`viewMode=profile` **폐기**. ② `yearly_mix` 8대 시장유형 3개년 건수·금액(상가·공장은 Profile 집계에서만 병합). ③ `jimok_group` 구성·TOP3(지목군 합산 — D-029에서 용도×지목군으로 교체). ④ `profile_version=v2.0-national`. ⑤ Macro 공통 헤더·딥링크. 상세: [`REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) §12.1. |
| D-029 | 2026-07-25 | **Region Profile SSOT + Twin-on-Profile**: ① DB에는 **`regional_profile`만** (Core Domain). **Feature Vector는 Catalog 기준 런타임 투영·비저장**. ② 시군구·읍면동·리 동일 스키마(시·도/`city` Twin 제외). ③ NULL≠0 — yearly_mix 0; 아파트 **최근3년 ㎡당** P25/P50/P75·없으면 NULL. ④ mask · Top1~3 컬럼 · 대표시장 Feature. ⑤ 파이프라인: **Candidate → Feature Catalog → Vector → Weight → Similarity → Top-N → Explainability**. ⑥ **`profile_feature_catalog.yaml` `twin_vector`** + **`profile_weight.yaml`** (Phase A 종료 전·가중치 코드 하드코딩 금지). ⑦ `region_scope_master` · Similarity Engine(`score_detail`). ⑧ `profile_version` (D-017). ⑨ **제품 `window_years=3`만** (토지 mart 3·5와 분리). ⑩ **Phase A→B** · 이후는 튜닝 중심. Twin v8 병행. 상세: [`REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) **§12**. |
| D-030 | 2026-07-27 | **Profile Phase B Preflight (구현 대기)**: ① **지역 선택** — 토지 `RegionSelector`와 tier·검색·딥링크 동일; beop 선택 시 Profile도 **`beopjungri` grain 유지**(eup 승격 폐지). ② **리 아파트 분위** — beop grain `market_stats` + **`apartment_count>=15`(3년)** 시 P25/P50/P75; **eup proxy 금지** 유지; Twin `apartment_profile` mask 연동. 상세: [`docs/REGIONAL_PROFILE_PHASE_B_PREFLIGHT.md`](docs/REGIONAL_PROFILE_PHASE_B_PREFLIGHT.md). |
| D-031 | 2026-08-02 | **후보모형 경쟁 문서 체계 채택**: ① **Vision** [`CH2_MACRO_VISION.md`](CH2_MACRO_VISION.md) — Profile은 가설·Validation이 판단. ② **Architecture** [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) §0 Candidate·Validation OS. ③ **상세** [`CANDIDATE_EVALUATION_DESIGN.md`](CANDIDATE_EVALUATION_DESIGN.md). ④ **로드맵** [`CH2_MACRO_IMPLEMENTATION_ROADMAP.md`](CH2_MACRO_IMPLEMENTATION_ROADMAP.md) V1~V3. Profile 도메인 SSOT는 [`REGIONAL_PROFILE_ARCHITECTURE.md`](REGIONAL_PROFILE_ARCHITECTURE.md) 유지. |
| D-032 | 2026-08-07 | **복합 모형 추천 — 기본 통계 vs 추천 변수 역할 분리**: 기본 통계는 사용자 변수·스케일; **`POST /built/regression/recommend`** 는 SSOT 서버 풀 탐색. 왼쪽 체크와 다른 결과는 **버그가 아님**. SSOT: [`CH2_RECOMMENDATION_ENGINE_DESIGN.md`](CH2_RECOMMENDATION_ENGINE_DESIGN.md). |
| D-033 | 2026-08-07 | **복합 `analysis_scope` SSOT**: 지역·기간·필터는 `/run`·`/recommend` 공유; **`anchor_region_code`·`region_unit_hints`** 로 anchor·표시명 보존. **`scope_n_tx` / `selection_n` / `fit_n`** 3종 n 라벨. |
| D-034 | 2026-08-07 | **단계형 Twin pool (식 고정)**: 1단계 Local 최적 **`blocks`+`response_scale` 고정** → 2단계 Profile Twin pool만 확장. **`/regression/suggest`·`/compare` deprecated** — successor `/regression/recommend`. |
| D-035 | 2026-08-07 | **만족 등급 — 고정 CV % UI 금지**: Excellent~Poor + ★; lookup [`recommendation/satisfaction/built.json`](../backend/app/recommendation/satisfaction/built.json). CV 50% 같은 제품 임계값 **두지 않음**. |
| D-036 | 2026-08-07 | **「추천」≠ 예측 채택**: UI는 **모형 탐색**·`conclusion.verdict`; CV-MAPE &gt;60 **예측 부적합** 시 adopt는 **검토용**만. |
| D-037 | 2026-08-07 | **Twin 2단계 사용자 opt-in**: `/recommend` 기본 stage1 only; `run_stage2=true` 또는 UI 「Twin pool 검토」클릭 시 2단계. |
| D-038 | 2026-08-08 | **월간 integrity 검증 grain SSOT**: `verify_monthly_integrity.py` 의 V2 중복 검사 grain은 **DB UNIQUE constraint와 동일**해야 한다 (`col_axis` 등 분석 축 포함). category/group 등 **동일 mart 테이블 내 병행 축** 도입 시 검증 SQL·DDL을 함께 갱신. **`golden_monthly_integrity.json`** 의 `ledger_exact` 등 앵커는 정상적인 거래 추가·삭제 시 **해당 fixture만 명시적으로** 갱신(`--update-golden` 일괄 남용 금지). 2608 cycle: V2 183k false positive = 검증 SQL 누락, 비하동 보녹·답 2→3 = fixture stale. |
| D-039 | 2026-08-09 | **2608 토지 Promote — 코드 배포와 DB 분리**: git push·`deploy-from-windows.ps1` 만으로는 **토지 7월 미반영**. 필수 순서 = (1) `run_land_cycle_csv.py --cycle-id 202608` 로 **원장 ingest + mart**, (2) `verify_monthly_integrity`, (3) **`land_stats` dump → VPS restore**, (4) `STATS_V2_DEFAULT_AS_OF_MONTH=2026-07-01`. mart-only 재빌드는 **원장에 7월 거래 없으면 무의미**. VPS Promote: PG18 custom dump는 PG16 `pg_restore` 불가 → PG18 bin 또는 `dump_land_for_promote.py` plain SQL.gz. SOP §9.4. |
| D-040 | 2026-08-15 | **주거 전월세 전환율 연구 종료.** `r_selected = mean_simple` 확정. 서울 4방법+hold-out 후 산식 재실험·연립 전용식 금지. REB/5% 고정 아님. SSOT: [`RENT_CONVERSION_EXPERIMENT.md`](RENT_CONVERSION_EXPERIMENT.md). |
| D-041 | 2026-08-16 | **Twin은 회귀 변수가 아니라 지역시장 비교 엔진.** Twin score를 회귀 X에 넣지 않음. Stage2 pool은 Local 대비 CV-MAPE가 ε 이상 개선될 때만 검토. 카드: [`lab/decisions/D-041.json`](lab/decisions/D-041.json). |
| D-042 | 2026-08-16 | **지역 QA 검증 엔진.** 숫자는 SQL·생산 빌더가 만들고 LLM은 해석만. 관리자 수동·원장/마트 WRITE 금지. 카드: [`lab/decisions/D-042.json`](lab/decisions/D-042.json). 계획: [`QA_REGION_AUDIT_PLAN.md`](QA_REGION_AUDIT_PLAN.md). |
| D-043 | 2026-08-16 | **무료/유료 5앱 통일.** 같은 UI·산식. 무료=어느 결이든 **지역 1곳·5년만**. 복수·AI·회귀/추천/Twin pool·CSV 없음. `?` 유지. 모달은 같은 껍데기, 유료 탭은 숨기지 않고 「유료」잠금. 랩은 관리자(유료 아님). 서버 강제. 토지 「무료=법정리」·무료 탭 **제거**. SSOT: [`CH2_ENTITLEMENT.md`](CH2_ENTITLEMENT.md). 카드: [`lab/decisions/D-043.json`](lab/decisions/D-043.json). |
| D-044 | 2026-08-16 | **Twin Engine V2.** V1 마트·카탈로그 유지. 거리 엔진(클러스터·ML 금지). 비교 Twin(구조 0.6/시장 0.4, 권역) · 풀 Twin(구조 0.4/시장 0.6, 시군+인접+n-hop). 인구 \|Δlog\|≤log(2). 지목군 7벡터 주력. 없음≠0점(가격 블록 제외). 신뢰도 별도. 가중 YAML 초기값. **제품 Twin 카드 V1 대체는 보류**(2026-08-16). SSOT: [`TWIN_ENGINE_V2.md`](TWIN_ENGINE_V2.md). 카드: [`lab/decisions/D-044.json`](lab/decisions/D-044.json). |
| D-045 | 2026-08-19 | **신규아파트 M2는 대전 잠정.** 충북 복제 후 같은 대전 hold-out이 13.2%→15.4%로 나빠져 통합 식 채택 안 함. M4 금지. **다음 제품 = 복합 회귀실험 UX 차용**(기초통계 유지, 지역회귀, 단지 1행, 개별 평균예측). 2026-08-26: 지역회귀는 값이 있으면 T·P 포함, 시공사·구조 결측은 미상 더미. 카드: [`lab/decisions/D-045.json`](lab/decisions/D-045.json). |
| D-046 | 2026-08-20 | **복합 마스킹 지번 복원 = 연면적 완전일치.** 청주 단독다가구 76.4%·상업업무 78.7%·공장창고 60.0% 확정(도로명·사용승인연도 독립 검증 ~99%). **A1·A2만 확정**, B tier(±1%·필지 합산) 폐기. **대지면적 필수 금지**(표제부 보유율 42.6%, 걸면 25%p 손실). 미확정은 다수결·최근접으로 메우지 않고 빈칸. 복원 지번은 화면 노출이 아니라 용도지역·구조·토지 **결합 키**. 2026-06의 11%·2.8% 결론은 재현 불가로 갱신. **보강은 단독다가구만 착수** — 구조·용도지역·층수로 hold-out MAPE 33.1%→29.0%(Adj R² 0.729→0.769). 상가는 41.5%→41.0%로 근거 부족(용도지역이 이미 원천에 있음), 공장은 hold-out 115건으로 판단 불가. SSOT: [`BUILT_MASKED_ADDRESS_RECOVERY.md`](BUILT_MASKED_ADDRESS_RECOVERY.md). 카드: [`lab/decisions/D-046.json`](lab/decisions/D-046.json). |
| D-049 | 2026-08-23 | **복합 지분거래.** 목록은 전체 표시+지분 열. 건수·금액 합은 포함. 단가·회귀·예측은 기본 제외, 분석 체크 시 포함. 단독은 원천 칸 없음. 토지 앱 기본값은 유지. 복원 매칭에서 지분은 확정하지 않음. SSOT: [`BUILT_SHARE_TRANSACTION_POLICY.md`](BUILT_SHARE_TRANSACTION_POLICY.md). 카드: [`lab/decisions/D-049.json`](lab/decisions/D-049.json). |
| D-050 | 2026-08-25 | **축약대장 축 승격 · 복합 SQL 이관 게이트 2019+ 75.0%.** 노출은 D-051. 카드: [`lab/decisions/D-050.json`](lab/decisions/D-050.json). |
| D-051 | 2026-08-26 | **속성 보강 노출.** 동의 4문장 · 표시=필터 · 원장 `zone_type` 미덮기 · 목록 배지. 운영 promote는 P5. 카드: [`lab/decisions/D-051.json`](lab/decisions/D-051.json). |

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

**유료 열만 유효.** 무료=법정동/리 단건은 D-043에서 폐기. 통일 무료는 [`CH2_ENTITLEMENT.md`](CH2_ENTITLEMENT.md) (어느 결이든 1곳·5년).

| 요청 레벨 | 유료 |
|-----------|------|
| 법정동/리 (10자리) | 최대 10개 (실시간 집계) |
| 읍면동 (8자리) | 단건 1개 (사전집계) |
| 시군구 (5자리) | 단건 1개 (사전집계) |
| 시도 (2자리) | 단건 1개 (사전집계) |

- `_MAX_STATS_REGIONS`: 유료 10 (법정동/리 한정).
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
- **제품 비전:** [`CH2_MACRO_VISION.md`](CH2_MACRO_VISION.md)
- **후보·검증 상세:** [`CANDIDATE_EVALUATION_DESIGN.md`](CANDIDATE_EVALUATION_DESIGN.md)
- **구현 로드맵 V1~V3:** [`CH2_MACRO_IMPLEMENTATION_ROADMAP.md`](CH2_MACRO_IMPLEMENTATION_ROADMAP.md)
- Regional Profile · Twin-on-Profile: `docs/REGIONAL_PROFILE_ARCHITECTURE.md` §12 (D-027·D-029)
- **복합 모형 추천 SSOT:** [`CH2_RECOMMENDATION_ENGINE_DESIGN.md`](CH2_RECOMMENDATION_ENGINE_DESIGN.md) (D-032~D-035)
- Twin v8 (병행·후속 전환): `docs/TWIN_V8_DESIGN.md`
- 정제 정책: `LAND_CLEANING.md`
- 다음 작업: `NEXT_STEPS.md`

## D-032 기본 통계 / 모형 추천 변수 분리

- **기본 통계** (`POST /built/regression/run`): 사용자가 체크한 변수·선택한 linear/log/log-log.
- **모형 추천** (`POST /built/regression/recommend`): 서버 SSOT 블록 풀에서 탐색; 사용자 체크 **무관**.
- UI: 사이드바 「모형 추천은 아래 체크와 무관」안내.

## D-033 analysis_scope SSOT

- `POST /built/regression/scope` · `/run` · `/recommend` 공통 `analysis_scope` 객체.
- n 라벨: **거래**(scope_n_tx) · **탐색**(selection_n) · **적합**(fit_n).

## D-034 단계형 Twin · legacy API deprecate

- 1단계: SSOT universe dual rank. 2단계: 1단계 식 고정 + Twin pool.
- `/regression/suggest`, `/regression/compare`: `Deprecation: true` + JSON `deprecated: true`; successor `/regression/recommend`.
- 프론트: `RecommendationModal` (구 ModelExploreModal).

## D-035 만족 등급 (고정 CV % 금지)

- lookup JSON per asset_slice; UI는 Excellent~Poor + ★.
- `proceed_twin`은 grade≤fair 등 **운영 보정** 규칙.

## D-036 탐색 결과 vs 예측 채택

- API `conclusion`: verdict·CV fitness tier·summary_ko.
- `no_predictive_model` → headline 「예측용 모형으로는 부적합」; 버튼 「검토용으로 적용」.

## D-037 Twin 2단계 opt-in

- `RegressionSelectionRequest.run_stage2` 기본 false.
- `twin_recommended`일 때만 UI CTA; 극소 n도 **자동 실행하지 않음** (강력 권장 문구만).

## D-047 복합 데이터 보강 — 매칭 인증·스냅샷 합집합·enrichment 스키마

- 매칭 규칙은 D-046 유지. 재현은 `pipeline/built/recover_address.py`.
- **표제부는 거래월에 가장 가까운 과거 스냅샷 1본**으로 A1/A2. 실패 시에만 다른 본, 필지 충돌은 미상 (`time_fallback`). 충북 **82.1%** · 서울 **68.8%**. 합집합은 대조군(충북 81.8%·충돌 107, 서울 68.3%·충돌 283) — 가락 146-6·호암 132-4는 합집합이면 미상, 시점 1본이면 정답.
- **충북·서울 두 지역 인증.** 순수 매칭 오류 **0.3~0.4%** (문턱 2%). 보정 매칭 정확도 91~97%, 구조 기대 98.6~98.9%. 커버리지만 지역차가 크다.
- **검증축은 도로명·사용승인연도만.** 용도지역은 판별력 없음(혼입 충북 86.7%·서울 71.0%).
- 용도지역은 `zone_labels` **배열** — 필지 복수 용도지역 충북 8.7%·서울 9.4%(지역차 없음). 화면 병기안은 미정.
- 단독다가구 용도지역 원장 0% → 충북 80.8%·서울 61.6%. 토지대장은 도시권에서 더 중요(A2 기여 서울 67%·충북 41%).
- **버그: AL_D155 대분류 라벨이 채움값으로 샜다.** 「도시지역」을 코드로 걸렀는데 코드 체계가 **시군구 단위로** 달라 서울 34.2%·충북 0.4%(91건이 진천군)가 용도지역 값으로 대분류를 가졌다. 라벨 이름 기준으로 수정.
- **교훈:** 매칭 지표는 멀쩡했고 충북은 집계도 안 움직였다. 검증로봇에 「채운 값이 상위 분류면 실패」를 **0건 조건**으로(비율 문턱은 0.4%를 통과) 넣고, 코드 기준 필터는 폐기한다.
- `built_transaction_enrichment` 신설, 원장 무수정, 미상은 행을 만들지 않음. 앱 복제 없음.
- D-046의 "단독다가구만 착수" 갱신 → 세 유형 모두.
- **마스킹 해제·건축구조는 표제부 조인.** 위성·로드뷰로 구조를 판정하지 않는다. 지번 외부 근거는 KAIS 28건. 150×2 로드뷰 구조 감사는 착수 게이트에서 제외 (2026-08-23).
- 상세: [`BUILT_DATA_ENRICHMENT.md`](BUILT_DATA_ENRICHMENT.md) · [`lab/decisions/D-047.json`](lab/decisions/D-047.json)

## D-048 용도지역 원천은 AL_D155 고정 · 축약대장 착수 조건

- **건축HUB 「지역지구구역」 대장을 쓰지 않는다.** 현행판(1,745MB·810만 행)을 확보해 실측했고 형식은 좋았다(구분 컬럼 명시·전국 18시도·통합 신코드).
- **내용이 현행 용도지역이 아니다.** 용도지역 행의 **89.4%가 2022년 생성 후 미갱신** — 「건축 인허가 당시」 자료이고 도시계획 변경을 따라가지 않는다.
- AL_D155 대조: 용도지역을 주는 필지가 서울 55.9%·충북 65.0%이고 그중 불일치가 서울 36.4%·충북 25.3%. **결국 옳은 값은 서울 35.5%·충북 48.5%뿐**(AL_D155는 100%).
- 「일반주거지역」 63만 행 등 2003년 세분화 이전 라벨이 남고, **제2종을 제1종으로 주는 사례**가 있다 — 용적률이 달라 가격에 직결되는데 라벨만 보면 정상이라 D-047의 대분류 0건 규칙으로도 안 걸린다.
- **AL_D155 시도별 수집을 계속한다.** 40GB → 411MB 절약은 없다. 검증축으로도 안 쓴다(D-047에서 이미 배제).
- **착수 조건:** 표제부 3스냅샷·총괄·K-apt는 확보 완료. **`AL_D155`·`AL_D003` 16시도 전부 확보**(2026-08-22 인벤토리). 전남광주 폴더·법정동 모두 통합코드 `12`.
- **집합 Track B 파일럿** — 로컬 `parcel_master`, 표제부 「집합」 대전·충북 3스냅샷. 대조 JSON [`lab/parcel_master_pilot_contrast.json`](lab/parcel_master_pilot_contrast.json). **pnu_new 22단지:** 약칭 14곳은 `pnu_unique`(tier P)로 목록 세대수·시공사만 채움. 재건축 2·묶음 6은 안 붙임. **pnu_no_kapt:** 표제부 동 합산(tier T) 854단지, 시공사 없음. 지역회귀는 A·B·C 유지. AL_D155 48GB·복합 enrichment는 구조 감사 후.
- 재현: `pipeline/built/_tmp_shtreg_probe.py` · 상세: [`PARCEL_MASTER_DESIGN.md`](PARCEL_MASTER_DESIGN.md) §6.3·§8.0 · [`lab/decisions/D-048.json`](lab/decisions/D-048.json)

## D-049 복합 지분거래 — 목록 전체 · 단가·회귀 기본 제외

- **거래는 숨기지 않는다.** 면적 정의가 필요한 분석의 기본 표본만 일반 거래를 쓴다.
- 상업·공장 일반 지분 **7.1%**(상업 8.1%·공장 4.8%). 단독 CSV에 지분 칸 없음.
- 목록: 지분 열/배지. 건수·금액 합: 기본 포함. 중위·㎡당·회귀·예측·Twin 가격 게이트: 기본 제외.
- 분석 전용 「지분거래 포함」체크(기본 해제). 면적 표본필터와 분리해 목록을 숨기지 않음. 체크 시 짧은 확인 팝업. n에 제외·포함 건수 표시.
- 토지 앱(포함이 기본)은 변경 없음. 등기 전용으로 국토부 연면적을 덮어쓰지 않음. 마스킹 복원에서 지분 건은 매칭하지 않음.
- SSOT: [`BUILT_SHARE_TRANSACTION_POLICY.md`](BUILT_SHARE_TRANSACTION_POLICY.md) · 카드: [`lab/decisions/D-049.json`](lab/decisions/D-049.json)

## D-050 축약대장 축 승격 · 복합 경로 이관 · 2019 게이트

- 축약 DB에 「일반」 표제부·AL_D151을 넣어 4대 원본을 담는다. `parcel_master`는 로컬 전용, 결과만 promote.
- 복합 매칭 SQL 이관 게이트: **2019+ 498,568행 · 75.0% · A1/A2 동등.** 전 기간 604,422 금지.
- 보강은 계약 2019년 이후. 2018년 이전 105,854행 DELETE(범위 축소).
- `ledger_snapshot`으로 미상 재시도 판정. 확정 행 재매칭 금지. 월간 창은 해시 유지 UPSERT. CASCADE로 보강 삭제 금지.
- 제품 용도지역은 대표 1개. 공시지가 제품은 최신 대표 필지. 원본 삭제는 게이트 후.
- 노출은 D-051. 월간 SSOT [`PARCEL_MASTER_MONTHLY_UPDATE.md`](PARCEL_MASTER_MONTHLY_UPDATE.md) · 구현 [`PARCEL_MASTER_IMPLEMENTATION.md`](PARCEL_MASTER_IMPLEMENTATION.md) · 카드 [`lab/decisions/D-050.json`](lab/decisions/D-050.json)
- 보완(같은 날): 명칭은 PNU 부동산 속성 DB. 수요 필지 적재. 저장소 3층(원장/속성/매칭). 주기 독립. 동결 DO NOTHING, 값 변경은 버전 행+승인. 연속 점수·전유부·land_stats 흡수·자동 `is_current`·39M 필지는 범위 밖.

## D-051 속성 보강 노출 — 동의 · 표시=필터 · 원장 미덮기

- 원장 `zone_type`을 UPDATE하지 않는다. 보강은 LEFT JOIN.
- 기본 끄기. 켜면 목록·CSV·회귀가 **같은 표시 용도지역**을 필터에도 쓴다. 기본통계 마트는 MOLIT-only.
- 동의 4문장: 2019+ 75.0% · 표제부는 이후 대장 기준(최대 7년 6개월) · 대표 용도지역 49.4% · 인증 서울·충북.
- 목록 배지 「건축물대장 확인」(A1/A2). 복원 지번은 칸에 안 넣음(D-046).
- 집합 목록: K-apt / 표제부 / 미연결 / 조인주의. 「경고 없음」이 아니다.
- 운영 promote는 P5. 카드: [`lab/decisions/D-051.json`](lab/decisions/D-051.json)


