# 집합 P2 — Cursor 이해 보고

작성: 2026-11-17. 이 파일은 이해 기록이다. 이 단계에서 런북과 스크립트는 고치지 않았다. 운영 서버에는 접속하지 않았다.

## 1. 현재 운영 상태

2026-11-17에 `git fetch origin main` 으로 확인한 원격 `main` 팁은 `6633cf5`(2026-11-14 17:15 KST, 「검토한 B1 관리자 기능 스위치를 main에 병합」)이다. `data/collective-p2`는 이 팁보다 75커밋 앞이고 7커밋 뒤다. 공통 조상은 `55bb29c`(임대 504 대응 병합)이다. 뒤처진 7커밋이 D-085 B1이다. P2를 main에 넣을 때 이 7커밋을 지우면 관리자 스위치가 빠진다.

로컬 원본 폴더 `D:\ch2\ch2_Macro`의 `main`은 `a2e7b37`(2026-11-12, 게시판 배포 수동화)에 머물러 있다. 이번 단계에서 그 폴더는 읽기만 했다.

배포 경로는 `docs/ops/DEPLOY_PATHS.md`(확인일 2026-11-12)를 읽었다.

- 코드는 `deploy/scripts/deploy-from-windows.ps1`가 scp로 `/opt/ch2_Macro`에 넣고, 서버의 `vps_apply_scope.sh`가 프런트를 빌드하고 `ch2-macro-backend`를 재시작한다.
- 서버의 `/opt/ch2_Macro`에는 `.git`이 없다. 그래서 git 팁과 서버에 떠 있는 트리가 같은지는 이 단계에서 확인하지 못했다.
- API는 `127.0.0.1:8000`. 공개 `/health`는 Basic 인증 때문에 401일 수 있다. 점검 중 확인은 서버 안 주소로 한다.
- 게시판 Actions는 `workflow_dispatch`만 남는다. 그 수동 본문은 아직 `git reset --hard origin/main`을 가정하는데, 서버에 git이 없어 그 전제와 맞지 않는다. P2 반영 경로로 쓰지 않는다.

세 DB 공급은 promote다. 근거는 런북 §2와 `deploy/scripts/vps_promote_db_sql.sh`를 직접 읽은 것이다.

1. 로컬에서 `scripts/monthly/dump_db_for_promote.py`로 plain SQL gzip을 만든다. 로컬은 PG 18, 운영은 PG 16이라 PG18 전용 줄을 거른다.
2. scp로 `/var/backups/ch2/`에 둔다.
3. DB마다 `vps_promote_db_sql.sh`를 따로 실행한다. 순서: 반영 직전 `pg_dump -Fc` → 백엔드 stop → `DROP DATABASE` / `CREATE` → 적재 → 권한 → 재시작 → `/health`를 60초 안에 확인. 실패하면 종료 1.
4. 세 DB를 묶는 트랜잭션은 없다. collective가 새 상태가 된 뒤 rent가 실패하면 둘은 세대가 다르다. 되돌리기는 이미 바뀐 DB를 각각 반영 직전 덤프로 복원한다(런북 §2.3a, §8).

11/3 실측(런북 §2.3, 저널에서 읽은 값)은 built 1분 5초, collective 15분 7초, rent 30분 44초, 합계 약 47분이다. API가 내려가 있는 시간은 약 36분이다. 보존 표가 더해지면 더 길 수 있다. 이 숫자는 과거 기준이다.

운영에 지금 어느 커밋이 떠 있는지는 확인하지 않았다. 승인 뒤에 읽을 명령만 적는다. 비밀값과 접속 문자열은 출력하지 않는다.

- 서버에서 `sha256sum /opt/ch2_Macro/backend/app/feature_gates.py`
- 로컬에서 `git show origin/main:backend/app/feature_gates.py`의 해시와 비교
- 서버 안에서 `curl -sf http://127.0.0.1:8000/health` (본문은 상태만)

`feature_gates.py`가 있고 해시가 `6633cf5`와 같으면 D-085 B1이 서버에 있는 것이다. P2 코드(C-01 409, C-2 안내)는 main에 없으므로 그 해시만으로는 P2가 배포된 것이 아니다.

## 2. 11월 8일 이후 주요 변경

원격 `main` 로그와 `data/collective-p2` 로그, `docs/DECISIONS.md`(P2 브랜치에는 D-084까지, D-085 본문은 `origin/main`에서 읽음)를 봤다.

