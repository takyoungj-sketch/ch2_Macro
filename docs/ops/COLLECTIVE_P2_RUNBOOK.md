# 집합 2단계 운영 런북 (초안)

> **상태:** 초안 (2026-11-14, Claude Code). **실행하지 않았다.**
> **실행 절차:** T 승인 → Codex 실행 → Opus 운영 확인.
> **근거:** [Phase C 리허설 보고](../lab/COLLECTIVE_P2_PHASEC_REPORT_20261113.md). 시간·기대값은 모두 **로컬 리허설 실측**이고, 운영 서버(메모리 7GB)는 더 느릴 수 있다.
> **C-2(같은 법정동 동명 다른 본번 분리)는 미확정**이다. 관련 칸은 「C-2 확정 후 채움」으로 비워 둔다.

## 0. 범위

| 바뀌는 것 | DB | 표 |
|---|---|---|
| 호남 시도명 표준화(전라남도·광주광역시 → 전남광주통합특별시) | collective_stats · built_stats · rent_stats | 원장 3종(집합 주거·비주거·복합) + 임대 원장 |
| C-01 동 분할(이름 키 1,531개 → 동 단위 새 키 3,447개) | collective_stats · rent_stats | 원장 키·부속 표·연결표 |
| 거래유형 보정 | collective_stats | collective_transactions.deal_type |
| 대표 주소 SQL(`=` 조인) | 빌더 코드 | 통계표 재생성 |
| 분할 새 키 속성·공시지가 | collective_stats | collective_building_attributes(202607 판) · builder_master · collective_building_assessed_land_price |
| (C-2 확정 후 채움) | | |

범위 밖: 세종 region_codes 열 밀림 · 직거래 더미·동 결측 경고·비주거 회귀 자동 제외(3단계) · 칩 건수·표기(4단계) · 기존 실패 테스트 12건.

## 1. 사전 조건

| # | 조건 | 확인 방법 |
|---|---|---|
| 1 | **코드 배포 버전** — `data/collective-p2` 를 main 에 병합한 커밋이 운영에 배포되어 있다. 키 재매핑 미들웨어(옛 키 → 새 키, 1:N 은 409)와 새 빌더가 포함된다. 미들웨어는 연결표가 비어 있으면 통과만 하므로 **데이터 반영 전에 배포해도 된다.** | 운영 `/opt/ch2_Macro` 의 배포 해시 기록 · `/health` |
| 2 | **월간 배치와 겹치지 않음** — 집합·임대·복합 월간 러너(`scripts/monthly/run_*_cycle_csv.py`)가 돌고 있지 않고, 반영 중에 시작하지 않는다. 월간 적재 직후(그 달 as_of 확정 뒤)가 가장 안전하다. | 운영 프로세스 목록 · 월간 일정 |
| 3 | **as_of** — 통계표 재생성은 운영의 현재 as_of(최근 월 1일, 예 `2026-11-01`) 하나만 한다. 과거 as_of 행은 키 이전이 건드리지 않는다. | `SELECT max(as_of_month) FROM collective_building_stats` |
| 4 | **디스크** — 덤프 + `_p2_before` 보존 표가 들어갈 여유. 로컬 기준 collective 12.7GB · rent 18.6GB · built 1.3GB(표 크기 합) — 덤프는 이보다 작다. 여유 30% 미만이면 멈춘다. | `df -h` |
| 5 | **공지** — 반영 중 집합·임대 상세 화면이 흔들린다(5절). 공지 여부를 T 가 정한다. | — |
| 6 | **원천 파일** — K-apt 기본정보·필지고유번호 xlsx, 공시지가 slim 원천이 실행 위치에 있다. title_fill 은 표제부 DB(parcel_master)가 필요하다(3.4). | 경로 존재 확인 |
| 7 | **운영 연결 대상** — `backend/.env` 의 `COLLECTIVE_DATABASE_URL`·`RENT_DATABASE_URL`·`BUILT_DATABASE_URL`·`DATABASE_URL`(토지)이 운영 DB 를 가리킴을 확인한다. **값은 출력하지 않고 DB 이름만** 확인한다. | `SELECT current_database()` |
| 8 | **키 목록 파일 위치** — 분할 새 키 목록(지번 없음, 해시만)을 서버 임시 경로(예 `/var/backups/ch2/p2/p2_split_new_keys.txt`)에 둔다. | 3.3 |

