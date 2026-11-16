# 집합 2단계 Phase D — Codex 재검수 체크리스트 (2026-11-16)

브랜치 `data/collective-p2`(로컬, push 안 함). 런북: [`COLLECTIVE_P2_RUNBOOK.md`](COLLECTIVE_P2_RUNBOOK.md).
지번·주소·좌표·키 원문이 든 산출물은 `logs/collective_p2/`(gitignore)에만 있다.

## 1. 커밋

| 커밋 | 내용 |
|---|---|
| `cd1992f` | Phase D 지적 6건(Insight 출력 분리·순서, C-2 판정 표 실제 적재 대조, 운영 전용 표 병합 스크립트, c6 예외 범위, R5 스모크) |
| `14a24ec` | 병합: 같은 키 충돌 건수 + 병합 리허설 검증 `c29` |
| `5e0bef9` | 병합 사전 확인(manifest SHA-256·덤프 시각 ≥ 동결 시각·행 수) · 병합 고아 건수 · c29 게이트·운영 DB 인자 · 런북 6.1 동결 직후 단계 · 이 체크리스트 |
| (이번 커밋) | 병합 충돌 규칙(status·geocoded_at, 운영 쪽이 이기면 UPDATE, 규칙별 건수) · R5 스모크 스크립트 · 체크리스트 확정 사항 |

## 2. Phase D 지적별 확인

| # | 지적 | 완료 | 커밋 | 확인할 곳 | 테스트 |
|---|---|---|---|---|---|
| 1 | Insight 출력 분리(03 부속 CSV·표제부 캐시 → `logs/collective_p2/insight/<label>/`, 실행 전후 추적 파일 변경 0) | ✅ | `cd1992f` | `scripts/lab/collective_p2/c22_insight_recompute.py` RUNNERS["03"]·`assert_clean` · `c27_insight14_compare.py` `check_repo_clean` | `test_collective_p2_insight14_compare.py`: `test_c22_runner03_redirects_attach_csv_and_title_cache` · `test_c22_tracked_change_guard` · `test_run_refuses_when_main_repo_tracked_files_change` |
| 2 | Insight 를 c8 앞으로(운영 before = 적용 직전, after = 적용 직후, `--gen14` → c27 통일) | ✅ | `cd1992f` | 런북 5절 머리·5.4·7.3·12.2(9 Insight → 10 c8) · `--label ops_before/ops_after` | (문서·인자) |
| 3 | C-2 표 로더 해시·행 수 검사(실제 DB 모드) + 키 이전 시작 전 대조 | ✅ | `cd1992f` | `pipeline/collective/load_c2_units.py` `check_approved_file`·`approved_table_state` · `migrate_p2_keys.py` `assert_c2_units_approved`·`--c2-approved-*` · 런북 5.1 0a·0b·2 | `test_collective_p2_load_c2_units.py`: 빈 표·다른 해시·정상(+행 수·적재 뒤 변경) · `test_migrate_cli_real_apply_requires_c2_approval_args` · `test_collective_p2_real_apply.py` 갱신 |
| 4 | 운영 전용 데이터 병합 | ✅ | `cd1992f`·`14a24ec`·`5e0bef9`·이번 | `scripts/ops/collective_p2_merge_prod_only.py`(`resolve_conflict`) · `scripts/lab/collective_p2/c29_merge_prod_only_check.py` · 런북 6.1 2(a~h) | `test_collective_p2_merge_prod_only.py` 23개(키 규칙·충돌 규칙·fixture DB 병합·UPDATE·멱등·가드·사전 확인) |
| 5 | c6 예외를 (키·유형·연도) 단위로 축소 | ✅ | `cd1992f` | `scripts/lab/collective_p2/c6_annual_check.py` `orphan_cells`·`compare_sample_key` | `test_collective_p2_rehearsal_runner.py::test_c6_sample_excludes_only_orphan_key_type_year_cells` |
| 6 | R5 스모크(C-01 분할 옛 키 409 · C-2 옛 키 200 + `key_split_c2` · 일반 키 200, 그 밖 실패) | ✅ | `cd1992f` · 이번 | 런북 8절 R5 · 6.3 · `scripts/ops/collective_p2_r5_smoke.py` | `test_collective_p2_r5_smoke.py` 18개(로컬 전용 가드·운영 URL 거부(종료 2, DB·HTTP 안 감)·세 판정·불일치 종료 1) · 리허설 백엔드 실측 3/3 |