| 무엇 | 어디 | 이해한 내용 |
|---|---|---|
| 집합 1단계 C-01 B안 | main `ded1f53`, D-084 | 동 선택 확장 코드를 공식 읍면동명으로 거른다. 조회 측만 고친 것이다. 키 이전은 아니다. |
| 집합 2단계 C-01·C-2 | P2 브랜치, main에 없음 | D-084는 C-01(동 혼입)과 C-02(호남 2019~2020 옛 시도명)를 한 번의 키 이전으로 묶는다. C-2는 같은 법정동·다른 본번을 단지로 나눈다. 옛 키 동작은 런북 R5와 같다. C-01 분할 옛 키는 409와 후보 목록, C-2 옛 키는 200과 분리 안내(`key_split_c2`), 1:1 옛 키는 200과 새 키로 재매핑. 판정은 `collective_building_key_c2_units`, 표시 이름은 `display_label`. |
| D-085 관리자 스위치 | main `0e9a8c2`~`6633cf5` | `rent_regression`, `land_regression`, `land_ledger_link`. 기본 `admin`. 서버가 403으로 거른다. 화면은 꺼진 탭을 그리지 않는다. AI 입구에서 비공개 값을 걷어 낸다. B1은 main에 병합됐다. 체크리스트는 11-14 배포라고 적지만, 서버 파일 해시는 아직 대조하지 않았다. B2(임대에서 집합 효용지수 바로 열기)는 P2 머지 뒤로 적혀 있다. |
| 임대 504 | main `1a7cf71`, `55bb29c`, `docs/lab/RENT_REGRESSION_504_20261112.md` | 원인은 계산식 `building_key`가 인덱스를 못 써서 전 아파트 원장을 읽는 것이다. nginx 120초 504 뒤에도 DB 쿼리가 남았다. T는 C안만 승인했다. 회귀 경로 `statement_timeout` 90초, 초과 시 503과 안내. 화면 상한 110초. 인덱스 수정(A)과 식 인덱스(B)는 하지 않았다. A는 임대 회귀를 공개할 때 다시 본다. |
| ops_guards | P2 `scripts/ops/collective_p2_verify/ops_guards.py` | 실제 적용·범위 드라이런은 최종 DSN이 로컬 루프백일 때만 통과한다. 결과 파일은 필수 칸, 측정 시각 48시간, 대상 일치, 실패 기록 0, diff·unverified 0을 통과해야 한다. 하나라도 아니면 「검증 못 함」이다. |
| promote 복구 | main `0408cc4`, `2fc85a1` | 비 git 서버에서 토지 복원 뒤 백엔드가 다시 뜨게 한 수정. P2는 같은 `vps_promote_db_sql.sh`의 health 60초 대기를 쓴다. |
| 그 외 main | 11-08~11-12 로그 | 누락 기능 복원(집합 롤링, 복합 Twin·배분단가, 토지 공시지가·회귀), 현장 모바일, AI 화면 근거, 토스 심사 자료 보관, 게시판 자동 배포 제거. P2 새벽 절차의 입력은 아니다. |

KB 시공사 보강(`a7295c3`, 11-08)은 main에 있다. 남은 명단 작업은 보류다. P2 동결 F4가 그 적재를 막는다.

## 3. 런북 §3 낮

목적은 로컬 반영 전에 「운영에만 있는 행」이 없는지 확인하고, 그 뒤 쓰기를 얼리는 것이다. promote는 DB를 통째로 바꾸므로, 동기화를 빼먹으면 운영 좌표·QA가 사라진다. 운영 전용 4표(집합 좌표 2, 집합 QA, 임대 좌표)의 차이는 여기서 멈추는 사유가 아니라 밤에 병합할 대상으로 적는다.