## 2. 백업

### 2.1 덤프 (반영 직전)

```bash
sudo -u postgres pg_dump -Fd -j 4 -d collective_stats -f /var/backups/ch2/p2/collective_stats.dir
sudo -u postgres pg_dump -Fd -j 4 -d rent_stats       -f /var/backups/ch2/p2/rent_stats.dir
sudo -u postgres pg_dump -Fd -j 4 -d built_stats      -f /var/backups/ch2/p2/built_stats.dir
```

- **덤프 직후 표 해시를 저장한다.** 롤백 뒤 비교의 기준이다(c8 과 같은 방식). 행 md5 를 정렬해 이어 붙이고 md5 를 한 번 더 한다. 통계표는 재빌드하면 id 가 바뀌므로 **id 열을 뺀 해시**도 같이 저장한다.
- 복원 시험: 덤프 하나에서 작은 표(builder_master) 하나를 임시 DB 에 `pg_restore --data-only -t builder_master` 로 넣어 행 수를 확인한다.
- **보존 기간 30일.** 6절 「보존 표」와 같이 지운다.

### 2.2 DB 안 보존본 (스크립트가 자동으로 만든다)

| 보존 표 | 만드는 단계 | 내용 |
|---|---|---|
| `*_p2_before`(원장·부속 표·상가 클러스터) | `migrate_p2_keys --apply` | 바뀌기 전 행 |
| `rent_sale_building_map_p2_before` | `migrate_p2_keys --apply` | 연결표 전체 사본 |
| `collective_building_annual_split_p2_before` | `prune_split_annual_p2 --apply` | 지운 2019~2020 annual 행(2,126) |
| 거래유형 보존 | `fix_p2_deal_types --apply` | 바꾼 행의 옛 값 |
| `p2_migration_log` | 각 단계 | 단계·건수 기록 |

## 3. 실행 순서

`PY=/opt/ch2_Macro/backend/.venv/bin/python`, `P=/opt/ch2_Macro/pipeline`, `AS_OF=<현재 as_of, YYYY-MM-01>`, `W="--as-of $AS_OF --windows 3,5,7"`.

### 3.1 키 이전 (원장)

| # | 명령 | 로컬 소요 | 중간 검증 · 기대값(로컬) | 화면 영향 |
|---|---|---|---|---|
| 1 | `$PY $P/collective/migrate_p2_keys.py --collective-db collective_stats --built-db built_stats --rent-db rent_stats` (드라이런, 기본) | 수 분 | 계획 건수: 키 바뀌는 집합 원장 행 **166,595**, 분할 옛 키 **1,531** → 새 키 **3,447**, 새 키 충돌 **0**, 여러 옛 키가 같은 새 키 **0**. 운영 값이 로컬과 크게 다르면 멈춘다. | 없음 |
| 2 | 위 + `--apply` | 23분 | 원자적(실패 시 전부 되돌림). `p2_migration_log` 에 단계 기록 | **여기서부터 상세 화면 키가 바뀐다** |
| 3 | 위 + `--verify` | 3.5분 | 16항목 OK(옛 시도명 0 · 옛 키 남은 행 0 · 연결표 7,414행 · 원장 행 수 불변 등) | |
| 4 | `$PY $P/collective/fix_p2_deal_types.py --collective-db collective_stats --raw-root <raw> --logs-dir <logs> --apply` | 5.3분 | 분양권 비정상·공란 117,553·23,590 → 0·0 · 비주거 공란 70,575 → ≤1 | 거래유형 칩 |

### 3.2 통계표 재생성 (이번 as_of 만)

