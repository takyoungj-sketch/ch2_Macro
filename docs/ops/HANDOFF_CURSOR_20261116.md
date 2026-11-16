# Cursor 인계 — 2026-11-16 (Claude Code → Cursor)

규칙은 [`AGENTS.md`](../../AGENTS.md) 와 [`.cursor/rules/ch2-safety.mdc`](../../.cursor/rules/ch2-safety.mdc)(항상 적용)에 옮겼다. 이 문서는 **상태와 다음 할 일**만 적는다. 비밀값·접속 정보는 없다.
**Opus 지시서는 T 가 전달한다**(이 문서에 없음).

---

## 1. 집합 2단계(P2)

| 항목 | 값 |
|---|---|
| 브랜치 | `data/collective-p2` (worktree `D:/ch2/ch2_Macro-collp2`) — **origin 에 없음(push 안 함)**, 마지막 fetch 기준 origin/main 보다 71 커밋 앞 · 7 뒤 |
| 런북 | [`docs/ops/COLLECTIVE_P2_RUNBOOK.md`](COLLECTIVE_P2_RUNBOOK.md) — 3.2 동결·낮 순서 · 5 로컬 적용 · 6.0 nginx 점검 모드 17곳 · 6.1 밤 점검 창(시간식) · 6.2 실패·OFF 뒤 되돌리기(보존만) · 7 운영 확인 · 8 롤백 · 12 리허설 |
| 재검수 체크리스트 | [`docs/ops/COLLECTIVE_P2_CODEX_RECHECK.md`](COLLECTIVE_P2_CODEX_RECHECK.md) — 2 Phase D · 2a 2차 · 2b 3차 · 2c 4차 · 3 병합 리허설 · 4 테스트 · 5 확정 사항 · 6 남은 점 |
| 운영 확인 스크립트 | `scripts/ops/collective_p2_verify/`(prod_sync_check · prod_c5_core · prod_hash_compare(+overlay) · **prod_stat_compare**(밤 가벼운 비교) · ops_guards · _common) — pipeline 불필요, 서버 backend venv 로 실행 |
| 운영용 도구 | `scripts/ops/collective_p2_merge_prod_only.py`(운영 전용 4표 병합) · `scripts/ops/collective_p2_r5_smoke.py`(R5, 로컬 주소만) · `pipeline/collective/load_c2_units.py` · `migrate_p2_keys.py` |

### 1.1 Phase D 이후 커밋(cd1992f ~ d580093, 오래된 순)

| 커밋 | 내용 |
|---|---|
| `cd1992f` | Codex Phase D 6건 — Insight 출력 분리·c8 앞으로, C-2 판정 표 실제 적재 대조, 운영 전용 표 병합 스크립트, c6 예외 (키·유형·연도), R5 기준 |
| `14a24ec` | 병합 같은 키 충돌 건수 + 병합 리허설 검증 c29 |
| `5e0bef9` | 병합 사전 확인(manifest SHA-256·덤프 시각 ≥ 동결 시각·행 수) · c29 게이트 · 체크리스트 |
| `e4a3d7a` | 충돌 규칙(status·geocoded_at) · R5 스모크 스크립트 |
| `cda06bb` | 재검수 2차 — nginx 점검 창(안 A) · manifest·c29 엄격 판정 · 멱등 판정 · R5 서버용 |
| `5134ea5` | 재검수 3차 — 점검 대상 17곳 · OFF 뒤 되돌리기(reverse 병합) · built QA · 시간 재합산 |
| `d580093` | 재검수 4차 — 되돌리기 보존만 · 무거운 동기화 낮으로 · 밤 가벼운 비교(`prod_stat_compare.py`) · 병합 표만 해시(overlay) · built QA 2a · 시간식 |
| (이 커밋) | 인계 문서 · AGENTS.md 안전·역할 규칙 · `.cursor/rules/ch2-safety.mdc` |

### 1.2 현재 상태 — Codex 5차 재검수

**반드시 수정 1건(미해결):**
- `scripts/ops/collective_p2_verify/prod_hash_compare.py:291`(`overlay`) 가 시각을 **`stat_result.compared_at ≥ base.measured_at` 하나만** 검사한다. 그래서
  - **전날(또는 오래된) 병합 표 해시 파일**(`--patch`)도 통과한다 — `patch.measured_at` 을 보지 않는다.
  - **낮 해시보다 늦게 기록된 카운터 기준**(가벼운 비교의 `baseline_measured_at` > 낮 해시 `measured_at`)도 통과한다 — 그 사이(낮 해시 → 카운터 기준) 쓰기는 카운터 비교에 안 잡히는데 낮 해시가 그대로 쓰인다.
  - 고칠 방향(제안, 미구현): `stat_result.baseline_measured_at ≤ base.measured_at` · `patch.measured_at ≥ stat_result.compared_at`(또는 `≥ FREEZE_AT`)· 셋 다 같은 점검 창 안 — 를 모두 요구하고, 각 경우 테스트(`pipeline/tests/test_collective_p2_stat_compare.py` 의 overlay 거절 표에 추가).