| 단계 | 하는 일 / 이유 | 명령 | 통과·실패 | 멈추는 곳 / 되돌리기 | 시간 |
|---|---|---|---|---|---|
| 동기화 스냅샷·비교 | 로컬과 운영의 행 수·as_of·최근 계약월·표 유무. 다르면 반영하면 안 된다. | `prod_sync_check.py snapshot` 후 `compare --result-out` (세 DB, 런북 §3 머리) | 0 통과, 1 차이, 2 검증 못 함. 큰 표는 `--allow-heavy` 없으면 검증 못 함. 48시간 지난 측정 시각도 검증 못 함. | 차이·검증 못 함이면 5절을 시작하지 않는다. 아직 아무것도 안 바꿨다. | 기본 1분/DB. heavy는 collective 3~6분, rent 5~10분, built 1분. 운영은 최대 2배. |
| 3.1 PG 해시 확인 | PG18과 PG16이 같은 행에 같은 md5를 내는지, 작은 표로 먼저 본다. | `prod_hash_compare.py pgcheck` 후 `compare` (`region_codes`, `region_code_history`) | hash 같음 → 7.2는 hash. hash만 다름 → sums. sums도 다름 → 동기화 실패로 중단. 표 없음·쿼리 실패는 2. | 5절 전. 되돌릴 DB 변경이 없다. | 작은 표라 분 단위가 아니다. |
| 3.2 동결 F1~F6 | 낮 동기화부터 밤 7절이 끝날 때까지 배치·promote·직접 SQL·보강·QA 저장·코드 배포를 멈춘다. 카운터와 행이 바뀌면 밤 비교가 무의미하다. | 사람·다른 에이전트에게 목록을 알림. 코드 명령은 없다. | 알림이 갔고, 해당 작업이 돌지 않음. | 어기면 그날 밤을 시작하지 않고 낮 동기화부터 다시 한다. | 알림 시간. |
| 예약 작업 확인 | 서버 cron이 밤에 쓰면 동결이 깨진다. 저장소 템플릿에는 ch2 타이머가 없다. | 읽기 전용 `crontab -l`, `sudo crontab -l`, `systemctl list-timers --all` | ch2 항목이 없으면 통과. | 무엇이 나오면 멈추고 T에게 보고. 끄기는 별도 승인. | 1분. |
| 무거운 동기화 + 운영 카운터 | 적용 전 로컬=운영을 큰 표까지 확정하고, 밤 비교의 운영 기준 카운터를 남긴다. | `prod_sync_check snapshot --allow-heavy` 후 compare. 이어서 서버에서 `prod_stat_compare.py snapshot --order-clock defer` → `stat_day_prod.json`. 직후 로컬로 가져와 `stamp-local --field measured_at`. | 동기화 0. 카운터 스냅샷 0. `track_counts` off, 두 번 읽기 불일치, 60초 초과는 1. stamp는 `server_now` 없거나 10분 초과면 2. | 5절 전. 운영 DB는 읽기만 했다. | heavy 합계 약 10~20분 + 카운터 1분(10초×3 DB가 60초 안에 있음). |
| 로컬 적용 후 ①② | 로컬 반영(5절)이 끝난 뒤, 밤 overlay의 기준을 만든다. 카운터를 해시보다 먼저 찍어야 그 사이 쓰기가 비교 밖에 남지 않는다. | ① `prod_stat_compare.py snapshot` → `stat_day_local.json`. ② 그 다음 `prod_hash_compare.py snapshot` 세 DB → `hash_local_<db>_day.json`. | 둘 다 종료 0. ①이 ②보다 늦으면 밤 overlay가 종료 2. 같은 초는 허용. | 로컬은 이미 5절이 적용된 상태. 운영은 아직 옛 DB. 로컬을 되돌리려면 5절 롤백(런북 표별)이고, 운영 promote는 하지 않는다. | 해시: collective 25~50분, rent 30~65분, built 1~2분. |

5절 로컬 적용 자체는 §3 표 밖이다. §3이 통과하기 전에는 시작하지 않는다.

## 4. 런북 §6 밤

전제: 낮 동결, heavy 동기화 결과(48시간 안), 운영·로컬 카운터 기준, 로컬 낮 해시, built QA 행 수 0, built 덤프는 이미 업로드. 점검 모드가 API를 503으로 막아 좌표 캐시와 QA가 더 쌓이지 않게 한다. 백엔드를 promote가 재시작해도 nginx 깃발은 유지된다.

시작 상한은 06:00에서 (106분 + 업로드 시간 S)를 뺀 시각이다. S는 낮에 built 덤프 업로드 속도로 잡는다. 11단계 직전에 「지금 + 47 + 3 + 2분 ≤ 06:00」이 아니면 promote를 시작하지 않고 점검만 끈다.