| # | 명령 | 로컬 소요 | 기대값(c5) |
|---|---|---|---|
| 5 | `$PY $P/build_collective_building_stats.py $W --replace-as-of --prune-annual` | 20분 | 3/5년 거래 합 불변(1,900,429 / 2,889,381) · 7년 옛 시도명 0 · 합성 주소 3/5/7 = 0 |
| 6 | `$PY $P/collective/prune_split_annual_p2.py --collective-db collective_stats --apply --mismatch-csv <logs>/split_annual_mismatch.csv` | 1분 미만 | 2019~2020 분할 옛 키 annual 2,126행 삭제, 불일치 0(불일치 행은 지우지 않음) |
| 7 | `$PY $P/build_collective_building_rolling_stats.py $W --replace-as-of` | 21분 | 광산구·순천 아파트 7년 버킷 종류 6 → 7 |
| 8 | `$PY $P/build_collective_presale_lifetime_stats.py --as-of $AS_OF --replace` | 14초 | |
| 9 | `$PY $P/build_collective_market_stats.py $W` | 21분 | 3·5년 행 불변(38,491) · 코드 12 7년 ≥ 5년 |
| 10 | `$PY $P/build_collective_commercial_cluster_stats.py $W --replace-as-of --prune-annual` | 1.6분 | |
| 11 | `$PY $P/build_collective_commercial_cluster_rolling_stats.py $W --replace-as-of` | 1.5분 | |
| 12 | `$PY $P/rent/build_building_stats.py $W --replace-as-of` | **1시간 28분** | 임대 합성 주소 3/5/7 = 0 · 분할 대상 옛 키 행 0 |

### 3.3 분할 새 키 속성·공시지가 (키 목록 범위)

키 목록 만들기(13): 연결표에서 분할 새 키만 뽑는다. 리허설에서는 3,447키가 나왔다.

```sql
\copy (SELECT DISTINCT new_key FROM collective_building_key_map WHERE reason LIKE '%split%' ORDER BY 1) TO '/var/backups/ch2/p2/p2_split_new_keys.txt'
```

**속성 단계 공통 규칙**

- `--snapshot-ym 202607` 을 **반드시 명시**한다. 파일명 추론이나 최신 판을 쓰면 1차 리허설처럼 새 판(202610)이 생긴다.
- `--keys-file` 로 분할 새 키만 채운다. `--keys-file` 은 `--new-keys-only` 와 `--snapshot-ym` 이 함께 있어야 동작한다.
- **`--replace` 는 키 목록과 같이 쓸 수 없다**(스크립트가 거부한다). 판 전체를 지우고 다시 넣는 기존 `deploy/scripts/vps_sync_collective_building_attributes.sh`(`--replace`)는 **이번에 쓰지 않는다.**
- builder_master 는 새 키가 참조하는 단지 코드만 추가한다(리허설 +1행).
- **실행 전 드라이런으로 「목록 밖 쓰기 0」을 확인한다.** 각 도구의 `--dry-run` 출력과 함께, 리허설 `scripts/lab/collective_p2/c15_scope_dryrun.py` 와 같은 범위 점검을 한다. 같은 함수로 쓸 행을 계산하고 키가 목록 안에 있는지 센다. 운영용 점검 스크립트(리허설 DB 이름 고정 해제판)가 필요하다 — 결정 사항 D-3.

| # | 단계 | 명령 | 로컬 소요 | 기대값(리허설) |
|---|---|---|---|---|
| 14 | K-apt(아파트) | `$PY $P/build_collective_building_attributes.py --kapt-file <K-apt 기본정보 xlsx> --asset-type apartment --new-keys-only --snapshot-ym 202607 --keys-file <목록>` (먼저 `--dry-run`) | 3.6분 | 274행 · builder_master +1 · 목록 밖 0 |
| 15 | title_fill(연립·오피스텔 등) | 3.4 참고 | 2.8분 | 연립 3,030 · 오피스텔 47 · 사전 단계 3,351행(목록 키만) |
| 16 | 공시지가 | `cd backend && $PY -m collective.import_assessed_land_price --from-slim --keys-file <목록> --insert-only` (먼저 `--dry-run`) | 약 5.6분 | +3,326행 · 기존 행 덮기 0 |
| 17 | 매매·임대 연결 | `$PY $P/rent/build_sale_building_map.py` | 3.5분 | 정확 연결 1,068 · 연결표 경유 400 · 1:N 6 |
| 18 | 복합 scope | `$PY $P/built/build_scope_stats.py --as-of $AS_OF --windows 3,5,7` 뒤 그 as_of 의 옛 시도명 행 삭제(리허설 `c3_built_scope_cleanup.py` 와 같은 SQL) | 15초 | scope 옛 시도명 81 → 0 |
| 19 | 재발 방지 검사 | `$PY $P/collective/integrity_p2.py --deep` | 수 분 | 옛 시도명 0 · 동 이름 ≥2 판정 밖 0 · annual 합 = 원장 합 · 합성 주소 0 |
| 20 | (C-2 확정 후 채움) | | | |

