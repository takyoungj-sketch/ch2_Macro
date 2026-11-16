# CH2 Macro — Cursor Agent 지침

전역 Git·버전 정책: `~/.cursor/agent.md`  
**제품 헌법:** [`docs/CH2_CONSTITUTION.md`](docs/CH2_CONSTITUTION.md) · 설명: [`docs/CH2_EXPLAIN_CONSTITUTION.md`](docs/CH2_EXPLAIN_CONSTITUTION.md) · AI: [`docs/CH2_AI_CONSTITUTION.md`](docs/CH2_AI_CONSTITUTION.md)

---

## 안전·역할 규칙 (항상 — 상세 [`.cursor/rules/ch2-safety.mdc`](.cursor/rules/ch2-safety.mdc))

- **최종 결정은 T.** 개발 에이전트는 지시 범위만, 자기 worktree·브랜치에서. 범위 밖 발견은 메모로 보고.
- **main 병합·push·배포는 관리 역할(Codex, 이관 뒤 T 가 지정)만, T 승인 뒤.** 지시에 「push 없음」이면 push 하지 않는다. 아래 배포 절차는 관리 역할이 T 의 배포 요청을 받았을 때 쓴다.
- **운영 DB 쓰기 금지.** 진짜 로컬 DB 는 읽기 전용 세션으로만 읽고, 쓰기는 런북의 `--real-apply`(5조건, `ops_guards`)로 T 지시가 있을 때만. 리허설 쓰기는 `*_p2r` 에만.
- 비밀값(`.env`·토큰·접속 문자열·`*.pem`) 출력·커밋 금지. 지번·주소·좌표가 든 산출물은 `logs/`(gitignore)에만, **`logs/` 커밋 금지.**
- 원천 `raw/` 정션은 필요할 때만 만들고 `rmdir` 로 해제(원본 4,176파일 확인).
- 단계 실패 → 그 자리에서 멈추고 보고. 「검증 못 함」은 통과가 아니다.
- 인계 상태: [`docs/ops/HANDOFF_CURSOR_20261116.md`](docs/ops/HANDOFF_CURSOR_20261116.md)

---

## 배포 (사용자가 「배포」「웹 반영」「VPS」 요청 시 — 관리 역할만)

**추가 확인 없이** [deploy/AGENT_DEPLOY_RUNBOOK.md](deploy/AGENT_DEPLOY_RUNBOOK.md) 전체를 따른다.

요약:

1. commit → `git push origin main`
2. `deploy/scripts/deploy-from-windows.ps1 -Scope <built|land|collective|insight|all>`
3. 운영 URL 스모크 검증 후 보고

고정값: SSH 키 `LightsailDefaultKey-ap-northeast-2.pem`(repo 루트), VPS `ubuntu@13.209.203.178`, 경로 `/opt/ch2_Macro`.

**배포 요청 = push 허용** (전역 agent.md §6 예외) — 관리 역할이 T 의 배포 요청을 받았을 때만. 개발 에이전트는 배포 요청을 받으면 관리 역할의 일임을 알린다(T 가 명시적으로 넘기면 예외).

---

## 로컬 dev URL

| 앱 | URL |
|----|-----|
| 복합 | http://localhost:5174/built/ |
| 토지 | http://localhost:5173/land/ |
| 토지 재구축 | http://localhost:5176/land/ → API `:8001` (`land_stats_next`) |
| 집합 | http://localhost:5175/collective/ |
| 임대 | http://localhost:5178/rent/ · 전환율 실험 종료 [`docs/RENT_CONVERSION_EXPERIMENT.md`](docs/RENT_CONVERSION_EXPERIMENT.md) |
| Macro Insight | http://localhost:5180/insight/ · FAQ [`docs/MACRO_INSIGHT_PLAN.md`](docs/MACRO_INSIGHT_PLAN.md) |
| 관리자 | http://localhost:5179/lab/ · 계획일지·검증로봇·Twin·전환율 [`docs/CH2_LAB_HUB.md`](docs/CH2_LAB_HUB.md) · 정리 규칙 [`.cursor/rules/lab-plan-log.mdc`](.cursor/rules/lab-plan-log.mdc) |
| API | http://127.0.0.1:8000 |
| AI | http://127.0.0.1:8000/api/ai/health · 헌법 [`CH2_CONSTITUTION.md`](docs/CH2_CONSTITUTION.md) · 설명 [`CH2_EXPLAIN_CONSTITUTION.md`](docs/CH2_EXPLAIN_CONSTITUTION.md) · AI [`CH2_AI_CONSTITUTION.md`](docs/CH2_AI_CONSTITUTION.md) |

---

## 토지 원장 조회 성능 (재발 금지)

기본통계·매트릭스 모달이 다시 수 초~수십 초로 느려지지 않게:

- **SSOT:** [`docs/LAND_LEDGER_QUERY_PERF.md`](docs/LAND_LEDGER_QUERY_PERF.md)
- **헬퍼:** `backend/app/ledger_region_sql.py` (`=` / expanding `IN`, `ANY` 금지)
- **규칙:** `.cursor/rules/land-ledger-query-perf.mdc`

원장 핫패스에 `beopjungri_code = ANY` 또는 롤링 버킷마다 DB 재조회를 넣지 말 것.

---

## 커밋

- 사용자가 배포만 요청: 변경 범위에 맞는 파일만 commit (전체 `git add .` 지양).
- `.env`, `*.pem`, 대용량 원본 커밋 금지.
- 에이전트가 만든 커밋에는 `Co-Authored-By:` 줄로 작성 에이전트를 밝힌다.

---

## 작업 폴더 (에이전트 여럿이 같은 저장소를 쓸 때)

- 에이전트마다 별도 worktree를 쓴다. 예: `git worktree add ../ch2_Macro-<작업명> origin/main -b <브랜치>`.
- 작업 시작 전에 반드시 `git fetch && git log HEAD..origin/main` 으로 최신 상태를 확인한다. 뒤처져 있으면 최신 main 에서 다시 시작한다.
- 원래 폴더 `D:/ch2/ch2_Macro` 에 커밋하지 않은 변경을 남기지 않는다.

---

## 집합(주거·비주거) 쌍 작업

주거용·비주거용 집합은 **분석 단위만 다름**(건물/단지 vs 도로명 cluster). **통계 방식·UI·UX는 동일**하게 유지한다.

집합 관련 작업 시 **기본으로 주거 + 비주거를 동시에** 수정한다. 상세: `.cursor/rules/collective-residential-commercial-parity.mdc`

---

## 5앱 형식 패리티

탭 글자·필터 UX·모달 크롬처럼 **형식이면** 토지·복합·집합·임대·지역프로필에 **같이** 적용한다. 랩 제외. 상세: `.cursor/rules/five-app-format-parity.mdc` · 결정 D-072
