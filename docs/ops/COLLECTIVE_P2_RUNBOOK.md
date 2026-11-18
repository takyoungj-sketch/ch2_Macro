# 집합 2단계 운영 런북 (초안 v6 — Codex 3차 검토 반영)

> **상태:** 초안 v4 (2026-11-14, Claude Code — Codex P2 검토 8+4 항목 반영). **실행하지 않았다.** C-2 칸은 Cursor 확인(16일 이후)·T 결정 뒤 채운다.
> **실행 절차:** Codex 검토 → T 승인 → Cursor 실행(로컬 반영 → promote) → Opus 운영 확인.
> **근거:** [Phase C 리허설 보고](../lab/COLLECTIVE_P2_PHASEC_REPORT_20261113.md). 시간·기대값은 **로컬 리허설 실측**이다. 운영 서버는 더 느릴 수 있다.

## 0. 결정 (T, 2026-11-14 — Opus 추천안)

| 항목 | 결정 | 이 문서 |
|---|---|---|
| 적용 방식 | **로컬 DB 에 적용한 뒤 기존 전체 DB 반영(promote) 경로로 운영에 올린다** | 2·5·6절 |
| title_fill | 로컬에서 실행. **원천 파일로 진짜 `parcel_master` 를 로컬에 만든 뒤** 실행(실제 반영 전에 만든다, `p2r` 사본은 쓰지 않음) | 5.0 · 5.3 |
| 운영 확인 | 읽기 전용 운영 확인 스크립트(`scripts/ops/collective_p2_verify/`) | 3·7절 |
| 롤백 | **반영 직전 운영 덤프로 되돌린다.** 통계표 재빌드 경로는 쓰지 않고 리허설도 하지 않는다 | 8절 |
| 서비스 | **새벽 점검 창에 nginx 점검 모드(API 전체 503)를 건다**(T 결정 2026-11-16 안 A — 운영 전용 표 덤프부터 promote 끝까지 운영 쓰기 차단) | 3.2 · 6.0 · 6.3 |
| 나누기 | **코드 선배포(4-1, 직후부터 배치·보강 금지) → 낮: 동결(3.2 F1~F6) → 무거운 동기화·(동결 확인 90초 뒤) 가벼운 비교 기준 기록 → 키 이전·로컬 적용·검증·T 확인(운영 서비스 그대로) → 새벽 한 묶음: 점검 모드 ON → 진행 중 요청 0 → 2a built QA → 2b 90초 → 3 비교 → 운영 전용 4표 덤프·병합·c29 → promote → R5 → OFF(06:00 마감).** | 4-1 · 3.2 · 5 · 6 |
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

**Codex 실측(운영, 읽기 전용 확인 — 2026-11-14):**

- **출처:** VPS sudo journal 의 단계별 명령 시작 시각, `*_vps_pre_promote_*.dump` mtime, 백엔드 journal.
- **읽는 법:**
  - 초 단위 로그라 「<1초」는 같은 초에 다음 단계가 시작됐다는 뜻이다.
  - 「덤프」는 운영 반영 전 백업이다. 로컬 덤프와 scp 는 들어 있지 않다.

| 실행일(KST) | DB | 덤프 | 정지 | DB 재생성 | 적재·인덱스 | 권한 | 재시작 | 덤프 시작→앱 준비 |
|---|---|---|---|---|---|---|---|---|
| 8/9 | built_stats | 8초 | 1초 | <1초 | 15초 | <1초 | 5초 | 29초 |
| 8/9 | collective_stats | 2분 22초 | <1초 | 1초 | 6분 37초 | <1초 | 5초 | 9분 5초 |
| 9/2† | built_stats | 16초 | 공통 | 1초 | 29초 | <1초 | 공통 | — |
| 9/2† | collective_stats | 3분 9초 | 공통 | 1초 | 8분 54초 | <1초 | 공통 | — |
| 9/2† | rent_stats | 4분 45초 | 공통 | 1초 | 18분 5초 | 1초 | 공통 | — |
| 10/2‡ | built_stats | 18초 | 공통 | <1초 | 29초 | <1초 | 공통 | — |
| 10/2‡ | collective_stats | 3분 54초 | 공통 | 4초 | 10분 29초 | <1초 | 공통 | — |
| 10/2 | rent_stats | 5분 43초 | <1초 | 1초 | 23분 19초 | <1초 | 7초 | 29분 10초 |
| 11/3§ | built_stats | 18초 | 1초 | <1초 | 39초 | <1초 | 7초 | 1분 5초 |
| 11/3§ | collective_stats | 4분 7초 | <1초 | 1초 | 10분 52초 | <1초 | 7초 | 15분 7초 |
| 11/3§ | rent_stats | 6분 13초 | <1초 | 2초 | 24분 23초 | <1초 | 6초 | 30분 44초 |

- † 9/2 **일괄 실행**(`_vps_promote_202609.sh`): 토지까지 포함해 한 번 정지했다가 시작했다. 공통 정지 1초, 재시작 9초.
- ‡ 10/2 **일괄 실행**: 백업을 먼저 뜨고 한 번 정지했다. 공통 정지 <1초, 재시작 7초.
- § 11/3 **재개 실행**(`_tmp_vps_promote_rest_202611.sh`): health 확인은 재시도 방식이다.
- 일괄·재개 실행은 `vps_promote_db_sql.sh` 직접 호출의 실적이 아니다.

**최신(11/3) 기준 합계:**
- 덤프 시작부터 앱 준비까지 세 DB 단계 합계 **약 47분**(1분 5초 + 15분 7초 + 30분 44초).
- API 중단(정지 ~ 재시작 끝) **약 36분**(DB 마다 정지·재생성·적재·권한·재시작의 합).

- **P2 보존 표가 더해지면 시간이 늘 수 있다.** 이 값은 과거 기준값으로만 쓴다. 이번 실행에서 단계별 시간을 다시 기록해 다음 달 SOP 에 남긴다.
- 8절 롤백 판단 R6(「지난 promote 기록의 2배」)의 기준은 위 표의 최신 DB 별 「덤프 시작→앱 준비」다(built 1분 5초 · collective 15분 7초 · rent 30분 44초).
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

- **결과는 셋:** 통과(종료 코드 0) / 차이(1) / 검증 못 함(2). 결과는 내기 전에 `ops_guards.validate_result` 를 거친다.
  - **측정 시각:** 스냅샷마다 `measured_at` 을 기록한다. 비교 결과 파일의 시각(`created_at`)은 입력 스냅샷 중 **가장 오래된 `measured_at`** 이다. 48시간 검사는 이 값으로 한다(비교한 시각은 `compared_at`).
    - 그래서 오래된 스냅샷을 지금 다시 compare 해도 통과가 되지 않는다.
    - 측정 시각이 없는 스냅샷은 「검증 못 함」이다.
  - 스냅샷 쿼리 실패, 빈 스냅샷, 서로 다른 DB 비교는 「검증 못 함」이다(예전 거짓 성공).
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

- PG 확인도 `--result-out` 과 종료 코드 0/1/2 를 낸다(결과 파일 종류 `prod_hash_pgcheck`, `validate_result` 를 거침).
  - 작은 표가 한쪽이라도 없거나 쿼리가 실패하면 「검증 못 함」(2)이다. 예전에는 표가 없어도 「hash 같음」이 나왔다.
- 결과에 따라 다음과 같이 한다.
  - 「hash 같음」 → 7.2 를 `--mode hash`(기본)로 한다.
  - 「hash 만 다름」 → 7.2 를 `--mode sums` 로 한다(조각마다 행 수 + 열마다 값 있는 행 수 + 숫자 열 합계 + 글자 열 길이 합).
  - 「sums 도 다름」 → 두 표가 실제로 다르다. 동기화 문제이므로 멈춘다.
- 로컬끼리(18.6 vs 18.6) 시험 실행으로 「hash 같음」을 확인했다(`collective_stats_p2r`).

### 3.2 동결 · 낮 무거운 동기화 · 운영 쓰기 차단(점검 모드) — T 결정 2026-11-16 「안 A」

- **월간 배치는 로컬 PC 에서 사람이 돌리고 promote 로 올린다.** 집합 `run_collective_cycle_csv.py`, 복합 `run_built_cycle_csv.py`, 토지 `run_land_cycle_csv.py`, 임대 분기 import 가 그렇다.
- 저장소에는 운영 서버 cron·systemd timer 가 없다(`deploy/templates` 에 `ch2-macro-backend.service`·`ch2-board.service` 만 있음).

**동결 범위(낮 무거운 동기화 전에 시작 → 밤 점검 창의 7절 확인 끝까지).** 다른 에이전트·작업자에게 아래 목록을 그대로 알린다:

**동결 이전 공백 구간도 금지:** 코드 선배포(4-1)가 끝난 직후부터 이 동결 시작까지, 로컬·운영의 **월간 배치(F1)·보강 작업(F4) 및 그 결과의 promote를 실행하지 않는다.** 새 키 빌더가 옛 DB를 먼저 바꾸면 코드만 되돌릴 수 있는 전제가 깨진다. 선배포 전에 진행 중인 해당 작업이 없음을 확인하고, 금지 시작 시각·대상·실행 주체(Cursor)를 기록한다. 이 금지는 동결 F1~F6으로 이어지며, 7절 확인 완료 뒤 해제한다. 5절의 승인된 P2 이전·보강은 이 런북 순서 안에서만 실행한다.

