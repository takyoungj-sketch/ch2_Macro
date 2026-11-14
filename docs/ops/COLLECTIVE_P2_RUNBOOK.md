# 집합 2단계 운영 런북 (초안 v4 — Codex 검토 반영)

> **상태:** 초안 v4 (2026-11-14, Claude Code — Codex P2 검토 8+4 항목 반영). **실행하지 않았다.** C-2 칸은 Cursor 확인(16일 이후)·T 결정 뒤 채운다.
> **실행 절차:** Codex 검토 → T 승인 → Codex 실행(로컬 반영 → promote) → Opus 운영 확인.
> **근거:** [Phase C 리허설 보고](../lab/COLLECTIVE_P2_PHASEC_REPORT_20261113.md). 시간·기대값은 **로컬 리허설 실측**이다. 운영 서버는 더 느릴 수 있다.

## 0. 결정 (T, 2026-11-14 — Opus 추천안)

| 항목 | 결정 | 이 문서 |
|---|---|---|
| 적용 방식 | **로컬 DB 에 적용한 뒤 기존 전체 DB 반영(promote) 경로로 운영에 올린다** | 2·5·6절 |
| title_fill | 로컬에서 실행. **원천 파일로 진짜 `parcel_master` 를 로컬에 만든 뒤** 실행(실제 반영 전에 만든다, `p2r` 사본은 쓰지 않음) | 5.0 · 5.3 |
| 운영 확인 | 읽기 전용 운영 확인 스크립트(`scripts/ops/collective_p2_verify/`) | 3·7절 |
| 롤백 | **반영 직전 운영 덤프로 되돌린다.** 통계표 재빌드 경로는 쓰지 않고 리허설도 하지 않는다 | 8절 |
| 서비스 | 공지·점검 모드 없이 **새벽**에 한다(사이트 Basic 인증으로 잠김, 일반 사용자 없음) | 6.3 |
| 나누기 | **두 번에 나눈다: 낮에 로컬 적용·전체 검증 → T 확인 → 새벽에 promote 만.** 그 사이 로컬 월간 실행·다른 promote 금지 | 3.2 · 5 · 6 |
| 운영 전용 데이터 | promote 전에 운영에서만 쓰이는 표를 떠서 로컬에 합친다 | 2.5 · 6.1 |
| 캐시 | promote 뒤 `analysis_cache` 를 비운다 | 6.3 |
| Insight 14 | wip 브랜치 생성기로 **비교만** 한다(main 에 반영하지 않음) | 7.3 |
| C-2 판정 | 저장소 파일이 아니라 **집합 DB 표 `collective_building_key_c2_units`** | 5.1 |
| C-2 옛 키 | **가장 큰 그룹이 옛 키 유지.** 미들웨어는 409 로 막지 않고 열며 「분리된 단지 있음」·새 키 목록을 붙인다(C-01 옛 키 409 는 그대로) | 5.1 |
| PG 버전 해시 | 시작 전 작은 표로 해시가 같은지 먼저 본다. 다르면 행 수·열 합계 비교로 바꾼다 | 3.1 |
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

**Codex 실측(운영, 읽기 전용 로그 확인 — 2026-11-14 검토):**

| 구분 | 실측 | 비고 |
|---|---|---|
| 단계 합계(덤프 → 업로드 → 복원 → 권한 → 재시작, DB 3개) | **약 47분** | 최신 기준. 일괄 실행·중간 재개 실행이 섞인 기록은 표에 「일괄」「재개」로 표시 |
| API 중단(백엔드 멈춤 ~ /health 응답) | **약 36분** | DB 3개 복원 동안의 합 |
| 단계별 행 | **Codex 실측표 원본을 그대로 붙여 넣는다(이 초안 작성 시점에 원본 표를 받지 못함 — C-4)** | 일괄·재개 표시 유지 |

- 위 합계는 Codex 가 운영 로그에서 잰 값이다. 이번 실행에서 단계별 시간을 다시 기록해 다음 달 SOP 에 남긴다. → 확인 사항 C-4.
- **반영 중 화면:** 스크립트가 백엔드를 멈춘 동안(2단계~6단계) **모든 앱의 API 가 응답하지 않는다.** 백엔드는 하나의 서비스(토지·복합·집합·임대·Insight·랩 공용)다.
  - 정적 화면은 열리지만 데이터 요청은 실패한다.
  - DB 3개를 차례로 올리면 백엔드가 세 번 멈췄다 켜진다.
  - 새벽·Basic 인증이라 일반 사용자는 없다(T 결정).

### 2.3a 원자성 — 3개 DB 는 전체가 원자적이지 않다

- `vps_promote_db_sql.sh` 는 **DB 하나씩 따로** 실행한다. DB 마다 DROP → CREATE → 적재가 각각이고, 세 DB 를 묶는 트랜잭션은 없다. 로컬 반영(5절)도 같다: `migrate_p2_keys` 는 DB 마다 자기 트랜잭션이다.
- **중간에 실패했을 때 되돌리는 범위:**

