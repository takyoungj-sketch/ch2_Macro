# 집합 2단계 Phase B — 코드 수정·테스트 보고 (2026-11-12)

- 근거: [Phase A 보고](COLLECTIVE_P2_PHASEA_REPORT_20261112.md) + T 결정(2026-11-12, 7개 채택 + 조건 5개).
- worktree `D:\ch2\ch2_Macro-collp2`, 브랜치 `data/collective-p2`. merge·배포·push 없음.
- **DB 쓰기 없음.** 실제 로컬 DB(collective_stats·built_stats·rent_stats)는 읽기 전용 드라이런·측정만 했다. 쓰기 테스트는 테스트가 직접 만들고 지우는 임시 DB `ch2_p2r_fixture`에서만 했다(끝난 뒤 `pg_database`에 `%p2r%` 0건 확인).
- 운영 DB·배포: 손대지 않음(조건 5).

## 바꾼 것

| 영역 | 파일 | 내용 |
|---|---|---|
| 분할 목록(고정) | [`pipeline/collective/data/p2_split_units.csv`](../../pipeline/collective/data/p2_split_units.csv) · 생성 [`b1_split_decide.py`](../../scripts/lab/collective_p2/b1_split_decide.py) | 키 해시·법정동8·조각 번호·결정·사유만(지번 없음). 1,531키 split → 3,447키, 12키 keep |
| 키 규칙 | [`building_keys.py`](../../pipeline/collective/building_keys.py) | `building_key_raw_series`(기존 원문 그대로) · `split_key_from_raw` = sha256(원문 + `\|emd:` + 조각 대표 법정동8) · `apply_building_key_split`(목록 키만, 원문이 키를 재현할 때만) · `CH2_COLLECTIVE_KEY_SPLIT=0` 비상 해제 |
| 적재기 | `collective/import_refined.py`, `rent/import_molit.py` | 법정동 코드 부여 **뒤** 분할 적용(집합 주거·임대 같은 규칙 → 같은 새 키) |
| 행정명 정규화 | [`pipeline/admin_names.py`](../../pipeline/admin_names.py), `collective/refine.py`, `built/refine_built.py` | 옛 시도명(광주광역시·전라남도) → 전남광주통합특별시, 키 생성 전. 복합·집합 비주거는 `parse_sigungu_to_addr` 공통 |
| 키 이전 | [`migrate_p2_keys.py`](../../pipeline/collective/migrate_p2_keys.py) | 드라이런 기본 · 쓰기 접속마다 `current_database()` = 지정 이름 + `…_p2r` 패턴 + 보호 목록 밖 확인 · 원장 `*_p2_before`(id, 바뀌기 전 값) · 부속 표 행 전체 사본 · 연결표 3종 · `--verify` · `--rollback` · 멱등 |
| mart 대표 주소 | [`rep_address_sql.py`](../../pipeline/collective/rep_address_sql.py) → `build_collective_building_stats.py`(rolling·annual) · `build_collective_presale_lifetime_stats.py` · `rent/build_building_stats.py` | 최다 거래 (addr3, addr4, addr5, 코드, 지번, 도로명) 한 세트, 동률 최신 계약일 → 코드·지번·도로명 순 |
| 같은 as_of 재빌드 | [`mart_replace.py`](../../pipeline/collective/mart_replace.py) + 빌더 5개 `--replace-as-of`, 2개 `--prune-annual` | 빌더가 UPSERT만 해서 같은 as_of를 다시 만들면 옛 키 행이 남는다 → Phase C 재생성용(기본 꺼짐, 월간 cycle 동작 불변) |
| N-2 적재기 | `collective_commercial/import_refined.py` | INSERT에 `deal_type`(중개거래·직거래만) |
| N-1·N-2 보정 | [`fix_p2_deal_types.py`](../../pipeline/collective/fix_p2_deal_types.py) | hash 대응 한 칸 UPDATE · 드라이런 기본 · 같은 가드 · `*_dealtype_p2_before` · 되돌리기 · 옮겨진 경로(C:/E:·staging 이동) 재해석 |
| bridge 재발 방지 | `ingest_collective_bridge_years.py`, `ingest_built_bridge_years.py` | purge에 시도(addr1, 옛 이름 포함) 조건 · 시도 빈 목록이면 거부 · **드라이런 기본**(`--apply`로 실행), 시도×연도×유형 건수 출력. 다른 스크립트 호출처 없음(문서만) |
| staging 탐색 | `reform_paths_202607.py` | `raw/*/*(201001_202605)`까지 탐색, `list_reform_csvs`는 0개면 `FileNotFoundError`. 로컬에서 인천·전남광주 루트 2개 찾음 |
| 월간 검사 | [`integrity_p2.py`](../../pipeline/collective/integrity_p2.py) + `verify_monthly_integrity.py --collective[-deep]` | 옛 시도명 행 0(ERR) · 동 이름 ≥2 키 중 판정 목록 밖(WARN, 판정 대기) · annual 합 = 원장 합 2019~(ERR) · 합성 주소 0(deep, ERR) |
| 옛 키 요청 | [`backend/app/collective/key_remap.py`](../../backend/app/collective/key_remap.py), `main.py`, `router.py` `GET /buildings/{key}/key-status` | ASGI 미들웨어(CORS 안쪽): 1:1 → 경로·`?building_key=`를 새 키로 바꾸고 `X-CH2-Key-Remapped` 헤더 · 1:N → 409 `{key_status:"split", candidates:[…]}`(이름·주소·건수) · 연결표 없으면 통과 · 로드 실패도 통과 · `CH2_KEY_REMAP_ENABLED=0` |
| 화면 | `frontend-collective` `BuildingRegressionPage.tsx`, `api/client.ts` | 유일한 키 딥링크(회귀 새 창 `?building_key=`)에서 키 확인 → 분할이면 후보 링크 목록 |