| # | 하는 일 / 이유 | 명령 | 통과·실패 | 멈추는 곳 / 되돌리기 | 시간 |
|---|---|---|---|---|---|
| 1 | 점검 ON. 쓰는 API를 막는다. | `sudo touch /etc/nginx/ch2_maintenance.on`. 17곳 503, 서버 안 `/health` 200. | 하나라도 503이 아니면 실패. | 6.2: 아직 반영 전. 설정을 보고, 5분 안에 안 되면 OFF 하고 다른 날. | 3분 |
| 2 | 진행 중 요청이 0인지 확인하고 동결 시각을 남긴다. 이 시각 이전 덤프는 병합에 쓰지 않는다. | `ss` 백엔드 연결 0, access.log의 비-503 API가 켠 시각 전, `pg_stat_activity` 비-idle 0. 같은 순간에 `FREEZE_AT`(KST)와 `FREEZE_AT_UTC`(로컬 UTC). | 셋 다 0. | 5분 초과 시 중단, OFF. 바꾼 것 없음. | 1~5분 |
| 2a | built QA가 낮 기록(0)과 같은지. built는 병합하지 않아 promote가 그 사이 행을 지운다. | 낮과 같은 읽기 전용 `count` / `max(id)`. | 같으면 통과. | 다르면 즉시 OFF. 아무것도 안 바뀐 상태. 다른 날, built 덤프부터. | 1분 |
| 3 | 낮 이후 운영 전용 표 밖에 쓰기가 없는지. 무거운 동기화를 밤에 다시 하지 않는다. | 운영·로컬 `prod_stat_compare.py compare`. 운영은 `--order-clock defer`. | 둘 다 0. 카운터 다름, stats_reset 변경, 표 빠짐·추가, DB 누락, track_counts off, 두 번 읽기 불일치, 60초 초과는 1. | 6.2: 즉시 OFF. 운영·로컬 병합 전. 다시 하려면 낮 동결부터. | L = 1분 |
| 4 | 운영 전용 4표만 데이터 덤프. 점검 이후에 뜬 것만 쓴다. | `pg_dump -Fc --data-only` collective 3표, rent 1표. manifest에 시각·크기·SHA-256·행 수. | `created_kst ≥ FREEZE_AT`. | 실패 시 4부터 다시. 세 번 실패하면 OFF. | 1분 (실측 1.6초) |
| 5~6 | 덤프를 임시 DB에 복원하고 병합 드라이런. 쓰기 전에 manifest가 정확한지 본다. | `collective_p2_merge_prod_only.py --freeze-at $FREEZE_AT` (real-apply 없음) | 0. DB 2·표 4가 아니면 2. SHA·크기·시각·행 수 불일치도 2. | 4부터 다시. 운영은 그대로. | 5~9 합계 약 5분 |
| 7 | 병합 적용. 좌표는 키 이전 규칙으로 옮기고, QA는 id를 보존·충돌 시 새 id. | 6에 `--real-apply`와 confirm-db, sync-result. 끝난 시각을 `MERGED_AT_UTC`. | 0, 보고서 `applied: true`, DB마다 한 트랜잭션. | 실패한 DB는 롤백된 채, 먼저 끝난 DB는 병합됐을 수 있다. 고친 뒤 7을 다시(멱등). 못 고치면 OFF. 운영은 아직 옛 상태. | 실측 1.3초 |
| 8~9 | 병합 결과 검사와 한 번 더 돌려 멱등 확인. | `c29_merge_prod_only_check.py check`, 이어서 snapshot A → 재실행 → snapshot B → `idempotent` | 0. 고아·옛 키 좌표·행 수·해시·시퀀스가 같아야 한다. | promote 하지 않고 OFF. | 실측 수 초 |
| 10 | 로컬 promote 덤프를 병합 뒤에 다시 만들고, 병합 표만 다시 해시해 낮 해시 위에 얹는다. | collective·rent `dump_db_for_promote.py`. `prod_hash_compare.py snapshot --tables <병합 표>`. `overlay --merged-at $MERGED_AT_UTC --freeze-at $FREEZE_AT_UTC`. built는 낮 해시 그대로. scp 후 크기·SHA-256. | overlay 0. 순서 ①≤②<③<④<⑤ 가 아니거나 ⑤가 점검 ON 이전이면 2. | 6.2: 운영은 반영 전, 로컬은 병합됨. 시간 안에 못 하면 11 전에 OFF. | 덤프 6분 21초 + H 1분 + S |
| 11 | 세 DB를 collective → rent → built 순으로 통째 교체. | `vps_promote_db_sql.sh` 세 번. DB마다 `/health` 0 다음에 다음 DB. | 스크립트 0. health가 60초 안에 없으면 1 (R4). 한 DB가 과거 기록의 2배를 넘고 원인이 없으면 R6. | **일부 DB만 새 상태일 수 있다.** 8절: 이미 바뀐 DB를 반영 직전 덤프로 복원 → `prod_sync_check` 다름 0 → 옛 키 상세 200. 점검 유지. | 47분(과거 기준) |
| 12 | 캐시가 옛 키를 잡지 않게 비우고, 옛 키 응답을 확인한다. | `clear_analysis_cache.py --with-base-cache`. `collective_p2_r5_smoke.py --base-url http://127.0.0.1:8000`. `vps_collective_smoke.sh`. | R5 3/3 종료 0. | 재시작 후 R5 한 번 더. 또 실패하면 세 DB 모두 8절 롤백. | 3분 |
| 13 | 점검 OFF. 마감 06:00. | `sudo rm -f /etc/nginx/ch2_maintenance.on`. 17곳 503이 0. | 화면이 열린다. | OFF 자체가 실패하면 깃발을 다시 확인하고, 사용자에게 열기 전에 고친다. | 2분 |
| 14 | 핵심 확인. R5는 12에서 끝났다. | 주요 화면과 7.1 `prod_c5_core.py`. | R1·R2 통과. | 실패 시 6.2 「OFF 뒤 되돌리기」: 다시 ON → 진행 중 0 → 운영 전용 표 보존 → 8절 복원 → OFF. 서버에서 역방향 병합은 하지 않는다. | 07:00까지 |

