# 대장 연결 결과 공통 소비 계약 v1 — 초안 (계획 7단계)

계획: [`LEDGER_NEXT_PHASE_PLAN.md`](../LEDGER_NEXT_PHASE_PLAN.md) 7단계 · 2026-10-18 · 앞 단계: [4단계 종합](BUILT_LEDGER_SUPPLY_4F_SUMMARY.md)

**초안이다.** DB·결과표·API·화면은 바꾸지 않았다. 아래 건수는 로컬 DB를 SELECT만 해서 셌다(`pipeline/parcel_master/check_consumption_contract_v1.py` → [`consumption_contract_check_v1_20261018.json`](consumption_contract_check_v1_20261018.json)).

## 0. 무엇을 정하나

토지·복합·집합·임대가 대장 연결 결과를 **같은 이름과 같은 상태값**으로 내보내는 약속이다. 표를 하나로 합치는 것이 아니다. 유형마다 분석 단위(거래 / 단지 / 도로 군집)와 결과표는 그대로 두고, 화면·API·품질지표가 읽는 층만 맞춘다.

이 계약이 담아야 하는 것(4-F 사용자 지시):

- 건물 식별 세 단계 — 확정 / 후보 속성 동일(식별 아님) / 후보 속성 충돌
- 속성은 **변수 단위**로 쓰임 여부를 판단한다. 충돌한 변수는 확정값으로 내지 않는다.
- 값마다 기준일과 시점(계약연도 관측, 계약 뒤 판 등)을 함께 둔다.
- 미검증 여부와 분모를 잃지 않는다.

## 1. 지금 결과표 (로컬, 2026-10-18)

| 유형 | 표 | 단위 | 행 | 미연결 행 | 건물 식별 | 시점 정보 |
|---|---|---|---:|---|---|---|
| 토지 | `land_transaction_trait_link` | 거래 | 2,684,877 | **있음**(상태로) | 해당 없음 | `trait_asof`, 공시지가 기준연도 |
| 복합 | `built_transaction_enrichment` | 거래 | 498,568 | **없음**(D-047) | `bldrgst_pk` 전부 비어 있음 | 사용한 판 하나(`evidence.snapshot_used`) |
| 집합(주거) | `collective_building_attributes`, `collective_building_assessed_land_price` | 단지 키 | 243,697 / 225,077 | Z 등급으로 | K-apt 등급 A~F·P·T·Z | K-apt 판 `snapshot_ym`, 공시지가 2026 한 해 |
| 집합(비주거) | 없음 | 도로 군집 | — | — | 지번 마스킹이라 연결 대상 아님(D-020) | — |
| 임대 | `rent_sale_building_map` | 단지 키 | 213,547 | 없음 | 집합 단지 키 대응(exact만) | 없음 |

거래 범위(전체 / 지분)는 토지·복합 원장에 `is_partial_ownership`이 있어 결과표에 따로 둘 필요가 없다. 복합은 지분거래를 매칭하지 않는다(D-049).

## 2. 계약 구조 — 세 부분

### 2-1. 연결 머리 (대상 하나에 한 행)

| 열 | 값 | 비고 |
|---|---|---|
| `domain` | land / built / collective / rent | |
| `target_kind` | transaction / building_key | 비주거 집합은 계약 밖 |
| `target_key` | 거래 해시 또는 단지 키 | id 금지(월간 재발급) |
| `link_state` | **linked / unlinked / not_applicable** | 5앱 공통 세 값 |
| `link_reason` | 유형별 원래 상태 그대로 | 토지 `link_status`, 복합 tier·fail, 집합 등급 |
| `link_level` | building / parcel / complex / none | building = 표제부 한 동(관리번호), parcel = 필지까지(동 미정), complex = 집합 단지 |
| `hold_flags` | 목록 | 보류 후보 표시(집합건축물 연결, 계약 뒤 사용승인 등). 연결 상태는 바꾸지 않음 |
| `source_digest` | md5 | 원장 행 지문. 원장 값은 복사하지 않고 무변경 확인에만 씀 |
| `parcel_resolved` | true / false | 필지가 하나로 정해졌나 |
| `building_id_state` | **confirmed / candidates_agree / candidates_conflict / aggregated / weak_match / not_applicable** | 토지는 not_applicable. aggregated·weak_match는 집합 등급용(§5) |
| `candidate_count` | 정수 | 미정일 때만 |
| `code_resolution` | held / reissued_1to1 / current_code / bridge_12 / prefix_v1 | 코드 변경 처리 방식 |
| `register_snapshot` | 판(YYYY-MM) | 건물 값을 읽은 판 |
| `register_after_contract` | true / false | 계약월보다 늦은 판인가 |
| `trait_asof` | 날짜 | 토지특성 판 |
| `rule_version` | 문자열 | |
| `unverified` | true | 지금은 모두 true |
| `verification_basis` | none / auto_crosscheck / sample | 정확도 근거 종류. 지금은 none 또는 auto_crosscheck |
| `computed_cycle` | YYYYMM | |

`link_state = linked`는 "필지(또는 단지)에 이어졌다"는 뜻이지 "맞았다"는 뜻이 아니다. 정확도는 `verification_basis`로만 말한다.