**공시지가 단계(16) 주의**

- 운영에는 `--rehearsal` 을 쓰지 않는다.
- 토지 DB 대체 조회가 `DATABASE_URL`(토지)로 간다. 집합 쪽 개편 지도가 비었을 때 **실행당 한 번** 쓰인다. 리허설에서는 0회 쓰였다.
- 실행 전 `DATABASE_URL` 이 운영 토지 DB 인지 DB 이름으로 확인한다.

### 3.4 title_fill — 실행 장소

- 운영 서버에는 표제부 DB(`parcel_master`)가 없을 수 있다. D-050 은 축약대장(표제부)을 로컬 속성 축(B)으로 두었고, 운영 enrichment 는 0행이다(D-050/D-051).
- 그래서 실행 장소를 정해야 한다(결정 사항 D-2).

| 안 | 방법 | 장단 |
|---|---|---|
| (가) 로컬에서 계산 → 운영에 행 추가 | 로컬 parcel_master 로 `apply_title_fill --snapshot-ym 202607 --new-keys-only --keys-file <목록>` 을 운영과 같은 키 목록의 로컬 사본 DB 에 실행한다. 그 결과 행(목록 키의 202607 속성 행)만 내보내 운영에 INSERT(충돌 시 무시)한다. | 운영에 표제부 DB 불필요. 내보내기·적재 스크립트가 필요하다. |
| (나) 운영에 parcel_master 사본 | 리허설처럼 사본을 만든다(로컬 37분). 운영 디스크·메모리 부담이 있다. | 명령이 리허설과 같다. |
| (다) 이번에는 건너뜀 | 분할 새 키의 연립·오피스텔 속성이 비게 된다(3,077키). | 빈 키가 96 → 약 3,170 으로 늘어난다. |

- **드라이런 대체안:** 실행 위치와 상관없이 먼저 `apply_title_fill --dry-run --snapshot-ym 202607 --new-keys-only --keys-file <목록>` 으로 **fill 건수와 blocked 건수**를 출력해 기록한다. 리허설 기대값(`logs/collective_p2/c3_title_fill_new_keys.log`)은 다음과 같다.
  - fill 3,077(아파트 0 · 연립 3,030 · 오피스텔 47)
  - blocked: 아파트 19,535 · 오피스텔 616 · 연립 0. blocked 는 키 목록으로 거르기 전, 판 전체 분류의 건수다. 아파트는 K-apt 단지가 표제부 보강을 막는다.
  - 운영 드라이런 값이 이와 크게 다르면 멈춘다.
- **K-apt PNU 파일 없음 → 실패:** `attach_kapt_pnu` 는 필지고유번호 파일을 못 읽거나 PNU 를 하나도 못 붙이면 `RuntimeError` 로 멈춘다(예전에는 로그만 남기고 계속했다). 테스트 `test_kapt_pnu_missing_file_fails` 가 있다.

## 4. 검증 (Phase C c5 지표의 운영판)

- 3.1~3.3 끝난 뒤 c5 39항목을 운영 DB 에 대해 읽기 전용으로 잰다.
- 운영 「전」 값은 2.1 덤프 직후에 같은 SQL 로 잰다. 리허설 스크립트 `c5_verify.py` 는 `*_p2r` 를 가리키므로 운영판으로 고친 사본이 필요하다(D-3).

| 지표 | 로컬 전 → 후 | 운영 판정 |
|---|---|---|
| 집합 주거 원장 행 · hash 중복 | 6,626,075 · 0 → 같음 | 전 = 후 (**어긋나면 롤백**) |
| 옛 시도명 행(주거·비주거·복합·임대) | 115,145 · 4,355 · 5,779 · 있음 → 0 | 0 (**아니면 롤백**) |
| 이름 키 수 | 267,499 → 265,616 | 운영 드라이런 예측과 같음 |
| 연결표 · 분할 옛 키 · 옛 키 남은 행 | 7,414 · 1,531 · 0 | 드라이런 예측과 같음 · 0 |
| building_stats 3/5년 거래 합 | 불변 | 전 = 후 (**어긋나면 롤백**) |
| market_stats 3·5년 행 | 불변(38,491) | 전 = 후 (**어긋나면 롤백**) |
| 합성 주소 3/5/7(집합·임대) | 1,646/2,399/3,204 · 2,836/4,037/4,714 → 0 | 0 |
| 아파트 5년 단지 속성 / 공시지가 / 지오코드 커버리지 | 99.52% / 98.51% / 9.48% → 99.52% / 98.63% / 9.40% | 전보다 0.5%p 넘게 떨어지면 멈춤 |
| 임대 원장 행 · 분할 대상 옛 키 행 | 14,874,634 · 54,486 → 같음 · 0 | 전 = 후 · 0 |
| 화면(c9) | 분할 옛 키 → 409(후보 목록), 1:1 옛 키 → 새 키로 열림, AI 「KEY_SPLIT」 안내 | 표본 10곳 |