7.2 세 DB 전체 해시는 이 표에 넣지 않았다. 07:00 창 밖, 09:00까지의 사후 검증이다. 차이가 나면 같은 6.2 되돌리기를 판단한다. 06:00~09:00에는 화면이 열려 있다.

## 5. 이해가 덜 되거나 위험해 보이는 점

1. **세 DB는 한 번에 바뀌지 않는다.** 11단계에서 collective만 새 상태가 되고 rent가 실패하면, 점검 중이라 사용자는 못 보지만 복원 순서를 빼먹으면 세대가 섞인다. 대안은 없다. 복원 대상을 「이미 새 상태가 된 DB 전부」로 적는 지금 문장이 맞다. 실행 때 DB마다 성공 여부를 종이(또는 `window_plan.txt`)에 남기지 않으면 빠뜨리기 쉽다.

2. **06:00에 열고 09:00에 해시를 끝낸다.** 해시가 어긋나면 그 사이 사용자는 새 DB를 본다. 이 간격은 이미 승인된 노출이다. 되돌릴 때는 OFF 뒤 쌓인 운영 전용 행을 보존만 하고 다시 넣지 않는다(6.2 a~e).

3. **시계 차이 10분을 재 본 적이 없다.** `stamp-local`은 DB `now()`와 로컬 UTC가 10분을 넘으면 거절한다. 서버 시계가 그 이상 어긋나 있으면 신선한 파일도 거절되어 낮·밤이 멈춘다. 승인 뒤 읽기 전용으로, 서버 `date -u`와 `SELECT now()`를 로컬 UTC와 한 번 비교할 것을 제안한다. 10분 안이면 그대로 두고, 넘으면 시계를 맞춘 뒤에야 P2를 진행한다. 시계를 맞추는 것은 이번 이해 단계의 실행이 아니다.

4. **운영 카운터 파일의 stamp는 순서 검사 입력이 아니다.** overlay가 읽는 것은 로컬 `stat_night_local_result.json`이다. 그런데 런북 3.2는 `stat_day_prod.json`도 생성 직후 `stamp-local` 하라고 한다. 서버 시계가 어긋나면 이 단계에서 종료 2가 나고, 순서 검사와 무관하게 날이 멈춘다. 대안: 순서에 쓰지 않는 운영 카운터 파일은 stamp를 필수로 하지 않고, `server_now`만 남긴다. 반영은 T 승인 뒤에 한다.

5. **동결 시각이 두 개다.** `FREEZE_AT`은 KST로 덤프·병합 스크립트가 보고, `FREEZE_AT_UTC`는 overlay가 본다. 같은 순간에 적지 않으면 덤프는 통과하고 overlay는 거절하거나 그 반대가 된다. 실행 메모에 두 값을 나란히 적는 것 외의 코드 강제는 없다.

