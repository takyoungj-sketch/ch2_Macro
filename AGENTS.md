# CH2 Macro — Cursor Agent 지침

전역 Git·버전 정책: `~/.cursor/agent.md`

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
| API | http://127.0.0.1:8000 |

---

## 커밋

- 사용자가 배포만 요청: 변경 범위에 맞는 파일만 commit (전체 `git add .` 지양).
- `.env`, `*.pem`, 대용량 원본 커밋 금지.
