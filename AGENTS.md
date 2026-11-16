# CH2 Macro — Cursor Agent 지침

전역 Git·버전 정책: `~/.cursor/agent.md`  
**제품 헌법:** [`docs/CH2_CONSTITUTION.md`](docs/CH2_CONSTITUTION.md) · 설명: [`docs/CH2_EXPLAIN_CONSTITUTION.md`](docs/CH2_EXPLAIN_CONSTITUTION.md) · AI: [`docs/CH2_AI_CONSTITUTION.md`](docs/CH2_AI_CONSTITUTION.md)

---

## 에이전트 작업방식 (2026-11-17 사용자 합의)

당분간 아래 절차를 기본으로 운영하고, 추후 사용자와 조정한다. 상세: [`.cursor/rules/agent-workflow.mdc`](.cursor/rules/agent-workflow.mdc).

- Opus 조사·진단 → GPT 독립 의견 → T(사용자) 수정 방향 승인 → Opus 구현 지시문 → Cursor 독립 판단·구현 → Codex 실제 코드 독립 검수 → Opus 검수 결과 판단 → T 배포 승인 → Cursor main 병합·배포·브랜치 정리.
- Codex는 실제 변경 코드·테스트·기존 기능 영향을 검증한다. 지시문 검토나 테스트 통과만으로 승인하지 않는다.
- 통계모형·데이터 정책 변경은 T의 명시적 승인, DB 구조·운영환경 변경은 별도 위험 검토와 T 승인이 필요하다. 오탈자·단순 UI는 사전 승인 범위 안에서 간소화한다.
- main 병합·운영 배포·작업 브랜치 정리 담당은 Cursor다. 아래 배포 절차의 실행 주체도 Cursor이며, Codex는 검수 결과를 전달한다.

---

## 배포 (Cursor가 사용자 「배포」「웹 반영」「VPS」 승인을 받은 경우)

**추가 확인 없이** [deploy/AGENT_DEPLOY_RUNBOOK.md](deploy/AGENT_DEPLOY_RUNBOOK.md) 전체를 따른다.

요약:

1. commit → `git push origin main`
2. `deploy/scripts/deploy-from-windows.ps1 -Scope <built|land|collective|insight|all>`
3. 운영 URL 스모크 검증 후 보고

고정값: SSH 키 `LightsailDefaultKey-ap-northeast-2.pem`(repo 루트), VPS `ubuntu@13.209.203.178`, 경로 `/opt/ch2_Macro`.

**배포 요청 = push 허용** (전역 agent.md §6 예외).

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