### 2-2. 변수 값 (대상 × 변수 한 행)

변수마다 쓰임 여부를 따로 정해야 하므로 긴 형식으로 둔다.

| 열 | 값 | 비고 |
|---|---|---|
| `variable` | 변수 사전 키(§2-3) | |
| `value_num` / `value_text` | 값 | 하나만 채움 |
| `value_state` | **confirmed / candidates_agree / conflict_missing / source_missing / undetermined / not_linked** | 아래 표 |
| `value_level` | building / parcel / complex_aggregate | 단지 합산값은 complex_aggregate이고 후보 동일 상태가 될 수 없다 |
| `source` | building_ledger / land_trait_slim / al_d155 / land_ledger / kapt / tx_source | |
| `basis_date` | 그 값의 기준일 | 토지 기준일, 대장 판 |
| `timing` | contract_year / contract_year_estimated / previous_year / adjacent_before / adjacent_after / pre_contract_register / post_contract_register / latest | 계약 시점과의 관계 |
| `change_risk` | none / next_base_differs / undetermined | 4-D 안정성 |
| `use_approved` | true / false | 변수별 사용 승인. **candidates_agree는 기본 false** |

| `value_state` | 뜻 | 화면 |
|---|---|---|
| confirmed | 건물(필지)이 하나로 정해졌고 값이 있음 | 값 |
| candidates_agree | 건물은 미정, 후보 모두 같은 값 | `use_approved`일 때만 값 + "동 미확정" |
| conflict_missing | 후보·기준일끼리 값이 다름 | 빈칸 + "후보 충돌" |
| source_missing | 연결은 됐으나 원천에 값 없음 | 빈칸 + "대장 값 없음" |
| undetermined | 근거가 부족해 판단 불가(승인 대응 없는 코드 개편 등). 추정하지 않음 | 빈칸 + "판단 불가" |
| not_linked | 연결 안 됨 | 빈칸 |

### 2-3. 변수 사전

| 변수 | 유형 | 원천 | 시점 성질 | candidates_agree 사용 |
|---|---|---|---|---|
| `official_price` | 토지·집합 | land_trait_slim | 연도별(계약연도 → 직전 연도) | 토지는 해당 없음(필지 단위) |
| `zone_contract_year` | 복합(토지 후보) | land_trait_slim | 계약연도 관측, 기준일 보존 | 해당 없음(필지 값) |
| `zone_latest` | 복합 | al_d155 / land_trait_slim | 최신 | 해당 없음 |
| `structure` | 복합 | building_ledger | 판이 늦어도 거의 불변 | 승인 필요 |
| `main_use` | 복합 | building_ledger | **변경 가능**(용도변경) | 승인 필요 |
| `floors_above` | 복합 | building_ledger | **변경 가능**(증축) | 승인 필요 |
| `approve_year` | 복합·집합 | building_ledger / kapt | 불변 | 승인 필요 |
| `land_area` | 복합 | land_trait_slim / land_ledger / 대장 | 분할·합병 시 변함 | 사용 안 함(동마다 다를 수 있음) |
| `households`, `builder` 등 | 집합 | kapt | K-apt 판 | 해당 없음(단지 등급으로) |

## 3. 유형별 대응

### 토지 — 계약에 가장 가깝다

| 지금 | 계약 |
|---|---|
| `exact` 1,846,363 · `label_normalized` 70,243 | linked, parcel_resolved |
| `multiple_candidates` 207,032 · `other_unmatched` 166,865 | unlinked |
| `clean_precontract_traits_differ` 125,363 · `label_normalized_traits_differ` 3,986 | unlinked(특성 불일치) |
| `post_contract_only` 62,024 · `no_precontract_observation` 203,001 | unlinked(시점) |
| `price_status` same_year 1,886,371 / previous_year 9,916 | `official_price` confirmed, timing contract_year / previous_year |
| price_conflict 16,622 / price_missing 3,697 | conflict_missing / source_missing |
| `code_resolution` held 1,807,739 · reissued_1to1 737,539 · current_code 139,599 | 같은 값 |

빠진 것: 특성값(용도지역·지목 등)을 값 행으로 내지 않는다. V1.1 그림자 시험 때 넣는다.

### 복합 — 바뀌는 것이 가장 많다

| 지금 | 계약 |
|---|---|
| A1 455,418 · A2 43,150 | linked, `link_reason`에 tier |
| `bldrgst_pk` 비어 있음 498,568 | `building_id_state`를 섀도(4-E)에서 채움: 확정 / 후보 동일 / 충돌 |
| `structure_raw` · `max_floor` · `approve_year` (첫 동 값) | 변수 행. 미정이면 candidates_agree 또는 conflict_missing |
| `approve_year` 비어 있음 19,362 | source_missing |
| `zone_labels` (AL_D155 최신, 491,128) · 복수 246,041 | `zone_latest`. 지금 표시는 첫 세부 라벨 하나 |
| 없음 | `zone_contract_year` + 기준일 + change_risk (4-D) |
| `land_area_source` title/summary/land_ledger | `land_area`, source에 land_trait_slim 추가 |
| 판 하나(`snapshot_used`) | register_snapshot, register_after_contract |
| 미연결 행 없음 | **결정 필요**(§5-2) |

