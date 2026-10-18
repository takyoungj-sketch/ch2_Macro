# 전국 대장 DB — 일시 중단 인계 (2026-10-18)

전국 대장 DB 구축은 여기서 멈춘다. 다음 확장 전에 4-C 독립 표본 1차분 110건을 사람이 검증한다. 검증 결과가 나올 때까지 개발(엔진·공급표·제품 전환)은 하지 않는다. Cursor·Codex 어느 쪽에서 재개하든 이 문서에서 시작한다.

계획 전체: [`LEDGER_NEXT_PHASE_PLAN.md`](../LEDGER_NEXT_PHASE_PLAN.md).

## 1. 저장소 상태

| 항목 | 값 |
|---|---|
| 브랜치 | `feature/land-trait-ledger-v1` (push 안 함, 원격에 없는 커밋 있음) |
| 마지막 커밋 | `4957306` 전국 V2 품질검사·면제 근거·현상 유지 범위·집합 `--from-slim` |
| 이 작업 커밋 흐름 | `06551ed`(7단계 계약) → … → `0f67a37`(8단계 증분) → `00c587c`(5단계 집합) → `6432ed3`(6단계 임대) → `1037525`(D-078) → `75fc59b`(ENGINE_V2·섀도) → `4957306` |
| 일부러 커밋하지 않은 것 | `docs/lab/plan.json`, `docs/lab/journal/*` (규칙상 커밋 안 함) |
| 이 작업과 무관한 미커밋 | SOP 문서들, `docs/lab/MACRO_TS_RAW_MONTH_MART.md`, `backend/tests/test_new_apartment_regression.py`, `deploy/hub/*`, 다수의 `_tmp_*` 파일 — 이 작업에서 손대지 않음 |

운영 DB·제품 표·제품 화면은 이 계획 동안 바꾸지 않았다. DDL은 초안만 있고 적용하지 않았다.

## 2. 단계별 상태

| 단계 | 상태 | 근거 문서 |
|---|---|---|
| 1 토지 원장 v1 동결 | 완료 (D: 백업 해시 일치) | [LAND_TRAIT_LEDGER_V1_FREEZE.md](LAND_TRAIT_LEDGER_V1_FREEZE.md) |
| 2 토지 slim 공급층 | 완료 (세 검증 통과) | [LAND_TRAIT_SLIM_V1_DESIGN.md](LAND_TRAIT_SLIM_V1_DESIGN.md) |
| 3 건축물대장 전국 원장 | 완료 (원천 해시·행 수 일치, 청주 v2 재현) | [BUILDING_LEDGER_V1_DESIGN.md](BUILDING_LEDGER_V1_DESIGN.md) |
| 4 복합 보강을 대장 공급으로 | 시험 완료 · **4-C 표본 정확도 미검증** · 제품 전환 안 함 | [BUILT_ENRICHMENT_LEDGER_SUPPLY.md](BUILT_ENRICHMENT_LEDGER_SUPPLY.md), [BUILT_LINK_QUALITY_V1.md](BUILT_LINK_QUALITY_V1.md) |
| 5 집합 대표필지·공시지가 | 섀도 표 완료 · 적재기 `--from-slim` 추가(dry-run만) · 마트 교체 안 함 | [COLLECTIVE_REP_PARCEL_SUPPLY_V1.md](COLLECTIVE_REP_PARCEL_SUPPLY_V1.md) |
| 6 임대 연결 | 설계 채택 · 시험 공급표 완료 · 앱 연결 안 함 | [RENT_LINK_STRUCTURE_V1.md](RENT_LINK_STRUCTURE_V1.md) |
| 7 공통 소비 계약 | 초안·결정 완료 · 복합 시험 공급표 · DDL 미적용 | [LEDGER_CONSUMPTION_CONTRACT_V1_DRAFT.md](LEDGER_CONSUMPTION_CONTRACT_V1_DRAFT.md), [BUILT_LINK_CONTRACT_SHADOW_V1.md](BUILT_LINK_CONTRACT_SHADOW_V1.md) |
| 8 증분 갱신 | 구현·R0~R9 재현성 시험 통과(ENGINE_V2) · 시험 환경만 | [LEDGER_INCREMENTAL_UPDATE_V1_DESIGN.md](LEDGER_INCREMENTAL_UPDATE_V1_DESIGN.md), [LEDGER_INCREMENTAL_UPDATE_V1_TESTS.md](LEDGER_INCREMENTAL_UPDATE_V1_TESTS.md) |
| 9 품질관리 | 설계·시험 완료 · 전국 V2 판정 needs_waiver · 승인 기록 없음 | [BUILT_LINK_QUALITY_GATE_V1.md](BUILT_LINK_QUALITY_GATE_V1.md) |
| 9 화면 표시 통일 | 시작 안 함 (D-078 주의문구 포함) | — |