## 3. 병합 리허설 결과(2026-11-16 덤프 `…_180626`, `*_p2r` 만, 운영 접속 없음)

- 덤프 SHA-256·크기 = manifest(2개). `logs/` 는 `.gitignore` 44행으로 제외.
- 대상 상태: c8 뒤 덤프 상태였던 리허설 DB 에 키 이전만 다시 적용(`migrate_apply` rc 0 · 57분, `migrate_verify` 20/20 OK).
- 원본: `prodonly_collective_p2r_src` · `prodonly_rent_p2r_src`(표 구조 = 리허설 DB, 데이터 = 덤프, 행 수 = manifest). **Codex 재검수 통과 전까지 유지.**

| 표 | 병합 전 | 덤프 | 병합 후 | 넣음 | 버림(C-2 · C-01) | 같은 키 값 다름(좌표) | 규칙 |
|---|---|---|---|---|---|---|---|
| collective_building_geocodes | 5,285 | 5,413 | 5,802 | 517 | 34 · 24 | 1(1) | 충돌 규칙 → 「한쪽만 ok」 로컬 1 |
| collective_commercial_map_geocodes | 603 | 695 | 695 | 92 | 0 · 0 | 0 | 값 그대로(전체 행 해시 = 덤프) |
| qa_audit_run | 1 | 1 | 1 | 0 | — | 같은 id 같은 내용 1 | 건너뜀(시퀀스 1→2) |
| rent_building_geocodes | 1,013 | 975 | 1,013 | 0 | 0 · 0 | 0 | — |

- 충돌 1건: 운영 행은 좌표 없음(`status=not_found`, 오류 기록, `geocoded_at` 없음, `updated_at` 2026-10-24 22:37), 로컬 행은 `ok`(`geocoded_at`·`updated_at` 2026-11-05 18:01) → 두 좌표 거리 계산 불가.
- 새 충돌 규칙으로 다시 실행(run3, 사전 확인 포함): 규칙별 운영만 ok 0 · **로컬만 ok 1** · 둘 다 ok 운영 최근 0 · 둘 다 ok 로컬 최근·같음 0 · 둘 다 실패 0 → 바꾼 행 0 · 로컬 유지 1. 실행 전후 4표·시퀀스 행 수·해시 같음, c29 게이트 통과.
- C-2: 운영 C-2 옛 키 좌표 34행 버림(조각 키로 옮기지 않는 규칙) · 병합 뒤 C-2 옛 키 좌표 0 · C-01 분할 옛 키 좌표 0 · C-2 조각 키 2,045 중 운영 좌표 붙은 키 0.
- 고아: 집합·비주거 0. 임대 28행은 원장에 없는 키지만 **진짜 로컬 rent_stats 에도 P2 전부터 같은 28행**(병합이 넣은 행 0).
- 1:1 재키 0: 운영 좌표에 호남 옛 키 행이 없다.
- 멱등: 두 번째 실행 넣은 행 0, 4표 + QA 시퀀스 행 수·해시가 첫 실행 뒤와 같다.
- 사전 확인: 동결 18:00(덤프 18:06:26) → 통과 · 동결 18:10 → 「덤프가 동결 시각보다 오래됨」 종료 코드 2.
- 산출물: `logs/collective_p2/merge_rehearsal/`(run1/run2/dryrun*.json · snap_*.json · check.md).

## 4. 테스트(새 실패 0)

| 묶음 | 결과 | 기준선 대비 |
|---|---|---|
| pipeline | 325 passed(제외 2개는 따로 7 + 4 passed) | 새 실패 0(+새 테스트). 저장소 루트에서 모아 돌릴 때만 로딩 실패하는 2개는 `--ignore`(아래) |
| backend | 1,327 passed · 12 failed · 1 error | 기준선과 같은 목록(built 지역 4 · insight 번들 6 · region_sido 1 · yield 1 · `test_profile_national_rank` 수집 오류) |
| 집합 컴포넌트 | 14/14 | 같음 |
| tsc(frontend-collective) | 0 오류 | 같음 |

### 로딩 실패로 제외한 테스트 파일 2개(이번 변경과 무관, 각각 따로 돌리면 통과)