## 5. 서비스 처리

| 구간 | 영향 | 처리 |
|---|---|---|
| 3.1 #2~#4(약 30분) | 집합·임대 상세: 원장 키는 새것, 통계표는 옛 키 → **상세 화면이 비거나 옛 숫자**. 목록·지도 집계도 이번 as_of 가 재생성 전 상태 | 공지 권장. 짧게 하려면 #2 를 시작하기 전에 백엔드를 점검 모드로 둘지 T 결정(D-5) |
| 3.2 #5~#11(약 1시간 6분) | 집합 통계표가 순서대로 바뀜(표마다 원자적 교체) | 같은 공지 범위 |
| 3.2 #12(약 1시간 28분) | 임대 단지 통계 | 같은 공지 범위 |
| 3.3(약 15분) | 분할 새 키 속성·공시지가가 순서대로 채워짐 | |
| 끝 | | 캐시 비우기(아래) → 백엔드 재시작 → 스모크 |

- 전체 영향 구간은 로컬 기준 **약 3시간 20분**이다(3.1 #2 부터 3.3 끝까지). 운영은 더 길 수 있다. 로컬의 2배를 넘으면 멈춰 확인한다.
- **캐시 비우기:**
  - `python backend/scripts/clear_analysis_cache.py --with-base-cache` 로 `analysis_cache`·`analysis_base_cache` 를 비운다(토지 DB, 유료 분석 24h 캐시).
  - 백엔드를 재시작하면 프로세스 안 캐시(연결표 로드 등)가 새로 읽힌다. 키 재매핑 미들웨어는 연결표를 시작 때 읽으므로 **재시작이 필요하다.**
  - 프런트 정적 자산은 바뀌지 않는다.
- 스모크: `deploy/scripts/vps_collective_smoke.sh` + 분할 옛 키 1개 → 409, 1:1 옛 키 1개 → 새 키 응답.

## 6. 사후 처리

| 항목 | 내용 |
|---|---|
| 보존 표 | `*_p2_before`·`collective_building_annual_split_p2_before`·`rent_sale_building_map_p2_before`·덤프: **30일 보관** 뒤 T 확인을 받고 삭제(삭제 날짜를 이 문서에 적음) |
| 연결표·`p2_migration_log` | 계속 둔다(옛 키 재매핑에 필요) |
| 월간 integrity | 다음 월간부터 `verify_monthly_integrity.py --collective` 의 integrity_p2 검사가 0 이어야 한다. 검사 2(동 이름 ≥2 판정 밖)는 새 동명 묶음을 대기열로 보여 준다. **같은 법정동 안 다른 본번(C-2)은 이 검사가 잡지 못한다.** |
| 기록 | 실행 해시·단계별 시간·검증값을 Phase D 보고에 남긴다 |

### 6.1 Macro Insight 재계산 비교

- 공개 Insight 숫자는 정적 스냅샷(`frontend-insight/src/copy/insight*.ts`)이라 반영만으로 바뀌지 않는다.
- 반영 뒤 같은 기간으로 다시 계산해 스냅샷과 비교한다. 기대 범위를 벗어나면 스냅샷은 바꾸지 않고 보고한다.

| Insight(파일 번호, 화면 q) | 데이터 | 키 변경 영향 | 기대 범위(제안, 미실측) |
|---|---|---|---|
| 14 · 동일 지번 아파트·오피스텔(q=13) | 같은 지번의 아파트·오피스텔 거래 쌍 | 지번 단위라 키 분할 영향 작음. 호남 표준화는 시도 이름만 바꿈 | 표본 수(104·62·88·84) ±2, 비율 ±1%p |
| 08 · 아파트 층별효용(q=9) | 아파트 단지(building_key) 단위 적격 표 | 분할 아파트 키가 동 단위로 나뉘어 적격 단지 수가 조금 늘 수 있음 | 적격 6,958 ±1%, 층별 지수 ±0.5 |
| 03 · 연립 층·승강기(q=10) | 연립 building_key 단위 적격 표 | **분할 새 키의 다수가 연립**(분할 새 키 3,447 중 표제부 보강 연립 3,030). 적격·known 이 바뀔 수 있음 | 적격 1,086 ±3%, 비율 지표 ±1%p |
| 12 · 상권·아파트 수익률(q=5) | 아파트 building_key × 지오코드 × 연도 | 분할 새 키는 지오코드가 없을 수 있어(커버리지 9.48 → 9.40%) 근처 아파트 쌍이 줄 수 있음 | 상관 행 818 ±1%, 상관계수 ±0.02 |

- 기대 범위는 **추정**이다. Phase D 리허설(또는 운영 반영 전 로컬 실제 DB)에서 한 번 재계산해 고정하자고 제안한다(D-6).

## 7. 롤백

### 7.1 판단 기준 (하나라도 해당하면 되돌린다)

- 원장 행 수가 전과 다름(주거·비주거·복합·임대 어느 하나라도).
- 옛 시도명 행이 0 이 아님, 또는 옛 키 남은 행이 0 이 아님(3.1 #3 검증 실패).
- building_stats 3/5년 거래 합, market_stats 3·5년 행이 전과 다름.
- 단계가 같은 이유로 두 번 실패.
- 영향 구간이 로컬의 2배(약 6시간 40분)를 넘고 원인이 불명.
- 화면 스모크에서 집합·임대 상세가 5곳 이상 비거나 500.

### 7.2 순서·명령·시간 (표별)

| 순서 | 표 | 방식 | 명령 | 로컬 시간 |
|---|---|---|---|---|
| ① | collective_transactions(거래유형) | 보존본 | `fix_p2_deal_types.py --collective-db collective_stats --rollback` | 27분 |
| ① | 원장 3종·임대 원장 키·시도명 + 부속 표(속성 키·지오코드·공시지가 키·신축 연도·상가 클러스터·임대 지오코드) + `rent_sale_building_map` | 보존본(`_p2_before`) | `migrate_p2_keys.py --collective-db collective_stats --built-db built_stats --rent-db rent_stats --rollback` | 27분 |
| ① | collective_building_annual_stats 2019~2020 분할 옛 키 행 | 보존본 | `prune_split_annual_p2.py --collective-db collective_stats --rollback` | 1분 미만 |
| ② | collective_building_attributes · builder_master · collective_building_assessed_land_price | **덤프 복원**(분할 새 키 행이 추가돼 있고 키 되돌리기는 그 행을 지우지 않음) | `TRUNCATE` 후 `pg_restore --data-only -d collective_stats -t <표> collective_stats.dir` | 약 1분 · 1분 미만 · 1.5분 |
| ② | 키 대응표(collective_building_key_map · collective_cluster_key_map · rent_building_key_map) · p2_migration_log | 이전 전에는 없던 표 → 되돌린 뒤 비워진 채 **기록으로 남김**(덤프 복원 대상 아님) | — | — |
| ② | 연결표 rent_sale_building_map | ①에서 보존본으로 복원됨(c8 확인). 실패 시 덤프 복원 | `pg_restore -t rent_sale_building_map` | 약 1.5분 |
| ③ | collective_building_stats + annual(이번 as_of) | 재빌드 | 3.2 #5 | 20분 |
| ③ | collective_building_rolling_stats | 재빌드 | #7 | 21분 |
| ③ | market_stats + market_annual_stats | 재빌드 | #9 | 21분 |
| ③ | collective_presale_lifetime_stats | 재빌드 | #8 | 1분 미만 |
| ③ | commercial cluster stats·annual / rolling | 재빌드 | #10 · #11 | 2분 · 2분 |
| ③ | built_scope_stats(이번 as_of) | 재빌드 | #18 | 1분 미만 |
| ③ | rent_building_stats + rent_building_rolling_stats | 재빌드 | #12 | 1시간 28분 |
| ④ | 전 표 | 2.1 저장 해시와 비교(통계표는 id 제외 해시) | — | 약 1시간 |

- **합(①~③) 약 3시간 35분**, ④ 약 1시간이다.
- 통계표까지 덤프로 복원하면(c8 방식) ①+복원이 약 4시간 35분이다. 그중 임대 2표 복원이 2시간 23분, 집합 12표가 1시간 17분이다.
- **재빌드 방식의 행 동일성은 아직 확인하지 않았다.** c8 은 덤프 복원 방식으로 「차이 0표」를 확인했다. 운영 전에 리허설 DB 에서 한 번 확인하자고 제안한다(D-4). ④에서 다른 표는 그 표만 덤프로 복원한다.
- 롤백 뒤 캐시 비우기·백엔드 재시작(5절)을 다시 한다.

## 8. 알려진 한계

- **판 이름과 출처:** 분할 새 키의 속성 행은 판 이름이 `202607` 이지만, 값의 출처는 10월 판 K-apt 파일이다. 기존 키의 202607 행과 출처 시점이 다르다.
- **빈 키 96개**(분할 새 키 3,447 중 202607 속성 행 없음):

| 유형 | 사유 | 키 |
|---|---|---|
| 연립 | 표제부 없음 | 69 |
| 연립 | 세대수 없음 | 16 |
| 연립 | 재건축 | 6 |
| 연립 | 비주거 | 1 |
| 오피스텔 | 표제부 없음 | 2 |
| 오피스텔 | 비주거 | 2 |

- 공시지가 빈 키 121(분할 새 키 중):
  - 그 유형 building_stats 없음 78
  - 원천 slim 에서 못 씀 43(최신 연도 아님 39 · slim 에 없음 3 · 값 갈림 1)
- 2010~2018 장기 annual 은 법정동 코드가 없어 분할을 적용할 수 없다. 그 기간 annual 은 옛 키에 남는다(연결표로 조회).

## 9. 출시 전 별도 과제 (이 런북 범위 밖, 기록만)

- **월간 갱신에 K-apt·title_fill 단계가 없다.**
  - 202607 이후 처음 거래된 단지와 분할과 무관한 새 키는 속성이 비어 있다. 리허설 기준 **2,076키**(아파트 828 · 연립 1,131 · 오피스텔 117)이고, 그중 1,372키는 첫 거래가 판 이후다.
  - 월간 러너에 「속성 없는 키만, 판 명시」 단계를 넣을지 따로 정한다.
- C-2 규칙 확정·적용(Cursor 확인 16일 이후, T 결정 뒤) → 리허설 재실행 → 이 런북 「C-2 확정 후 채움」 칸을 채운다.

## 10. 운영 실행 전에 정할 것 (T·Codex)

| # | 결정 | 선택지 |
|---|---|---|
| D-1 | 반영 방식 | (A) 운영 서버에서 이 순서대로 실행 / (B) 로컬 실제 DB 에 반영·검증 뒤 기존 promote 경로(`vps_promote_collective_pg18.sh` 등, DB 통째 교체)로 올림. (B)는 운영·로컬 데이터가 같다는 전제가 필요하다. |
| D-2 | title_fill 실행 장소 | 3.4 (가) 로컬 계산 → 운영 INSERT / (나) 운영 사본 / (다) 건너뜀 |
| D-3 | 운영판 점검 스크립트 | 범위 드라이런(`c15` 운영판)·검증(`c5` 운영판)·해시 저장/비교(`c8` 운영판)를 리허설 DB 이름 고정을 푼 읽기 전용 운영 도구로 만들지. 누가 만들지(Claude Code 브랜치 → Codex 검토) |
| D-4 | 롤백 방식 | 통계표 재빌드(약 3시간 35분, 동일성 미검증) / 덤프 복원(약 4시간 35분, c8 검증됨). 재빌드 동일성 리허설 여부 |
| D-5 | 서비스 처리 | 공지 여부 · 점검 모드 여부 · 반영 시간대(월간 배치 회피) |
| D-6 | Insight 기대 범위 | 6.1 제안값을 쓸지, 반영 전에 로컬에서 재계산해 고정할지 |
| D-7 | C-2 | 확정 전에 C-01·호남만 먼저 반영할지, C-2 와 묶어 한 번에 반영할지 |
| D-8 | 보존 기간 | 덤프·`_p2_before` 30일(제안) |
| D-9 | 월간 속성 단계 | 출시 전 과제(9절)를 Phase D 반영 전에 할지 뒤에 할지 |