| 실패 지점 | 상태 | 되돌리기 |
|---|---|---|
| collective_stats 복원 중 | collective 만 깨짐(나머지 둘은 옛 상태) | collective 만 반영 직전 덤프로 복원(8절) → 세 DB 모두 옛 상태 |
| collective 끝, rent_stats 복원 중 | collective = 새, rent 깨짐, built = 옛 | **collective·rent 둘 다** 반영 직전 덤프로 복원(연결표가 걸려 있어 collective 만 새면 키가 어긋남) |
| collective·rent 끝, built_stats 복원 중 | collective·rent = 새, built 깨짐 | 세 DB 모두 복원(8절) — 또는 built 만 다시 promote(원인이 일시적이면, T 판단) |
| 셋 다 끝, 7절 확인 실패 | 셋 다 새 | 세 DB 모두 복원(8절) |
| 로컬 반영(5절) 중 실패 | 로컬 DB 중 일부만 바뀜 | 5절 첫 줄의 로컬 덤프로 **바뀐 DB 모두** 복원 후 처음부터 |

- 원칙: **한 DB 라도 새 상태가 되면, 되돌릴 때는 새 상태가 된 DB 를 모두 되돌린다.**

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

### 2.5 운영 서버가 직접 쓰는 표 (코드 전수 조사, 2026-11-14 · 읽기 전용)

**조사 방법:**
- `backend/app` 의 모든 엔진·세션 경로를 봤다: `get_collective_engine/_db`, `get_rent_engine/_db`, `get_built_engine/_db`, `app.db`(토지), `platform`, `macro_ts`, `parcel_lab`.
- SQL 문자열의 `INSERT/UPDATE/DELETE/TRUNCATE/CREATE/ALTER/ON CONFLICT`, ORM `add/merge/commit`, `COPY`·`to_sql` 을 모두 찾았다.
- 키 재매핑 미들웨어(`collective/key_remap.py`)는 연결표를 **읽기만** 한다.

| DB | 표 | 쓰는 경로 | 무엇 | 처리 |
|---|---|---|---|---|
| collective_stats | `collective_building_geocodes` | `POST /api/collective/buildings/map-points` → `collective/building_geocode.resolve_building_map_points` (`INSERT … ON CONFLICT DO UPDATE`, commit) | 지도에서 처음 본 단지의 VWorld 좌표 캐시 | **promote 전에 운영에서 떠서 로컬에 합친다**(6.1) |
| collective_stats | `collective_commercial_map_geocodes` | `POST /api/collective/commercial/roads/map-points` → `collective_commercial/road_geocode.resolve_commercial_map_points` (INSERT·ON CONFLICT) | 비주거 도로 지도 좌표 캐시 | 같음 |
| collective_stats | `qa_audit_run` | `POST /api/admin/qa/specified|random` 에서 `save_db=true` 일 때 `qa_audit/store.insert_run`(관리자 QA 기록) | 관리자 점검 기록 | 같음(운영에 행이 있으면) |
| rent_stats | `rent_building_geocodes` | `POST /api/rent/buildings/map-points` → `resolve_building_map_points(table_name="rent_building_geocodes")` | 임대 지도 좌표 캐시 | 같음 |
| built_stats | — | 없음. `qa_audit` 의 복합 도메인(`built_enriched`)은 built 엔진으로 `qa_audit_run` 을 쓰려 하지만, 로컬 built_stats 에는 그 표가 없다. 운영에도 없으면 기록 실패, 있으면 위와 같이 처리 | — | 6.1 에서 `to_regclass` 로 확인 |

**쓰지 않는 것(근거):**
- 유료 분석 캐시·로그(`analysis_cache`·`analysis_base_cache`·`paid_analysis_logs`)는 **토지 DB**(`app.db`)다.
- 사용자·구독·게시판·AI 사용량·운영 이벤트(`users`·`subscriptions`·`entitlements`·`posts`·`comments`·`device_ai_usage`·`ops_events`)는 **플랫폼 DB**(`DATABASE_URL_PLATFORM`)다.
- `apt_floor_lab` 은 세션 임시 표(`CREATE TEMP TABLE`)만 쓴다.
- `new_apartment_complex_year` 는 파이프라인(`pipeline/build_new_apartment_dataset.py`)만 쓰고 API 경로가 없다.

**그래서 promote 전에 할 일**(6.1):
- 위 4개 표를 운영에서 떠서, 로컬 반영본에 **키 이전을 적용해** 합친다. geocode 는 `building_key` 기준이라 옛 키 → 새 키 변환이 필요하다.
- 합친 뒤 로컬 덤프를 다시 뜬다.

## 3. 시작 전 동기화 확인 (로컬 = 운영)

로컬에 반영하기 **전에** 한다. 다르면 멈춘다(promote 가 운영에만 있는 것을 지운다).

