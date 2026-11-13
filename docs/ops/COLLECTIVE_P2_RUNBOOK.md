# 집합 2단계 운영 런북 (초안 v2 — T 결정 반영)

> **상태:** 초안 v2 (2026-11-14, Claude Code). **실행하지 않았다.** C-2 칸은 Cursor 확인(16일 이후)·T 결정 뒤 채운다.
> **실행 절차:** Codex 검토 → T 승인 → Codex 실행(로컬 반영 → promote) → Opus 운영 확인.
> **근거:** [Phase C 리허설 보고](../lab/COLLECTIVE_P2_PHASEC_REPORT_20261113.md). 시간·기대값은 **로컬 리허설 실측**이다. 운영 서버는 더 느릴 수 있다.

## 0. 결정 (T, 2026-11-14 — Opus 추천안)

| 항목 | 결정 | 이 문서 |
|---|---|---|
| 적용 방식 | **로컬 DB 에 적용한 뒤 기존 전체 DB 반영(promote) 경로로 운영에 올린다** | 2·5·6절 |
| title_fill | 로컬에서 실행 | 5.3 (※ 로컬 표제부 DB 확인 필요 — 5.3) |
| 운영 확인 | 읽기 전용 운영 확인 스크립트(`scripts/ops/collective_p2_verify/`) | 3·7절 |
| 롤백 | **반영 직전 운영 덤프로 되돌린다.** 통계표 재빌드 경로는 쓰지 않고 리허설도 하지 않는다 | 8절 |
| 서비스 | 공지·점검 모드 없이 **새벽**에 한다(사이트 Basic 인증으로 잠김, 일반 사용자 없음) | 6.3 |
| Insight 비교 | 로컬에서 실제로 재계산한 값으로 고정(C-2 리허설 때) | 7.3 |
| C-2 시점 | **C-01·호남 표준화·C-2 를 한 번에** 반영 | 5절 「C-2 확정 후 채움」 |
| 보관 | 덤프·보존 표 **30일** 보관 뒤 삭제 | 9절 |
| 월간 속성 단계 | Phase D 뒤, 출시 전 별도 작업 | 11절 |

## 1. 범위

| 바뀌는 것 | DB | 표 |
|---|---|---|
| 호남 시도명 표준화(전라남도·광주광역시 → 전남광주통합특별시) | collective_stats · built_stats · rent_stats | 원장 3종(집합 주거·비주거·복합) + 임대 원장 |
| C-01 동 분할(이름 키 1,531개 → 동 단위 새 키 3,447개) | collective_stats · rent_stats | 원장 키·부속 표·연결표 |
| **C-2 같은 법정동 동명 다른 건물 분할** | collective_stats (· rent_stats 여부 C-2 확정 후) | **C-2 확정 후 채움** |
| 거래유형 보정 | collective_stats | collective_transactions.deal_type |
| 대표 주소 SQL(`=` 조인) | 빌더 코드 | 통계표 재생성 |
| 분할 새 키 속성·공시지가 | collective_stats | collective_building_attributes(202607 판) · builder_master · collective_building_assessed_land_price |

- **land_stats(토지)는 바뀌지 않는다.** 이번 promote 대상이 아니다. 공시지가 단계가 토지 DB 를 **읽기만** 할 수 있다(5.3).
- 범위 밖: 세종 region_codes 열 밀림 · 직거래 더미·동 결측 경고·비주거 회귀 자동 제외(3단계) · 칩 건수·표기(4단계) · 기존 실패 테스트.

## 2. promote 경로 (지금 쓰는 전체 DB 반영 방법)

코드·문서 근거:
- `scripts/monthly/dump_db_for_promote.py`
- `deploy/scripts/vps_promote_db_sql.sh`
- `docs/COLLECTIVE_MONTHLY_UPDATE_SOP.md` §5
- `docs/MONTHLY_UPDATE_CHECKLIST.md` §4.4
- `docs/reports/KB_FILL_PROD_20261109.md` §2

### 2.1 무엇을

- DB 하나를 **통째로 바꾼다**(DROP DATABASE → CREATE → 덤프 적재). 표 단위 병합이 아니다.
- 운영에만 있는 행·표가 있으면 사라진다. 그래서 3절 동기화 확인이 필요하다.
- 로컬 PostgreSQL 18.6, 운영 16.14 다(KB_FILL 보고 §1 확인). 그래서 PG18 전용 줄을 걸러 낸 **plain SQL(.sql.gz)** 경로를 쓴다.

### 2.2 명령 (DB 마다)