## 조건 1 — (c) 419키 재판정

[`b1_split_decide.py`](../../scripts/lab/collective_p2/b1_split_decide.py). 동 단위 쌍을 묶는 규칙: ① `region_code_history`로 이어진 동 ② 분양권 키 전체 ③ 대표 지번이 같음. 묶은 결과 조각이 1개면 유지, 2개 이상이면 조각마다 새 키.

| Phase A | 결정 | 사유 | 키 | 거래 |
|---|---|---|---|---|
| (a) | split | a_evidence | 1,119 | 46,032 |
| (a) | keep | 동 단위 하나가 법정동 코드 없음(양지읍 행 코드 미부여) → 나눌 수 있는 조각 1개 | 5 | 34 |
| (c) | split | c_lot_diff(대표 지번 다름) | **412** | 5,418 |
| (c) | keep | keep_presale(분양권 BL 지번 등) | **7** | 1,956 |
| **합계** | split 1,531키 → **새 키 3,447** · keep 12키 | | | |

- **① 연혁 연결은 0건이다.** 로컬 `region_code_history`는 191행 전부 `code_reissue`(화성 분구·면→읍 승격)이고 분동·합동 기록이 없다. 법정동코드 원천 파일 두 개(`data/region_codes/`)에도 연혁 열이 없다. 지시 예시 **남양읍↔새솔동** 키는 1개 있었고 분양권(BL 지번 같음)이라 ②·③으로 유지됐다. 다른 분동 쌍이 (c) 분할 412키에 섞였을 수 있다 → 분동 연혁 자료를 넣을지 결정 필요(아래).
- ③ 같은 지번: (c) 중 동 단위 대표 지번이 같은 키는 3개, 전부 분양권(②와 겹침). 분양권이 아닌 같은 지번 키가 없어 **건축물대장으로 같은 지번의 다른 건물을 가리는 측정은 대상 0건**이라 하지 않았다.
- 키별 판정·사유: `logs/collective_p2/b1_decisions.csv`(지번 포함, gitignore). 분할 목록에는 지번이 없다.
- 법정동 코드 없는 동 단위: 적재 때도 코드 없는 행은 1조각으로 간다(`resolve_split_unit`). 처음 보는 동(분할 뒤 새로 생긴 동)은 그 동이 새 조각이 된다.

## 드라이런 (실제 로컬 DB, 읽기 전용)

`migrate_p2_keys.py --collective-db collective_stats --built-db built_stats --rent-db rent_stats`(쓰기 없음). `--apply`는 같은 이름에서 `GuardError`로 거부됨을 확인.

| 대상 | 결과 |
|---|---|
| 집합 주거 원장 | 바뀌는 행 **166,595** = 호남 115,145 + 분할 51,450 · 연결표 **7,414행**(호남 3,967 + 분할 3,447) · 옛 키 5,498 |
| 호남 | 옛 키 3,967 → 기존 새 이름 키와 병합 3,799 · 이름만 바뀜 168 |
| **새 키 충돌** | 기존 키와 겹침 **0** · 여러 옛 키가 같은 새 키 **0** |
| 비주거 | 4,355행 · cluster 778 → 778개 모두 **이미 `commercial_clusters`에 새 이름 cluster 행이 있음**(거래 없는 cluster 행) → 거래를 그쪽 id로 옮기고 옛 cluster 778행 보존 후 제거. Phase A(거래 기준 693/85)와 다른 이유 |
| 복합 | addr1 5,779행 |
| 임대 | 분할 54,486행 · 옛 키 1,475 → 새 키 2,976 · 충돌 0 · 임대 옛 시도명 행 0 |
| 거래유형 N-1 | 141,143행 전부 대응(직접 139,644 + staging 폴더로 확정 1,499) → 중개 117,626 · 직거래 23,517 |
| 거래유형 N-2 | 미상 70,575 중 대응 **70,574**, 실행 간 충돌 **1**(A-5의 6건 중 5건은 두 실행의 값이 같아 확정) → 직거래 39,384 · 중개 31,190 |

