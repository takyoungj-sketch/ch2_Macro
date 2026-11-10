# 토지 대장 연결 V2 운영 반영 계획서

작성 2026-11-10. 이 문서는 계획만 담는다. 실행 순서와 시점은 T가 정한다. 코덱스 배포와 겹치지 않게 하기 위해서다. 아래 명령은 모두 T의 승인 뒤에 실행한다.

## 대상과 범위

| 항목 | 내용 |
|---|---|
| 코드 | 브랜치 `claude/land-link-shadow-20261110`. `land_trait_link_missing.classify`가 V2 코드 층을 쓴다(월간 신규 판정). `land_trait_link_rejudge.py --apply`가 생겼다(`honam_v2`만 허용). |
| DB 변경 | `db/084_land_trait_link_event.sql`. 새 테이블 1개와 연결 테이블의 nullable 열 2개(`judged_at`, `ledger_latest_asof`)를 추가만 한다. 기존 열·제약은 바꾸지 않는다. |
| 데이터 변경 | `land_transaction_trait_link`의 광주·전남(`12`) 미연결 8,232행. exact 7,391, multiple_candidates 841. 이벤트 8,232행. |
| 화면 | 연결 칸과 공시지가 표시가 바뀐다. 2026-07~10 광주·전남 거래 약 7,400건이 미연결에서 "일치"로 보인다. 전국 9월 연결률은 65.1%에서 76.8%가 된다(로컬 실측). 백엔드 코드는 바꾸지 않는다(`rule_version`을 읽는 곳이 없음). |
| 운영 현재 (2026-11-10 읽기 전용 확인) | 연결 행 2,701,573. `12` 행 9,186개는 모두 `other_unmatched`. 이벤트 테이블과 새 열은 없고, `orphaned` 열도 없다. 백업 디스크 여유는 44GB. |

## 로컬 적용 결과 (2026-11-10, 승인된 범위)

- 백업: `C:\CH2\parcel_master\backup_land_trait_link_12_before_honam_v2_20261110.json.gz`. 적용 전 `12` 9,186행이다.
- 마이그레이션 084를 로컬 `land_stats`에 적용했다.
- `--apply --cycle-id honam_v2-local-20261110` 결과: 대상 9,085건, 이벤트 8,232행, 갱신 8,232행.
  - exact 7,391. 이 중 공시지가 same_year 7,389, price_missing 2.
  - multiple_candidates 841.
  - 변화 없음 851, 판정 안 됨 2.
- 대상이 9,085건이라 `12` 9,186행보다 101건 적다. 이 101건은 연결 행은 있지만 `land_transactions`에 그 해시가 없는 행이다(재적재로 사라진 거래). 대상 SQL이 거래와 JOIN하므로 빠진다.
- 같은 명령을 다시 dry-run하면 바뀔 행은 0건이다(멱등).
- 로컬 연결률(판정 대상 기준):

| 월 | 적용 전 | 적용 후 |
|---|---:|---:|
| 2026-07 | 62.3% | 74.7% |
| 2026-08 | 62.6% | 74.7% |
| 2026-09 | 65.1% | 76.8% |
| 2026-10 | 63.8% | 78.6% |

## 운영 반영 경로

운영 `land_stats`는 로컬에서 Promote(전체 덤프 복원)로 올린다. git 배포만으로는 데이터가 바뀌지 않는다(MONTHLY_UPDATE_SOP). 그래서 길은 두 가지다.

- **경로 1: 다음 Promote에 실어 보낸다 (권장).** 로컬에는 이미 적용됐다. 다음 월간 Promote 때 이벤트 테이블, 새 열, 갱신 행이 함께 넘어간다. 운영 DB에 따로 쓰는 단계가 없다.
- **경로 2: 운영에서 단독으로 반영한다.** Promote를 기다리지 않을 때 쓴다. 아래 순서를 따른다.

### 경로 2 순서

1. **사전 확인(읽기 전용).**
   `12` 행 상태별 건수(현재 9,186 `other_unmatched`)와 연결 행 총수(2,701,573)를 기록한다. 이벤트 테이블이 없는지 확인한다.
2. **백업.** VPS에서 실행한다.
   ```
   sudo -u postgres pg_dump -Fc --no-owner --no-acl -t land_transaction_trait_link -f /tmp/land_trait_link_pre_honam_v2_YYYYMMDD.dump land_stats
   sudo mv /tmp/land_trait_link_pre_honam_v2_YYYYMMDD.dump /var/backups/ch2/
   ```
3. **마이그레이션.**
   ```
   sudo -u postgres psql -d land_stats -v ON_ERROR_STOP=1 -f /opt/ch2_Macro/db/084_land_trait_link_event.sql
   ```
   추가만 하므로 앱 중단은 필요 없다. 테이블 잠금은 `ALTER TABLE ADD COLUMN`(nullable, 기본값 없음)이 짧게 잡는 것뿐이다.