**권장(미해결 — T 지시의 「권장 2건」 항목 그대로):**
1. **`track_counts` 기록과 통계 안정 확인** — 가벼운 비교는 `pg_stat_user_tables` 카운터에 기대므로 `SHOW track_counts`(on) 를 스냅샷에 남기고 off 면 실패. 카운터는 비동기로 반영되므로 밤 비교 전에 짧게 두 번 읽어 같은지(안정) 본 뒤 비교.
2. **60초 강제 중단 구조** — 지금은 쿼리마다 남은 시간을 `statement_timeout` 으로 주고 끝난 뒤 경과를 본다. 접속 단계(`connect_timeout`)·DNS 등에서 멈추면 60초를 넘길 수 있다 → 별도 프로세스/스레드 타이머로 전체를 끊는 구조로.
3. **07:00 검증 마감 재산정** — 06:00 OFF 뒤 7절 운영 확인(c5 핵심 지표 · 해시 비교 collective 25~50분·rent 30~65분)이 07:00 안에 끝나는지 다시 계산해 시간식에 넣기.

**그 밖 열린 점**(체크리스트 6절): scp 속도 `S` 는 낮 built 업로드에서 실측 · built QA 행 수(낮·밤 2a)는 Codex 실행 · nginx 실효 location 17곳 서버 확인 · 판정 표 「내용 해시」 범위.

### 1.3 테스트 명령과 기준선

```bash
# pipeline(저장소 루트, 2파일 제외) — 마지막 405 passed
python -m pytest -q pipeline/tests --ignore=pipeline/tests/test_beopjungri_mapping_report.py --ignore=pipeline/tests/test_purge_built_contract_window.py
# 제외한 2파일은 따로 — 7 passed · 4 passed
(cd pipeline && python -m pytest -q tests/test_beopjungri_mapping_report.py)
python -m pytest -q pipeline/tests/test_purge_built_contract_window.py
# backend — 기준선 1,327 passed · 12 failed · 1 error(아래 목록과 같아야 「새 실패 0」)
cd backend && python -m pytest --continue-on-collection-errors -rfE
# 집합 화면 — 14/14 · 0
cd frontend-collective && node scripts/component-tests.mjs && node node_modules/typescript/bin/tsc --noEmit -p .
```

- Python 은 `D:\ch2\ch2_Macro\backend\.venv\Scripts\python.exe`, `PYTHONUTF8=1`. Node 는 `D:\tools\node-v24.21.0-win-x64\node.exe`.
- **backend 기준선 실패 12 + 오류 1**(P2 와 무관, main 에서도 같음):
  - `tests/test_built_recommend_deprecated.py::test_suggest_compare_deprecation_headers`
  - `tests/test_built_region_all_asset.py::test_gyeongbuk_addr2_with_all` · `::test_gyeongbuk_pohang_structure_with_all` · `::test_gyeongbuk_leaf_with_all`
  - `tests/test_insight_06.py::test_insight_06_bundle_not_01` · `test_insight_07.py::test_insight_07_bundle_not_01` · `test_insight_08.py::test_insight_08_bundle_not_01` · `test_insight_10.py::test_insight_10_bundle_not_08` · `test_insight_11.py::test_insight_11_bundle_not_01` · `test_insight_12.py::test_insight_12_bundle_not_11`
  - `tests/test_region_sido.py::test_retired_sido_addr2_returns_empty`
  - `tests/test_yield_compare.py::test_apartment_december_matches_table`
  - 오류: `tests/test_profile_national_rank.py`(수집 오류)
  - 전체 로그: `logs/collective_p2/backend_tests_20261116_r4.log`(로컬, gitignore)
- **pipeline 제외 2파일과 이유**(저장소 루트에서 모아 돌릴 때만 로딩 실패):
  - `test_beopjungri_mapping_report.py` — 테스트가 `pipeline/` 를 `sys.path` 에 넣지 않아 `ModuleNotFoundError: beopjungri_mapping_report`(모듈은 `pipeline/beopjungri_mapping_report.py` 에 있음).
  - `test_purge_built_contract_window.py` — 같은 이름 `db_utils.py` 가 5개(`pipeline/`·`built/`·`collective/`·`rent/`·`parcel_master/`). 앞 테스트가 `pipeline/db_utils.py` 를 먼저 올리면 `from db_utils import get_built_engine` 이 그 모듈을 써서 `ImportError`.