```bash
# 로컬
py scripts/ops/collective_p2_verify/prod_sync_check.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file backend/.env --out logs/collective_p2/sync_local_collective.json
# (rent_stats·built_stats 도 --db-env RENT_DATABASE_URL / BUILT_DATABASE_URL 로 같게)
# 운영 — 스크립트 폴더만 /opt/ch2_Macro/scripts/ops/collective_p2_verify/ 로 복사해 실행(pipeline 불필요)
python3 prod_sync_check.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/sync_prod_collective.json
# 운영 JSON 을 로컬로 가져와
py scripts/ops/collective_p2_verify/prod_sync_check.py compare logs/collective_p2/sync_local_collective.json sync_prod_collective.json \
   --result-out logs/collective_p2/sync_result_collective.json
```

- **결과는 셋:** 통과(종료 코드 0) / 차이(1) / 검증 못 함(2).
  - 큰 표를 건너뛰었거나(`--allow-heavy` 없이 200만 행 초과 표) 쿼리가 시간 초과면 「검증 못 함」이다.
  - 필수 표가 양쪽 모두 없어도 「검증 못 함」이다.
  - **실제 적용(5절)은 「통과」 결과 파일만 받는다.** 그래서 큰 표 비교(T 승인)를 포함해 통과를 받아야 한다.
- `--result-out` 결과 파일(DB 마다)이 5절 `--sync-result` 로 들어간다. 파일이 48시간보다 오래되면 거부된다.

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

- **운영 전용 표(2.5)는 동기화 비교에서 다를 수 있다**(지도를 본 만큼 좌표 캐시가 늘어남). 이 4개 표의 차이는 멈춤 사유가 아니라 6.1 에서 합칠 대상으로 기록한다. 그 밖의 표 차이는 멈춘다.

### 3.1 PG 버전 해시 확인 (해시 비교를 쓸 수 있는지)

- 로컬 PG 18.6 과 운영 PG 16.14 에서 같은 행이 같은 해시(`to_jsonb`·`md5`·`COLLATE "C"`)를 내는지 미검증이다.
- **동기화 확인과 같은 날, 이미 같다고 알려진 작은 표로 먼저 본다.** 세 DB 모두 있고 토지에서 복사해 오는 `region_codes`·`region_code_history` 다. 3절 행 수 비교에서 같게 나온 것을 확인한 뒤 돌린다.

```bash
py scripts/ops/collective_p2_verify/prod_hash_compare.py pgcheck --db-env COLLECTIVE_DATABASE_URL --env-file backend/.env --out logs/collective_p2/pgcheck_local.json
python3 prod_hash_compare.py pgcheck --db-env COLLECTIVE_DATABASE_URL --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/pgcheck_prod.json
py scripts/ops/collective_p2_verify/prod_hash_compare.py compare logs/collective_p2/pgcheck_local.json pgcheck_prod.json
```

- 결과에 따라 다음과 같이 한다.
  - 「hash 같음」 → 7.2 를 `--mode hash`(기본)로 한다.
  - 「hash 만 다름」 → 7.2 를 `--mode sums` 로 한다(조각마다 행 수 + 열마다 값 있는 행 수 + 숫자 열 합계 + 글자 열 길이 합).
  - 「sums 도 다름」 → 두 표가 실제로 다르다. 동기화 문제이므로 멈춘다.
- 로컬끼리(18.6 vs 18.6) 시험 실행으로 「hash 같음」을 확인했다(`collective_stats_p2r`).

### 3.2 월간 배치 멈추기·다시 켜기

- **월간 배치는 로컬 PC 에서 사람이 돌리고 promote 로 올린다.** 집합 `run_collective_cycle_csv.py`, 복합 `run_built_cycle_csv.py`, 토지 `run_land_cycle_csv.py`, 임대 분기 import 가 그렇다.
- 저장소에는 운영 서버 cron·systemd timer 가 없다(`deploy/templates` 에 `ch2-macro-backend.service`·`ch2-board.service` 만 있음).
- **멈추기:**
  1. 반영 기간(3절 시작 → 낮 로컬 적용·검증 → T 확인 → 새벽 promote → 7절 확인 끝) 동안 로컬 월간 러너와 다른 promote 를 시작하지 않는다(T 결정). 다른 에이전트·작업자에게 「집합·임대·복합 DB 동결」을 알린다.
  2. 운영 서버에서 읽기 전용으로 예약 작업이 없는지 확인한다: `crontab -l; sudo crontab -l; systemctl list-timers --all | grep -i ch2`. 무엇이 나오면 멈추고 보고한다.
- **다시 켜기:** 7절 운영 확인(Opus)이 끝나면 동결을 푼다. 다음 월간 cycle 은 SOP 대로 진행한다.
  - 다음 월간 적재부터 `building_keys.py` 의 C-01·C-2 키 규칙이 적용된다.
  - 월간 integrity 의 C-2형 경고가 0 인지 본다(9절).

## 4. 사전 조건

