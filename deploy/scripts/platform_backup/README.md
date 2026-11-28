# 플랫폼 DB 매일 백업 (PAY-003-A)

회원 DB와 서버 설정 묶음을 암호화해 서울 버킷의 새 폴더에 둔다. 이 스크립트는 보관 세트를 지우지 않는다. 성공한 뒤에 후보 이름만 로그에 남긴다.

실행은 `ubuntu`가 한다. cron 등록, 서버 배치, 첫 수동 실행은 이 폴더에 포함되지 않는다. crontab의 `MAILTO`도 바꾸지 않는다.

## 파일

| 파일 | 내용 |
| --- | --- |
| `platform_backup.sh` | 백업 스크립트 |
| `platform_backup.conf` | 버킷 이름, 지문, 경로. 비밀 없음 |
| `expected_tables.txt` | 스키마를 포함한 표 이름. 표가 바뀌면 이 파일만 고친다 |
| `local_test.sh` | 로컬 시험. 운영 서버와 운영 키는 쓰지 않는다 |
| `local_db.py` | 시험용 빈 데이터베이스를 localhost에만 만든다 |

설정 묶음은 `backend/.env`와 현재 사용자의 crontab 텍스트뿐이다. 허용 이름은 스크립트 상단의 `CONFIG_BUNDLE_ENV`와 `CONFIG_BUNDLE_CRON`이다.

하트비트 주소는 `HEARTBEAT` 파일에 둔다. 그 파일은 저장소에 없다. 없거나 권한이 600이 아니면 백업 성공 기록은 남기고 핑만 생략하거나 실패로 적는다. 수동 실행은 핑을 보내지 않는다.

평문은 `WORK_PARENT` 안의 이번 실행 디렉터리에만 둔다. 운영 설정은 이 경로가 tmpfs일 때만 진행한다. 업로드 전에 평문을 지운다.

## 로컬 시험

Git bash에서 실행한다. `PAY003_TEST_ENV`는 localhost의 `DATABASE_URL_PLATFORM`이 있는 파일이어야 한다.

```bash
PAY003_TEST_ENV=/path/to/local.env bash deploy/scripts/platform_backup/local_test.sh
```

시험이 끝나면 가짜 데이터베이스, 시험용 gpg 키, 임시 폴더를 지운다. Git bash에는 `flock`이 없으므로 로컬 동시 실행 시험만 Perl 잠금을 쓴다. 그 변수는 로컬 폴더 흉내(`PAY003_SINK=dir`)에서만 동작한다. 운영 경로의 잠금은 `flock`이다.