```powershell
# 로컬(Windows) — 반영·검증이 끝난 로컬 DB 를 plain SQL gzip 으로
py scripts\monthly\dump_db_for_promote.py -d collective_stats -o backups\collective_stats_p2_promote.sql.gz
py scripts\monthly\dump_db_for_promote.py -d rent_stats       -o backups\rent_stats_p2_promote.sql.gz
py scripts\monthly\dump_db_for_promote.py -d built_stats      -o backups\built_stats_p2_promote.sql.gz
scp -i LightsailDefaultKey-ap-northeast-2.pem backups\*_p2_promote.sql.gz ubuntu@13.209.203.178:/var/backups/ch2/
```

```bash
# 운영(VPS) — DB 마다 한 번씩. 스크립트가 반영 직전 덤프를 먼저 만든다(8절 롤백 원본)
bash /opt/ch2_Macro/deploy/scripts/vps_promote_db_sql.sh collective_stats /var/backups/ch2/collective_stats_p2_promote.sql.gz
bash /opt/ch2_Macro/deploy/scripts/vps_promote_db_sql.sh rent_stats       /var/backups/ch2/rent_stats_p2_promote.sql.gz
bash /opt/ch2_Macro/deploy/scripts/vps_promote_db_sql.sh built_stats      /var/backups/ch2/built_stats_p2_promote.sql.gz
```

`vps_promote_db_sql.sh` 가 하는 일(순서대로):
1. 반영 직전 덤프 `pg_dump -Fc`(PG16) → `/var/backups/ch2/<db>_vps_pre_promote_<시각>.dump`
2. 백엔드 중지(`systemctl stop ch2-macro-backend`)
3. 연결 끊기 → `DROP DATABASE` → `CREATE DATABASE … OWNER ch2app`
4. `gunzip | (PG18 줄 거르기) | psql -v ON_ERROR_STOP=1`
5. 권한 부여
6. 백엔드 재시작
7. `/health` 확인

**이번에 쓰지 않는 스크립트:**
- `vps_promote_collective_pg18.sh`: PG18 `pg_restore` 경로를 가정하고, 반영 전 덤프를 만들지 않는다.
- `vps_restore_collective_stats.sh`: `--clean` 부분 교체.
- `vps_sync_collective_building_attributes.sh`: `--replace` 로 판 전체를 다시 만든다.
- `vps_promote_7y_marts.sh`: 속성 표를 TRUNCATE 한다.

### 2.3 몇 분 · 반영 중 화면

| DB | 로컬 표 크기 합 | 로컬 덤프 | scp | 운영 복원 | 근거 |
|---|---|---|---|---|---|
| collective_stats | 12.7GB (+ 보존 표) | 미실측 | 미실측 | 미실측 | — |
| rent_stats | 18.6GB (+ 보존 표) | 미실측 | 미실측 | 미실측 | — |
| built_stats | 1.3GB | 미실측 | 미실측 | 미실측 | — |

- **promote 소요는 저장소에 기록이 없다.** 예상 범위는 운영에서 지난 promote 로그를 읽기 전용으로 확인해 채운다(`/var/backups/ch2/restore_*.log`, `ls -l --time-style=full-iso /var/backups/ch2/*_vps_pre_promote_*`). 이번 실행에서 단계별 시간을 기록해 다음 달 SOP 에 남긴다. → 확인 사항 C-4.
- **반영 중 화면:** 스크립트가 백엔드를 멈춘 동안(2단계~6단계) **모든 앱의 API 가 응답하지 않는다.** 백엔드는 하나의 서비스(토지·복합·집합·임대·Insight·랩 공용)다.
  - 정적 화면은 열리지만 데이터 요청은 실패한다.
  - DB 3개를 차례로 올리면 백엔드가 세 번 멈췄다 켜진다.
  - 새벽·Basic 인증이라 일반 사용자는 없다(T 결정).

### 2.4 같이 올라가는 DB

| DB | 올림 | 이유 |
|---|---|---|
| collective_stats | 예 | 원장·통계·속성·연결표 |
| rent_stats | 예 | 임대 원장 키·시도명, 임대 통계, 매매·임대 연결표 |
| built_stats | 예 | 복합 원장 시도명, scope 통계 |
| land_stats | **아니오** | 변경 없음. 토지는 따로 쓰는 `promote_restore.sh` 경로. |

세 DB 모두 통째로 바뀌므로 **로컬과 운영의 차이가 이번 변경분뿐이어야 한다.** 이를 확인하는 단계:
- 3절: 반영 시작 전 동기화 확인.
- 6.1: promote 직전 재확인. 운영이 그 사이 바뀌지 않았는지 본다.
- 7.2: promote 뒤 행 해시 비교.

## 3. 시작 전 동기화 확인 (로컬 = 운영)

로컬에 반영하기 **전에** 한다. 다르면 멈춘다(promote 가 운영에만 있는 것을 지운다).