### 집합(주거) — 단지 단위, 거래 단위 보강 없음

| 지금 | 계약 |
|---|---|
| A·B·C (명칭·지번 일치) 18,002 | linked, building_id_state confirmed |
| D·F (여러 단지 세대 합산) 366 | linked, `aggregated` — 합산값이라 candidates_agree가 아니다 |
| E(부분일치 단일후보) 866 · P(필지 유일) 2,215 · T(표제부 동 합산) 221,167 | linked, `weak_match`. 지금 회귀 `usable=false`와 같은 경계 |
| Z(미매칭) 1,081 | unlinked |
| 대표필지 공시지가 225,077 (2026 한 해) | `official_price`, timing latest. 과거 거래별 공시지가는 붙이지 않는다(정책 유지) |

비주거 집합은 `not_applicable`이다. 주거·비주거가 같은 화면 형식을 쓰되, 비주거는 "도로 군집 분석이라 대장 연결 없음"을 같은 자리에 보인다.

### 임대 — 6단계 전까지 상속만

`rent_sale_building_map` exact 213,547(아파트 40,634 · 오피스텔 11,841 · 연립 161,072)로 집합 단지 키에 붙고, 단지 속성은 집합 계약 값을 그대로 읽는다. 단독다가구 임대는 6단계 실측 전까지 `not_applicable`.

## 4. 저장 방식 (제안)

기존 결과표에 열을 더하거나 CHECK를 바꾸지 않고, 유형별 DB에 **섀도 표 두 개**를 새로 둔다.

- `ledger_link_header_v1` (2-1), `ledger_link_value_v1` (2-2)
- 동결 행·기존 표는 그대로라 롤백이 표 삭제 하나로 끝난다.
- 기존 표를 고치는 경우의 CHECK 변경 목록: 복합 `zone_source`에 land_trait_slim, `land_area_source`에 land_trait_slim, 식별 단계 열 추가, 토지 `link_status`에 V1.1 상태. 섀도 표로 가면 이 변경이 모두 필요 없다.
- 크기 가늠: 복합 연결 507,116 × 변수 약 8 = 약 400만 행, 토지 2,684,877 × 변수 1~3. 수백 MB 수준.

## 5. 결정

2026-10-18 사용자 결정:

1. **저장 방식:** 유형별 DB에 섀도 표 두 개를 새로 둔다. 기존 결과표·CHECK는 바꾸지 않는다.
2. **복합 미연결 행:** 섀도 머리 표에만 unlinked 행(약 15.6만)을 둔다. `built_transaction_enrichment`는 D-047대로 확정 행만.
3. **집합 등급 대응:** A·B·C = confirmed, D·F = `aggregated`(여러 단지 합산값), E·P·T = `weak_match`(근거 약함), Z = unlinked.
4. **`use_approved`:** 독립 표본 판정 결과가 있는 변수만 사용자 승인으로 켠다. 그 전에는 모두 false.

남은 결정:

5. **화면 표시명(5앱 공통, D-072):** 연결됨 / 미연결 / 해당 없음, 동 미확정, 후보 충돌, 대장 값 없음, 계약 후 대장, 같은 해 변경 가능 — 9단계에서 확정.
6. **복합 용도지역 기본 표시:** `zone_latest`(지금) 유지, `zone_contract_year`는 별도 칸 — D-050·D-051 개정 여부는 회귀 비교 뒤.

## 6. 4-F 승인 대기 정책과의 관계

| 4-F 정책 | 계약에서 받는 자리 |
|---|---|
| 1 시도 12 대응표 | `code_resolution = bridge_12` |
| 2 slim 대지면적 | `land_area` source |
| 3 관리번호 세 단계 | `building_id_state`, `candidate_count` |
| 4 속성 공급 원칙 | `value_state`, `use_approved` |
| 5 용도지역 별도 필드 | `zone_contract_year`, `zone_latest`, `basis_date`, `change_risk` |
| 6 제품 대지면적 지목 규칙 | 변수 사전 `land_area` 정의 |
| 7 계약 후 판 표시 | `register_after_contract`, `timing = post_contract_register` |
| 8 보류 후보(집합 연결 402 등) | `link_state` unlinked + `link_reason` |
| 9 계약 뒤 사용승인 규칙 | `building_id_state` 산정 규칙 |

## 7. 다음

1. (완료) 섀도 표 DDL 초안 [`sql/ledger_link_shadow_v1_draft.sql`](sql/ledger_link_shadow_v1_draft.sql) — 적용 금지.
2. (완료) 복합 시험 공급표 — [복합 시험 공급표 v1](BUILT_LINK_CONTRACT_SHADOW_V1.md). 원장 2019+ 672,764건 전부(연결 507,116 · 미연결 156,480 · 해당 없음 9,168), 키 누락·중복 0, 원장 지문 차이 0.
3. 9단계에서 같은 표로 품질지표와 화면 표시를 만든다.