| # | 조건 | 확인 |
|---|---|---|
| 1 | **코드:** `data/collective-p2` 가 main 에 병합돼 운영에 배포됨. 키 재매핑 미들웨어·새 빌더 포함. 미들웨어는 연결표가 비어 있으면 통과만 하므로 데이터보다 먼저 배포해도 된다 | 운영 배포 해시 · `/health` |
| 2 | **동기화:** 3절 비교 다름 0 | 3절 JSON |
| 3 | **동결:** 3.2 | — |
| 4 | **디스크:** 로컬 — 덤프 3개 + `_p2_before` 보존 표 · 운영 — 반영 전 덤프 3개(-Fc) + 업로드한 .sql.gz 3개 + 새 DB. 운영 디스크(Lightsail 80GB SSD, `docs/PARCEL_MASTER_DESIGN.md`)의 여유가 **올릴 DB 크기의 2.5배**보다 작으면 멈춘다 | `df -h /var/lib/postgresql /var/backups` |
| 5 | **원천 파일(로컬):** K-apt 기본정보·필지고유번호 xlsx, 공시지가 slim 원천, 표제부 DB(5.3) | 경로 존재 |
| 6 | **접속 대상:** 로컬 `backend/.env` 의 `COLLECTIVE_/RENT_/BUILT_DATABASE_URL`·`DATABASE_URL`·`PARCEL_MASTER_DATABASE_URL` 이 의도한 DB 를 가리킴. 값은 출력하지 않고 `SELECT current_database()` 로 이름만 확인 | — |
| 7 | **두 번에 나눔(T 결정):**<br>- 1회차(낮): 3절 확인 → 로컬 적용(약 3시간 20분) → 5.4 전체 검증 → **T 확인**<br>- 2회차(새벽): 6.1 운영 전용 표 합치기 → promote → 7절 확인<br>- 그 사이 동결 유지 | — |
| 8 | **표제부 DB:** 5.0 으로 진짜 `parcel_master` 를 로컬에 만들어 둠(1회차 전) | 5.0 |

## 5. 실행 순서 — 로컬 실제 DB 에 반영 (Codex)

- 로컬 반영 전 **로컬 덤프**(로컬 되돌리기용)를 뜬다: `pg_dump -Fd -j 4 -d <db> -f backups\p2\<db>.dir`.
- 명령·기대값은 Phase C 리허설과 같다. DB 이름만 `*_p2r` 대신 실제 이름이다(`--collective-db collective_stats` 등).
- 아래 시간은 로컬 리허설 실측이다.
- `PY`, `P=pipeline`, `AS_OF=<현재 as_of, YYYY-MM-01>`, `W="--as-of $AS_OF --windows 3,5,7"`.

### 5.0 표제부 DB `parcel_master` 만들기 (1회차 전, 실제 반영 전에 — 지금은 만들지 않음)

- Phase C 에서 로컬 서버에 `parcel_master` 가 없었다.
- title_fill 은 이 DB 의 `building`(표제부 집합 행)을 읽는다.
- 리허설 사본 `parcel_master_p2r` 는 **실제 반영에 쓰지 않는다**(T 결정). 원천 파일로 진짜 이름의 DB 를 만든다.

```powershell
# 1) 빈 DB (로컬)
psql -U postgres -c "CREATE DATABASE parcel_master"
# 2) 접속 대상을 그 DB 로(세션 환경변수만, .env 는 바꾸지 않음)
$env:PARCEL_MASTER_DATABASE_URL = "<로컬 서버 URL>/parcel_master"
# 3) 원천 표제부 파일에서 집합 표제부 적재 — 시도 두 묶음(리허설 c14 와 같은 명령), 대장 겹치기 생략
cd pipeline
py -u -m parcel_master.load_title_pilot --skip-ledger
py -u -m parcel_master.load_title_pilot --skip-ledger --sido <parcel_master.paths.EXPAND_SIDO 전부>
```

| 항목 | 내용 |
|---|---|
| 원천(읽기만) | `raw/raw addition/건축물대장/국토교통부_건축물대장_표제부+(2024년+09월·2025년+07월·2026년+07월)/mart_djy_03.txt` |
| 쓰는 곳 | `parcel_master` DB(스키마는 로더가 `apply_schema` 로 만듦) · 스캔 캐시 `pipeline/parcel_master/_cache/`(gitignore) |
| 리허설 소요 | 37분(대전·충북 19분 + 나머지 18분, 3판 재스캔) |
| 기대 | 집합 `building` 1,881,261행 · 필지 366,838(리허설 사본과 같아야 함 — `SELECT count(*) FROM building` 비교) |
| worktree 에서 돌릴 때 | 로더가 저장소 기준 `raw/` 를 찾는다. 원본 저장소(`D:\ch2\ch2_Macro`)에서 돌리거나, worktree 면 `mklink /J raw <원본 raw>` → 끝나면 `rmdir raw` → raw 4,176파일 확인(`docs/ops/DEPLOY_PATHS.md`) |

- 만든 뒤 5.3 범위 드라이런(`scope_dryrun.py`)이 `--parcel-db parcel_master` 로 이 DB 를 읽기 전용으로 본다.

### 5.1 키 이전 (원장)

