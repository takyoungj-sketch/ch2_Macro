# 운영 배포 경로

확인: 2026-11-12 · VPS `ubuntu@13.209.203.178` · 코드 공급 경로 `/opt/ch2_Macro`.
현재 서버는 SCP/tar로 소스를 공급하는 구조이며 `/opt/ch2_Macro/.git`은 없다. 아래 스크립트·nginx·실행 서비스는 읽기 전용으로 확인했다. 과거 운영자가 마지막에 실행한 명령까지 확인한 것은 아니다.

## Macro 앱

- 로컬 `deploy/scripts/deploy-from-windows.ps1 -Scope <앱>`이 `scp`로 scope별 `backend/app`, `frontend*/src`, `shared` 등을 `/opt/ch2_Macro/`에 복사한다. `-SkipPush`는 이미 push한 경우에 쓴다.
- 서버 `deploy/scripts/vps_apply_scope.sh`가 해당 프런트를 빌드해 `/opt/ch2_Macro/frontend*/dist`를 만들고 `ch2-macro-backend`를 재시작한다. nginx는 앱별 dist를 alias로 제공한다.
- API는 `/opt/ch2_Macro/backend`에서 실행하는 FastAPI `127.0.0.1:8000`이다. 내부 `/health`로 확인한다. 공개 Macro `/health`는 별도 인증 보호에 의해 401일 수 있다.

## hub와 게시판

- hub 소스 `deploy/hub/`를 먼저 scp/tar로 `/opt/ch2_Macro/deploy/hub/`에 공급한다. 로컬 `-Scope all`의 scp는 hub 소스도 복사하지만, 해당 `vps_apply_scope.sh`는 hub 웹 루트 동기화까지 자동 수행하지 않는다.
- 서버 `deploy/scripts/deploy-hub.sh`는 `rsync -a --delete --exclude board --exclude admin`으로 소스를 `/var/www/ch2data-hub/`에 복사한다. 이곳이 `ch2data.com`의 nginx 웹 루트다. 이어 board/admin 정적 파일을 별도로 복사하고 nginx를 검사·reload한다.
- 게시판은 `deploy/scripts/redeploy-board.sh`가 `/opt/ch2_Macro/deploy/board/public/` → 웹 루트 `/board/`, `deploy/admin/public/` → `/admin/`으로 rsync한다. 조건부 플랫폼 DB 스크립트 호출, FastAPI 재시작과 nginx 설정 적용도 포함한다.
- 현재 nginx `/api/board/`는 FastAPI `:8000`으로 연결된다. 구 Node `ch2-board.service`도 실행 중이지만 현재 게시판 API 프록시 대상과 구분한다. 정적 `/board/`와 `/api/board/meta`가 상태 확인 경로다.

## Actions는 수동 실행만

`.github/workflows/deploy-ch2-board.yml`은 `workflow_dispatch`만 남긴다. main push는 이 워크플로를 자동 실행하지 않는다.
수동 작업 본문에는 여전히 `git fetch/checkout/reset --hard origin/main`과 게시판·hub 배포 호출이 있다. **서버의 Git 저장소 부재와 이 전제는 아직 맞지 않는다.** 이번 변경은 push 트리거 제거이며 수동 배포 경로를 수정·실행·검증한 작업이 아니다. 수동 실행 전 별도 검토가 필요하다.

## toss-review 재노출 확인 방법 — 실제 재배포는 하지 않음

심사 자료의 보관 위치는 `docs/archive/toss-review/`이며 삭제 전 공개 서버 사본은 `server-copy/`에 있다. SCP는 로컬에서 없어진 원격 파일을 자동 삭제하지 않으므로 오래된 서버 소스가 남아 있으면 `deploy-hub.sh`가 다시 공개할 수 있다.

소스 제거 뒤 재배포 없이 확인하는 방법:

1. `/opt/ch2_Macro/deploy/hub/toss-review/`와 `/var/www/ch2data-hub/toss-review/`가 없는지 확인한다.
2. `deploy-hub.sh`가 위 hub 소스만 rsync하며 toss-review를 별도로 생성하는 단계가 없는지 확인한다.
3. 필요하면 아래 **dry-run만** 실행해 toss-review 추가가 계획되지 않는지 확인한다. 이 명령은 파일을 복사·삭제하지 않는다.

   ```bash
   rsync -ani --delete --exclude board --exclude admin /opt/ch2_Macro/deploy/hub/ /var/www/ch2data-hub/
   ```

4. 승인된 실제 재배포가 향후 있다면 그 후 `/toss-review/` 및 보존 manifest의 개별 URL이 404인지 다시 확인한다. 소스 부재·스크립트 검토·dry-run은 실제 재배포 검증과 구분한다.

이번 정리에서는 배포 스크립트 실행, 빌드, 서비스 재시작, nginx reload를 하지 않는다.
