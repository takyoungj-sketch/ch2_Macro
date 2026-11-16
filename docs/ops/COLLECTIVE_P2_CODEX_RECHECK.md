# 집합 2단계 Phase D — Codex 재검수 체크리스트 (2026-11-16)

브랜치 `data/collective-p2`(로컬, push 안 함). 런북: [`COLLECTIVE_P2_RUNBOOK.md`](COLLECTIVE_P2_RUNBOOK.md).
지번·주소·좌표·키 원문이 든 산출물은 `logs/collective_p2/`(gitignore)에만 있다.

## 1. 커밋

| 커밋 | 내용 |
|---|---|
| `cd1992f` | Phase D 지적 6건(Insight 출력 분리·순서, C-2 판정 표 실제 적재 대조, 운영 전용 표 병합 스크립트, c6 예외 범위, R5 스모크) |
| `14a24ec` | 병합: 같은 키 충돌 건수 + 병합 리허설 검증 `c29` |
| (이번 커밋) | 병합 사전 확인(manifest SHA-256·덤프 시각 ≥ 동결 시각·행 수) · 병합 고아 건수 · c29 게이트·운영 DB 인자 · 런북 6.1 동결 직후 단계 · 이 체크리스트 |

## 2. Phase D 지적별 확인

| # | 지적 | 완료 | 커밋 | 확인할 곳 | 테스트 |
|---|---|---|---|---|---|
| 1 | Insight 출력 분리(03 부속 CSV·표제부 캐시 → `logs/collective_p2/insight/<label>/`, 실행 전후 추적 파일 변경 0) | ✅ | `cd1992f` | `scripts/lab/collective_p2/c22_insight_recompute.py` RUNNERS["03"]·`assert_clean` · `c27_insight14_compare.py` `check_repo_clean` | `test_collective_p2_insight14_compare.py`: `test_c22_runner03_redirects_attach_csv_and_title_cache` · `test_c22_tracked_change_guard` · `test_run_refuses_when_main_repo_tracked_files_change` |
| 2 | Insight 를 c8 앞으로(운영 before = 적용 직전, after = 적용 직후, `--gen14` → c27 통일) | ✅ | `cd1992f` | 런북 5절 머리·5.4·7.3·12.2(9 Insight → 10 c8) · `--label ops_before/ops_after` | (문서·인자) |
| 3 | C-2 표 로더 해시·행 수 검사(실제 DB 모드) + 키 이전 시작 전 대조 | ✅ | `cd1992f` | `pipeline/collective/load_c2_units.py` `check_approved_file`·`approved_table_state` · `migrate_p2_keys.py` `assert_c2_units_approved`·`--c2-approved-*` · 런북 5.1 0a·0b·2 | `test_collective_p2_load_c2_units.py`: 빈 표·다른 해시·정상(+행 수·적재 뒤 변경) · `test_migrate_cli_real_apply_requires_c2_approval_args` · `test_collective_p2_real_apply.py` 갱신 |
| 4 | 운영 전용 데이터 병합 | ✅ | `cd1992f`·`14a24ec`·이번 | `scripts/ops/collective_p2_merge_prod_only.py` · `scripts/lab/collective_p2/c29_merge_prod_only_check.py` · 런북 6.1 2(a~h) | `test_collective_p2_merge_prod_only.py` 13개(규칙·충돌·fixture DB 병합·멱등·가드·사전 확인) |
| 5 | c6 예외를 (키·유형·연도) 단위로 축소 | ✅ | `cd1992f` | `scripts/lab/collective_p2/c6_annual_check.py` `orphan_cells`·`compare_sample_key` | `test_collective_p2_rehearsal_runner.py::test_c6_sample_excludes_only_orphan_key_type_year_cells` |
| 6 | R5 스모크(C-01 분할 옛 키 409 · C-2 옛 키 200 + `key_split_c2` · 1:1 200, 그 밖 실패) | ✅ | `cd1992f` | 런북 8절 R5 · 6.3 스모크 표 | (문서) — 스모크 자동 스크립트는 없음(아래 5절) |

## 3. 병합 리허설 결과(2026-11-16 덤프 `…_180626`, `*_p2r` 만, 운영 접속 없음)

- 덤프 SHA-256·크기 = manifest(2개). `logs/` 는 `.gitignore` 44행으로 제외.
- 대상 상태: c8 뒤 덤프 상태였던 리허설 DB 에 키 이전만 다시 적용(`migrate_apply` rc 0 · 57분, `migrate_verify` 20/20 OK).
- 원본: `prodonly_collective_p2r_src` · `prodonly_rent_p2r_src`(표 구조 = 리허설 DB, 데이터 = 덤프, 행 수 = manifest). **Codex 재검수 통과 전까지 유지.**