| 파일 | 실패 | 이유 | 따로 실행 |
|---|---|---|---|
| `pipeline/tests/test_beopjungri_mapping_report.py` | `ModuleNotFoundError: No module named 'beopjungri_mapping_report'` | 테스트가 `pipeline/` 를 `sys.path` 에 넣지 않는다. 모듈(`pipeline/beopjungri_mapping_report.py`)은 있지만 저장소 루트에서 모아 돌리면 알파벳 순으로 먼저 수집돼 경로가 없다 | `cd pipeline && pytest tests/test_beopjungri_mapping_report.py` 통과 |
| `pipeline/tests/test_purge_built_contract_window.py` | `ImportError: cannot import name 'get_built_engine' from 'db_utils' (pipeline/db_utils.py)` | 같은 이름 모듈 `db_utils.py` 가 5개(`pipeline/`·`built/`·`collective/`·`rent/`·`parcel_master/`). `purge_built_contract_window.py` 는 `built/` 를 경로에 넣고 `from db_utils import get_built_engine` 하지만, 앞 테스트가 이미 `pipeline/db_utils.py` 를 `db_utils` 로 올려 두면 그 모듈(함수 없음)이 쓰인다 | 단독 실행 4 passed |

## 5. 확정 사항(T 결정 2026-11-16 — 재검수 때 이 기준으로 본다)

| # | 판단 | 확정 |
|---|---|---|
| D1 | 같은 키 충돌 규칙(좌표 3표 공통) | 한쪽만 `status=ok` → ok 쪽 · 둘 다 ok → `geocoded_at` 최근(같거나 운영 쪽 없음 → 로컬) · 둘 다 실패 → 로컬. 운영 쪽이 이기면 값 그대로 UPDATE. 시각 열만 다르면 충돌 아님. 보고서에 규칙별 건수. 테스트: 규칙 8경우 + 계획 집계 + DB UPDATE·멱등 |
| D2 | R5 스모크 | 스크립트 `scripts/ops/collective_p2_r5_smoke.py` — 기준 URL 인자(기본 로컬), 로컬 주소만(운영 URL 거부), 세 검사 중 하나라도 다르면 종료 1. 표본 키는 리허설 DB 에서, 번지 출력 없음. 운영 반영 뒤 실행은 Codex/Opus |
| D3 | C-2 옛 키 좌표 | 본 조각 옛 키 포함 **버린다**(키 이전 P2 · 병합 같은 규칙). 조각 키는 지도에서 처음 볼 때 새로 좌표를 받는다 |
| D4 | 실제 DB 쓰기 경로 | `load_c2_units --real-apply`·`migrate_p2_keys --real-apply`·병합 `--real-apply` 는 운영 절차(런북 5·6.1) 때 처음 실제 DB 에 쓴다. 지금까지는 리허설 DB·fixture·인자 가드 테스트로만 검증. 승인 해시 = `c2_units_final.csv` 바이트 SHA-256, 행 4,311 |

## 6. 재검수 때 볼 점 · 남은 한계

- [ ] 판정 표 「내용 해시」는 (키·법정동·본번·유형·연도·조각·판정)만 본다(source·note·decided_at 제외). 이 범위가 충분한지.
- [ ] c6 (키·유형·연도) 축소는 단위 테스트만 — 리허설 DB 가 덤프 상태가 아니라(키 이전 + 병합 뒤) 실제 데이터 재실행은 다음 전체 리허설 때.
- [ ] R5 스모크를 운영 서버에서 돌리려면 서버에 `pipeline/`·DB 접속(표본 고르기)이 있어야 한다. 없으면 표본 키를 미리 골라 넘기는 방식이 필요 — 반영 전에 Codex 가 확인.
- [x] Insight 03 출력 분리는 실제 로컬 DB(읽기 전용)로 한 번 돌려 확인: 결과 숫자 이전 실행과 같음(scanned 153,108 · eligible 1,097 · known 985 · yes 406 · no 579), 추적 파일 변경 0, 커밋된 캐시 파일 그대로. raw 정션은 쓰고 `rmdir` 해제(4,176파일).
- [x] 리허설 DB 현재 상태: 키 이전 + 병합 적용 뒤(덤프 상태 아님). 다음 전체 리허설은 12.2 1번(덤프에서 다시 만들기)부터.
