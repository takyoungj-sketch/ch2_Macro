# 토지 원장 v1 동결

동결: 2026-10-17. 계획: [대장 DB 다음 단계 계획](../LEDGER_NEXT_PHASE_PLAN.md) 1단계.

토지특성 전국 원장과 실거래 연결 결과를 "토지 원장 v1"로 고정한다. 이후 작업(slim, 2018 확장, V1.1)은 이 원장을 읽기만 하고 고치지 않는다. 원장을 바꿔야 하면 v2로 새로 만들고 v1은 남긴다.

## 무엇이 v1인가

| 항목 | 값 |
|---|---|
| 원장 파일 | `C:\CH2\parcel_master\land_trait_observations.sqlite` (206,953,832,448바이트) |
| 표 | `parcel_observation`, `observation_conflict` |
| 키 | 필지번호 × 데이터기준일자 × 기준연도 × 기준월 |
| 원천 | `raw\raw addition\토지특성정보CSV(브이월드)` ZIP 825개 (57,580,654,180바이트) |
| 기준일 | 31개, 2017-10-17 ~ 2026-07-20 |
| 저장 관측 | 970,577,839 · 고유 필지 45,965,788 · 충돌 키 43,651,649 (변형 87,353,687) |
| 연결 규칙 | `LAND_CODE_HISTORY_LAYER_V1+LAND_LINK_RULE_V1` |
| 결과표 | PostgreSQL `land_transaction_trait_link` 2,684,877행 (계약 2019-01-01 이후 비교 가능 거래) |

파일 해시, ZIP 825개의 이름·크기·수정일·해시, 결과표 상태별 건수는 동결 기록 [`land_trait_ledger_v1_freeze_20261017.json`](land_trait_ledger_v1_freeze_20261017.json)에 있다. 다시 만들 때 이 기록과 맞춰 본다.

동결 기록 생성:

```powershell
cd D:\ch2\ch2_Macro
backend\.venv\Scripts\python.exe pipeline\parcel_master\freeze_land_trait_ledger_manifest.py --out docs\lab\land_trait_ledger_v1_freeze_20261017.json
```

해시 없이 빠르게 확인할 때는 `--no-hash`.

## 지키는 것

- 원장은 `mode=ro`와 `PRAGMA query_only=ON`으로만 연다.
- 원장에 행을 추가·수정·삭제하지 않는다. 새 판은 v2 또는 증분 설계(계획 8단계) 뒤에 넣는다.
- 결과표를 다시 쓰는 것은 규칙 버전이 바뀔 때뿐이다. 같은 V1로 다시 적재하지 않는다.
- 실거래 원장(`land_transactions`)은 바꾸지 않는다.

## git에 없는 것

| 파일 | 위치 | 잃었을 때 |
|---|---|---|
| 원장 SQLite | `C:\CH2\parcel_master\land_trait_observations.sqlite` | 아래 재생성 (약 21.6시간) |
| 원천 ZIP 825개 | `D:\ch2\ch2_Macro\raw\raw addition\토지특성정보CSV(브이월드)` | 브이월드에서 다시 받아야 한다. 해시로 같은 파일인지 확인 |
| 결과표 진행 파일 | `C:\CH2\parcel_master\land_trait_link_progress.json` | 결과표 재적재 때만 필요 |
| 2026-05-12 가늠 DB | `data/research/land_trait_slim/gauge_asof_2026-05-12.sqlite` | 밀도 기록용. 원장이 아니다 |

## 다시 만들기

원장(약 77,742초):

```powershell
cd D:\ch2\ch2_Macro\pipeline
.\.venv\Scripts\python.exe -u -m parcel_master.load_national_trait_ledger
```

끝나면 `docs/lab/land_trait_national_slim_20261010.json`이 다시 쓰인다. 저장 관측·고유 필지·충돌 키가 위 표와 같아야 한다. 이어하기 조건은 [`land_trait_national_resume_20261011.md`](land_trait_national_resume_20261011.md).

결과표:

```powershell
cd D:\ch2\ch2_Macro
backend\.venv\Scripts\python.exe -u pipeline\parcel_master\land_trait_link_materialize.py
```

진행 파일에 있는 시군구는 건너뛴다. 처음부터 다시 쓰려면 진행 파일을 치우고 결과표를 비운 뒤 실행한다. 이 작업은 규칙 버전이 바뀔 때만 한다. 청주 4구는 V1 점검을 통과해야 기록된다.

## 백업

원장 복사본 한 벌: `D:\CH2_backup\land_trait_ledger_v1\land_trait_observations.sqlite` (2026-10-17 robocopy, 206,953,832,448바이트). SHA-256 `982855688626b998cf40216041e2d11afa8f67301ea04cd087785e65010f73b1`로 원본과 같다.

원장이 망가지면 이 파일을 `C:\CH2\parcel_master\`로 되돌리고 해시를 다시 확인한다. 재생성(약 21.6시간)보다 빠르다.