```bash
# 로컬
py scripts/ops/collective_p2_verify/prod_sync_check.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file backend/.env --out logs/collective_p2/sync_local_collective.json
# (rent_stats·built_stats 도 --db-env RENT_DATABASE_URL / BUILT_DATABASE_URL 로 같게)
# 운영 — 스크립트 폴더만 /opt/ch2_Macro/scripts/ops/collective_p2_verify/ 로 복사해 실행(pipeline 불필요)
python3 prod_sync_check.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/sync_prod_collective.json
# 운영 JSON 을 로컬로 가져와
py scripts/ops/collective_p2_verify/prod_sync_check.py compare logs/collective_p2/sync_local_collective.json sync_prod_collective.json
```

- 비교 항목:
  - 표별 행 수
  - 최신 `as_of_month`(열이 있는 표)
  - 원장 4종의 최근 4개 계약월 거래 수
  - 표 있음·없음
- **기대값: 다름 0.**
- **10초 규칙:**
  - 통계상 200만 행이 넘는 표의 정확한 행 수·월별 거래 수는 10초를 넘을 수 있다. 그래서 기본은 실행하지 않고 **「승인 필요」로 표시**하며, 추정 행 수만 남긴다.
  - 로컬 기준 해당 표:
    - collective_transactions(6.6M)
    - collective_building_rolling_stats(7.5M)
    - collective_building_stats(3.3M)
    - rent_transactions(14.7M)
    - rent_building_rolling_stats(11.1M)
    - rent_building_stats(4.2M)
  - **T 승인 뒤** `--allow-heavy` 로 다시 돌린다(쿼리마다 300초 제한).
- 예상 소요: 기본은 DB 마다 1분 안. `--allow-heavy` 는 collective 3~6분 · rent 5~10분 · built 1분(로컬 추정, 운영 최대 2배).
- 운영에만 있는 표·행이 나오면 멈추고 T 에게 보고한다. 2026-11-09 KB 보강값은 운영=로컬로 확인돼 있다.

### 3.1 월간 배치 멈추기·다시 켜기

- **월간 배치는 로컬 PC 에서 사람이 돌리고 promote 로 올린다.** 집합 `run_collective_cycle_csv.py`, 복합 `run_built_cycle_csv.py`, 토지 `run_land_cycle_csv.py`, 임대 분기 import 가 그렇다.
- 저장소에는 운영 서버 cron·systemd timer 가 없다(`deploy/templates` 에 `ch2-macro-backend.service`·`ch2-board.service` 만 있음).
- **멈추기:**
  1. 반영 기간(3절 시작 ~ 7절 확인 끝) 동안 로컬 월간 러너와 다른 promote 를 시작하지 않는다. 다른 에이전트·작업자에게 「집합·임대·복합 DB 동결」을 알린다.
  2. 운영 서버에서 읽기 전용으로 예약 작업이 없는지 확인한다: `crontab -l; sudo crontab -l; systemctl list-timers --all | grep -i ch2`. 무엇이 나오면 멈추고 보고한다.
- **다시 켜기:** 7절 운영 확인(Opus)이 끝나면 동결을 푼다. 다음 월간 cycle 은 SOP 대로 진행한다.
  - 다음 월간 적재부터 `building_keys.py` 의 C-01·C-2 키 규칙이 적용된다.
  - 월간 integrity 의 C-2형 경고가 0 인지 본다(9절).

## 4. 사전 조건

| # | 조건 | 확인 |
|---|---|---|
| 1 | **코드:** `data/collective-p2` 가 main 에 병합돼 운영에 배포됨. 키 재매핑 미들웨어·새 빌더 포함. 미들웨어는 연결표가 비어 있으면 통과만 하므로 데이터보다 먼저 배포해도 된다 | 운영 배포 해시 · `/health` |
| 2 | **동기화:** 3절 비교 다름 0 | 3절 JSON |
| 3 | **동결:** 3.1 | — |
| 4 | **디스크:** 로컬 — 덤프 3개 + `_p2_before` 보존 표 · 운영 — 반영 전 덤프 3개(-Fc) + 업로드한 .sql.gz 3개 + 새 DB. 운영 디스크(Lightsail 80GB SSD, `docs/PARCEL_MASTER_DESIGN.md`)의 여유가 **올릴 DB 크기의 2.5배**보다 작으면 멈춘다 | `df -h /var/lib/postgresql /var/backups` |
| 5 | **원천 파일(로컬):** K-apt 기본정보·필지고유번호 xlsx, 공시지가 slim 원천, 표제부 DB(5.3) | 경로 존재 |
| 6 | **접속 대상:** 로컬 `backend/.env` 의 `COLLECTIVE_/RENT_/BUILT_DATABASE_URL`·`DATABASE_URL`·`PARCEL_MASTER_DATABASE_URL` 이 의도한 DB 를 가리킴. 값은 출력하지 않고 `SELECT current_database()` 로 이름만 확인 | — |
| 7 | **시간대:** 새벽. 로컬 반영(약 3시간 20분) + promote(2.3 미실측)를 이어서 할지, 로컬 반영·검증을 낮에 끝내고 promote 만 새벽에 할지 → 확인 사항 C-3 | — |