### 1.4 리허설·임시 DB(로컬 PostgreSQL, 이름만)

| DB | 크기 | 상태 | 유지·삭제 조건 |
|---|---|---|---|
| `collective_stats_p2r` | 12GB | 키 이전 + 운영 전용 표 병합 적용 뒤(덤프 상태 아님). 확인용 쓰기로 `qa_audit_run` 시퀀스 +2·카운터 증가(행 내용 그대로) | 다음 전체 리허설 때 런북 12.2 1번(덤프에서 다시 만들기)으로 덮는다. 그 전까지 유지 |
| `rent_stats_p2r` | 18GB | 키 이전 뒤 | 같음 |
| `built_stats_p2r` | 985MB | 키 이전 뒤 | 같음 |
| `parcel_master_p2r` | 656MB | 표제부 사본(리허설 12.2 에서 그대로 둠) | 실제 반영 5.0 의 진짜 `parcel_master` 를 만든 뒤 T 확인 받고 삭제 |
| `prodonly_collective_p2r_src` · `prodonly_rent_p2r_src` | 10MB · 8.6MB | 운영 전용 4표 덤프(2026-11-16 18:06) 복원본 | **Codex 재검수 통과 전까지 유지**(T 지시). 통과 뒤 삭제 |
| `collective_old_p2r` · `rent_old_p2r` · `collective_new_p2r_src` | 39MB · 35MB · 10MB | 역방향 병합 리허설(런북 12.6, 필수 단계 아님) | 필요 없으면 T 확인 뒤 삭제 |
| `ch2*_p2r_fixture`·`ch2mpo_*_p2r` 등 | — | 테스트가 만들고 지움 | 남아 있으면 지워도 됨 |

- 리허설 덤프(Phase C, 복원 원본): `logs/collective_p2/dumps/{collective_stats,rent_stats,built_stats}.dir`(5.0GB) — 다음 리허설에 필요, 실제 반영 끝날 때까지 유지.
- 운영 전용 표 덤프(T 승인 읽기 전용): `logs/collective_p2/prod_only/`(manifest 포함) — 재검수 통과 전까지 유지. 실제 반영 때는 **점검 ON 뒤 새로 뜬 덤프만** 쓴다.
- 디스크: D: 여유 264G(72% 사용).

### 1.5 `--real-apply` · logs/

- 실제 로컬 DB 쓰기는 `--real-apply` 하나뿐이다. 통과 조건(`ops_guards.py`·`migrate_p2_keys.py`): ① 플래그 ② `--confirm-db` 재입력(목록 일치) ③ 접속 대상 로컬 루프백(최종 DSN 기준, `PGHOST`/`PGHOSTADDR` 포함, service 거부) ④ DB 마다 `prod_sync_check` 통과 결과 파일(`--sync-result`, 48시간 이내) ⑤ 도구별: 판정 표 적재·키 이전 = 승인 SHA-256·행 수(4,311) · 병합 = `--manifest`·`--freeze-at`(+임대 쪽 필수). 허용 대상은 `collective_stats`·`built_stats`·`rent_stats`.
- 쓰기 직전 `current_database()` 를 다시 본다. 리허설 모드(`--apply`)는 `*_p2r` 이름만.
- **`logs/` 는 커밋하지 않는다**(`.gitignore` 44행). 지번·주소·좌표·키 원문이 든 산출물, 덤프, 테스트 로그는 모두 여기.

---

## 2. worktree 상태(2026-11-16, 마지막 fetch 기준 — 이 인계에서 다른 worktree 는 손대지 않음)