| # | 멈추는 것 | 대상 | 왜 |
|---|---|---|---|
| F1 | 월간 배치 | 집합·복합·토지·임대 러너(로컬), 그 결과의 promote | 로컬 반영본·운영이 바뀌면 낮 동기화·밤 비교가 무의미 |
| F2 | 다른 promote·복원 | `vps_promote_*`·`vps_restore_*`·`vps_sync_*` 등 운영 DB 를 바꾸는 모든 스크립트 | 운영 DB 가 바뀜 |
| F3 | 직접 SQL | 운영·로컬 `collective_stats`·`rent_stats`·`built_stats` 에 쓰는 psql·스크립트(수동 보정·DDL·VACUUM FULL 포함). 읽기 전용 확인 쿼리만 허용 | 카운터·행이 바뀜 |
| F4 | 보강 작업 | 속성·K-apt·표제부(title_fill)·공시지가·좌표 일괄 채우기·KB 채우기 등 보강 적재(로컬·운영) | 같은 |
| F5 | 관리자 QA 저장 | `POST /api/admin/qa/specified`·`/random` 의 `save_db=true`(특히 복합 `built_enriched` — 6절 머리) | 운영 `qa_audit_run` 이 바뀜(built 는 병합 대상이 아님) |
| F6 | 운영 코드 배포 | 백엔드·스키마를 바꾸는 배포(이번 반영 코드는 4절 #1 로 미리 배포) | 운영 DB·동작이 바뀜 |

- 운영 서버 예약 작업 없음 확인(읽기 전용): `crontab -l; sudo crontab -l; systemctl list-timers --all | grep -i ch2`. 무엇이 나오면 멈추고 보고한다.
- **낮 순서:** 동결 시작 → 동결 확인 시각 기록 → (1) 무거운 동기화 → 확인 시각부터 90초 뒤 (2) 운영 카운터 기록 → 5절 로컬 적용 → 5.4 검증·(3) 로컬 카운터 기록(①) → 로컬 전체 해시(②) → T 확인 → built 덤프·업로드(S 실측)·built QA 행 수 기록 → 밤 6.1.
- **순서 판정 시계:** ①~⑤ 에 쓰는 시각은 모두 로컬 PC 시계의 UTC 이고, 각 명령이 끝난 뒤에 찍는다. 출처는 `local`. DB `now()` 는 산출물의 `server_now`(출처 `server`)로만 남기고 순서 판정에 쓰지 않는다. 로컬에서 끝나는 명령은 스크립트가 끝날 때 찍는다. 운영 서버에서 실행한 산출물은 `--order-clock defer` 로 비워 두고, **생성 직후 바로 로컬로 가져와** `stamp-local` 로 찍는다. `server_now` 가 없거나 출처가 `server` 가 아니면 거절한다. 찍는 시각(로컬 UTC)과 `server_now` 의 차이가 10분을 넘어도 거절한다(종료 2, 파일은 고치지 않음). 서버에서 만든 오래된 파일을 늦게 가져와 오늘 시각이 찍히는 것을 막는다.
- **낮(동결 시작 직후, 로컬 적용 전, Cursor) — 무거운 동기화와 카운터 기록을 같이:**
  - 동결을 확인한 순간, 명령을 돌릴 기계의 UTC 를 적는다. 운영 기록은 서버 `date -u -Iseconds` → `QUIET_AT_SERVER`. 로컬 기록은 로컬 PC UTC → `QUIET_AT_LOCAL`. PostgreSQL 이 직전 쓰기를 통계에 올리기까지 최대 약 60초 걸리므로, **그 시각부터 90초가 지난 뒤에** 카운터 기준을 기록한다. 90초 미만으로 명령을 시작하면 종료 1 이고 DB 를 읽지 않으며 파일을 쓰지 않는다.
  1. 3절 `prod_sync_check snapshot --allow-heavy`(세 DB) → 아직 적용 전인 로컬과 compare(다름 0) → 결과 파일(`--result-out`, 48시간 유효 — 5절 로컬 적용·밤 병합 `--real-apply` 가 쓴다). 예상 collective 3~6 · rent 5~10 · built 1분(운영 최대 2배). 이 확인은 읽기만 하므로 90초를 기다리지 않아도 된다. 90초는 아래 카운터 기록에만 걸린다.
  2. **동결 확인 90초 뒤** 운영의 가벼운 비교 기준을 기록한다(읽기 전용, 몇 초):
     `cd /opt/ch2_Macro && backend/.venv/bin/python scripts/ops/collective_p2_verify/prod_stat_compare.py snapshot --confirmed-at $QUIET_AT_SERVER --order-clock defer --db-env COLLECTIVE_DATABASE_URL --db-env RENT_DATABASE_URL --db-env BUILT_DATABASE_URL --env-file backend/.env --out /var/backups/ch2/p2/stat_day_prod.json`
     — 세 DB 모든 표의 `pg_stat_user_tables(n_tup_ins, n_tup_upd, n_tup_del)` 와 `pg_stat_database.stats_reset`, `track_counts`. 한 DB 를 10초 간격으로 두 번 읽어 값이 같을 때만 남긴다. 종료 0 이어야 한다(`--confirmed-at` 부터 90초 미만 · 시간 초과 · DB 누락 · `track_counts` 가 on 이 아님 · 두 번 읽기가 다름은 1). 이 파일의 순서 시각은 서버에서 찍지 않는다. 생성이 끝나면 바로 로컬로 가져와 `stamp-local --field measured_at` 한다. `server_now` 와 10분을 넘기면 종료 2 로 거절되므로 나중에 찍지 않는다.
  3. 로컬 카운터 기준(①)은 5.4 전체 해시(②)보다 **먼저** 기록한다: `py scripts\ops\collective_p2_verify\prod_stat_compare.py snapshot --confirmed-at $QUIET_AT_LOCAL --db-env … --env-file backend\.env --out logs\collective_p2\stat_day_local.json`. 같은 90초 규칙이다. 명령이 끝난 시각이 `measured_at`(출처 `local`)이다.
  - 이 뒤로 밤까지 F1~F6 을 하지 않는다. 밤에는 무거운 동기화를 다시 하지 않고 **가벼운 비교**(6.1 3)로 「낮 이후 운영 전용 표 밖 쓰기 없음」만 본다.
- **운영 쓰기 차단 = nginx 점검 모드(안 A):** 운영 서버가 직접 쓰는 표(2.5 — 좌표 캐시 3표·QA 기록)는 API 요청으로만 바뀐다. 밤 점검 창(6.1) 동안 **nginx 가 API 전체에 503** 을 돌려주게 해서, 운영 전용 4표 덤프부터 promote 끝까지 운영에 새 쓰기가 생기지 않게 한다.
  - **나누기:** 코드 선배포·즉시 배치/보강 금지(4-1) → 낮 = 동결·무거운 동기화·카운터 기록 → 키 이전·로컬 적용·검증·T 확인(운영 서비스는 그대로). 밤 = 6.1 의 한 묶음(점검 모드 ON → … → OFF).
  - **`FREEZE_AT`** = 점검 모드 ON 을 확인하고 진행 중 요청 0 을 확인한 시각(KST). 운영 전용 4표 덤프는 이 시각 뒤에 뜬 것만 쓴다(병합 스크립트 `--freeze-at` 가 검사, 오래되면 종료 코드 2).
  - **점검 모드는 nginx 에서 걸고 백엔드와 무관하다.** `vps_promote_db_sql.sh` 가 DB 마다 백엔드(`ch2-macro-backend`)를 멈추고 다시 켜도 nginx 는 그대로라 점검 모드(503)가 유지된다. promote 스크립트의 `/health` 확인과 R5 스모크는 nginx 를 거치지 않고 `http://127.0.0.1:8000` 으로 백엔드에 직접 묻는다 → 점검 모드 중에도 확인할 수 있다.
  - 설치·명령·확인 방법은 6.0(서버 파일 수정은 Cursor 몫).
- **다시 켜기:** 6.1 마지막에 점검 모드 OFF, 7절 운영 확인(Opus)이 끝나면 동결을 푼다. 다음 월간 cycle 은 SOP 대로 진행한다.
  - 다음 월간 적재부터 `building_keys.py` 의 C-01·C-2 키 규칙이 적용된다.
  - 월간 integrity 의 C-2형 경고가 0 인지 본다(9절).

## 4. 사전 조건

| # | 조건 | 확인 |
|---|---|---|
| 1 | **코드:** `data/collective-p2`의 main 병합·구형 DB 호환 검수 뒤 **4-1 코드 선배포**. 키 재매핑 미들웨어·새 빌더 포함. 연결표가 없거나 비면 재매핑·C-2 라벨은 적용하지 않는다. 선배포 직후부터 월간 배치·보강 금지 | 배포 파일 해시 · `/health` · 구형 DB 주요 API |
| 2 | **동기화:** 3절 비교 다름 0 | 3절 JSON |
| 3 | **동결:** 3.2(로컬 동결) · 6.0 점검 모드 설치 끝(점검 창 전날까지, 깃발 ON/OFF 시험) | `nginx -t` · 깃발 시험 503 |
| 4 | **디스크:** 로컬 — 덤프 3개 + `_p2_before` 보존 표 · 운영 — 반영 전 덤프 3개(-Fc) + 업로드한 .sql.gz 3개 + 새 DB. 운영 디스크(Lightsail 80GB SSD, `docs/PARCEL_MASTER_DESIGN.md`)의 여유가 **올릴 DB 크기의 2.5배**보다 작으면 멈춘다 | `df -h /var/lib/postgresql /var/backups` |
| 5 | **원천 파일(로컬):** K-apt 기본정보·필지고유번호 xlsx, 공시지가 slim 원천, 표제부 DB(5.3) | 경로 존재 |
| 6 | **접속 대상:** 로컬 `backend/.env` 의 `COLLECTIVE_/RENT_/BUILT_DATABASE_URL`·`DATABASE_URL`·`PARCEL_MASTER_DATABASE_URL` 이 의도한 DB 를 가리킴. 값은 출력하지 않고 `SELECT current_database()` 로 이름만 확인 | — |
| 7 | **두 번에 나눔(T 결정):**<br>- 낮(운영 무관): 3절 확인 → 로컬 적용(약 3시간 20분) → 5.4 전체 검증 → **T 확인** · built promote 덤프·업로드 미리<br>- 새벽(한 묶음, 6.1): 점검 모드 ON → 진행 중 요청 0 → 90초 대기 → 운영 전용 4표 덤프·병합·c29·재실행 → collective·rent promote 덤프·scp → 세 DB promote → R5 → OFF → 7절 확인<br>- 그 사이 로컬 동결 유지 | — |
| 8 | **표제부 DB:** 5.0 으로 진짜 `parcel_master` 를 로컬에 만들어 둠(1회차 전) | 5.0 |
| 9 | **운영 서버 스크립트(배포 전 확인, Cursor):** R5 스모크가 서버에서 돈다 — `/opt/ch2_Macro/scripts/ops/collective_p2_r5_smoke.py` 가 배포돼 있음 · `cd /opt/ch2_Macro && backend/.venv/bin/python scripts/ops/collective_p2_r5_smoke.py --help` 종료 0 · `backend/.venv/bin/python -c "import sqlalchemy, psycopg2"` 종료 0 · `backend/.env` 에 `COLLECTIVE_DATABASE_URL`. 이 스크립트는 `pipeline/` 이 필요 없다(서버에 `pipeline/collective/*` 가 없어도 됨). 운영 확인 스크립트(`scripts/ops/collective_p2_verify/`)도 같은 방식으로 `--help` 확인. **가벼운 비교(6.1 3)도 서버에서 돈다:** `backend/.venv/bin/python scripts/ops/collective_p2_verify/prod_stat_compare.py --help` 종료 0(pipeline 불필요). OFF 뒤 되돌리기는 보존만 하므로 병합·c29 를 서버에 둘 필요 없다 | 각 명령 종료 0 |

### 4-1. 코드 선배포 · DB 반영 전 코드 복귀 (Cursor)

**선배포 실행:** 2026-11-18 09:37 KST. `origin/main`은 `6633cf5`에서 `eec7883`으로 fast-forward했다. `deploy/scripts/deploy-from-windows.ps1 -Scope all`. 서버 `main.py`·`collective/key_remap.py`·`product_gate.py`·`shared/macro-shell/features.tsx` 해시는 이 커밋과 같다. DB는 바꾸지 않았다. 이 시각부터 2026-11-20 데이터 반영(7절 확인)까지 로컬·운영의 월간 배치(F1)·보강(F4)와 그 결과의 promote를 하지 않는다. 실행 주체 Cursor.

1. **코드부터 배포한다.** D-085가 포함된 main `6633cf5`와 P2를 합친 `762804e` 및 후속 검수 수정본을 main에 병합·검증한 뒤, `deploy/AGENT_DEPLOY_RUNBOOK.md`에 따라 배포한다. 집합뿐 아니라 임대·공통 게이트·AI·공유 UI도 바뀌므로 `deploy/scripts/deploy-from-windows.ps1 -Scope all` 범위로 확인한다. `collective` 단일 scope로 공통 모듈까지 배포됐다고 가정하지 않는다. R5·검증 스크립트의 서버 배치는 4절 #9대로 별도 확인한다. 서버에는 git이 없으므로 커밋명만 적지 말고 배포 파일 해시와 실행 시각을 남긴다.
2. 아직 운영 DB는 옛 형태다. `/health`, 집합 주거·비주거 목록/상세, 임대 목록·rolling·거래·매매 연결, built 주요 API와 D-085 공개/관리자 차단을 확인한다. 이때 C-01 409·C-2 안내가 나오는 **R5는 실행하지 않는다. R5는 세 DB promote가 끝난 뒤 6.1 #12에서만 실행**한다. 연결표가 없는 구형 DB에서 R5의 분할 기대값은 성립하지 않는다.
3. **선배포 직후부터 낮 동결까지도 월간 배치·보강 작업 금지.** 3.2의 선배포 공백 구간 금지를 알리고 기록한다. 코드 배포만 하고 P2 이전 전에 `run_collective_cycle_csv.py` 등 새 빌더를 실행하지 않는다. 동결 뒤에도 5절 승인 절차 외 쓰기는 금지한다.
4. **운영 데이터 반영 전 코드 문제:** 운영 DB가 세 개 모두 옛 상태이고, 선배포 뒤 새 빌더·배치·보강이 실행되지 않았음을 확인한 경우에만 **`6633cf5` 코드를 재배포**한다. `git revert`나 서버 git 명령으로 대신하지 않는다. 별도 복귀 worktree를 `git worktree add <복귀폴더> --detach 6633cf5`로 준비하고, 고정 SSH 키를 안전하게 제공한 뒤 그 worktree의 `deploy/scripts/deploy-from-windows.ps1 -Scope all -SkipPush`로 재배포한다(main·원격을 과거로 되감거나 키를 커밋하지 않는다). 파일 해시·health·옛 키 상세 및 D-085를 재확인한다. 로컬 DB만 P2 적용됐다면 로컬은 5절 백업으로 따로 복원한다.
5. **운영 데이터가 일부라도 반영된 뒤에는 코드만 `6633cf5`로 되돌리기 금지.** 새 키·연결표를 옛 코드가 해석하지 못한다. 6.2·8절대로 점검 모드를 유지/다시 켜고, 새 상태가 된 DB를 모두 반영 직전 덤프로 복원·검증한 뒤에만 옛 코드 복귀를 판단한다. OFF 뒤에는 6.2의 운영 전용 데이터 보존 절차도 먼저 수행한다.

## 5. 실행 순서 — 로컬 실제 DB 에 반영 (Cursor)

- **실제 적용 전 단계:** 실제 적용(`--real-apply`)은 동기화 확인 「통과」 결과 파일을 요구한다.
  - 통과를 받으려면 큰 표를 포함한 **운영 동기화 확인 전체 실행**(3절 `prod_sync_check snapshot --allow-heavy`)이 필요하다.
  - 이 전체 실행은 운영 DB 에 10초를 넘는 쿼리를 보내므로 T 승인을 받고, **낮에 동결(3.2 F1~F6)을 시작한 뒤 로컬 적용 전에** 한다(T 결정 2026-11-16 — 밤에는 하지 않는다). 같은 때, 동결 확인 시각부터 90초가 지난 뒤에 가벼운 비교 기준(운영 `stat_day_prod.json`)을 기록한다(3.2).
  - 그 결과 파일(48시간 유효) 안에 로컬 적용과 밤 점검 창(병합 `--real-apply` 도 같은 파일을 쓴다)을 끝낸다.
- 로컬 반영 전 **로컬 덤프**(로컬 되돌리기용)를 뜬다: `pg_dump -Fd -j 4 -d <db> -f backups\p2\<db>.dir`.
- **Insight before 확보 — 로컬 적용 직전**(5.1 0a 전, 덤프와 같은 상태): `c22_insight_recompute.py run --side before`(08·03·12) · `c27_insight14_compare.py prepare → run --side before`. after 는 5.3 끝난 직후(5.4 전) 확보한다(7.3). 둘 다 c8 같은 되돌리기 전에 끝낸다.
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

**순서: C-2 판정 표 적재 → 승인값 대조 → 키 이전**(Codex Phase D 3). `H` = 승인된 판정 파일 `logs/collective_p2/c2_units_final.csv` 의 SHA-256(T 승인 때 기록), 행 수 4,311.

| # | 명령 | 소요 | 기대값(리허설) |
|---|---|---|---|
| 0a | `load_c2_units.py --collective-db collective_stats --approved-sha256 $H --approved-rows 4311` (드라이런 — 파일 해시·행 수 대조 + 형식 검사) | 수 초 | 4,311행 · split 단위 1,610 · 늘어나는 키 2,045 · 값이 다른 행 0 |
| 0b | 위 + `--real-apply --confirm-db collective_stats --sync-result logs/collective_p2/sync_result_collective.json` | 1분 | 판정 표 4,311행. `p2_migration_log`(step `load_c2_units`)에 파일 SHA-256·내용 해시 기록 |
| 1 | `migrate_p2_keys.py --collective-db collective_stats --built-db built_stats --rent-db rent_stats` (드라이런) | 수 분 | C-01: 키 바뀌는 행 166,595 · 분할 옛 키 1,531 → 새 키 3,447 · C-2: 늘어나는 키 2,045 · 옮겨지는 거래 14,288 · 충돌 0 · 자동 등록 0 |
| 2 | 위 + `--real-apply --confirm-db collective_stats --confirm-db built_stats --confirm-db rent_stats --sync-result logs/collective_p2/sync_result_collective.json --sync-result …_rent.json --sync-result …_built.json --c2-approved-sha256 $H --c2-approved-rows 4311` | 1시간(리허설 재실행 실측 59분) | **시작 전 판정 표 대조**: 표가 없거나 비었음 · 판정 행(자동 등록 `p2_migrate`·`auto_ingest` 제외) 수 ≠ 4,311 · 마지막 적재 기록의 파일 해시 ≠ `H` · 적재 뒤 내용이 바뀜 → 쓰기 전에 거부. 통과하면 DB 마다 원자적(3개 전체는 아님, 2.3a). `p2_migration_log` 기록 |
| 3 | 위 + `--verify` | 5.5분 | 20항목 OK(옛 시도명 0 · 옛 키 남은 행 0 · 연결표 9,695(C-01 7,414 + C-2 2,281) · 원장 행 수 불변 · C-2 4항목) |
| 4 | `fix_p2_deal_types.py --collective-db collective_stats --raw-root <raw> --logs-dir <logs> --real-apply --confirm-db collective_stats --sync-result logs/collective_p2/sync_result_collective.json` | 5.3분 | 분양권 비정상·공란 → 0·0 · 비주거 공란 ≤ 1 |
| 4a | C-2 키는 2번(`migrate_p2_keys`)이 판정 표를 읽어 같이 옮긴다(12.1 P1). 별도 명령 없음 | | |

**실제 적용 모드(`--real-apply`) — 키 이전·거래유형 보정·annual 정리 공통:**

- 쓰기는 네 조건을 모두 만족해야 한다(하나라도 빠지면 쓰기 전에 멈춤). 판정은 공통 가드 `scripts/ops/collective_p2_verify/ops_guards.py`.
  1. `--real-apply` 플래그
  2. 대상 DB 이름을 `--confirm-db` 로 **다시 입력**(대상마다 한 번, 목록이 정확히 같아야 함)
  3. 접속 대상이 **로컬 루프백**(`ops_guards.assert_local_target`, 허용 목록 방식).
     - URL 쿼리는 `sslmode`·`connect_timeout`·`application_name` 만 허용한다. 그 밖(`dsn`·`service`·`host`·`hostaddr`·`options` …)은 모두 거부한다.
     - 판정은 psycopg2 에 실제로 넘어갈 DSN 을 `psycopg2.extensions.parse_dsn` 으로 푼 값으로 한다. `PGHOST`·`PGHOSTADDR` 환경변수를 포함하고, hostaddr 가 host 보다 먼저 쓰인다.
     - `service`·`PGSERVICE`·`PGSERVICEFILE` 은 거부한다.
  4. 대상 DB 마다 3절 동기화 확인 결과 파일(`--sync-result`)이 `ops_guards.validate_result` 로 **통과**.
     - 필수 필드·형식을 갖춰야 한다.
     - 측정 시각은 미래가 아니고 48시간 이내여야 한다.
     - 대상 목록이 일치하고, 실패 기록이 없고, diff·unverified 가 모두 0 이어야 한다.
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
  - **동시 실행 안전:**
    - 배치에 든 판정 키마다 base_key 단위 advisory lock(`pg_advisory_xact_lock`)을 잡는다. 잡은 뒤 판정 표를 다시 읽고 조각 번호를 배정한다. 두 적재가 동시에 「최대+1」을 같은 번호로 배정하지 않는다.
    - 자동 등록이 `DO NOTHING` 으로 충돌하면(잠금 밖 다른 쓰기) 표의 실제 조각 번호를 다시 읽어 그 값으로 다시 배정한다.
  - 월간 검사가 자동 등록 조각 수를 「판정 검토 대상」 경고로 보여 준다.
  - 표가 없거나 비면 그대로다. 비상 해제는 `CH2_COLLECTIVE_KEY_SPLIT_C2=0`.
- **옛 키:**
  - 가장 큰 그룹(`part 0`)이 옛 키를 유지하고, 나머지 그룹만 새 키가 된다.
  - 연결표 `collective_building_key_map` 에 `reason` 에 `c2` 가 들어간 행(예 `c2_split`)으로 「옛 키 → 새 조각 키」를 남긴다.
  - 키 재매핑 미들웨어는 C-2 옛 키를 409 로 막지 않고 그 키로 연다.
  - `/key-status` 는 숫자를 돌려주지 않으므로 `product_gate` 에서 무료 집합 화면을 볼 수 있는 사용자(비로그인 포함)에게 연다. 임대 `/key-status` 는 임대 화면과 같은 규칙이다.
    - C-01 409 본문·안내문과 C-2 후보 목록 모두 **키·이름·동만** 담는다. `n_tx`·`n_tx_window`·조각 번호 같은 수치는 넣지 않는다(미들웨어가 상세 함수의 다른 칸도 버림).
    - 비로그인 응답에 숫자 값이 없는지 테스트로 확인한다. 화면에도 후보 건수를 표시하지 않는다.
  - 화면(집합·임대):
    - 조회에 실패하면(401·403·5xx·연결) 「정상」이 아니라 「단지 분리 여부를 확인할 수 없습니다」로 알린다.
    - 분리된 단지 링크를 누르면 기존 행을 복사하지 않는다. 후보 키의 실제 목록 행을 다시 조회한 뒤 상세를 연다. 조회하는 동안 로딩을 보이고, 실패하면 안내한다. 응답 헤더 `X-CH2-Key-C2-Split` 와 JSON 객체 응답의 `key_split_c2`(「분리된 단지 있음」·새 키 목록)를 붙인다.
  - C-01 옛 키(1:N)는 그대로 409. C-01 새 키가 다시 C-2 옛 키면 그 키로 열고 C-2 안내를 붙인다(테스트로 확인).
- **연결됨:** 1회성 이전(`migrate_p2_keys`)이 C-2 판정 표를 읽어 원장 키·연결표를 바꾼다(12.1 P1). 실제 DB 는 판정 표 적재·대조(위 0a·0b·2번 시작 전 대조) 뒤에만 시작한다.

### 5.2 통계표 재생성 (이번 as_of 만)

| # | 명령 | 소요 | 기대값 |
|---|---|---|---|
| 5 | `build_collective_building_stats.py $W --replace-as-of --prune-annual` | 20분 | 3/5년 거래 합 불변 · 7년 옛 시도명 0 · 합성 주소 0 |
| 6 | `collective/prune_split_annual_p2.py --collective-db collective_stats --real-apply --confirm-db collective_stats --sync-result logs/collective_p2/sync_result_collective.json --mismatch-csv <logs>/…csv` | 1분 미만 | 2019~2020 분할 옛 키 annual 2,126행 삭제, 불일치 0 |
| 6a | `python -m collective.c2_annual_replace_p2 --collective-db collective_stats --real-apply --confirm-db collective_stats --sync-result logs/collective_p2/sync_result_collective.json` (먼저 드라이런) → `--verify` 는 c6 | 1분 미만 | 리허설: 대상 키 3,654 · 교체 3,835 · 삭제 558 · 재계산 거래 11,299 |
| 6b | `python -m collective.prune_fixed_annual_orphans_p2 --collective-db collective_stats --real-apply --confirm-db collective_stats --sync-result logs/collective_p2/sync_result_collective.json` (먼저 드라이런: 지역·유형별, `unexpected_regions`) | 1분 미만 | 리허설: 5,866행(거래 38,830) 삭제, 전부 인천 검단구·서해구·영종구·제물포구 · 고정 연도 annual 합 = 원장 합(전 지역) |
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
  - 시간 제한:
    - 쿼리마다 `statement_timeout`(`--statement-timeout`, 기본 600초)을 둔다.
    - 전체 실행 시간 제한(`--max-minutes`, 기본 30분)은 **실제 타이머**다. 진행 중인 쿼리가 있어도 끝내고 종료 코드 3 을 낸다.
  - 호스트는 공통 가드 `ops_guards.assert_local_target` 로 판정한다(실제 적용 모드와 같음).
    - URL 쿼리 host·hostaddr 와 원격 `PGHOST`·`PGHOSTADDR`(localhost URL + 원격 `PGHOSTADDR` 포함)를 거부한다.
    - service·`PGSERVICE`·`PGSERVICEFILE` 도 거부한다.
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

- **먼저 Insight after 확보**(5.3 끝난 직후, 이 검증 전 — 7.3): `c22 run --side before --label ops_after` · `c27 run --side before --label ops_after` → 각 `compare`.
- `prod_c5_core.py --env-file backend/.env --out logs/collective_p2/local_c5.json` 를 돌린다.
- 7.1 기대값(0 이어야 할 지표)을 모두 통과해야 한다. 이 JSON 이 운영 비교의 기준이다.
- 운영 비교용 행 해시 스냅샷도 뜬다.
  - **먼저** 3.2 의 로컬 카운터 기준(`stat_day_local.json`, ①)을 끝내고, **그 다음** `prod_hash_compare.py snapshot --db-env <DB별> --out logs/collective_p2/hash_local_<db>_day.json` 로 DB 3개를 뜬다(**낮 전체 해시** ② — 밤에는 병합한 표만 다시 떠서 overlay, 6.1 10). ① 과 ② 가 같은 초여도 된다. ② 가 ① 보다 이르면 밤 overlay 가 거절한다.
  - 로컬 반영 직후에 뜨고, 그 뒤 로컬은 밤 병합(4표) 말고는 바꾸지 않는다. 해시가 끝난 시각이 각 파일의 `measured_at`(출처 `local`)이다. `server_now` 는 참고다.

## 6. 운영 반영 (새벽 점검 창 — 한 묶음)

**낮(운영 무관):** 5절 키 이전·로컬 적용 → 5.4 검증 → **T 확인**. built_stats 는 운영 전용 표가 없고 병합이 바꾸지 않으므로 promote 덤프·업로드(2.2)를 **낮에 미리** 해 둔다. 3절 동기화 확인 결과 파일(48시간 유효)이 새벽까지 유효한지 본다.

- **built QA 기록(운영 `built_stats.qa_audit_run`) — 낮 built 덤프 시점:** 이 표는 운영 관리자 QA(`POST /api/admin/qa/specified|random`, 복합 도메인 `built_enriched`, `save_db=true`)가 쓴다. built 는 병합 대상이 아니라 promote 가 덮으면 그 사이 생긴 행이 사라진다. 그래서:
  1. 낮 built promote 덤프를 뜰 때 Cursor 가 운영에서 **읽기 전용으로 행 수를 기록**한다(현재 0):
     `sudo -u postgres psql -d built_stats -v ON_ERROR_STOP=1 -Atc "SET default_transaction_read_only = on; SELECT to_regclass('public.qa_audit_run') IS NOT NULL, (SELECT count(*) FROM qa_audit_run), (SELECT coalesce(max(id), 0) FROM qa_audit_run)"`
     → 결과(`t|0|0` 형태)와 시각을 `logs/collective_p2/built_qa_count_day.txt` 에 남긴다. 표가 없으면 `to_regclass` 만 `f` 로 확인하고(`SELECT to_regclass('public.qa_audit_run')`) 「없음」으로 기록.
  2. **그 뒤 밤 점검 창이 끝날 때까지 built QA(관리자 QA 저장) 실행 금지.** 관리자·에이전트에게 알린다(3.2 동결 알림에 함께). 다른 도메인 QA 저장도 이 기간에는 하지 않는다(집합 QA 기록은 병합되지만 늘리지 않는다).
  3. **낮 기록이 0 이 아니면 그날은 진행하지 않는다**(6.2 첫 줄).
  4. 밤 6.1 **2a**(점검 ON → 진행 중 요청 0 다음)에서 같은 쿼리로 다시 확인한다. **다르면 즉시 중단 → 점검 모드 OFF**(아무것도 바꾸지 않은 상태 — 6.2).

### 6.0 nginx 점검 모드 — 설치(1회, 점검 창 전날까지) · 켜기 · 끄기 · 확인 (Cursor)

**점검 대상 = 백엔드(`127.0.0.1:8000`)로 넘기는 실효 location 17곳**(Codex 운영 확인 2026-11-16). 저장소 템플릿에 있는 16곳 + viewer(템플릿 없음, 서버 설정만). **17곳 모두의 맨 앞**에 같은 조각을 넣는다(서버 파일 수정은 Cursor).

| # | 서버(server_name) | 설정 파일 | location | ON 시험 URL(→ 503) |
|---|---|---|---|---|
| 1 | macro.ch2data.com (HTTPS 443) | `nginx-ch2-macro.conf` | `/api/` | `https://macro.ch2data.com/api/` |
| 2 | 〃 | 〃 | `= /health` | `https://macro.ch2data.com/health` |
| 3 | 〃 | 〃 | `~ ^/(docs\|redoc\|openapi\.json)$` | `https://macro.ch2data.com/docs` · `/redoc` · `/openapi.json` |
| 4 | 〃 | `nginx-ch2-lab-api.conf`(include) | `^~ /api/regional-profile/lab/` | `https://macro.ch2data.com/api/regional-profile/lab/` |
| 5 | 〃 | 〃 | `^~ /api/admin/` | `https://macro.ch2data.com/api/admin/` |
| 6 | 〃 | 〃 | `^~ /api/built/lab/` | `https://macro.ch2data.com/api/built/lab/` |
| 7 | 13.209.203.178 (HTTP 80) | `nginx-ch2-macro.conf` | `/api/` | `http://13.209.203.178/api/` |
| 8 | 〃 | 〃 | `= /health` | `http://13.209.203.178/health` |
| 9 | 〃 | `nginx-ch2-lab-api.conf`(include) | `^~ /api/regional-profile/lab/` | `http://13.209.203.178/api/regional-profile/lab/` |
| 10 | 〃 | 〃 | `^~ /api/admin/` | `http://13.209.203.178/api/admin/` |
| 11 | 〃 | 〃 | `^~ /api/built/lab/` | `http://13.209.203.178/api/built/lab/` |
| 12 | ch2data.com (허브) | `nginx-ch2data-hub.conf` | `/api/auth/` | `https://ch2data.com/api/auth/` |
| 13 | 〃 | 〃 | `/api/billing/` | `https://ch2data.com/api/billing/` |
| 14 | 〃 | 〃 | `/api/platform/` | `https://ch2data.com/api/platform/` |
| 15 | 〃 | 〃 | `/api/board/` | `https://ch2data.com/api/board/` |
| 16 | 〃 | 〃 | `/api/ops/` | `https://ch2data.com/api/ops/` |
| 17 | viewer.ch2data.com | 서버의 viewer 설정(저장소 템플릿 없음 — Cursor 가 경로 기록) | `/api/auth/` | `https://viewer.ch2data.com/api/auth/` |

- 설치 때 `sudo nginx -T | grep -n "proxy_pass http://127.0.0.1:8000"` 로 백엔드 proxy 줄을 다시 센다. `nginx -T` 는 파일을 한 번씩만 출력하므로 **두 서버가 include 하는 랩 API 조각(3줄)은 한 번만 보인다** → 기대 **14줄**(macro 설정 5 · 랩 조각 3 · 허브 5 · viewer 1) = 실효 location 17곳. `sudo nginx -T | grep -c "include /etc/nginx/snippets/ch2-maintenance.conf"` 도 **14**. 수가 다르면 표를 고치고 T 에게 알린다. 실효 17곳은 아래 일괄 확인(19 URL)으로 본다.
- 17곳 일괄 확인(켜기·끄기 시험 공통, 응답 코드만 출력):

```bash
for u in https://macro.ch2data.com/api/ https://macro.ch2data.com/health https://macro.ch2data.com/docs https://macro.ch2data.com/redoc \
         https://macro.ch2data.com/openapi.json https://macro.ch2data.com/api/regional-profile/lab/ https://macro.ch2data.com/api/admin/ \
         https://macro.ch2data.com/api/built/lab/ http://13.209.203.178/api/ http://13.209.203.178/health \
         http://13.209.203.178/api/regional-profile/lab/ http://13.209.203.178/api/admin/ http://13.209.203.178/api/built/lab/ \
         https://ch2data.com/api/auth/ https://ch2data.com/api/billing/ https://ch2data.com/api/platform/ https://ch2data.com/api/board/ \
         https://ch2data.com/api/ops/ https://viewer.ch2data.com/api/auth/; do
  printf '%s %s\n' "$(curl -s -o /dev/null -m 5 -w '%{http_code}' "$u")" "$u"; done
# 켜기: 모든 줄 503 · 끄기: 503 인 줄 0(평소 200·401·404 등)
```

```nginx
# /etc/nginx/snippets/ch2-maintenance.conf — 깃발 파일이 있으면 503(백엔드에 넘기지 않음)
if (-f /etc/nginx/ch2_maintenance.on) {
    add_header Retry-After 3600 always;
    return 503 '{"detail":"점검 중입니다. 잠시 뒤 다시 시도해 주세요.","maintenance":true}';
}
```

```nginx
location /api/ {
    include /etc/nginx/snippets/ch2-maintenance.conf;   # 추가(첫 줄)
    include /etc/nginx/snippets/ch2-api-proxy-token.conf;
    proxy_pass http://127.0.0.1:8000/api/;
    # …
}
```

- `return` 은 rewrite 단계라 Basic 인증(access 단계)보다 먼저 503 을 낸다 — 인증 없이도 점검 응답이 보인다.
- 깃발 파일 방식이라 켜기·끄기에 nginx reload 가 필요 없다(요청마다 파일이 있는지 본다).
- **설치(1회):** 조각 파일 만들기 → 위 location 들에 include → `sudo nginx -t && sudo systemctl reload nginx` → 깃발이 없는 상태에서 평소 응답(200·401 등)이 그대로인지 확인 → 깃발을 잠깐 만들어 503 이 나오는지 보고 바로 지운다.

| 동작 | 명령(운영 서버) | 확인 |
|---|---|---|
| **켜기** | `sudo touch /etc/nginx/ch2_maintenance.on` | 위 17곳 일괄 확인 → **도메인별 모두 503**: macro.ch2data.com 8 URL(6 location) · 13.209.203.178 5 · ch2data.com 5 · viewer.ch2data.com 1. 그리고 `curl -sf http://127.0.0.1:8000/health` → 200(백엔드 직접, nginx 안 거침) |
| **진행 중 요청 0** | ① `sudo ss -Htn state established '( dport = :8000 )' \| wc -l` → **0**(nginx→백엔드 연결) ② `sudo tail -n 500 /var/log/nginx/access.log \| grep ' /api/' \| grep -v '" 503 ' \| tail -3` → 보이는 줄의 시각이 모두 켠 시각 **전** ③ `sudo -u postgres psql -Atc "SELECT count(*) FROM pg_stat_activity WHERE datname IN ('collective_stats','rent_stats','built_stats') AND state <> 'idle' AND pid <> pg_backend_pid()"` → **0** | 셋 다 맞을 때까지 기다린다(최대 5분, 넘으면 남은 연결을 보고 결정). 확인한 시각 = `FREEZE_AT` |
| **끄기** | `sudo rm -f /etc/nginx/ch2_maintenance.on` | 17곳 일괄 확인 → **503 인 줄 0**(도메인별) · 화면 하나 열어 데이터 확인 |
| 상태 보기 | `test -f /etc/nginx/ch2_maintenance.on && echo ON \|\| echo OFF` | — |

- 점검 모드 중에도 서버 안 `http://127.0.0.1:8000` 은 열려 있다. 운영 확인 스크립트·R5 스모크·promote `/health` 는 이 주소로 한다.
- **promote 가 DB 마다 백엔드를 재시작해도 점검 모드는 유지된다**(nginx 설정·깃발 파일은 백엔드 재시작과 무관). 백엔드가 멈춘 동안 nginx 는 깃발 때문에 503 을 내고 502 로 바뀌지 않는다.

### 6.1 새벽 점검 창 — 순서(한 묶음, 실패하면 6.2)

**전제(낮에 끝나 있어야 함):** 3.2 동결(F1~F6) · 무거운 동기화 통과 결과 파일(48시간 유효) · 가벼운 비교 기준(`stat_day_prod.json`·`stat_day_local.json`) · 5.4 로컬 전체 해시(`hash_local_<db>_day.json`) · built QA 행 수 낮 기록 **= 0**(0 이 아니면 그날 진행하지 않음, 6절 머리) · built promote 덤프 업로드와 그 속도로 정한 `S`.

| # | 할 일 | 누가 | 통과 조건 | 예상 |
|---|---|---|---|---|
| 1 | **점검 모드 ON**(6.0 켜기) · 17곳 503 확인 | Cursor | 도메인별 17곳 모두 503(macro·IP·허브·viewer), 서버 안 `/health` 200 | 3분 |
| 2 | **진행 중 요청 0**(6.0 ①②③) → `FREEZE_AT`(KST, 덤프·병합용)와 `FREEZE_AT_UTC`(로컬 PC UTC, 순서 판정용)를 같은 순간에 기록. 같은 순간 서버 UTC(`date -u -Iseconds`)를 `QUIET_AT_SERVER` 로 적는다 | Cursor | 백엔드 연결 0 · 켠 뒤 503 아닌 API 응답 없음 · 앱 DB 세션 0 | 1~5분 |
| 2a | **built QA 행 수 재확인**(낮과 같은 읽기 전용 쿼리, 6절 머리) | Cursor | 낮 기록(0)과 같음. **다르면 즉시 중단 → 점검 모드 OFF**(아직 아무것도 바꾸지 않음) | 1분 |
| 2b | **90초 대기.** PostgreSQL 이 직전 쓰기를 통계에 올리기까지 최대 약 60초 걸린다. 2의 확인 시각부터 90초가 지난 뒤에만 3을 시작한다. 2a 와 따로 센다 | Cursor | 3의 `--confirmed-at` 이 90초 미만이면 종료 1(DB 를 읽지 않고 파일을 쓰지 않음). 90초는 통과 | 1.5분 |
| 3 | **가벼운 비교**(③, 무거운 동기화 대신 — 낮 이후 운영 전용 표 밖 쓰기 없음): 운영 `prod_stat_compare.py compare --confirmed-at $QUIET_AT_SERVER --order-clock defer --baseline /var/backups/ch2/p2/stat_day_prod.json --db-env COLLECTIVE_DATABASE_URL --db-env RENT_DATABASE_URL --db-env BUILT_DATABASE_URL --env-file backend/.env --result-out /var/backups/ch2/p2/stat_night_prod_result.json` · 로컬 `prod_stat_compare.py compare --confirmed-at $FREEZE_AT_UTC --baseline logs\collective_p2\stat_day_local.json --result-out logs\collective_p2\stat_night_local_result.json`(끝난 시각 = `compared_at`, 출처 `local`) | Cursor · Opus | 둘 다 종료 0. **실패(종료 1) = 중단 → OFF**: 확인 시각부터 90초 미만 · 운영 전용 표(집합 3 · 임대 1 · 복합 `qa_audit_run`) 밖 표의 `n_tup_ins·upd·del` 하나라도 다름 · `stats_reset` 바뀜 · 표 빠짐·새 표 · DB 누락 · `track_counts` 가 on 이 아님 · 한 DB 를 10초 간격으로 두 번 읽은 값이 다름 · **60초 안에 안 끝남**(10초 대기 3회를 포함한다. 접속이 멈춰도 60초에 끊는다. 시간 초과·누락은 통과가 아님) | **L** |
| 4 | **운영 전용 4표 새 덤프**(데이터만, 아래 명령) + manifest → 로컬 `logs/collective_p2/prod_only/` | Cursor | `created_kst ≥ FREEZE_AT` | 1분(덤프 실측 1.6초 · 0.6MB) |
| 5 | `git check-ignore` 로 커밋 대상 아님 확인 · 임시 원본 DB 2개 복원(표 구조는 로컬 반영본 `pg_dump --schema-only -t <표>` → `pg_restore --data-only`) | Opus | ignore 됨 · 임시 DB 행 수 = manifest | 5~9 합 5분(실측 4.6초) |
| 6 | 병합 드라이런(`--manifest … --freeze-at $FREEZE_AT`) | Opus | 종료 0. **manifest 엄격 검사**: DB 2개(`collective_stats`·`rent_stats`)·표 4개 정확히 — 누락·중복·모르는 DB/표·행 수 누락이면 쓰기 전에 종료 2 · SHA-256·크기 = 덤프 · 덤프 시각 ≥ `FREEZE_AT` · 임시 DB 행 수 = manifest | (실측 1.4초) |
| 7 | **병합 적용** `--real-apply …`(아래). 명령이 끝난 시각을 로컬 PC UTC 로 `MERGED_AT_UTC`(④)에 적는다 | Opus | 종료 0 · 보고서 `applied: true` · DB 마다 한 트랜잭션 · 계획 = 넣은/바꾼 행 = 최종 행 · 대상 원장에 없는 키는 버리고 `drop_not_in_ledger` 로 기록 | (실측 1.3초) |
| 8 | **c29 검사** `check --report <7 보고서>` | Opus | 종료 0. **엄격 판정**: `applied=true` · 두 쪽·네 표 보고서 · 필수 카운터 · 보고서의 원본/대상 DB 이름 = 검사 인자. 게이트: 병합 고아 0 · C-2/C-01 옛 키 좌표 0 · 조각 키 운영 좌표 0. 충돌 건수·규칙별 건수 기록 | (실측 4.4초) |
| 9 | 스냅샷 A → **병합 재실행** → 스냅샷 B → `idempotent --report <재실행 보고서> --a A --b B` | Opus | 종료 0: insert 0 · update 0 · QA 같은 id 추가·새 id 0 · 네 표 행 수·해시 같음 · QA 시퀀스 `last_value`·`is_called` 같음 | (실측 합 약 3초) |
| 10 | **전제: 3 의 가벼운 비교(운영·로컬) 통과.** ① 로컬 promote 덤프 collective·rent(2.2 — 병합 뒤라 여기서 다시 만든다) ② **병합한 표만 다시 해시**(⑤, 전체 행 해시는 낮 5.4 결과를 쓴다): `prod_hash_compare.py snapshot --db-env COLLECTIVE_DATABASE_URL --tables collective_building_geocodes,collective_commercial_map_geocodes,qa_audit_run --out logs\collective_p2\hash_local_collective_merged.json` · rent 는 `--tables rent_building_geocodes` → `overlay --base hash_local_<db>_day.json --patch hash_local_<db>_merged.json --stat-result logs\collective_p2\stat_night_local_result.json --merged-at $MERGED_AT_UTC --freeze-at $FREEZE_AT_UTC --out hash_local_<db>.json`. 거절(종료 2): 가벼운 비교가 통과가 아님, 시각 출처가 `local` 이 아님, ① 카운터 기준 > ② 낮 해시, 또는 ②<③<④<⑤ 가 아님, ⑤ 가 점검 ON 이전이거나 같음. built 는 낮 해시 그대로 ③ scp → 서버에서 크기·SHA-256 대조 | Opus → Cursor | 덤프 종료 0 · overlay 종료 0 · 대조 일치 | 덤프 6분 21초(리허설 DB 실측) + **H** + **S** |
| 11 | **세 DB promote**(2.2 `vps_promote_db_sql.sh`, collective → rent → built). DB 마다 `/health` OK 뒤 다음 | Cursor | 스크립트 종료 0(R4) | 47분(11/3 실측: built 1분 5초 · collective 15분 7초 · rent 30분 44초, 반영 전 덤프 포함) |
| 12 | `analysis_cache` 비우기(6.3) · **R5 스모크를 서버 localhost 로**(6.3) · `vps_collective_smoke.sh` | Cursor/Opus | R5 종료 0(3/3) · 스모크 통과 | 3분 |
| 13 | **점검 모드 OFF**(6.0 끄기) · 17곳 확인 — **마감 06:00 KST** | Cursor | 503 인 곳 0 | 2분 |
| 14 | 7절 핵심 확인(Opus, 읽기 전용) — OFF 뒤 **07:00 까지**: R5 는 12 에서 이미 끝났다. 여기서는 주요 화면과 7.1 | Opus | R1·R2 · 화면 | 7.1 |

- **시간식(T 결정):** **점검 ON 시작 ≤ 06:00 − (75.5분 + L + H + S + 30분)**. 06:00 = 점검 OFF 마감. 07:00 까지는 핵심 확인(R5·주요 화면·7.1)만 한다. 세 DB 전체 해시(7.2)는 **09:00 까지** 마치는 사후 검증이다. 거기서 차이가 나면 6.2 되돌리기를 판단한다. 그 사이 화면은 열려 있다.
  - **75.5분** = 기존 74분 + **1.5분**(2b. 요청 0 확인 뒤 90초. 2a 1분과 따로 센다).
  - **74분**(2b 를 빼기 전, L·H·S 를 뺀 단계 합): 1 3분 · 2 5분(상한) · 2a 1분 · 4 1분 · 5~9 5분 · 10 로컬 덤프 6분 21초 · 11 47분 · 12 3분 · 13 2분 = 73분 21초 → 74분.
  - **L = 1분**(가벼운 비교. 세 DB 를 10초 간격으로 두 번 읽는 30초가 60초 제한 안에 들어간다. 리허설 실측 2026-11-16 쿼리 자체는 0.5초 안쪽 — 표 47·14·9개. 운영 2배·사람 확인을 더해 1분으로 잡음).
  - **H = 1분**(병합 표 해시, 리허설 실측: collective 3표 0.49초 · rent 1표 0.41초 + overlay. 1분으로 잡음).
  - **S** = 낮 built 업로드에서 실측: 속도 `v = 파일 크기 / 걸린 시간`(`Measure-Command { scp … built_stats_p2_promote.sql.gz … }`), `S = 5.0GB / v × 1.2`. `logs/collective_p2/window_plan.txt` 에 v·S·시작 상한을 적는다.
  - 따라서 **시작 상한 = 06:00 − (107.5분 + S)**. 75.5 + L 1 + H 1 + 30 = 107.5. 예: v = 10MB/s → S ≈ 10분 → **04:02:30 전에 ON**. v = 5MB/s → S ≈ 20분 → 03:52:30 전.
  - 밤에 단계가 늦어지면 11(47분) 직전에 다시 본다: 「지금 + 47 + 3 + 2 분 ≤ 06:00」 이 아니면 11 을 시작하지 않고 6.2(반영 전 상태)로 OFF.
- 2a·2b·3·6·8·9 의 실패는 promote 전이라 운영이 바뀌지 않는다(6.2).

```bash
# 4 — 운영(읽기) · 표만 데이터로 · 점검 모드 ON·FREEZE_AT 뒤
TS=$(TZ=Asia/Seoul date +%Y%m%d_%H%M%S)
sudo -u postgres /usr/lib/postgresql/16/bin/pg_dump -Fc --data-only -d collective_stats \
  -t collective_building_geocodes -t collective_commercial_map_geocodes -t qa_audit_run -f /var/backups/ch2/p2/prod_only_collective_stats_${TS}.dump
sudo -u postgres /usr/lib/postgresql/16/bin/pg_dump -Fc --data-only -d rent_stats -t rent_building_geocodes \
  -f /var/backups/ch2/p2/prod_only_rent_stats_${TS}.dump
# manifest: production_read_only=true, created_kst=$TS,
#   archives=[{db: collective_stats, file, bytes, sha256, archive_rows: {collective_building_geocodes, collective_commercial_map_geocodes, qa_audit_run}},
#             {db: rent_stats, file, bytes, sha256, archive_rows: {rent_building_geocodes}}]  ← 정확히 이 DB 2개·표 4개
```

```powershell
# 6 드라이런 · 7 은 6 + --real-apply … (로컬 실제 반영본)
PY scripts\ops\collective_p2_merge_prod_only.py --src-collective prodonly_collective_src --src-rent prodonly_rent_src `
  --dst-collective collective_stats --dst-rent rent_stats --manifest logs\collective_p2\prod_only\<manifest>.json --freeze-at $FREEZE_AT `
  --report-out logs\collective_p2\merge_ops\run1.json
#   7: + --real-apply --confirm-db collective_stats --confirm-db rent_stats --sync-result …_collective.json --sync-result …_rent.json
# 8
PY scripts\lab\collective_p2\c29_merge_prod_only_check.py --dst-collective collective_stats --dst-rent rent_stats `
  --src-collective prodonly_collective_src --src-rent prodonly_rent_src --out-dir logs\collective_p2\merge_ops check --report <run1.json 절대 경로>
# 9 — (같은 c29 인자) snapshot --tag A → 7 다시(--report-out run2.json) → snapshot --tag B → idempotent --report <run2.json 절대 경로> --a A --b B
```

- **병합 규칙**(`scripts/ops/collective_p2_merge_prod_only.py`, 13절 C-9):
  - 좌표 3표: 키 이전 적용(연결표 1:1 은 새 키 · C-01 분할 옛 키·C-2 옛 키(본 조각 옛 키 포함) 좌표는 버림) → 로컬에 없는 키는 추가.
  - **같은 키 충돌(시각 열 밖 값이 다름) — 3표 공통(T 결정 2026-11-16):** 한쪽만 `status=ok` → ok 쪽 · 둘 다 ok → `geocoded_at` 이 더 최근인 쪽(같거나 운영 쪽이 없으면 로컬) · 둘 다 실패 → 로컬. 운영 쪽이 이기면 값 그대로 UPDATE. 시각 열만 다르면 그대로. 보고서에 `rule_*`·`update`·`kept_local`.
  - `qa_audit_run`: 시퀀스를 먼저 `max(로컬, 운영) + 1` 로 → 없는 id 그대로 추가 → 같은 id 같은 내용 건너뜀 → 같은 id 다른 내용은 새 id(`logs/collective_p2/qa_audit_id_remap.csv`) → 시퀀스 ≥ max(id) · 행 수 = 원래 + 추가.
  - 비주거(`collective_commercial_map_geocodes`)는 값을 고치지 않고 그대로 옮긴다(도로선 오류 수정은 별도 작업).
  - 보고서는 `applied`(적용해서 모든 트랜잭션이 커밋됐을 때만 true)와 DB 이름을 담는다. 드라이런 보고서는 c29 가 받지 않는다.
- 리허설 실측(2026-11-16 덤프, `*_p2r`): 좌표 5,413행 → 넣음 517 · C-2 옛 키 버림 34 · C-01 분할 옛 키 버림 24 · 같은 키 값 다름 1(운영 `not_found` · 로컬 `ok` → 「로컬만 ok」 로컬 유지, 바꾼 행 0) · 비주거 695행 → 넣음 92(값 그대로) · 임대 975행 → 넣음 0 · QA 1행 같음 · 고아 0(임대 28행은 P2 전부터 있던 것) · 재실행 insert·update 0, 4표 해시·시퀀스(`is_called` 포함) 같음.

### 6.2 실패하면 — 점검 모드를 유지한 채 할 일

**원칙:** 점검 모드는 운영이 「반영 전 상태」 또는 「반영 후 확인된 상태」가 될 때까지 켜 둔다. 끄는 것은 각 줄의 마지막 칸을 마친 뒤다.

| 멈춘 단계 | 운영 | 로컬 | 할 일(점검 모드 ON 유지) | 끝 |
|---|---|---|---|---|
| (낮) built QA 행 수가 0 이 아님 | — | — | 그날은 진행하지 않는다(점검 모드를 켜지 않음). 행의 출처를 확인하고 T 에게 알린다 | 다른 날 |
| 1~2 점검 모드가 안 걸림 · 진행 중 요청이 0 이 안 됨 | 반영 전 | 병합 전 | 설정 확인(`nginx -t`, include 누락 location), 남은 연결의 출처 확인. 5분 안에 안 되면 중단 | OFF · 다른 새벽에 다시 |
| 2a built QA 행 수가 낮 기록과 다름 | 반영 전 | 병합 전 | **즉시 중단.** 아무것도 바꾸지 않은 상태다. 늘어난 행의 출처(누가 QA 를 저장했는지)를 확인하고 T 에게 알린다 | OFF · 다른 날(낮 built 덤프부터 다시) |
| 2b·3 90초 미만으로 비교를 시작함 · 3 가벼운 비교 실패(카운터 다름 · `stats_reset` 바뀜 · 표 빠짐 · DB 누락 · `track_counts` off · 두 번 읽기 불일치 · 60초 초과) | 반영 전 | 병합 전 | **즉시 중단.** 90초 미만은 DB 를 읽기 전에 끝나므로 결과 파일이 없다. 그 외에는 결과 파일의 문제 목록으로 어느 표가 바뀌었는지 기록. 다시 하려면 낮 동결·무거운 동기화·카운터 기록부터(밤에 무거운 동기화를 하지 않는다) | OFF · 다른 날 |
| 4~6 덤프·manifest·사전 확인 거절(종료 2) | 반영 전 | 병합 전 | 4 부터 다시(새 덤프 → 새 manifest). manifest 형식 문제면 Cursor 가 고쳐 다시 만든다 | 통과 → 7 · 세 번 실패 → OFF · 중단 |
| 7 병합 실패 | 반영 전 | DB 마다 트랜잭션: 실패한 DB 는 그대로, 먼저 끝난 DB 는 병합됐을 수 있음 | 보고서·오류 확인 → 고친 뒤 7 다시(멱등 — 이미 들어간 행은 다시 넣지 않음) | 8 로 · 못 고치면 OFF · 중단(로컬 병합분은 그대로 두고 다음 창에서 4 부터, 낮 작업은 되돌리지 않음) |
| 8~9 c29 · 멱등 실패 | 반영 전 | 병합됨 | 실패 항목 확인(보고서 형식이면 7 다시 → 8, 고아·옛 키 좌표면 연결표·규칙 확인). 고칠 수 없으면 promote 하지 않음 | OFF · 중단 |
| 10 덤프·병합 표 해시·overlay·scp 실패 | 반영 전 | 병합됨 | 다시(overlay 거절이면 3 의 로컬 가벼운 비교 결과 확인). 시간식(6.1)에 안 들어오면 11 전에 멈춤 | 11 로 · 안 되면 OFF · 중단 |
| 11 promote 중 실패(R4·R6) | **일부 DB 반영됨** | 병합됨 | 8절 롤백 — **이미 새 상태가 된 DB 모두**를 반영 직전 덤프로 → `prod_sync_check` 로 반영 전 운영 스냅샷과 다름 0 → 옛 상태 확인(옛 키 상세 200) | OFF |
| 12 R5·스모크 실패 | 반영됨 | 병합됨 | 백엔드 재시작 뒤 R5 한 번 더. 그래도 실패면 8절 롤백(세 DB 모두) → 다름 0 확인 | OFF |
| 14 핵심 확인(07:00, R1·R2·화면) 또는 7.2 해시(09:00, R3) 실패 | 반영됨 · 사용자 접근 중 · OFF 뒤 새로 쌓인 운영 전용 행 있음 | — | 아래 「OFF 뒤 되돌리기」. 해시 차이는 09:00 까지 나온 결과로 판단한다 | OFF |

**OFF 뒤 되돌리기(T 결정 2026-11-16 — 서버 역방향 병합은 하지 않는다):**

| # | 할 일 | 통과 조건 |
|---|---|---|
| a | **점검 모드 ON**(6.0) · 17곳 503 | 6.0 |
| b | **진행 중 요청 0**(6.0 ①②③) → 이 시각 = `KEEP_AT` | 셋 다 0 |
| c | **운영 전용 표 덤프·manifest 검증·보존** — 6.1 4 와 같은 명령·같은 manifest 형식(새 키 상태의 운영에서). 검증은 로컬에서 `collective_p2_merge_prod_only.py` 드라이런(`--manifest … --freeze-at $KEEP_AT`, 대상은 아무 리허설 DB) 의 사전 확인 통과로 한다(쓰지 않음). 보존은 아래 | manifest 엄격 검사 통과 · `created_kst ≥ KEEP_AT` |
| d | **8절 되돌리기**(새 상태가 된 DB 모두를 반영 직전 덤프로) → `prod_sync_check` 로 반영 전 스냅샷과 다름 0 → **옛 상태 확인**(옛 키 상세 200 · `vps_collective_smoke.sh`) | 다름 0 · 스모크 통과 |
| e | **점검 모드 OFF** · 17곳 확인 | 503 인 곳 0 |

- **보존(c):**
  - 위치: 운영 `/var/backups/ch2/p2/rollback_keep/<KEEP_AT>/`(덤프 2개 + manifest) — 로컬 사본 `logs/collective_p2/rollback_keep/<KEEP_AT>/`(gitignore).
  - 기간: **90일**. 지울 때 T 확인을 받고 9절 표에 지운 날짜를 적는다.
  - SHA-256 기록 위치: manifest 의 `archives[].sha256`(덤프별) + 같은 폴더 `SHA256SUMS`(`sha256sum *.dump manifest.json`) + 이 문서 9절 「되돌리기 보존본」 줄(날짜·폴더·manifest SHA-256).
- **즉시 복원하지 않는다:** 되돌린 옛 DB 에 보존본을 바로 합치지 않는다.
  - **위치 캐시(좌표 3표)는 재생성된다** — 지도에서 단지를 다시 볼 때 VWorld 로 다시 받는다(키가 옛 상태라 새 키 좌표는 어차피 쓸 수 없다).
  - **QA 기록은 보존본에서 나중에 확인한다** — 필요하면 관리자가 보존본을 임시 DB 에 복원해 읽는다(운영에 다시 넣지 않음).
- 병합 스크립트의 `--direction reverse`(대상 원장에 없는 키는 버림)와 그 테스트는 남겨 두지만 **런북 필수 단계가 아니다**(2026-11-16 리허설 기록은 12절 끝).

### 6.3 서비스 처리

- 점검 창(6.1 1~13) 동안 API 전체가 503(점검 모드, T 결정 안 A). 새벽에 한다. 정적 화면은 열리고 데이터 요청은 점검 응답을 받는다.
- **캐시:**
  - `vps_promote_db_sql.sh` 가 백엔드를 재시작하므로 프로세스 안 캐시가 새로 읽힌다. 키 재매핑 미들웨어의 연결표, `lru_cache` 등이 해당된다.
  - **promote 뒤 `analysis_cache` 를 비운다**(T 결정): `cd /opt/ch2_Macro/backend && .venv/bin/python scripts/clear_analysis_cache.py --with-base-cache`. 토지 DB 의 유료 분석 캐시라 이번 DB 와 직접 관련은 없지만 확인 전에 비운다.
- 스모크: `deploy/scripts/vps_collective_smoke.sh` + 키 이전 확인(R5):

| 키 종류(연결표 reason) | 기대 응답(집합 상세 `…/stats/rolling?window_years=5`) | 그 밖이면 |
|---|---|---|
| C-01 분할 옛 키(`split`·`honam_sido+split`) | **409** + 후보 목록(키·이름·동만, 숫자 없음) | 실패(R5) |
| C-2 옛 키(본 조각 옛 키, `c2_split`·`honam_sido+c2_split`) | **200** + 분리 안내: JSON 본문 최상위 `key_split_c2`, 헤더 `X-CH2-Key-C2-Split` | 실패(R5) — 409·404·500·안내 없는 200 모두 |
| 일반 키(연결표·판정 표에 없음) | **200** + 안내 없음 | 실패(R5) |
| 1:1 옛 키(`honam_sido`) | **200** + 새 키 응답(`X-CH2-Key-Remapped`) | 실패(R5) |

  - C-2 확인은 `key_split_c2` 가 본문에 실제로 있어야 통과다.
  - **스크립트:** `scripts/ops/collective_p2_r5_smoke.py`(C-01 · C-2 · 일반 세 가지, 하나라도 다르면 종료 1). 로컬 주소만 받고 운영 도메인·IP URL 이면 아무것도 하지 않고 종료 2. 키는 앞 8자만 출력.
    - **운영 실행(6.1 12 — 서버 안이라 점검 모드 중에도 된다):**
      `cd /opt/ch2_Macro && backend/.venv/bin/python scripts/ops/collective_p2_r5_smoke.py --base-url http://127.0.0.1:8000 --collective-db collective_stats --out /tmp/r5_smoke.json`
    - 의존: 백엔드 venv 의 sqlalchemy·psycopg2 와 `backend/.env` 의 `COLLECTIVE_DATABASE_URL` 뿐이다. `pipeline/` 을 import 하지 않는다. **배포 전 확인(4절 #9).**
    - 리허설 실측(2026-11-16, 리허설 DB 에 붙인 로컬 백엔드 :8017): 3/3 통과(409 · 200+안내 · 200).

## 7. 운영 확인 (Opus, 읽기 전용)

07:00 까지는 핵심만 본다. R5 스모크는 6.1 12 에서 이미 끝나 있다. 여기서는 주요 화면과 7.1 이다.

세 DB 전체 해시(7.2)는 07:00 창에서 빼서, 09:00 까지 마치는 사후 검증으로 둔다. 차이가 나면 6.2 의 되돌리기를 판단한다. 점검 OFF(06:00) 뒤 해시가 끝나기 전까지 화면은 열려 있다.

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

### 7.2 행 해시 비교 — `prod_hash_compare.py` (사후 검증, 09:00 까지)

```bash
python3 prod_hash_compare.py snapshot --db-env COLLECTIVE_DATABASE_URL --env-file /opt/ch2_Macro/backend/.env --out /var/backups/ch2/p2/hash_prod_collective.json
py scripts/ops/collective_p2_verify/prod_hash_compare.py compare logs/collective_p2/hash_local_collective.json hash_prod_collective.json
```

- 로컬 쪽 `hash_local_<db>.json` 은 6.1 10 의 overlay 결과(낮 전체 해시 + 밤 병합 표 해시)다. built 는 낮 해시(`hash_local_built_stats_day.json`) 그대로.

- 대상 표는 이번 반영이 바꾸는 표다. 원장·통계·속성·연결표·보존 표가 들어간다(스크립트 `TARGETS`).
- 큰 표는 `building_key` 첫 글자 16조각, 또는 id 범위 16조각으로 나눠 조각마다 시간 제한(기본 600초)을 둔다.
- 기대값은 **다른 표·조각 0** 이다. promote 는 같은 덤프라 id 까지 같다.
- 결과는 셋: 통과(0) / 차이(1) / 검증 못 함(2).
  - 조각 쿼리가 실패(시간 초과)하면 「검증 못 함」이다.
  - **필수 표가 한쪽이라도 없으면** 「검증 못 함」이다. 비교는 결과 JSON 의 키가 아니라 필수 표 목록(DB 기본 대상 + 두 스냅샷이 요청한 표)을 순회한다.
- 기본 대상에는 보존 표(`*_p2_before`, 이름 꼴로 자동 포함)와 C-2 판정 표(`collective_building_key_c2_units`)가 들어 있다.
- 예상 소요는 collective 25~50분 · rent 30~65분 · built 1~2분이다(로컬 c8 해시 실측 기반, 운영 최대 2배).

### 7.3 Insight 비교

- **확보 시점(Codex Phase D 2):** Insight 는 되돌리기(c8·로컬 덤프 복원) **앞에서** 확보·검증한다. 되돌린 뒤에는 after 상태가 없다.
  - 운영 절차: **before = 로컬 적용 직전**(5절 머리, 5.1 0a 전), **after = 적용 직후**(5.3 끝, 5.4 전). 둘 다 실제 로컬 DB 를 읽기 전용으로 읽는다.
  - 리허설: before = 실제 로컬 DB(읽기 전용), after = `*_p2r`(12.2 9번, c8 앞).
- **08·03·12 — `scripts/lab/collective_p2/c22_insight_recompute.py`:**
  - 운영: `run --side before --label ops_before` → (적용) → `run --side before --label ops_after` → `compare --before-label ops_before --after-label ops_after`
  - 리허설: `run --side before` · `run --side after` → `compare`
  - 기간은 공개 스냅샷과 같게 고정한다(03·08 as_of 2026-08-01).
  - 출력은 모두 `logs/collective_p2/insight/<label>/`(03 의 부속 CSV·표제부 캐시 포함). 실행 전후 저장소 추적 파일 변경이 0 이어야 하고, 생기면 종료 코드 4 로 멈춘다.
- **14 — `scripts/lab/collective_p2/c27_insight14_compare.py`**(wip 생성기를 main 에 넣지 않음, T 결정 · 12.1 P5 와 같은 절차):
  - `prepare`(고정 커밋 detached worktree) → 운영 `run --side before --label ops_before` · (적용) · `run --side before --label ops_after` / 리허설 `run --side after` → `compare --label <ops_after|after>` → `cleanup`
  - 실행 전후 worktree 무변경 + 이 저장소 추적 파일 변경 0 을 확인한다(있으면 멈춤). as_of 2026-10-01 고정.
- **운영 반영 뒤에는 공개 스냅샷(정적)이 바뀌지 않는다.** 고정한 after 값을 공개할지는 별도 결정이다.

## 8. 롤백 — 반영 직전 운영 덤프로 되돌림

**코드 복귀 경계:** 운영 DB 반영 전에는 4-1 #4의 조건을 만족할 때 `6633cf5`를 재배포할 수 있다. 운영 DB가 하나라도 새 상태라면 **코드만 되돌리지 않는다**(4-1 #5). 먼저 이 절과 6.2에 따라 바뀐 DB를 모두 복원한다.

**판단 기준(하나라도 해당하면 되돌린다):**

| # | 확인 항목 | 되돌리는 조건 |
|---|---|---|
| R1 | 7.1 옛 시도명 · 합성 주소 · annual 불일치 · 남은 분할 옛 키 행 | 0 이 아님 |
| R2 | 7.1 `--expect` 비교 | 결과 「차이」(종료 코드 1). 「검증 못 함」(2)은 무거운 검사를 다시 돌려 통과·차이로 확정 |
| R3 | 7.2 해시 비교 | 결과 「차이」. 「검증 못 함」은 시간 제한을 늘려 다시 돌려 확정 |
| R4 | promote 스크립트 | `psql ON_ERROR_STOP` 실패 · `/health` 가 60초 안에 응답 없음(스크립트 종료 코드 1) |
| R5 | 스모크(6.3, `collective_p2_r5_smoke.py` 종료 코드 1) | 집합·임대 상세가 5곳 이상 비거나 500 · **C-01 분할 옛 키가 409 가 아님** · **C-2 옛 키가 200 + `key_split_c2` 분리 안내가 아님**(409·404·500·안내 없는 200) · 일반 키가 200 이 아니거나 안내가 붙음 · 1:1 옛 키가 200 이 아님 |
| R6 | 시간 | 한 DB 복원이 지난 promote 기록(2.3)의 2배를 넘고 원인이 불명 |

- **점검 모드:** 점검 창(6.1) 안에서 되돌릴 때는 점검 모드를 켠 채로 한다. 점검 모드를 끈 뒤(7절에서) 되돌릴 때는 **먼저 다시 켠다**(6.0, 진행 중 요청 0 확인). 단계별 처리는 6.2.

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
# /health 는 재시작 직후 실패할 수 있다 → 다시 묻되 전체를 60초 안으로(curl 은 남은 시간·3초 중 짧은 쪽, 쉼은 2초 이하)
deadline=$((SECONDS + 60)); ok=0
while :; do rem=$((deadline - SECONDS)); (( rem > 0 )) || break
  if curl -sf --max-time "$(( rem < 3 ? rem : 3 ))" http://127.0.0.1:8000/health; then ok=1; break; fi
  rem=$((deadline - SECONDS)); (( rem > 0 )) || break; sleep "$(( rem < 2 ? rem : 2 ))"; done
[ "$ok" = 1 ] || { echo "ERROR: /health 60초 안에 응답 없음" >&2; exit 1; }
```

- **예상 시간:** promote 복원 시간과 비슷하다(2.3 미실측). -Fc 덤프의 `pg_restore -j 2` 는 plain SQL 적재보다 빠를 수 있다.
- **새 상태가 된 DB 는 모두 함께 되돌린다**(2.3a 표). 연결표가 DB 사이에 걸려 있어 한 DB 만 되돌리면 키가 어긋난다.
- 되돌린 뒤 `prod_sync_check` 로 반영 전 운영 스냅샷(3절 JSON)과 다름 0 인지 확인하고, 스모크를 다시 한다.
- 재빌드 경로(통계표 다시 만들기)는 쓰지 않는다(T 결정). 로컬 쪽은 5절 첫 줄의 로컬 덤프로 되돌린다.

## 9. 사후 처리

| 항목 | 내용 |
|---|---|
| 되돌리기 보존본(6.2 c) | 운영 `/var/backups/ch2/p2/rollback_keep/<KEEP_AT>/`(+ 로컬 사본) → **90일 보관**. 생기면 여기에 날짜·폴더·manifest SHA-256 을 적는다(지금 없음) |
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

## 12. C-2 확정 뒤 전체 리허설 재실행 (T 승인 뒤 실행 — 순서·예상 시간만)

C-2 판정은 `logs/collective_p2/c2_units_final.csv`(`collective_building_key_c2_units` 형식, 지번 포함·로컬, `c25_c2_finalize.py`)로 확정했다. 리허설 DB 에도 아직 쓰지 않았다.

### 12.1 리허설 전에 만든 코드 (2026-11-16 완료 · `data/collective-p2` · Codex 검토 대상)

| # | 할 일 | 한 것 |
|---|---|---|
| P1 | `migrate_p2_keys` 에 C-2 연결 | 판정 표(`collective_building_key_c2_units`)를 읽어 2단계 키(호남·C-01 뒤) 위에 `apply_building_key_split_c2`. 본 조각 = 옛 키, 나머지 = `c2_key(원문, p<n>)`. 3건 미만 본번은 같은 규칙(같은 건축년도 조각 → 가까운 본번). 표에 없는 3건+ 본번은 새 조각으로 표에 등록(`source=p2_migrate`, `--rollback` 때 지움). 연결표: 옛 키 → 조각(`c2_split`, 앞 단계가 있으면 `honam_sido+c2_split`·`split+c2_split`), 2단계 키 → 조각(`c2_chain`), 옛 키 → 2단계 키(n_tx 0 경로 행, 필요할 때만). 부속 표(속성·공시지가)는 C-2 전 단계 연결표로 처리 → 본 조각이 그대로 가진다. `--verify` C-2 4항목(조각 본번이 옛 키에 남은 행 0 · c2 연결표 행 있음 · C-2 키 좌표 남은 행 0 · 조각 키 하나에 유형 여럿 0). `prune_split_annual` 은 본 조각이 남는 C-2 키(`c2_split`·`c2_chain` 만)를 대상에서 뺀다 |
| P2 | C-2 옛 키 좌표 버리기 | `--apply` 안에서 같이: C-2 분할 키(본 조각 옛 키 포함)와, 재키하면 그 키가 되는 행의 `collective_building_geocodes` → `c2_discard`(원래 행은 `_p2_before`, 되돌리기 복원). 임대 키는 C-2 로 나누지 않으므로(임대 적재도 C-2 안 함) `rent_building_geocodes` 는 건드리지 않는다 |
| P3 | 판정 표 적재 | `pipeline/collective/load_c2_units.py`: 이름 가드(…_p2r) + 접속 DB 이름 확인, 형식 검사(키·법정동·조각 0 존재·조각 번호 법정동 간 중복 금지 등), 멱등, 값이 다른 행이 있으면 멈춤, 출력은 건수만. 실제 로컬 DB 모드(`--real-apply`, 키 이전과 같은 가드 + 승인 파일 SHA-256·행 수 대조, Codex Phase D 3 — 5.1 0a·0b). 운영은 promote |
| P4 | 분할 아파트 표시 이름 | 12.3 |
| P5 | Insight 14 비교 | `scripts/lab/collective_p2/c27_insight14_compare.py`: wip 생성기를 main 에 가져오지 않고 `wip/ai-revision-20261109`(ed56f0d) detached worktree 를 읽기 전용으로 실행(PGOPTIONS 읽기 전용, 출력 logs/, 실행 전후 worktree 무변경 확인, as_of 2026-10-01 고정) → 공개값(main `insight14.ts` SNAP + 고정 커밋 JSON)과 비교 |

- 미리 보기(읽기 전용, `c26_c2_plan_dryrun.py`, 판정 파일을 DB 에 넣지 않고 계획만): 충돌 0 · 문제 0 · C-2 키 1,609(법정동 단위 1,610) · 늘어나는 키 **2,045**(아파트 54 · 연립 1,859 · 오피스텔 132) · 옮겨지는 거래 **14,288**(c25 의 3건+ 본번 14,002 + 3건 미만 본번 286) · 자동 등록 새 조각 0 · c2_chain 231 · 경로 행 0.
- 이 미리 보기에서 오피스텔 키 1개가 두 법정동에서 같은 조각 번호(1)를 써 한 키로 합쳐지는 것을 찾아 고쳤다(c25 가 키 안에서 번호를 다시 매김, 적재 도구가 거부).

### 12.2 실행 순서·예상 시간 (로컬, Phase C 실측 기반 — 「추정」은 미실측)

| # | 단계 | 예상 |
|---|---|---|
| 1 | 리허설 DB 다시 만들기: `*_p2r` 3개를 지우고 Phase C 덤프(`logs/collective_p2/dumps/*.dir`)에서 `pg_restore -j 4`. `parcel_master_p2r` 는 그대로 둔다 | 추정 1~2시간 |
| 2 | 판정 표 적재 `load_c2_units.py --collective-db collective_stats_p2r --apply`(P3) | 1분 |
| 3 | 키 이전 C-01 + C-2 + 좌표 폐기(`migrate_p2_keys --apply`, P1·P2) → `--verify`(20항목) | 23분 + C-2 추정 5분 · 4분 |
| 4 | 거래유형 보정 · 2019~2020 분할 옛 키 annual 정리 · **C-2 키 2019~2020 annual 범위 교체**(`python -m collective.c2_annual_replace_p2 --collective-db collective_stats_p2r --apply`, 먼저 드라이런) · **고정 연도 annual 원장 근거 없는 행 정리**(`python -m collective.prune_fixed_annual_orphans_p2 … --apply` → `--verify`) | 5분 · 1분 · 17초 · 수 초 |
| 5 | 15단계(통계표 재생성: building_stats·rolling·presale·market·commercial·rent 등) | 2시간 41분 |
| 6 | 속성·공시지가 — 새 분할 키 목록(C-01 3,447 + C-2 2,045) | 추정 20분(Phase C 3,447키 12분) |
| 7 | 매매·임대 연결(C-2 판정 키·조각 키는 exact 보류, `c2_held` 출력) · 복합 scope · integrity_p2 --deep(C-2형 판정 밖 0) | 4분 · 1분 · 수 분 |
| 8 | 검증 c5(39항목 + C-2 항목) · c6(+ C-2 annual: 통계 = 원장 재계산, 근거 없는 행 0) · c7(+ C-2 보류 연결 수, 보류 대상 누출 0) · c9 · c10 | 추정 1~1.5시간 |
| 9 | **Insight 확보·검증(c8 앞 — c8 이 after 상태를 지운다)**: 08·03·12(`c22 run --side before/after` → `compare`) · 14(`c27 prepare → run --side after → compare → cleanup`). 실행 전후 추적 파일 변경 0 | 7분(재실행 실측 22b 225초 + 22a 206초) · 수 분 |
| 10 | c8 롤백·행 해시(덤프 복원 방식) | 6시간 16분(재실행 실측) |
| 11 | 백엔드 전체 테스트 + pipeline 전체 테스트 + 집합 컴포넌트 테스트·tsc | 3분 + 30초 + 1분 |
| | 합(c8 포함) | 약 12~14시간 |

- 2~7 은 하루 안에 이어서 한다(약 4시간 20분). 8~11 은 다음 날 해도 된다(리허설 DB 는 그대로).
- Insight(9)는 반드시 c8(10) 앞이다. 2026-11-16 재실행은 이 순서로 했다(지시 순서와 달랐던 것을 Codex Phase D 2 로 런북에 고정).
- 멈춤 조건은 Phase C 와 같다:
  - 지표가 예측과 다름(규칙·설계 문제) — 3단계 기준: 미리 보기 숫자(키 +2,045 · 옮겨지는 거래 14,288 · 충돌 0 · 자동 등록 0)
  - 쓰기 대상이 `*_p2r` 밖
  - 디스크 20% 미만
  - 같은 단계가 두 번 연속 실패

### 12.3 분할 아파트 표시 이름 「단지명 (YYYY년 준공)」 — 표시만, 키는 그대로 (P4 완료)

| 위치 | 파일 | 한 것 |
|---|---|---|
| 목록 API 행 | `backend/app/collective/building_stats_query.py` · `display_label.py` | 연결표에서 reason 에 c2 가 든 옛 키(본 조각)·새 키 중 아파트면 `display_label = "단지명 (YYYY년 준공)"`(연도 = 행의 building_year). `display_name` 그대로. 연결표는 key_remap 캐시 공유 |
| 목록 표 | `BuildingStatsTable.tsx` | 이름 칸·툴팁 `display_label` 우선. 검색은 두 이름 모두 |
| 상세 모달 | `BuildingDetailModal.tsx` | 제목·「원래 단지」·인근 후보·유형 카드 |
| 모바일 목록 | `MobileCollectiveApp.tsx` | 같음 |
| 지도 라벨 | `App.tsx` → map-points `label` | 선택·후보 모두 |
| AI 문맥 | `api/aiContext.ts` 목록 문맥(visible_rows·first_row) | 같음 |
| CSV | `cohort_router.py` 코호트 거래 내보내기 「단지」 칸(원장 최빈 준공연도) | 단건 내보내기는 단지 칸이 없어 그대로 |
| 그대로 둔 곳 | 상세 하위 API 응답의 `display_name`(롤링·연도별·회귀 등), 분리 안내 후보(`KeySplitC2Notice`, 숫자 없음 원칙) | 화면 제목은 목록 행에서 오므로 보이는 이름은 바뀐다 |

- 대상: C-2 로 나뉜 아파트 조각(이번 확정 47 (키·법정동), 늘어나는 키 54). 연립·오피스텔은 이번 지시 범위 밖이다(필요하면 같은 방식).

### 12.4 Codex 검토 반영 (2026-11-16)

| # | 반영 | 위치 |
|---|---|---|
| 1 | C-2 키 2019~2020 annual 범위 교체: 판정 표 본 키 + C-2 조각 키 × 2019·2020 을 annual 빌더와 같은 SQL·레코드 함수(`annual_record_from_row`)로 재계산 → 교체·삽입, 유효 0건이면 삭제. 2010~2018 그대로. 원래 행은 `collective_building_annual_c2_p2_before`, `--rollback` | `pipeline/collective/c2_annual_replace_p2.py` · 리허설 4단계 · c6 |
| 2 | 임대 연결: C-2 판정 키(본 조각)·조각 키는 exact 연결을 만들지 않는다(임대는 C-2 로 나누지 않아 여러 건물이 합쳐진 키). 화면은 기존 「연결되지 않음」 | `pipeline/rent/build_sale_building_map.py` · c7 |
| 3 | 판정 표 적재: 표 기존 행 + 파일 새 행의 최종 상태에서 0 이 아닌 (키, 조각 번호)가 두 법정동 이상에 쓰이면 거절(본 조각 0 없음·유형 여럿도) | `load_c2_units.final_state_errors` |
| 4 | AI 이름: AI 대상 이름(App), 회귀 문맥(단지 하나일 때), 코호트 추이 문맥 | `App.tsx` · `BuildingRegressionPanel.tsx` · `aiContext.ts` |

- 연결표 `split_part` 는 C-2 조각 행이면 C-2 조각 번호다(C-01 조각 번호는 같은 옛 키의 경로 행·C-01 행에 남는다).
- 임대 C-2 규모(읽기 전용, `c28_rent_c2_scale.py`)는 결정 전 자료로 보고서에 둔다.

### 12.5 고정 연도 annual 원장 근거 없는 행 정리 (T 결정 2026-11-16)

- 발견: 리허설 재실행(2026-11-16) `integrity_p2 --deep` ERR 8건 — 인천 2019~2020 annual 합 > 원장 합. 원인은 덤프에 원래 있던(2026-08-09 batch) 인천 새 구(검단구·서해구·영종구·제물포구) 이름의 2019~2020 annual 행이다. 그 해 원장은 옛 구 이름(옛 키)이라 근거가 없다. 기존 `prune-annual` 은 옛 시도명만 지운다.
- 규칙(지역 한정 없음): 2019·2020 annual 중 원장(is_valid·unit_price>0)에 같은 (키·유형·연도·시도) 거래가 없는 행을 지운다. annual 은 (키·유형·연도)에 한 행이라 이것이 그 행의 근거다. addr2 비교는 세종(NULL)을 거짓으로 걸어 넣지 않았다.
- 보존: `collective_building_annual_orphan_p2_before`, `--rollback`. 드라이런은 지역·유형별 삭제 수와 인천 새 구 4곳 밖 지역(`unexpected_regions`)을 보여 준다.
- 의존: 5~7단계 재집계(rolling·presale·market·commercial·rent·built_scope)는 원장을 읽고 `collective_building_annual_stats` 를 읽지 않는다 → 리허설은 적용 뒤 integrity 만 다시 돌렸다.
- c6: 「고정 연도 annual 합 = 원장 합(전 지역)」·「원장 근거 없는 행 0」.
- 파일: `pipeline/collective/prune_fixed_annual_orphans_p2.py` · 테스트 `pipeline/tests/test_collective_p2_fixed_annual_orphans.py` · 실행기 `fixed_annual_orphan_prune`·`fixed_annual_orphan_verify`.

### 12.6 참고 — 되돌린 옛 DB 로 역방향 병합(`--direction reverse`, 런북 필수 단계 아님)

- OFF 뒤 되돌리기는 보존만 한다(6.2, T 결정 2026-11-16). 역방향 병합 코드·테스트는 나중을 위해 남겨 둔다.
- 규칙: 두 방향 모두 대상 DB 원장에 없는 키의 행은 버리고 `drop_not_in_ledger` 로 기록. reverse 는 연결표 없는 대상을 허용(재키 없음), forward 는 연결표가 없으면 종료 2.
- 리허설(2026-11-16, `*_p2r`): 새 DB(`collective_stats_p2r` 를 복사하고 반영 뒤 지도에서 본 것처럼 새 키 59개 가짜 좌표 행을 더한 `collective_new_p2r_src`, `rent_stats_p2r`) → 옛 DB(진짜 로컬 = 반영 전 상태에서 4표·원장 키 목록만 복사한 `collective_old_p2r`·`rent_old_p2r`): forward 거절(종료 2) · reverse 적용 — 좌표 5,861행 중 **원장에 없는 키 42행 버림**(C-2 조각 20 · C-01 새 키 20 · 호남 새 키 2) · 넣음 17(호남 새 키 중 2026 개편 재적재로 옛 원장에도 있던 키) · 나머지 5,802 같음 · 비주거 0 버림 · 임대 28 버림(옛 원장에도 없는 P2 전부터의 고아) · c29 게이트 통과 · 재실행 `idempotent` 통과. 테스트 `test_reverse_direction_new_to_old_drops_keys_not_in_old_ledger`.

## 13. 실행 전 확인 사항 (T·Codex)

| # | 확인 | 상태 |
|---|---|---|
| C-1 | title_fill 표제부 DB | **결정됨** — 5.0 진짜 `parcel_master` 생성(p2r 미사용) |
| C-2 | C-2 판정 저장 위치 | **결정됨** — 집합 DB 표 `collective_building_key_c2_units` |
| C-3 | 반영 나누기 | **결정됨** — 낮 로컬 적용·검증 → T 확인 → 새벽 promote |
| C-4 | promote 소요(2.3) | **반영됨** — Codex 단계별 실측표(8/9·9/2·10/2·11/3), 최신 합계 약 47분·API 중단 약 36분 |
| C-5 | 범위 드라이런 실제 DB 판 | **만듦** — `scripts/ops/collective_p2_local/scope_dryrun.py`(Codex 검토) |
| C-6 | `analysis_cache` 비우기 | **결정됨** — promote 뒤 |
| C-7 | Insight 14 | **결정됨** — wip 생성기로 비교만 |
| C-8 | C-2 옛 키·미들웨어 | **결정됨·구현** — 가장 큰 그룹 옛 키 유지, 409 대신 안내 |
| C-9 | 운영 전용 표(2.5) 합치기 SQL — 스크립트화·리허설 시험 | **완료** — 스크립트·fixture·리허설 DB 시험(2026-11-16 덤프, 6.1 실측). 운영 때는 점검 모드 ON 뒤 새 덤프만(6.1 4~9) |
| C-11 | 운영 쓰기 차단 | **결정됨(안 A)** — nginx 점검 모드(API 503), 설치·켜기·끄기·확인 6.0, 점검 창 순서·실패 처리·시간식 6.1·6.2 |
| C-12 | 밤 동기화 | **결정됨** — 무거운 동기화는 낮(동결 뒤), 밤은 가벼운 비교(`prod_stat_compare.py`, 3.2 · 6.1 3) · 해시는 낮 전체 + 밤 병합 표만(overlay) |
| C-13 | OFF 뒤 되돌리기 | **결정됨** — 보존만(덤프·manifest·90일), 즉시 복원하지 않음(6.2). 역방향 병합은 참고(12.6) |
| C-10 | PG 버전 해시 | **절차 넣음** — 3.1 `pgcheck`, 다르면 `--mode sums` |