6. **코드가 옛 DB에서 도는지**는 아직 보지 않았다. 런북 §4는 연결표가 비면 재매핑이 통과만 한다고 적는다. `c2_units`가 없을 때와 옛 키만 있을 때는 Phase 3에서 코드를 읽고 판단한다.

7. **서버에 떠 있는 커밋**은 §1의 해시 비교 전에는 모른다. git 팁을 운영 상태라고 부르지 않는다.

## 6. 원본 폴더의 `_vps_*.sh` 7개

원본 폴더에서 읽기만 했다. 커밋된 판은 없다(`git ls-files` 비어 있음). P2 런북, `vps_promote_db_sql.sh`, `deploy-from-windows.ps1` / `vps_apply_scope.sh` 쪽 검색에서 이 파일명은 나오지 않는다.

| 파일 | 읽은 역할 |
|---|---|
| `_vps_built_chungbuk_audit.sh` | 복합 원장에서 특정 읍면동 코드 건수를 센다. |
| `_vps_built_daeso_detail.sh` | 대소 일대 건수를 주소·코드로 다시 센다. |
| `_vps_compare_daeso_hashes.sh` | 로컬 jsonl의 transaction_hash가 운영 원장에 있는지 센다. |
| `_vps_oauth_smoke.sh` | 게시판 메타와 구글 로그인 리다이렉트를 서버 안에서 두드린다. |
| `_vps_verify_oauth_env.sh` | `.env`와 설정 객체의 OAuth 값을 비교한다. 비밀은 가리도록 적혀 있다. |
| `_vps_platform_setup_once.sh` | `ch2_platform` DB가 없으면 만들고 마이그레이션을 적용한다. 읽기가 아니다. |
| `_vps_sync_history_and_smoke.sh` | 지역코드 이력을 토지에서 복합·집합으로 복사한 뒤 스모크한다. 읽기가 아니다. |

판단: P2 반영 전에 저장소 판으로 맞출 필요가 없다. 맞출 커밋된 판이 없고, promote와 런북이 이 파일을 부르지 않는다. 커밋하면 OAuth 식별자와 일회성 감사 쿼리가 main에 들어간다. 특히 플랫폼 DB 생성과 지역코드 복사 두 개는 실행하면 운영을 바꾼다. P2 창에서 실행하지 않는다. 보존이 필요하면 git이 아니라 작업 폴더 밖으로 복사한다.

## 7. 실행 주체를 Cursor로 바꿀 문장

아래만 바꾼다. 「Codex 실측」「Codex 검토」「Codex 재검수」처럼 과거 검토를 가리키는 문장은 그대로 둔다. 반영은 T 승인 뒤에 한다.

1. 머리말 실행 절차: 「Codex 실행(로컬 반영 → promote)」→「Cursor 실행(로컬 반영 → promote)」.
2. §3.2: 「낮(동결 시작 직후, 로컬 적용 전, Codex)」→ Cursor.
3. §3.2 다시 켜기 문단: 「서버 파일 수정은 Codex 몫」→ Cursor 몫.
4. §4 조건 9: 「운영 서버 스크립트(배포 전 확인, Codex)」→ Cursor.
5. §5 제목: 「로컬 실제 DB에 반영 (Codex)」→ Cursor.
6. §6 머리: 「Codex가 운영에서 읽기 전용으로 행 수를 기록」→ Cursor가.
7. §6.0 제목의 「(Codex)」→ Cursor.
8. §6.0 본문: 「서버 파일 수정은 Codex」→ Cursor.
9. §6.0 표 17행: 「Codex가 경로 기록」→ Cursor가 경로 기록.
10. §6.1 표의 실행 칸: 1, 2, 2a, 4, 11, 13의 Codex → Cursor. 3의 「Codex · Opus」→「Cursor · Opus」. 10의 「Opus → Codex」→「Opus → Cursor」. 12의 「Codex/Opus」→「Cursor/Opus」. 5·6·7·8·9·14의 Opus는 확인 역할이라 그대로 둔다.
11. §6.2 4~6행: 「Codex가 고쳐 다시 만든다」→ Cursor가.

11월 17일 작업 방식에서는 배포 승인 뒤의 머지·배포도 Cursor다. 그 문장은 런북에 아직 없고, 이 목록에 넣지 않았다. 런북 머리의 「Codex 실행 → Opus 운영 확인」을 바꿀 때 확인 주체(Opus)는 유지하는 쪽이 맞다.
