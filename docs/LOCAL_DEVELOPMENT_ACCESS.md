# 로컬 개발용 제품 접근

복합 실행: `powershell -File scripts/local/start-built.ps1 -NoBrowser`

이 실행기는 API 프로세스에만 `CH2_LOCAL_DEV_ACCESS=1`을 전달합니다. `.env`나 운영 배포 설정은 변경하지 않습니다. 이미 일반 모드로 실행 중인 API가 있으면 자동 종료하지 않고 재시작 안내를 표시합니다.

제품 구독 게이트 생략 조건은 명시적인 설정, API_TOKEN 미설정, loopback 클라이언트, HTTP 로컬 Host입니다. 외부 Origin과 프록시 전달 헤더가 있는 요청에는 적용하지 않습니다. 관리자·로그인·결제 API의 기존 권한은 그대로 유지합니다.

프런트는 Vite 개발 모드의 로컬 주소에서 서버가 로컬 개발 접근을 확인해 준 경우에만 제품 화면을 엽니다. 운영 빌드에서는 이 분기를 사용하지 않습니다. 운영 서버에는 `CH2_LOCAL_DEV_ACCESS`를 설정하지 마세요.