## 5. 실행 순서 — 로컬 실제 DB 에 반영 (Codex)

- 로컬 반영 전 **로컬 덤프**(로컬 되돌리기용)를 뜬다: `pg_dump -Fd -j 4 -d <db> -f backups\p2\<db>.dir`.
- 명령·기대값은 Phase C 리허설과 같다. DB 이름만 `*_p2r` 대신 실제 이름이다(`--collective-db collective_stats` 등).
- 아래 시간은 로컬 리허설 실측이다.
- `PY`, `P=pipeline`, `AS_OF=<현재 as_of, YYYY-MM-01>`, `W="--as-of $AS_OF --windows 3,5,7"`.

### 5.1 키 이전 (원장)

| # | 명령 | 소요 | 기대값(리허설) |
|---|---|---|---|
| 1 | `migrate_p2_keys.py --collective-db collective_stats --built-db built_stats --rent-db rent_stats` (드라이런) | 수 분 | 키 바뀌는 행 166,595 · 분할 옛 키 1,531 → 새 키 3,447 · 충돌 0 · **C-2 확정 후 채움** |
| 2 | 위 + `--apply` | 23분 | 원자적. `p2_migration_log` 기록 |
| 3 | 위 + `--verify` | 3.5분 | 16항목 OK(옛 시도명 0 · 옛 키 남은 행 0 · 연결표 7,414 · 원장 행 수 불변) |
| 4 | `fix_p2_deal_types.py --collective-db collective_stats --raw-root <raw> --logs-dir <logs> --apply` | 5.3분 | 분양권 비정상·공란 → 0·0 · 비주거 공란 ≤ 1 |
| 4a | **C-2 키 이전 — C-2 확정 후 채움** (`migrate_p2_keys` 에 C-2 판정 파일 연결 필요, 아래 메모) | | |

**C-2 메모:**
- 적재 규칙은 `building_keys.apply_building_key_split_c2` 다(Part C). 판정 파일 `pipeline/collective/data/p2_split_units_c2.csv` 를 읽는다.
- 1회성 이전(`migrate_p2_keys`)에 같은 함수를 연결하는 일은 C-2 확정 뒤에 한다. 연결표 reason 이름(예 `c2_split`)과 「본 조각은 옛 키 유지」 때 재매핑 미들웨어 동작도 그때 정한다.

### 5.2 통계표 재생성 (이번 as_of 만)

| # | 명령 | 소요 | 기대값 |
|---|---|---|---|
| 5 | `build_collective_building_stats.py $W --replace-as-of --prune-annual` | 20분 | 3/5년 거래 합 불변 · 7년 옛 시도명 0 · 합성 주소 0 |
| 6 | `collective/prune_split_annual_p2.py --collective-db collective_stats --apply --mismatch-csv <logs>/…csv` | 1분 미만 | 2019~2020 분할 옛 키 annual 2,126행 삭제, 불일치 0 |
| 7 | `build_collective_building_rolling_stats.py $W --replace-as-of` | 21분 | |
| 8 | `build_collective_presale_lifetime_stats.py --as-of $AS_OF --replace` | 14초 | |
| 9 | `build_collective_market_stats.py $W` | 21분 | 3·5년 행 불변 · 코드 12 7년 ≥ 5년 |
| 10 | `build_collective_commercial_cluster_stats.py $W --replace-as-of --prune-annual` | 1.6분 | |
| 11 | `build_collective_commercial_cluster_rolling_stats.py $W --replace-as-of` | 1.5분 | |
| 12 | `rent/build_building_stats.py $W --replace-as-of` | 1시간 28분 | 임대 합성 주소 0 |

### 5.3 분할 새 키 속성·공시지가 (키 목록 범위)

키 목록(13):

```sql
\copy (SELECT DISTINCT new_key FROM collective_building_key_map WHERE reason LIKE '%split%' ORDER BY 1) TO 'logs/collective_p2/p2_split_new_keys.txt'
```

- C-2 새 키는 C-2 확정 후 reason 을 정해 같은 목록에 더한다.

**속성 단계 공통 규칙**

