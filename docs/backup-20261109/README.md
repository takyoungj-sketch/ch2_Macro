# 2026-11-09 미커밋 작업 백업

원본 `D:/ch2/ch2_Macro`의 파일은 수정하지 않았다. 기준 커밋은 `05fa48fdc707e64f417fefdec2eb05fa96032745`이며 `wip/ai-revision-20261109`에 보존한다.

- 추적 변경 64개, 미추적 대상 148개. 임시·디버그·release worktree 145개 항목은 `excluded-paths.txt`에만 기록한다.
- 대상 212개 중 210개를 커밋한다. 원본 파일과 복사본의 SHA-256을 대조했다. Git의 기존 줄바꿈 정규화는 유지한다.
- 아래 대용량 원본 2개는 저장소 지침상 커밋하지 않고 이 worktree에 바이트 그대로 별도 복사했다. 원격 백업에 포함되지 않는다.
  - `data/research/land_trait_slim/gauge_asof_2026-05-12.sqlite` (8,826,650,624 bytes)
  - `pipeline/_land_annual.sql` (1,583,383,475 bytes)
- 비밀값 패턴 검사: 대상 텍스트 및 Office/HWPX XML에서 검출 없음. 대용량 원본 2개는 검사·커밋 대상에서 제외. 이미지/PDF는 텍스트 비밀값 검사 범위 밖이다.
- `manifest.json`에 파일별 원본 크기·SHA-256·제외 사유를 기록한다. 원본 정리는 사용자가 승인할 때까지 수행하지 않는다.
