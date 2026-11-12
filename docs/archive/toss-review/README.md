# 토스 심사 자료 보관

2026-11-12 `wip/ai-revision-20261109`의 PPT 2개와 스크린샷 13개를 보관했다. 웹 제공 루트 `deploy/hub/`에서 분리했다. 기존 main의 같은 경로 파일은 이 위치로 옮기고, WIP에서 갱신된 자료(08_identity 포함)를 사용한다. 과거 버전은 Git 이력에 남는다.

재생성: `python deploy/scripts/build_toss_payment_path_ppt_manual.py` 또는 자동 캡처 스크립트 `build_toss_payment_path_ppt.py`. 두 스크립트의 출력 경로도 이 폴더로 변경했다.

운영 HTML 네 파일은 nginx의 실제 루트 `/var/www/ch2data-hub`를 읽어 가져왔으며 HTTPS 응답과도 바이트가 같다. 배포·nginx reload·서비스 restart는 수행하지 않았다. 파일별 SHA-256은 `production-comparison-20261112.json`에 기록했다.
