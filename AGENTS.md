# CH2 Macro — Cursor Agent 지침

전역 Git·버전 정책: `~/.cursor/agent.md`  
**제품 헌법:** [`docs/CH2_CONSTITUTION.md`](docs/CH2_CONSTITUTION.md) · AI: [`docs/CH2_AI_CONSTITUTION.md`](docs/CH2_AI_CONSTITUTION.md)

---

## 배포 (사용자가 「배포」「웹 반영」「VPS」 요청 시)

**추가 확인 없이** [deploy/AGENT_DEPLOY_RUNBOOK.md](deploy/AGENT_DEPLOY_RUNBOOK.md) 전체를 따른다.

요약:

1. commit → `git push origin main`
2. `deploy/scripts/deploy-from-windows.ps1 -Scope <built|land|collective|all>`
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
| API | http://127.0.0.1:8000 |
| AI | http://127.0.0.1:8000/api/ai/health · 헌법 [`CH2_CONSTITUTION.md`](docs/CH2_CONSTITUTION.md) · AI [`CH2_AI_CONSTITUTION.md`](docs/CH2_AI_CONSTITUTION.md) |

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

---

## 집합(주거·비주거) 쌍 작업

주거용·비주거용 집합은 **분석 단위만 다름**(건물/단지 vs 도로명 cluster). **통계 방식·UI·UX는 동일**하게 유지한다.

집합 관련 작업 시 **기본으로 주거 + 비주거를 동시에** 수정한다. 상세: `.cursor/rules/collective-residential-commercial-parity.mdc`