## 3. 데이터 위치와 판본 (모두 저장소 밖)

| 대상 | 경로 | 판본·크기 |
|---|---|---|
| 토지 원장 | `C:\CH2\parcel_master\land_trait_observations.sqlite` | v1 동결 192.74GB · [동결 기록](land_trait_ledger_v1_freeze_20261017.json) |
| 토지 slim | `C:\CH2\parcel_master\land_trait_slim_v1.sqlite` | v1, 63.7GB(디스크 약 59GB), 911,610,981행 |
| 건축물대장 원장 | `C:\CH2\parcel_master\building_ledger_v1.sqlite` | v1 동결 약 15.1GB · 원본 줄 순서 `building_ledger_v1_line_order.sqlite` |
| 호남 코드 브리지 | `C:\CH2\parcel_master\honam_code_bridge_v1.sqlite` | v1 (`held_not_1to1` 보류 포함) |
| 복합 시험 공급표(7단계) | `C:\CH2\parcel_master\verification\built_link_contract_shadow_v1.sqlite` (+ `_rebuild`) | 규칙 V1 |
| 복합 전국 판본(엔진) | `C:\CH2\parcel_master\versions_test\built\N_full_ENGINE_V2.sqlite` · 재생성 `N_full_ENGINE_V2_again.sqlite` | `BUILT_A1A2_TIME_FALLBACK+LEDGER_SUPPLY_PROPOSED+CONTRACT_V1+ENGINE_V2` |
| 판본 등록부 | `C:\CH2\parcel_master\versions_test\built\registry\` | 시험용 |
| 품질검사 결과 | `versions_test\built\N_full_ENGINE_V2_gate_with_rebuild.json` · 요약 [built_link_gate_engine_v2_20261018.json](built_link_gate_engine_v2_20261018.json) | needs_waiver |
| 증분 시험 결과 | `versions_test\built\results.json`(V2) · `results_v1.json` · R0~R9 판본 SQLite | 모두 통과 |
| 집합 공시지가 섀도 | `C:\CH2\parcel_master\shadow\collective_building_assessed_land_price_shadow_v1.sqlite` | `slim_latest_year_v1` |
| 임대 시험 공급표 | `C:\CH2\parcel_master\shadow\rent_link_shadow_v1.sqlite` | `rent_link_key_v1` + `rent_link_header_v1` |
| 표본·검증표 | `C:\CH2\parcel_master\verification\built_link_sample_v1\` | §4 |

원장 세 개는 D: 백업(해시 일치)이 있다. 시험 판본·섀도는 원장에서 다시 만들 수 있어 백업하지 않았다.

## 4. 110건 독립 검증 — 바로 시작할 준비

### 4.1 목적

전국 정확도를 확정하는 검사가 아니다. **연결 방식에 구조적 문제가 있는지 보는 1차 독립 검증**이다. 세 가지를 본다.

1. 실제로 같은 건물인가 — 주소·사용승인연도가 비슷하다는 이유로 다른 건물에 붙은 사례가 있는가.
2. 실제로 같은 필지인가 — 여러 필지에 걸친 건물, 지번이 바뀐 필지를 맞게 처리했는가.
3. 오류가 특정 유형(집합건물, 공장, 복수 필지 건물 등)에 몰리는가.

사람이 확인할 수 없는 행은 반드시 **판정 불가**로 남긴다. 추정으로 채우지 않는다.

### 4.2 파일

| 파일 | 용도 | 누가 여나 |
|---|---|---|
| `worksheet.csv` | 검증표 219행. `확인차수`=1인 110행이 이번 범위 | 검증자 |
| `key.csv` | 정답 키(우리가 고른 지번·등급 등) | **1단계가 끝날 때까지 열지 않음** |
| `worksheet_before_cols_20261018.csv` | 칸 추가 전 원본 백업 | — |
| `new_links_worksheet.csv` / `new_links_key.csv` | 새 연결·바뀐 연결 30건(110건 다음) | 나중 |
| `followup_worksheet.csv` / `followup_key.csv` | 후속 목록 248건(추정에 넣지 않음) | 나중 |

### 4.3 표본 추출 기준

- 모집단: 복합 연결 507,116건. 설계 [built_link_sample_design_v1_20261017.json](built_link_sample_design_v1_20261017.json), seed 20261018, 전체 219건.
- 층: 일반건축물 유형 3개(단독다가구·상업업무·공장창고) × 권역 3개(수도권·광역시·도) = 9칸, 집합건축물 3칸, 기타(동률·대장 변경·원장 없음) 1칸.
- 칸 안 순서가 무작위라 `확인차수` 1(110건)만 끝내도 무작위 표본이다. 1차 110건은 일반 9칸 × 10, 집합 3칸 × 5, 기타 5.
- 검증자는 우리가 고른 지번을 보지 않는다(블라인드). `마스킹지번`은 원천에 있는 가려진 지번이다.

### 4.4 검증 방법

**1단계 — 블라인드(검증자)**: 행마다 `KAIS검색힌트`·주소·계약일·가격·연면적으로 KAIS에서 그 거래를 찾는다.

| 칸 | 적는 것 |
|---|---|
| `KAIS_실제지번` | KAIS에서 확인한 실제 지번(예: `123-4`, `산12`) |
| `KAIS_건물근거` | KAIS에서 보이는 건물 정보 중 확인한 것(사용승인연도, 연면적, 층수, 건물명 등). 없으면 비움 |
| `확인불가` | 거래를 못 찾았거나 후보가 여럿이면 사유(예: `미검색`, `후보2`) |
| `메모` | 그 밖의 관찰(여러 필지 표기, 지번 변경 흔적 등) |
| `판정` | **비워 둔다** — 2단계에서 채운다 |

**2단계 — 대조(1단계가 끝난 뒤)**: 정답 키를 열어 KAIS 지번·건물근거를 우리가 연결한 필지·건물(대장의 대표·부속 지번, 사용승인, 연면적)과 맞춰 본다. 자동으로 분명한 행은 판정안을 채우고, 나머지는 검증자가 정한다. 대조 결과는 저장소 밖 같은 폴더에 둔다.

### 4.5 판정 기준 — 건물과 필지를 나눠 본다

| 판정 | 기준 |
|---|---|
| **건물·필지 모두 일치** | KAIS 지번 = 우리 지번이고, 건물근거가 우리 건물과 어긋나지 않는다(한 필지에 건물이 여럿이면 근거가 우리 건물을 가리켜야 함) |
| **같은 건물의 다른 필지** | 지번은 다르지만 KAIS 지번이 우리 건물의 부속 지번이거나, 합병·분할·지번 변경으로 같은 건물에 이어진다 |
| **다른 건물** | 지번이 다르고 같은 건물로 이어지지 않는다. 또는 지번은 같지만 건물근거가 같은 필지의 다른 건물을 가리킨다 |
| **판정 불가** | KAIS에서 못 찾음, 후보가 여럿, 근거 부족. 분모에서 빼고 건수를 따로 보고 |

- 필지 정확도 = 모두 일치 ÷ (판정 불가 제외). 건물 정확도 = (모두 일치 + 같은 건물의 다른 필지) ÷ (판정 불가 제외). 둘 다 층 가중치로 낸다(`estimate_link_accuracy_v1.py`는 지금 필지 기준만 계산 — 재개 때 `판정` 칸을 읽게 넓힌다).
- 110건은 칸마다 5~10건이라 칸별 수치는 구간이 넓다. 칸별로는 오류 **유형과 집중 여부**를 보고, 전국 수치는 참고값으로 둔다.
- 4-C 합격 기준(D-079)은 판정 결과를 본 뒤 사용자와 정해 기록한다. 이 문서는 기준을 정하지 않는다.

### 4.6 오류가 나왔을 때

- 유형별로 원인을 나눈다: 층(집합·공장·기타), 등급 A1/A2, 시도 12(코드 브리지), 대장 구분 변경, 복수 필지, 같은 필지 여러 동, 지번 변경.
- **연결 엔진을 자동 수정하지 않는다.** 원장·거래 DB(land/built_transactions)·`built_transaction_enrichment`·제품 DB에 반영하지 않는다. 원인 분석과 규칙 개선안 문서까지만 한다.
- 행 단위 결과(지번 포함)는 저장소 밖 `verification`에만 둔다. 저장소 JSON은 건수만.

## 5. 미해결 문제

| 문제 | 상태 |
|---|---|
| 고아 285건 처리 | 면제 근거·조건만 정리(품질검사 §4.2). `orphaned` 처리 구현은 전환 때 |
| 최신 용도지역 기본 표시 | 기존 표시 유지 조건으로 면제 제안. 표시 전환은 별도 결정 |
| 집합건축물에 붙은 복합 연결 402건 | 위험 신호, 보류 전환 여부 미정 |
| 2023년 사용승인 일치 하락 | 원인 미확인 |
| 거래 해시 안정성(계약월이 해시에 없음) | 8단계 점검 항목, 미착수 |
| 호남 브리지 `held_not_1to1` | 집합 13건 등 공급 보류 |
| 집합 마트의 낡은 대표 지번 | 433키(가격 다름 286). `--from-slim` 실행 시 공급분은 고쳐지고 113키는 남음 |
| `parcel_land_price` 소실 | 로컬·VPS 모두 없음. 월간 SOP `--from-parcel-master`는 실행 불가 |
| 표본 2차분 109건 · 새 연결 30건 · 후속 248건 | 미판정 |

## 6. 승인 대기

- 복합 제품 전환(보강표 → 엔진 공급). 선행: 4-C 판정, 품질검사 면제 승인 기록(`docs/lab/approvals/`).
- 집합 공시지가 마트 교체(`--from-slim` 운영 실행)와 월간 SOP 경로 교체. 주거·비주거 같이.
- 임대 앱이 시험 공급표를 읽게 하는 것(집합 마트 전환과 함께).
- D-078 화면 반영(회귀 결과의 복수 용도지역 건수·주의문구, 5앱 같은 위치).
- 4-C 합격 기준 결정(D-079).

## 7. 재개 순서

1. **검증 결과 분석** — 110건 판정 집계(4분류 × 층), 오류 유형·집중 여부, 참고용 가중 추정.
2. **필요한 연결 규칙 개선** — 구조적 오류가 있으면 규칙 개선안을 문서로 내고 승인 뒤 엔진 판을 올린다. 없으면 현재 설계 유지.
3. **전국 재구축 및 재현성 검증** — 새 판본 전국 재구축, R0~R9, 품질검사(재생성 안정성 포함).
4. **집합·임대 공급체계 후속** — 집합 마트 교체, 임대 연결, 화면 표시 통일.
5. **제품 전환 검토** — 승인 기록을 갖춘 뒤에만.

push·배포·운영 DB 수정은 별도 승인 없이 하지 않는다.