| worktree | 브랜치 | 마지막 커밋 | push | 커밋 안 된 변경 · 추적 안 된 파일(logs/ 제외) | 메모 |
|---|---|---|---|---|---|
| `D:/ch2/ch2_Macro` | `main` | `a2e7b37` 11-12 게시판 배포 수동화 | upstream origin/main, 10 뒤 | 변경 0 · **추적 안 된 53**(docs/lab 실험 결과·문서 다수, docs/reports 9, deploy/scripts `_vps_*.sh` 7, backend/app lab 모듈 4·tests 1, scripts/local 2, data PDF 4·research, `.vite` 캐시 3, `참고/*.hwpx` 등) | **애매 — 커밋하지 않음.** 원래 폴더에 남기지 말아야 하는 규칙 위반 상태. 주인(작성한 작업)별로 나눠 T 가 정리 결정 |
| `ch2_Macro-collp2` | `data/collective-p2` | `d580093`(+ 이 인계 커밋) | **origin 에 없음** | 0 · 0 | P2. 위 1절 |
| `ch2_Macro-ai` | `claude/ai-revision-v2` | `7ea9a86` 11-10 AI 답변 내부 용어 | 같음(0/0) | 0 · 0 | |
| `ch2_Macro-coll0` | `lab/collective-phase0` | `b84f691` 11-11 집합 점검 0단계 문서 | 같음 | 0 · 0 | |
| `ch2_Macro-collp1` | `fix/collective-p1` | `dfa3082` 11-12 경고 모드 식별자 | 같음 | 0 · 0 | P1 — main 에 반영됨(main 최근 커밋에 있음) |
| `ch2_Macro-deploypaths` | `codex/manual-board-deploy` | `6ff618c` 11-12 토스 문서 | origin 에 없음(1 앞) | 0 · 0 | Codex 작업 |
| `ch2_Macro-gates` | `feature/admin-gates` | `ad0bee7` 11-14 gates unknown 근거 | origin 에 없음 | 0 · 0 | |
| `ch2_Macro-hubsync` | `fix/hub-sync-production` | `09e423b` 11-12 토스 공개 파일 | 2 앞 · 1 뒤 | 0 · 0 | push 안 된 2 커밋 |
| `ch2_Macro-landlink` | `claude/land-link-shadow-20261110` | `6df84d3` 11-10 토지 V2 결과 문서 | origin 에 없음(6 앞) | 0 · 0 | |
| `ch2_Macro-landv2` | `claude/land-v2-monthly-20261110` | `b8688b1` 11-10 광주·전남 개편 | 같음 | 0 · 0 | |
| `ch2_Macro-rent504` | `codex/rent504-release` | `55bb29c` 11-14 임대 회귀 요청 | origin 에 없음 | 0 · 0 | Codex 작업 |
| `ch2_Macro-wip1109` | `wip/ai-revision-20261109` | `ed56f0d` 11-12 보존 작업 비교 | 같음 | 0 · **추적 안 된 2**(`data/research/`, `pipeline/_land_annual.sql`) | 애매 — 커밋하지 않음. Insight 14 생성기 원본 브랜치(c27 이 읽기 전용으로 씀) |
| `ch2_Macro-b1-audit` · `-mainapi` · `-p2-audit` · `-rent504-baseline` · `-rent504-review` | (분리 HEAD) | `ad0bee7` · `08aea31` · `bbfec74` · `a2e7b37` · `1a7cf71` | — | 0 · 0 | 검수용 읽기 worktree. 지워도 됨(T·Codex 확인 뒤 `git worktree remove`) |
| `ch2_Macro-retained-worktrees-20261112/*` | `baseline-d563d97`(분리) · `codex/deploy-collective-help-20261029` · `codex/deploy-regression-ui-20261029` · `codex/help-and-dump` | `d563d97` · `3ecae7b` · `a025239` · `f6fab5e` | 뒤 2는 origin 에 없음 | 0 · 0 | 11-12 보관용. 정리는 Codex |

- 이 인계에서는 **다른 worktree 의 변경을 커밋하지 않았다**(지시: 인계 문서·규칙 파일만 커밋). 애매한 것은 위 표에 남겼다.

## 3. 다음 할 일

| 순서 | 일 | 상태 | 비고 |
|---|---|---|---|
| 1 | P2 5차 재검수 **반드시 1건**(overlay 시각 검사) 고치기 + 권장 2건 판단 | 미착수 | 1.2 |
| 2 | Codex 재검수 통과 → T 승인 → 런북 낮 단계(동결·무거운 동기화·로컬 적용) → 밤 점검 창 | 대기 | 런북 3.2·5·6 |
| 3 | FieldNote 서버 **Phase A** | 미착수(다른 작업) | 지시서는 T 전달 |
| 4 | 비주거 **도로선 오류 지시서** | 미착수 | 병합은 값을 고치지 않고 옮겼음(P2 범위 밖) |
| 5 | 호남 지역 프로필 · **임대 C-2 분할** | **P2 이후** | 임대 C-2 규모 자료: `scripts/lab/collective_p2/c28_rent_c2_scale.py`(런북 12.4) |
| 6 | main 원래 폴더의 추적 안 된 53개 정리 | T 결정 필요 | 2절 |