| # | 명령 | 소요 | 기대값(리허설) |
|---|---|---|---|
| 1 | `migrate_p2_keys.py --collective-db collective_stats --built-db built_stats --rent-db rent_stats` (드라이런) | 수 분 | 키 바뀌는 행 166,595 · 분할 옛 키 1,531 → 새 키 3,447 · 충돌 0 · **C-2 확정 후 채움** |
| 2 | 위 + `--real-apply --confirm-db collective_stats --confirm-db built_stats --confirm-db rent_stats --sync-result logs/collective_p2/sync_result_collective.json --sync-result …_rent.json --sync-result …_built.json` | 23분 | DB 마다 원자적(3개 전체는 아님, 2.3a). `p2_migration_log` 기록 |
| 3 | 위 + `--verify` | 3.5분 | 16항목 OK(옛 시도명 0 · 옛 키 남은 행 0 · 연결표 7,414 · 원장 행 수 불변) |
| 4 | `fix_p2_deal_types.py --collective-db collective_stats --raw-root <raw> --logs-dir <logs> --real-apply --confirm-db collective_stats --sync-result logs/collective_p2/sync_result_collective.json` | 5.3분 | 분양권 비정상·공란 → 0·0 · 비주거 공란 ≤ 1 |
| 4a | **C-2 키 이전 — C-2 확정 후 채움** (`migrate_p2_keys` 에 C-2 판정 파일 연결 필요, 아래 메모) | | |

**실제 적용 모드(`--real-apply`) — 키 이전·거래유형 보정·annual 정리 공통:**

- 쓰기는 세 조건을 모두 만족해야 한다(하나라도 빠지면 쓰기 전에 멈춤).
  1. `--real-apply` 플래그
  2. 대상 DB 이름을 `--confirm-db` 로 **다시 입력**(대상마다 한 번, 목록이 정확히 같아야 함)
  3. 대상 DB 마다 3절 동기화 확인 **통과** 결과 파일(`--sync-result`, `prod_sync_check compare --result-out`, 48시간 이내)
- 허용 대상은 `collective_stats`·`built_stats`·`rent_stats` 뿐이다(`land_stats`·`*_p2r` 거부).
- 쓰기 직전 `current_database()` 가 지정 이름과 같은지 다시 본다.
- `--real-apply` 는 적용만 한다. 실제 DB 되돌리기는 로컬 덤프 복원이고, `--rollback` 과 같이 쓰면 거부된다.
- 리허설 모드(`--apply`, `*_p2r`)의 가드는 그대로다.

**C-2 메모(코드 준비됨, 판정값은 Cursor 확인 뒤):**
- **판정 저장:** 집합 DB 표 `collective_building_key_c2_units`(DDL `building_keys.C2_DDL`). 열은 `base_key·asset_type·beopjungri_code·main_lot·building_year·part·decision(split|keep)·source·decided_at·note` 다. 본번이 들어 있어 저장소 파일로 두지 않는다(T 결정).
- **월간 적재:**
  - `import_refined` 가 이 표를 읽어 `building_keys.apply_building_key_split_c2` 로 키를 배정한다.
  - 처음 보는 본번이 3건 이상이라 새 조각이 생기면, 그 조각을 **판정 표에 자동 등록**한다(`source=auto_ingest`, 조각 번호 = 그 키·동의 최대 + 1). 다음 달에는 표를 기준으로 같은 조각에 배정되므로, 3건 → 새 조각 다음 달 1건이 다른 조각으로 새지 않는다.
  - 처음 보는 본번의 「기존 거래 수」는 base_key 와 그 **모든 파생 조각 키**를 합해 센다.
  - 월간 검사가 자동 등록 조각 수를 「판정 검토 대상」 경고로 보여 준다.
  - 표가 없거나 비면 그대로다. 비상 해제는 `CH2_COLLECTIVE_KEY_SPLIT_C2=0`.
- **옛 키:**
  - 가장 큰 그룹(`part 0`)이 옛 키를 유지하고, 나머지 그룹만 새 키가 된다.
  - 연결표 `collective_building_key_map` 에 `reason` 에 `c2` 가 들어간 행(예 `c2_split`)으로 「옛 키 → 새 조각 키」를 남긴다.
  - 키 재매핑 미들웨어는 C-2 옛 키를 409 로 막지 않고 그 키로 연다. 응답 헤더 `X-CH2-Key-C2-Split` 와 JSON 객체 응답의 `key_split_c2`(「분리된 단지 있음」·새 키 목록)를 붙인다.
  - C-01 옛 키(1:N)는 그대로 409. C-01 새 키가 다시 C-2 옛 키면 그 키로 열고 C-2 안내를 붙인다(테스트로 확인).
- **남은 일:** 1회성 이전(`migrate_p2_keys`)에 C-2 판정 표를 읽어 원장 키·연결표를 바꾸는 단계를 연결하는 일은 C-2 확정 뒤에 한다(12절 3).

### 5.2 통계표 재생성 (이번 as_of 만)