4. **코드 배포.** 브랜치를 main에 병합한 뒤 `deploy-from-windows.ps1 -Scope land`로 배포한다. 백엔드 동작은 바뀌지 않는다. VPS의 `pipeline/`을 맞추려는 단계다.
5. **apply.** 재판정은 대장 SQLite(193GB, 로컬 전용)를 읽어야 하므로 VPS에서 직접 돌릴 수 없다. 대신 로컬 계획 파일을 VPS에 적용한다.
   - 로컬에서 운영과 같은 상태의 계획을 만든다. 운영 `12` 행이 로컬 적용 전과 같다는 것(건수·해시)을 1번에서 확인한 뒤, 로컬 백업 시점의 계획 파일 `land_trait_link_rejudge_plan_honam_v2_local_apply_20261110.json.gz`를 쓴다.
   - 이 계획을 VPS로 올리고, 같은 `EVENT_SQL`/`UPDATE_SQL`을 한 트랜잭션으로 실행한다. 이 단계는 `land_trait_link_rejudge.py`에 "계획 파일 적용" 옵션으로 추가해야 한다(미구현. 승인되면 구현한다). 조건은 이렇다.
     - 행 상태가 계획의 이전 상태와 같을 때만 갱신한다.
     - 건수가 다르면 전체 롤백한다.
     - `--expect-host 127.0.0.1 --expect-db land_stats`를 확인한다.
6. **확인(읽기 전용).**
   - `12` 행 상태별 건수: exact 7,391, multiple_candidates 841, other_unmatched 954(851 + 고아 101 + 판정 안 됨 2).
   - 이벤트 8,232행.
   - 연결 행 총수 2,701,573 그대로.
7. **화면 확인.**
   - 토지 앱(`/land/`)에서 광주·전남 시군구, 2026-08~10 거래 목록에 대장 보강을 켠다. "일치"와 공시지가가 보이는지 본다.
   - 회귀 화면에서 "공시지가 연결 n건 / 미연결 m건"이 늘었는지 본다.
   - 다른 시도 목록이 그대로인지 서울 1곳만 표본으로 확인한다.

### 되돌리기

- **데이터.** 이벤트 행의 `previous_*`로 원래 값을 되돌린다. 한 트랜잭션에서 실행하고, 건수가 8,232인지 확인한다.
  ```sql
  BEGIN;
  UPDATE land_transaction_trait_link l
     SET link_status = e.previous_status,
         rule_version = e.previous_rule_version,
         price_status = e.previous_price_status,
         official_price_won = NULL, price_year = NULL, recovered_lot = NULL,
         trait_asof = e.previous_trait_asof,
         ledger_beopjungri_code = e.previous_ledger_beopjungri_code,
         code_resolution = e.previous_code_resolution,
         judged_at = NULL, ledger_latest_asof = NULL
    FROM land_transaction_trait_link_event e
   WHERE e.cycle_id = :cycle_id AND e.transaction_hash = l.transaction_hash;
  -- rowcount = 8,232 확인 후
  DELETE FROM land_transaction_trait_link_event WHERE cycle_id = :cycle_id;
  COMMIT;
  ```
  이전 상태는 모두 미연결이므로 공시지가·지번은 NULL로 돌리는 것이 원래 값이다(테이블 제약상 미연결 행은 공시지가가 없다).
- **전체.** 2번 백업으로 `pg_restore --clean -t land_transaction_trait_link`를 실행한다.
- **스키마.** 084는 추가만 하므로 되돌리지 않아도 된다. 꼭 지워야 하면 `DROP TABLE land_transaction_trait_link_event; ALTER TABLE land_transaction_trait_link DROP COLUMN judged_at, DROP COLUMN ledger_latest_asof;`를 실행한다.
- **코드.** 병합 커밋을 되돌린다. 월간 판정은 V1로 돌아간다.

## 12월 월간 배치 전에 할 일

- 브랜치를 main에 병합한다. 월간 러너가 V2를 쓰려면 필요하다.
- `docs/MONTHLY_UPDATE_SOP.md` §월간 신규 대장 공급 2번을 V2로 고쳤다(대응표 필수 명시).
- 월간 실행 PC에 `C:\CH2\parcel_master\honam_code_bridge_v1.sqlite`가 있어야 한다. 없으면 V2가 모든 대응을 보류하고 경고를 남긴다(V1과 같은 결과).
- 로컬 `land_stats`에 `orphaned` 열이 없다. `coverage()`는 그 열을 읽는다. 월간 `publish`는 `reconcile_orphans`가 먼저 `ADD COLUMN IF NOT EXISTS`를 하므로 문제가 없다. 다만 단독으로 `coverage()`를 부르면 실패한다.

## 대장이 `12`로 적재되기 시작할 때 (설계 메모)

- 그 판부터 같은 필지가 새 PNU(`12…`)로 나오고, 옛 PNU(29·46)의 이력은 끊긴다. V2의 "새 시도 코드 필지가 대장에 없음" 조건은 그 판부터 자동으로 꺼져 V1과 같아진다.
- 그 판보다 늦게 맺은 계약은 새 PNU에서 판 하나만 보게 된다. exact는 대부분 그대로지만, `label_normalized`·`traits_differ` 판단과 공시지가 직전연도 fallback은 옛 이력을 못 본다.
- 필요한 것:
  1. 적재 때 `honam_code_bridge`로 새 PNU와 옛 PNU 대응(법정동 대응 + 꼬리 같음)을 만든다.
  2. 판정할 때 두 PNU의 판을 한 필지 이력으로 합친다.
  3. 그 판의 날짜를 "대장 코드 전환일"로 기록한다.
  4. 이미 V2로 연결된 행은 다시 판정하지 않는다.