## 조건 2 — 검증 지표(`migrate_p2_keys.py --verify`)

- 원장 행 수 = 이전 전(삭제 0), hash 중복 수 = 이전 전, 옛 시도명 행 0(3원장), 분할 대상 옛 키 남은 행 0(집합·임대)
- **분할 전후 거래 수 합계:** 보존 행 수 = 연결표로 설명되는 행 + 키 유지 행(누락·중복 0)
- **새 키 충돌 0:** 분할 새 키를 가진 행은 모두 그 옛 키에서 온 행(보존 표에 없는 행이 붙으면 실패)
- 연결표 행 수 = 바뀐 (옛, 새) 키 쌍 수 · 비주거 cluster_id 고아 0 · 거래·cluster 키 일치

## 조건 3 — 매매·임대 연결 (예측, 읽기 전용)

[`b3_rent_link_predict.py`](../../scripts/lab/collective_p2/b3_rent_link_predict.py): 이전 계획의 매매 새 키 ∩ 임대 새 키(연결은 정확 키 일치).

| 항목 | 값 |
|---|---|
| 지금 연결된 분할 대상 매매 키 | **1,474** (Phase A의 1,083은 (a) 키만; (c) 분할 412키가 더해짐) |
| 분할 뒤 모든 매매 조각이 임대와 이어짐 | 1,068 |
| 일부 조각만 이어짐(나머지 조각은 그 동 임대 거래 없음) | 400 |
| 하나도 안 이어짐 | 6 |
| 분할 뒤 새 연결(조각 단위) | 2,878 |
| 한 임대 단지가 여러 매매 단지에 붙음 | 0 (정확 일치 규칙, 새 키 하나는 옛 키 하나에서만 나옴) |

실측(재생성 후 비교)은 Phase C에서 `rent_sale_building_map_p2_before`와 대조한다.

## 조건 4 — 지역프로필·market_stats 의존 (코드 + 데이터)

- **코드:** `build_collective_market_stats.py`는 원장 거래를 법정동 코드로 묶는다(`building_key`·building_stats 미사용). `build_regional_profile.py`는 `market_stats`(as_of·3/5년)와 `market_annual_stats`(최근 완결 3개 연도)만 읽는다. **D-030 `apartment_count`는 단지 수가 아니라 `market_stats`의 아파트 거래 건수**다(`_sanitize_apartment_nulls`, `profile_twin/v2.py`, AI 근거 라벨 「아파트 거래」). 단지 키·단지 수·building_stats를 읽는 곳은 없다.
- **데이터:** 최신 market_stats 창 3년(2023-11~) · 5년(2021-11~) 안 옛 시도명 거래 **0**, 7년(2019-11~) 76,469. 프로필 연간은 최근 완결 연도(2026 기준 2023~2025)이고 옛 시도명 계약연도는 2019~2020뿐.
- → 분할·대표 주소는 거래 단위 집계라 무관하고, 호남 표준화는 7년 창과 2019~2020 연간만 바꾼다. **프로필 3·5년 값은 바뀌지 않는다.** 바뀌는 것: `market_stats` 7년 코드 12 계열(의도한 수정), `market_annual_stats` 2019·2020 코드 12(같은 addr1 루프 덮어쓰기 해소 — 프로필은 안 읽음). Phase C에서 3·5년 행 전후 동일을 실측한다.

## 테스트