| # | 명령 | 소요 | 기대값 |
|---|---|---|---|
| 5 | `build_collective_building_stats.py $W --replace-as-of --prune-annual` | 20분 | 3/5년 거래 합 불변 · 7년 옛 시도명 0 · 합성 주소 0 |
| 6 | `collective/prune_split_annual_p2.py --collective-db collective_stats --real-apply --confirm-db collective_stats --sync-result logs/collective_p2/sync_result_collective.json --mismatch-csv <logs>/…csv` | 1분 미만 | 2019~2020 분할 옛 키 annual 2,126행 삭제, 불일치 0 |
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
  - **실제 DB 판 `scripts/ops/collective_p2_local/scope_dryrun.py`**(읽기 전용, Codex 검토 대상)로 네 단계를 실제 실행과 같은 함수·같은 키 목록 제한으로 계산해 「목록 밖」 수를 센다. 네 단계는 K-apt·title_fill·사전 단계·공시지가다.
  - 가드:
    - 집합 DB 이름 = `collective_stats`, 표제부 DB = `parcel_master` 와 정확히 같아야 한다.
    - `*_p2r` 는 거부한다.
    - 접속 호스트는 localhost 만 허용한다.
    - 모든 세션 읽기 전용이다.
  - 시간 제한: 쿼리마다 `statement_timeout`(`--statement-timeout`, 기본 600초) + 전체 실행 시간 제한(`--max-minutes`, 기본 30분, 넘으면 종료 코드 3).
  - 호스트는 SQLAlchemy 실제 접속 인자로 판정한다. URL 쿼리의 `host`·`hostaddr`·`service` 와 원격 `PGHOST`·`PGHOSTADDR`·`PGSERVICE` 는 거부한다.
  - 기대: 모든 「목록 밖」 = 0(아니면 종료 코드 1, 실행하지 않음). 예상 5~10분.
  - 명령: `py scripts/ops/collective_p2_local/scope_dryrun.py --keys-file <목록> --kapt-file <K-apt xlsx> --snapshot-ym 202607`

| # | 단계 | 명령 | 소요 | 기대값(리허설) |
|---|---|---|---|---|
| 14 | K-apt | `build_collective_building_attributes.py --kapt-file <xlsx> --asset-type apartment --new-keys-only --snapshot-ym 202607 --keys-file <목록>` (먼저 `--dry-run`) | 3.6분 | 274행 · builder_master +1 · 목록 밖 0 |
| 15 | title_fill | `python -m parcel_master.apply_title_fill --snapshot-ym 202607 --new-keys-only --keys-file <목록>` (먼저 `--dry-run`) | 2.8분 | fill 3,077(아파트 0 · 연립 3,030 · 오피스텔 47) · 사전 단계 3,351행(목록 키만) |
| 16 | 공시지가 | `cd backend; python -m collective.import_assessed_land_price --from-slim --keys-file <목록> --insert-only` (먼저 `--dry-run`) | 약 5.6분 | +3,326행 · 기존 행 덮기 0 |
| 17 | 매매·임대 연결 | `rent/build_sale_building_map.py` | 3.5분 | 정확 1,068 · 연결표 경유 400 · 1:N 6 |
| 18 | 복합 scope | `built/build_scope_stats.py --as-of $AS_OF --windows 3,5,7` 뒤 그 as_of 옛 시도명 행 삭제(리허설 `c3_built_scope_cleanup.py` 와 같은 SQL) | 15초 | 옛 시도명 81 → 0 |
| 19 | 재발 방지 검사 | `collective/integrity_p2.py --deep` | 수 분 | 옛 시도명 0 · 동 이름 ≥2 판정 밖 0 · annual 합 = 원장 합 · 합성 주소 0 · **C-2형 판정 밖 0**(C-2 반영 뒤) |
| 20 | **C-2 관련 — C-2 확정 후 채움** | | | |

**title_fill(15) — 표제부 DB**

- 5.0 에서 만든 **진짜 `parcel_master`** 를 읽는다(`PARCEL_MASTER_DATABASE_URL=…/parcel_master`).
- `parcel_master_p2r` 는 쓰지 않는다(T 결정).
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

### 5.4 로컬 검증 (1회차 끝 → T 확인)

- `prod_c5_core.py --env-file backend/.env --out logs/collective_p2/local_c5.json` 를 돌린다.
- 7.1 기대값(0 이어야 할 지표)을 모두 통과해야 한다. 이 JSON 이 운영 비교의 기준이다.
- 운영 비교용 행 해시 스냅샷도 뜬다.
  - `prod_hash_compare.py snapshot --db-env <DB별> --out logs/collective_p2/hash_local_<db>.json` 로 DB 3개를 뜬다.
  - 로컬 반영 직후에 뜨고, promote 덤프 전에는 로컬을 바꾸지 않는다.

## 6. 운영 반영 (promote, 새벽)

### 6.1 직전 재확인·운영 전용 표 합치기 (2회차 새벽, promote 직전)

1. 3절 `prod_sync_check` 로 **운영**만 다시 스냅샷한다. 3절의 운영 JSON 과 비교해 2.5 의 4개 표 밖은 다름 0 이어야 한다(그 사이 운영이 바뀌지 않음).
2. **운영 전용 표 떠서 로컬에 합치기**(2.5):