- `--snapshot-ym 202607` **필수**. 파일명 추론·최신 판 금지.
- 키 목록 옵션(`--keys-file`)으로 **새 분할 키만** 채운다. `--keys-file` 은 `--new-keys-only` 와 `--snapshot-ym` 이 함께 있어야 한다.
- **`--replace` 는 키 목록과 같이 쓸 수 없다**(스크립트가 거부).
- builder_master 는 새 키가 참조하는 단지 코드만 추가한다.
- **실행 전 드라이런으로 「목록 밖 쓰기 0」을 확인한다.**
  - 각 도구의 `--dry-run` 을 먼저 돌린다.
  - 리허설 `scripts/lab/collective_p2/c15_scope_dryrun.py` 와 같은 방식으로 범위를 점검한다: 쓸 행을 같은 함수로 계산하고 목록 밖 키 수를 센다.
  - `c15` 는 리허설 DB 이름을 고정해 두었다. 실제 로컬 DB 용으로 DB 이름을 인자로 받는 판을 만들어야 한다 → 확인 사항 C-5.

| # | 단계 | 명령 | 소요 | 기대값(리허설) |
|---|---|---|---|---|
| 14 | K-apt | `build_collective_building_attributes.py --kapt-file <xlsx> --asset-type apartment --new-keys-only --snapshot-ym 202607 --keys-file <목록>` (먼저 `--dry-run`) | 3.6분 | 274행 · builder_master +1 · 목록 밖 0 |
| 15 | title_fill | `python -m parcel_master.apply_title_fill --snapshot-ym 202607 --new-keys-only --keys-file <목록>` (먼저 `--dry-run`) | 2.8분 | fill 3,077(아파트 0 · 연립 3,030 · 오피스텔 47) · 사전 단계 3,351행(목록 키만) |
| 16 | 공시지가 | `cd backend; python -m collective.import_assessed_land_price --from-slim --keys-file <목록> --insert-only` (먼저 `--dry-run`) | 약 5.6분 | +3,326행 · 기존 행 덮기 0 |
| 17 | 매매·임대 연결 | `rent/build_sale_building_map.py` | 3.5분 | 정확 1,068 · 연결표 경유 400 · 1:N 6 |
| 18 | 복합 scope | `built/build_scope_stats.py --as-of $AS_OF --windows 3,5,7` 뒤 그 as_of 옛 시도명 행 삭제(리허설 `c3_built_scope_cleanup.py` 와 같은 SQL) | 15초 | 옛 시도명 81 → 0 |
| 19 | 재발 방지 검사 | `collective/integrity_p2.py --deep` | 수 분 | 옛 시도명 0 · 동 이름 ≥2 판정 밖 0 · annual 합 = 원장 합 · 합성 주소 0 · **C-2형 판정 밖 0**(C-2 반영 뒤) |
| 20 | **C-2 관련 — C-2 확정 후 채움** | | | |

**title_fill(15) — 로컬 실행 전제 확인**

- Phase C 에서 **로컬 서버에 `parcel_master` DB 가 없었다**(`pg_database` 확인, 보고서 「title_fill」 절).
- 리허설은 원본 표제부 파일로 만든 사본 `parcel_master_p2r`(37분, 집합 1,881,261행)을 썼다.
- 「로컬에서 실행」은 다음 둘 중 하나여야 한다 → 확인 사항 C-1.
  - (가) `PARCEL_MASTER_DATABASE_URL` 을 이미 있는 `parcel_master_p2r` 로 둔다(읽기만 하므로 사본을 그대로 씀).
  - (나) 같은 방법으로 실제 이름의 `parcel_master` 를 만든다(`load_title_pilot`, 약 37분).
- **K-apt PNU 파일이 없으면 실패하는지:**
  - `build_collective_building_attributes.attach_kapt_pnu` 는 필지고유번호 파일을 못 읽거나 PNU 를 하나도 못 붙이면 `RuntimeError` 로 멈춘다.
  - 테스트는 `pipeline/tests/test_collective_p2_attr_scope.py::test_kapt_pnu_missing_file_fails` 다.
  - title_fill 은 K-apt PNU 를 직접 읽지 않는다. title_fill 쪽 K-apt 연결 확인은 `has_kapt`·`blocked` 건수로 본다.
- **드라이런 대체안:** 실행 전 `--dry-run` 의 fill·blocked 건수를 기록한다.
  - 리허설 로그(`c3_title_fill_new_keys.log`)의 blocked 는 아파트 19,535 · 오피스텔 616 · 연립 0 이다(키 목록으로 거르기 전 판 전체 분류).
  - 크게 다르면 멈춘다.

**공시지가(16) — 토지 DB 접속 대상**

- 운영용으로 `--rehearsal` 은 쓰지 않는다.
- 집합 쪽 개편 지도가 비면 실행당 한 번 `DATABASE_URL`(토지)을 **읽는다.** 리허설에서는 0회였다.
- 실행 전에 `DATABASE_URL` 이 로컬 `land_stats` 인지 DB 이름으로 확인한다.

### 5.4 로컬 검증 (promote 전)