| 표 | 병합 전 | 덤프 | 병합 후 | 넣음 | 버림(C-2 · C-01) | 같은 키 값 다름(좌표) | 규칙 |
|---|---|---|---|---|---|---|---|
| collective_building_geocodes | 5,285 | 5,413 | 5,802 | 517 | 34 · 24 | 1(1) | 로컬 값 유지 |
| collective_commercial_map_geocodes | 603 | 695 | 695 | 92 | 0 · 0 | 0 | 값 그대로(전체 행 해시 = 덤프) |
| qa_audit_run | 1 | 1 | 1 | 0 | — | 같은 id 같은 내용 1 | 건너뜀(시퀀스 1→2) |
| rent_building_geocodes | 1,013 | 975 | 1,013 | 0 | 0 · 0 | 0 | 로컬 값 유지 |

- 충돌 1건: 운영 행은 좌표 없음(`status=not_found`, 오류 기록, `geocoded_at` 없음, `updated_at` 2026-10-24 22:37), 로컬 행은 `ok`(`geocoded_at`·`updated_at` 2026-11-05 18:01) → 두 좌표 거리 계산 불가. 로컬이 12일 늦은 성공값이라 유지가 맞다.
- C-2: 운영 C-2 옛 키 좌표 34행 버림(조각 키로 옮기지 않는 규칙) · 병합 뒤 C-2 옛 키 좌표 0 · C-01 분할 옛 키 좌표 0 · C-2 조각 키 2,045 중 운영 좌표 붙은 키 0.
- 고아: 집합·비주거 0. 임대 28행은 원장에 없는 키지만 **진짜 로컬 rent_stats 에도 P2 전부터 같은 28행**(병합이 넣은 행 0).
- 1:1 재키 0: 운영 좌표에 호남 옛 키 행이 없다.
- 멱등: 두 번째 실행 넣은 행 0, 4표 + QA 시퀀스 행 수·해시가 첫 실행 뒤와 같다.
- 사전 확인: 동결 18:00(덤프 18:06:26) → 통과 · 동결 18:10 → 「덤프가 동결 시각보다 오래됨」 종료 코드 2.
- 산출물: `logs/collective_p2/merge_rehearsal/`(run1/run2/dryrun*.json · snap_*.json · check.md).

## 4. 테스트(새 실패 0)

| 묶음 | 결과 | 기준선 대비 |
|---|---|---|
| pipeline | 297 passed | 같음(+새 테스트). 수집 오류 2개(`test_beopjungri_mapping_report` 모듈 없음 · `test_purge_built_contract_window` `get_built_engine` import)는 이번 변경과 무관해 `--ignore` |
| backend | 1,327 passed · 12 failed · 1 error | 기준선과 같은 목록(built 지역 4 · insight 번들 6 · region_sido 1 · yield 1 · `test_profile_national_rank` 수집 오류) |
| 집합 컴포넌트 | 14/14 | 같음 |
| tsc(frontend-collective) | 0 오류 | 같음 |

## 5. 재검수 때 볼 점 · 남은 한계

- [ ] `load_c2_units --real-apply` 와 `migrate_p2_keys --real-apply` 는 실제 DB 에 돌려 보지 않았다(fixture·인자 가드 테스트만). 대조 해시는 승인 파일 바이트 SHA-256(이번 `c2_units_final.csv` 4,311행) — T 승인 값과 같은지 확인.
- [ ] 판정 표 「내용 해시」는 (키·법정동·본번·유형·연도·조각·판정)만 본다(source·note·decided_at 제외). 이 범위가 충분한지.
- [ ] 병합 규칙: C-2 옛 키(본 조각 옛 키 포함) 좌표를 버린다(키 이전 P2 와 같게). 본 조각은 옛 키를 유지하므로 「본 조각 좌표는 남긴다」로 바꿀지 결정 필요하면 지적.
- [ ] 같은 키 값 다름은 항상 로컬 유지. 운영 쪽이 더 새 `ok` 값이고 로컬이 `not_found` 인 경우도 로컬 유지다(이번 리허설엔 없음). 바꿀지.
- [ ] R5·6.3 스모크는 런북 표로만 있다(자동 스크립트 없음). `vps_collective_smoke.sh` 에 넣을지.
- [ ] c6 (키·유형·연도) 축소는 단위 테스트만 — 리허설 DB 가 c8 뒤 덤프 상태라 실제 데이터 재실행은 다음 전체 리허설 때.
- [ ] Insight 03 출력 분리는 실제 로컬 DB(읽기 전용)로 한 번 돌려 확인: 결과 숫자 이전 실행과 같음(scanned 153,108 · eligible 1,097 · known 985 · yes 406 · no 579), 추적 파일 변경 0, 커밋된 캐시 파일 그대로. raw 정션은 쓰고 `rmdir` 해제(4,176파일).
- [ ] 리허설 DB 현재 상태: 키 이전 + 병합 적용 뒤(덤프 상태 아님). 다음 전체 리허설은 12.2 1번(덤프에서 다시 만들기)부터.