```bash
# 운영(읽기) — 표만 데이터로
sudo -u postgres /usr/lib/postgresql/16/bin/pg_dump -Fc --data-only -d collective_stats \
  -t collective_building_geocodes -t collective_commercial_map_geocodes -t qa_audit_run -f /var/backups/ch2/p2/prod_only_collective.dump
sudo -u postgres /usr/lib/postgresql/16/bin/pg_dump -Fc --data-only -d rent_stats -t rent_building_geocodes -f /var/backups/ch2/p2/prod_only_rent.dump
```

   - 로컬로 가져와 **임시 DB**(예 `prod_only_tmp`)에 복원한다.
   - 그다음 로컬 반영본에 합친다.
     - geocode 3표: `building_key`(비주거는 `cluster_key`)에 키 이전을 적용한다. 연결표로 1:1 은 새 키, 분할 옛 키 좌표는 버린다(동이 갈려 좌표가 맞지 않음). 그 뒤 `INSERT … ON CONFLICT (키) DO NOTHING` 한다. 로컬에 이미 있는 키는 로컬 값을 유지한다.
     - `qa_audit_run`(관리자 QA 기록) — **id 충돌을 비교해 합친다:**
       1. 운영 행의 `id` 가 로컬에 없으면 그대로 추가한다.
       2. 같은 `id` 가 로컬에도 있으면, `id` 를 뺀 모든 열을 비교한다. 같으면 같은 기록이므로 건너뛴다.
       3. 다르면 서로 다른 기록이다. 운영 행에 **새 id**(`nextval` 로 받은 로컬 시퀀스 값)를 주어 추가하고, 옛 id → 새 id 대응을 `logs/collective_p2/qa_audit_id_remap.csv` 에 남긴다.
       4. 끝나면 시퀀스를 보정한다: `SELECT setval(pg_get_serial_sequence('qa_audit_run','id'), (SELECT max(id) FROM qa_audit_run));`
       - 건수 확인: 합친 뒤 행 수 = 로컬 원래 행 + 1번 행 + 3번 행.
   - 합친 뒤 5.4 의 `prod_c5_core`(가벼운 지표)·해시 스냅샷을 다시 뜨고, promote 용 덤프를 다시 만든다(2.2).
   - 이 합치기 SQL 은 C-2 확정 뒤 리허설 때 스크립트로 만들어 리허설 DB 에서 시험한다(13절 C-9).