| 묶음 | 결과 |
|---|---|
| 새 단위 [`test_collective_p2_keys.py`](../../pipeline/tests/test_collective_p2_keys.py) (17) | 목록 밖 키 비트 불변(이름·무이름·분양권 원문 고정) · 분할 접미·조각 해석(코드 변형·코드 없음·처음 보는 동) · 원문 불일치 시 키 유지 · 고정 목록 형식(조각별 대표 코드 중복 0, 지번 열 없음) · 비상 해제 · 시도명 정규화 · 호남+분할 사유 · 가드 6사례 · SQL 모양 |
| fixture 왕복 [`test_collective_p2_migration_roundtrip.py`](../../pipeline/tests/test_collective_p2_migration_roundtrip.py) (3) | 드라이런 무변경 → apply → verify 통과 → 재실행 동일(멱등) → rollback 후 원래 표 12개 **행 단위 동일** · 호남 병합/재키·분할(코드 없는 행 1조각)·비주거 병합/재키(addr5 옛 키 재현)·복합·임대·부속 표 행동 확인 · 대표 주소(최다·동률 최신) · `delete_as_of`/`prune_annual` · 거래유형 갱신·되돌리기 |
| 미들웨어 [`test_collective_p2_key_remap.py`](../../backend/tests/test_collective_p2_key_remap.py) (6) | 1:1 경로·쿼리 재작성+헤더 · 1:N 409 후보 · 미등록 키·다른 앱·연결표 없음·비활성·로드 실패 통과 · main 등록 |
| 대표 주소 실데이터 | [`b4_check_rep_sql.py`](../../scripts/lab/collective_p2/b4_check_rep_sql.py): 충북 5년 3,282행이 A-3 측정과 **주소 칸 차이 0**. annual·분양권·임대 SQL 실행 확인 |
| 재발 방지 검사(이전 전 DB) | [`b6_integrity_now.py`](../../scripts/lab/collective_p2/b6_integrity_now.py): 옛 시도명 ERR 3 · 판정 대기 1,531(= 분할 목록, 이전 뒤 0 예상) · annual≠원장 ERR 86 · 합성 주소 ERR 1,646/2,399/3,204 — 이전 전이라 나와야 정상 |
| pipeline 전체 | base(dfa3082) 147 passed·collection error 2 → 이 브랜치 **167 passed**·같은 2건. 새 실패 0 |
| backend 전체 | base(dfa3082) 1,294 passed·12 failed·1 error → 이 브랜치 **1,299 passed**·같은 12 failed·같은 1 error(기존 목록: insight_06~12, built_region_all_asset 3, region_sido 1, yield_compare 1, built_recommend_deprecated 1, profile_national_rank import). **새 실패 0.** skip 1건은 `test_collective_p1_identifiability`가 이 worktree에 없는 로컬 로그(`logs/collective_phase0/c03_detail.csv`)를 찾는 환경 차이 |
| 프론트 | `frontend-collective` `tsc --noEmit` 통과(다른 앱 변경 없음) |

## Phase C에 넘기는 것·발견 사항

1. **annual 낡은 행:** 빌더가 UPSERT만 해서 원장에 없는 키의 2019~ annual 행이 **12,811행(157,754건)** 남아 있다(이번 이전과 무관하게 이미 있음). 그래서 「annual 시도 합 = 원장 합」이 호남 밖(경기·강원 등 86건)에서도 어긋난다. Phase C 재생성은 `--prune-annual`로 함께 정리한다(2010~2018 장기 annual은 원장 밖 원천이라 건드리지 않음). 월간 cycle에 넣을지는 별도 결정.
2. 재생성 순서(Phase C): migrate `--apply` → `--verify` → `fix_p2_deal_types --apply` → building_stats `--replace-as-of --prune-annual` → rolling·presale(`--replace`)·market 7년·비주거 cluster `--replace-as-of --prune-annual` → 임대 building_stats `--replace-as-of` → K-apt 속성·공시지가·지오코드(분할 새 키) → `build_sale_building_map.py` → `integrity_p2 --deep` 0 확인.
3. 비주거 `commercial_clusters`의 `n_total` 등 집계 칸은 병합 대상 cluster에서 갱신되지 않는다(적재기 upsert가 쓰는 칸). 화면 사용 여부 Phase C 확인.
4. 2010~2018 장기 annual(`ingest_collective_long_term_annual.py`)은 법정동 코드를 붙이지 않아 분할을 적용할 수 없다 → 분할 키의 2018년 이전 annual은 옛 키에 남는다(연결표로 조회 가능). 행 수는 Phase C에서 센다.
5. 옛 키 처리는 경로·`?building_key=`만 한다. 코호트 회귀 body의 `building_keys` 목록은 바꾸지 않는다(화면이 매번 새 목록에서 키를 받으므로 낡은 키가 들어올 경로가 없음).
6. 레거시 `collective_cluster_*` 표(월간 cycle 밖)는 이전·재생성 대상에서 뺐다.

## T 결정 필요

1. **분동·합동 연혁:** `region_code_history`에 분동 기록이 없어 ①이 0건이다. (가) 이대로 진행(분동 쌍도 대표 지번이 다르면 분할) / (나) 법정동 연혁 자료(행안부 「법정동코드 변경내역」 등)를 받아 이력 표를 보강한 뒤 B-1 재실행. 자료 내려받기는 별도 승인이 필요하다.
2. **annual 낡은 행 정리(12,811행)**를 이번 Phase C 재생성에 포함할지(권장: 포함, `--prune-annual`).
3. 양지읍 코드 미부여 행 때문에 분할 못 한 (a) 5키(34건) — 그대로 둘지(권장: 둠, 코드 매핑은 범위 밖).

## 범위 밖 (손대지 않음)
비주거 cluster 옛 addr5 키(2,080조합), 비주거 hash 실행 간 비유일(이번 대응 불가 1건), 세종 region_codes 열 밀림, 기존 실패 테스트.