- `prod_c5_core.py --env-file backend/.env --out logs/collective_p2/local_c5.json` 를 돌린다.
- 7.1 기대값(0 이어야 할 지표)을 모두 통과해야 한다. 이 JSON 이 운영 비교의 기준이다.
- 운영 비교용 행 해시 스냅샷도 뜬다.
  - `prod_hash_compare.py snapshot --db-env <DB별> --out logs/collective_p2/hash_local_<db>.json` 로 DB 3개를 뜬다.
  - 로컬 반영 직후에 뜨고, promote 덤프 전에는 로컬을 바꾸지 않는다.

## 6. 운영 반영 (promote, 새벽)

### 6.1 직전 재확인

1. 3절 `prod_sync_check` 로 **운영**만 다시 스냅샷한다. 3절의 운영 JSON 과 비교해 다름 0 이어야 한다(그 사이 운영이 바뀌지 않음).
2. 운영 디스크(4절 #4)를 확인한다.
3. 반영 직전 운영 덤프를 따로 하나 더 뜰지 정한다. 스크립트가 자동으로 뜨지만, 위치를 고정하려면 아래를 쓴다.

```bash
sudo -u postgres /usr/lib/postgresql/16/bin/pg_dump -Fc --no-owner --no-acl -f /var/backups/ch2/p2/<db>_pre_p2_<YYYYMMDD_HHMM>.dump <db>
```

### 6.2 반영

2.2 의 `vps_promote_db_sql.sh` 를 collective_stats → rent_stats → built_stats 순서로 실행한다. DB 마다 `/health` OK 를 확인한 뒤 다음으로 간다.

### 6.3 서비스 처리

- 공지·점검 모드 없음(T 결정). 새벽에 한다.
- 영향 구간은 각 DB 복원 동안 백엔드 전체 중단(2.3)이다.
- **캐시:**
  - `vps_promote_db_sql.sh` 가 백엔드를 재시작하므로 프로세스 안 캐시가 새로 읽힌다. 키 재매핑 미들웨어의 연결표, `lru_cache` 등이 해당된다.
  - `analysis_cache`·`analysis_base_cache` 는 **토지 DB** 의 유료 분석 캐시라 이번 DB 와 무관하다. 그래도 지도·분석 화면 확인 전에 비워 두는 편이 안전하다: `python backend/scripts/clear_analysis_cache.py --with-base-cache`(운영). → 확인 사항 C-6.
- 스모크: `deploy/scripts/vps_collective_smoke.sh` + 분할 옛 키 1개 → 409(후보 목록), 1:1 옛 키 1개 → 새 키 응답.

## 7. 운영 확인 (Opus, 읽기 전용)

### 7.1 c5 핵심 지표 — `prod_c5_core.py`

```bash
python3 prod_c5_core.py --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/prod_c5.json --expect local_c5.json
```

| 지표 | 기대값 |
|---|---|
| 옛 시도명 행(집합 주거·비주거·복합·임대 원장 · 복합 scope as_of) | 0 |
| 합성 주소(building_stats 3/5/7 · 임대 rent_building_stats) | 0 |
| annual 합 ≠ 원장 합(2019~) | 0 |
| 연결표 사유별 행·옛 키·새 키 수 | 로컬과 같음(리허설: 7,414 · 옛 1,531 · 새 3,447 + C-2 확정 후 채움) |
| 원장에 남은 C-01 분할 옛 키 행 | 0 |
| 아파트 5년 단지 속성·공시지가·지오코드 커버리지 | 로컬과 같음(리허설 99.52% · 98.63% · 9.40%) |
| 동 이름 ≥2 판정 밖 · C-2형 판정 밖 | 0 |

- 무거운 쿼리(합성 주소·annual·동 이름 검사)는 쿼리마다 900초 제한이 있다. 예상 15~30분(운영 최대 2배).
- `--skip-heavy` 로 가벼운 지표만 1분 안에 먼저 볼 수 있다.
- 무거운 검사는 T 승인 뒤 실행한다.

### 7.2 행 해시 비교 — `prod_hash_compare.py`

```bash
python3 prod_hash_compare.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/hash_prod_collective.json
py scripts/ops/collective_p2_verify/prod_hash_compare.py compare logs/collective_p2/hash_local_collective.json hash_prod_collective.json
```

- 대상 표는 이번 반영이 바꾸는 표다. 원장·통계·속성·연결표·보존 표가 들어간다(스크립트 `TARGETS`).
- 큰 표는 `building_key` 첫 글자 16조각, 또는 id 범위 16조각으로 나눠 조각마다 시간 제한(기본 600초)을 둔다.
- 기대값은 **다른 표·조각 0** 이다. promote 는 같은 덤프라 id 까지 같다.
- 예상 소요는 collective 25~50분 · rent 30~65분 · built 1~2분이다(로컬 c8 해시 실측 기반, 운영 최대 2배).

### 7.3 Insight 비교

- Insight 14·08·03·12 를 C-2 반영 리허설 뒤 로컬에서 다시 계산한 값으로 고정한다(`scripts/lab/collective_p2/c22_insight_recompute.py`).
  - before = 로컬 원본, after = 리허설. 기간은 공개 스냅샷과 같게 한다.
- **운영 반영 뒤에는 공개 스냅샷(정적)이 바뀌지 않는다.** 고정한 after 값을 공개할지는 별도 결정이다.
- Insight 14 생성기 `apt_officetel_same_building_lab.py` 는 main 에 없다(`wip/ai-revision-20261109`). → 확인 사항 C-7.

## 8. 롤백 — 반영 직전 운영 덤프로 되돌림

**판단 기준(하나라도 해당하면 되돌린다):**

| # | 확인 항목 | 되돌리는 조건 |
|---|---|---|
| R1 | 7.1 옛 시도명 · 합성 주소 · annual 불일치 · 남은 분할 옛 키 행 | 0 이 아님 |
| R2 | 7.1 `--expect` 비교 | 로컬과 다른 지표가 있음(쿼리 시간 초과만 있는 경우는 다시 실행해 확인) |
| R3 | 7.2 해시 비교 | 다른 표·조각이 있음 |
| R4 | promote 스크립트 | `psql ON_ERROR_STOP` 실패 · `/health` 실패 |
| R5 | 스모크 | 집합·임대 상세가 5곳 이상 비거나 500 · 분할 옛 키가 409 가 아님 |
| R6 | 시간 | 한 DB 복원이 지난 promote 기록(2.3)의 2배를 넘고 원인이 불명 |

**되돌리기(DB 마다, 운영):**

```bash
DB=collective_stats; DUMP=/var/backups/ch2/${DB}_vps_pre_promote_<시각>.dump   # 2.2 1단계가 만든 파일(또는 6.1 수동 덤프)
sudo systemctl stop ch2-macro-backend
sudo -u postgres psql -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB}' AND pid<>pg_backend_pid();" \
  -c "DROP DATABASE IF EXISTS ${DB};" -c "CREATE DATABASE ${DB} OWNER ch2app;"
sudo -u postgres /usr/lib/postgresql/16/bin/pg_restore -d ${DB} --no-owner --no-acl -j 2 "$DUMP"
sudo -u postgres psql -d ${DB} -v ON_ERROR_STOP=1 -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ch2app;" \
  -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO ch2app;" -c "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO ch2app;"
sudo systemctl start ch2-macro-backend; curl -sf http://127.0.0.1:8000/health
```

- **예상 시간:** promote 복원 시간과 비슷하다(2.3 미실측). -Fc 덤프의 `pg_restore -j 2` 는 plain SQL 적재보다 빠를 수 있다.
- **세 DB 는 함께 되돌린다.** 연결표가 DB 사이에 걸려 있어 한 DB 만 되돌리면 키가 어긋난다.
- 되돌린 뒤 `prod_sync_check` 로 반영 전 운영 스냅샷(3절 JSON)과 다름 0 인지 확인하고, 스모크를 다시 한다.
- 재빌드 경로(통계표 다시 만들기)는 쓰지 않는다(T 결정). 로컬 쪽은 5절 첫 줄의 로컬 덤프로 되돌린다.

## 9. 사후 처리

| 항목 | 내용 |
|---|---|
| 덤프·보존 표 | 운영 반영 전 덤프(`*_vps_pre_promote_*`, `p2/*_pre_p2_*`) · 로컬 덤프 · `*_p2_before`·`collective_building_annual_split_p2_before`·`rent_sale_building_map_p2_before` → **30일 보관** 뒤 T 확인을 받고 삭제(삭제 날짜를 이 문서에 기록) |
| 연결표·`p2_migration_log` | 계속 둔다(옛 키 재매핑에 필요) |
| 월간 integrity | 다음 월간부터 `verify_monthly_integrity.py --collective` 의 integrity_p2: 옛 시도명 0 · 동 이름 ≥2 판정 밖 0 · **C-2형 판정 밖 0(경고)** · C-2 판정 파일에 없는 본번(확인 필요, 경고) |
| 기록 | 실행 해시 · 단계별 시간(특히 promote 2.3 표 채우기) · 검증 JSON 을 Phase D 보고에 남긴다 |

## 10. 알려진 한계

- **판 이름과 출처:** 분할 새 키 속성 행은 판 이름이 `202607` 이지만, 값의 출처는 10월 판 K-apt 파일이다.
- **빈 키 96개**(분할 새 키 3,447 중 속성 행 없음):

| 유형 | 사유 | 키 |
|---|---|---|
| 연립 | 표제부 없음 | 69 |
| 연립 | 세대수 없음 | 16 |
| 연립 | 재건축 | 6 |
| 연립 | 비주거 | 1 |
| 오피스텔 | 표제부 없음 | 2 |
| 오피스텔 | 비주거 | 2 |

- 공시지가 빈 키 121:
  - 그 유형 building_stats 없음 78
  - 원천 slim 에서 못 씀 43(최신 연도 아님 39 · slim 에 없음 3 · 값 갈림 1)
- 2010~2018 장기 annual 은 법정동 코드가 없어 분할이 안 된다. 옛 키에 남는다(연결표로 조회).
- C-2 적재 규칙에서 3건 미만 새 본번은 가장 가까운 조각에 붙고 월간 「확인 필요」로 뜬다. 나중에 3건이 넘으면 새 조각이 생기지만, 이미 붙은 옛 행은 그대로다.

## 11. 출시 전 과제 (런북 범위 밖, 기록만 — Phase D 뒤 별도 작업)

- **월간 갱신에 K-apt·title_fill 단계가 없다.**
  - 202607 이후 새 단지와 분할과 무관한 새 키는 속성이 비어 있다(리허설 기준 **2,076키**: 아파트 828 · 연립 1,131 · 오피스텔 117, 그중 1,372키는 첫 거래가 판 이후).
  - 월간 러너에 「속성 없는 키만, 판 명시, 키 목록」 단계를 넣는다.
- **`vps_sync_collective_building_attributes.sh`:**
  - `--replace` 로 판 전체를 다시 만든다. KB 보강값(`kb_internet_*`)을 덮을 수 있다(KB_FILL 보고 §2).
  - 월간 SOP·체크리스트는 이 스크립트를 부르지 않는다. 언급은 `docs/NEW_APARTMENT_REGRESSION_DESIGN.md`(「VPS K-apt 공통 전제」)와 KB_FILL 보고뿐이다.
  - 월간 속성 단계를 만들 때 이 스크립트를 키 목록·추가 전용 방식으로 바꾸거나 폐기할지 같이 정한다.
- `vps_promote_collective_pg18.sh`(반영 전 덤프 없음)·`vps_promote_7y_marts.sh`(속성 TRUNCATE)의 정리 여부.

## 12. 16일 이후 순서 (지금 하지 않음)

1. Cursor 가 불확실 상위 100건을 확인한다(`logs/collective_p2/c2_uncertain_for_cursor.csv`). T 는 「다른 단지」 판정만 검토한다.
2. 판정을 반영해 C-2 판정 파일(`p2_split_units_c2.csv`)을 확정한다. 「확인 불가」와 나머지 171건은 분할하지 않는다(`decision=keep` 으로 기록).
3. `migrate_p2_keys` 에 C-2 를 연결한다(5.1 메모).
4. 리허설 DB 를 덤프에서 다시 만들고 키 이전부터 전체 리허설을 다시 돌린다. 속성·공시지가는 새 분할 키 목록(C-01 + C-2)으로 채운다.
5. c5~c10 과 c8(해시)을 다시 검증한다. Insight 재계산 값을 고정한다(`c22_insight_recompute.py run --side before/after` → `compare`).
6. 이 런북의 「C-2 확정 후 채움」 칸을 채운다.
7. Codex 검토 → T 승인 → 운영 반영(promote) → Opus 운영 확인.

## 13. 실행 전 확인 사항 (T·Codex)

| # | 확인 | 메모 |
|---|---|---|
| C-1 | title_fill 표제부 DB: 로컬 서버에 `parcel_master` 가 없음. (가) `parcel_master_p2r` 사본을 읽기로 씀 / (나) 실제 이름으로 새로 적재 | 5.3 |
| C-2 | C-2 판정 파일에 본번이 들어간다. 저장소에 커밋할지(지번 취급), 로컬 전용(gitignore·경로 환경변수 `CH2_COLLECTIVE_KEY_SPLIT_C2_PATH`)으로 둘지 | Part C |
| C-3 | 로컬 반영과 promote 를 한 새벽에 이어서 할지, 로컬은 낮에 끝내고 promote 만 새벽에 할지(그 사이 동결 유지) | 4절 #7 |
| C-4 | promote 소요(2.3) — 운영 지난 로그를 읽기 전용으로 확인해 채우기 | 2.3 |
| C-5 | 범위 드라이런(`c15`)의 실제 DB 판 — 누가 만들지 | 5.3 |
| C-6 | `analysis_cache` 비우기(토지 DB, 이번 변경과 무관) 실행 여부 | 6.3 |
| C-7 | Insight 14 생성기를 main 으로 가져올지(재계산하려면 필요) | 7.3 |
| C-8 | C-2 본 조각 「옛 키 유지」 방식과 키 재매핑 미들웨어(1:N → 409) 동작 | 5.1 메모 |