3. 반영 직전 운영 덤프(2.2 스크립트가 자동으로 뜸, 아래는 위치 고정용 수동 덤프).
4. 운영 디스크(4절 #4)를 확인한다.

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
  - **promote 뒤 `analysis_cache` 를 비운다**(T 결정): `cd /opt/ch2_Macro/backend && .venv/bin/python scripts/clear_analysis_cache.py --with-base-cache`. 토지 DB 의 유료 분석 캐시라 이번 DB 와 직접 관련은 없지만 확인 전에 비운다.
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
- `--skip-heavy` 로 가벼운 지표만 1분 안에 먼저 볼 수 있다. 무거운 검사는 **실행하지 않고 「건너뜀」**으로 표시한다. 가벼운 검사는 쿼리마다 10초 제한이 있다.
  - 결과는 셋: 통과(0) / 차이(1) / 검증 못 함(2, 건너뜀·쿼리 실패 포함). 건너뜀이 하나라도 있으면 통과가 아니다.
  - 남은 옛 키 검사는 C-01 사유(`split`·`honam_sido+split`)만 센다. `c2_split` 은 본 조각이 옛 키를 쓰므로 뺀다.
  - `c2_shape_pending` 은 0 이어야 한다.
- 무거운 검사는 T 승인 뒤 실행한다.

### 7.2 행 해시 비교 — `prod_hash_compare.py`

```bash
python3 prod_hash_compare.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/hash_prod_collective.json
py scripts/ops/collective_p2_verify/prod_hash_compare.py compare logs/collective_p2/hash_local_collective.json hash_prod_collective.json
```

- 대상 표는 이번 반영이 바꾸는 표다. 원장·통계·속성·연결표·보존 표가 들어간다(스크립트 `TARGETS`).
- 큰 표는 `building_key` 첫 글자 16조각, 또는 id 범위 16조각으로 나눠 조각마다 시간 제한(기본 600초)을 둔다.
- 기대값은 **다른 표·조각 0** 이다. promote 는 같은 덤프라 id 까지 같다.
- 결과는 셋: 통과(0) / 차이(1) / 검증 못 함(2). 조각 쿼리 실패(시간 초과)나 필수 표가 양쪽 모두 없으면 「검증 못 함」이다.
- 기본 대상에는 보존 표(`*_p2_before`, 이름 꼴로 자동 포함)와 C-2 판정 표(`collective_building_key_c2_units`)가 들어 있다.
- 예상 소요는 collective 25~50분 · rent 30~65분 · built 1~2분이다(로컬 c8 해시 실측 기반, 운영 최대 2배).

### 7.3 Insight 비교

- Insight 14·08·03·12 를 C-2 반영 리허설 뒤 로컬에서 다시 계산한 값으로 고정한다(`scripts/lab/collective_p2/c22_insight_recompute.py`).
  - before = 로컬 원본, after = 리허설. 기간은 공개 스냅샷과 같게 한다.
- **운영 반영 뒤에는 공개 스냅샷(정적)이 바뀌지 않는다.** 고정한 after 값을 공개할지는 별도 결정이다.
- **Insight 14 는 wip 브랜치 생성기로 비교만 한다**(main 에 반영하지 않음, T 결정).
  - 생성기 파일만 logs 로 꺼낸다: `git show wip/ai-revision-20261109:backend/app/collective/apt_officetel_same_building_lab.py > logs/collective_p2/insight/gen14.py`
  - `c22_insight_recompute.py run --side before|after --gen14 logs/collective_p2/insight/gen14.py` 로 돌린다.
  - 그 파일이 main 에 없는 모듈을 import 하면 실패한다. 그때는 「재계산 못 함」으로 기록하고 공개 스냅샷만 둔다.

## 8. 롤백 — 반영 직전 운영 덤프로 되돌림

**판단 기준(하나라도 해당하면 되돌린다):**

| # | 확인 항목 | 되돌리는 조건 |
|---|---|---|
| R1 | 7.1 옛 시도명 · 합성 주소 · annual 불일치 · 남은 분할 옛 키 행 | 0 이 아님 |
| R2 | 7.1 `--expect` 비교 | 결과 「차이」(종료 코드 1). 「검증 못 함」(2)은 무거운 검사를 다시 돌려 통과·차이로 확정 |
| R3 | 7.2 해시 비교 | 결과 「차이」. 「검증 못 함」은 시간 제한을 늘려 다시 돌려 확정 |
| R4 | promote 스크립트 | `psql ON_ERROR_STOP` 실패 · `/health` 가 60초 안에 응답 없음(스크립트 종료 코드 1) |
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
sudo systemctl start ch2-macro-backend
# /health 는 재시작 직후 실패할 수 있다 → 최대 60초(2초 간격 30번) 다시 묻는다
ok=0; for i in $(seq 1 30); do if curl -sf --max-time 3 http://127.0.0.1:8000/health; then ok=1; break; fi; sleep 2; done
[ "$ok" = 1 ] || { echo "ERROR: /health 60초 안에 응답 없음" >&2; exit 1; }
```

- **예상 시간:** promote 복원 시간과 비슷하다(2.3 미실측). -Fc 덤프의 `pg_restore -j 2` 는 plain SQL 적재보다 빠를 수 있다.
- **새 상태가 된 DB 는 모두 함께 되돌린다**(2.3a 표). 연결표가 DB 사이에 걸려 있어 한 DB 만 되돌리면 키가 어긋난다.
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
3. `migrate_p2_keys` 에 C-2 판정 표를 연결한다(원장 키 바꾸기·연결표 `c2_split` 행, 5.1 메모). 6.1 운영 전용 표 합치기 스크립트도 만든다.
4. 리허설 DB 를 덤프에서 다시 만들고 키 이전부터 전체 리허설을 다시 돌린다. 속성·공시지가는 새 분할 키 목록(C-01 + C-2)으로 채운다.
5. c5~c10 과 c8(해시)을 다시 검증한다. Insight 재계산 값을 고정한다(`c22_insight_recompute.py run --side before/after` → `compare`).
6. 이 런북의 「C-2 확정 후 채움」 칸을 채운다.
7. 5.0 표제부 DB 를 만든다(실제 반영 전).
8. Codex 검토 → T 승인 → 1회차(낮, 로컬 적용·검증) → T 확인 → 2회차(새벽, promote) → Opus 운영 확인.

## 13. 실행 전 확인 사항 (T·Codex)

| # | 확인 | 상태 |
|---|---|---|
| C-1 | title_fill 표제부 DB | **결정됨** — 5.0 진짜 `parcel_master` 생성(p2r 미사용) |
| C-2 | C-2 판정 저장 위치 | **결정됨** — 집합 DB 표 `collective_building_key_c2_units` |
| C-3 | 반영 나누기 | **결정됨** — 낮 로컬 적용·검증 → T 확인 → 새벽 promote |
| C-4 | promote 소요(2.3) | 합계 반영(단계 약 47분·API 중단 약 36분). **단계별 Codex 실측표 원본 붙여 넣기 필요** |
| C-5 | 범위 드라이런 실제 DB 판 | **만듦** — `scripts/ops/collective_p2_local/scope_dryrun.py`(Codex 검토) |
| C-6 | `analysis_cache` 비우기 | **결정됨** — promote 뒤 |
| C-7 | Insight 14 | **결정됨** — wip 생성기로 비교만 |
| C-8 | C-2 옛 키·미들웨어 | **결정됨·구현** — 가장 큰 그룹 옛 키 유지, 409 대신 안내 |
| C-9 | 운영 전용 표(2.5) 합치기 SQL — 스크립트화·리허설 시험 | 열림(C-2 리허설 때) |
| C-10 | PG 버전 해시 | **절차 넣음** — 3.1 `pgcheck`, 다르면 `--mode sums` |
