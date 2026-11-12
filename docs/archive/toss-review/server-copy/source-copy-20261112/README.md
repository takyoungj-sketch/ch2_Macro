# 서버 소스 삭제 전 사본

2026-11-12 사용자 추가 승인으로 `/opt/ch2_Macro/deploy/hub/toss-review/`의 파일 14개와 빈 디렉터리를 제거했다. 삭제 직전 승인 목록·SHA-256을 다시 대조하고, 코드 소스와 공개 웹 루트 양쪽에 toss-review가 없음을 확인했다. 실제 배포·dry-run·빌드·서비스 재시작은 하지 않았다.

이 폴더는 기존 공개본 사본을 덮어쓰지 않고 소스에만 있거나 버전이 다른 4개를 추가 보존한다.

- `screenshots/07_payment_window.png`: 공개본 13개 목록에 없던 소스 전용 파일.
- PPT 2개와 `screenshots/06_subscribe.png`: 공개본 사본과 바이트가 다른 소스 버전.

소스 14개를 복원하려면 상위 `server-copy/`의 공개본 13개에 이 폴더의 4개를 같은 상대 경로로 겹쳐 사용한다. 해시·크기·삭제 검증은 `manifest.json`에 있다. 복원은 보관 목적으로만 하며 deploy/hub/로 다시 넣으면 공개될 수 있다. 재배포 없이 확인하는 절차는 `docs/ops/DEPLOY_PATHS.md`를 따른다.
