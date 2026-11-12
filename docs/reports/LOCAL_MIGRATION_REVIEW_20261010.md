# 새 컴퓨터 이전 후 Macro 로컬 검토 결과

검토일: 2026-10-10 (한국 시간). 담당: Codex.

## 작업 분담과 결론

Cursor는 대장 DB·전국 슬림 적재를 담당하고, Codex는 기준월·토지 기능·실행 환경·월간 경로를 검토했다. 대장 계획문, 기준일 목록 JSON, `pipeline/parcel_master` 코드와 대장 DB·원본은 이번 작업에서 수정하지 않았다. 거래 원장 재적재·복원·마트 재생성·배포·커밋·push도 실행하지 않았다. HTTP 조회 과정에서 앱의 일반 분석 캐시는 생성될 수 있다.

복원된 토지 데이터로 로컬 개발을 이어갈 수 있다. 기준월 설정을 9월 집계와 맞췄고, 토지 HTTP 기능 검증 35개·프론트 빌드·Python 의존성 검사·월간 실행기 사전점검이 통과했다. 이 결과는 대표 지역 검증이며 전체 DB의 이전 컴퓨터 대비 동일성 인증은 아니다.

## 1. 기준월 확인과 수정

- 읽기 전용 SQL로 거래 원장의 2026년 최대 계약일 `2026-09-30`을 확인했다.
- `land_basic_stats_v2`의 9월 스냅샷에 3·5·7년 × category/group 여섯 조합이 모두 있다. 7월 집계도 남아 있다.
- 복대동 5년 기본 요청은 수정 전 7월 125건이었다. 9월 명시 요청은 120건이었다. 기간 시작일도 2021-08-01에서 2021-10-01로 달라지므로, 건수 감소를 거래 누락으로 판단하지 않는다.
- `backend/.env`, `pipeline/.env`의 `STATS_V2_DEFAULT_AS_OF_MONTH`만 `2026-07-01`에서 `2026-09-01`로 바꿨다. 그 밖의 비밀값은 변경하지 않았다.
- 로컬 API를 재시작했다. 기본 응답은 이제 `as_of_month=2026-09-01`, `period_end=2026-09-30`, `stats_reference_date=2026-10-01`이다. UI의 기존 포맷터는 이를 “2026년 9월 말 기준”으로 표시한다.
- 이번 수정은 로컬 설정이다. 운영 VPS의 설정은 확인하거나 변경하지 않았다. 다음 월갱신 때도 집계 완료 후 기준월을 맞추는 기존 절차가 필요하다.

## 2. 토지 검증

실행기: `scripts/local/check-land.py`. 요약 근거: `docs/reports/LOCAL_MIGRATION_LAND_SMOKE_20261010.json`.

최종 결과: **35 통과, 0 실패**. Vite 프록시 `http://127.0.0.1:5173/api`를 통과해 검증했다.

- 청주 복대동·사창동의 3·5·7년, 지목·지목군 통계.
- 5년 복수 지역 합계: 120 + 111 = 231건.
- 필터 분석: 2022~2026년 114건, 면적 100~500㎡ 적용 시 45건.
- 선택 매트릭스 셀과 거래 목록 전체 건수 58건 일치. 첫 페이지 ID 중복 없음, 계약일이 요청 기간 안에 있음.
- 롤링 추세·히스토그램·장기 연간 추세·상위 지역 통계 응답.
- 지도 설정·경계 응답: 경계 피처 80개. 복대동 읍면동 단위 이웃 8개, graph_ready=true.
- 기본 기준월과 적재 최신 기준월 일치.

토지 `npm.cmd run build`도 통과했다. 기존 대용량 JS chunk 경고는 남아 있으며 실행 실패는 아니다. 브라우저 자동화 도구가 초기화 오류로 연결되지 않아, 클릭 동작·화면 배치·지도 타일의 실제 렌더링은 자동 시각 검증하지 못했다. 이전 컴퓨터의 동일 화면과 수치 비교도 수행하지 않았다. 지도 경계 API 성공을 화면의 모든 지도 기능 검증으로 확대하지 않는다.

## 3. 실행 환경

- 기존 Python 3.14.4 가상환경을 유지했다. 재생성하지 않았다.
- backend에 requirements의 누락 항목 Shapely 2.2.0 설치, 실제 import 확인.
- pipeline에 requirements의 누락 항목 PyYAML 6.0.3 설치, 실제 import 확인.
- 두 가상환경의 `python -m pip check`: `No broken requirements found`.
- backend·pipeline의 CMD `activate.bat`에 남은 `C:\ch2`를 현재 `D:\ch2`로 고쳤다. 실행 중인 대장 프로세스를 중단하지 않았다.
- `pyvenv.cfg`의 생성 당시 executable/command 기록은 남겼다. base Python `C:\Python314`는 존재하며, 실제 로컬 API와 패키지 import가 동작하므로 이 역사적 기록만 보고 재생성할 필요는 없다.
- Node.js v24.21.0 LTS와 npm 11.19.0을 공식 배포처에서 받아 SHA-256 검증 후 `D:\tools\node-v24.21.0-win-x64`에 설치했다.
- ZIP SHA-256: `158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541`.
- 프로젝트의 package.json·package-lock.json·node_modules는 재설치하거나 업데이트하지 않았다. 시스템/사용자 전역 PATH도 바꾸지 않았다.
- `scripts/local/use-env.ps1`을 dot-source하면 해당 PowerShell 세션에서 새 Node/npm과 backend Python을 사용할 수 있다. 패키지 작업은 `python -m pip`를 사용한다.

## 4. 경로와 월간 작업

- 월간 SSOT는 `docs/MONTHLY_UPDATE_CHECKLIST.md`의 CSV 러너 3종이다. xlsx 러너는 복구·레거시다.
- CSV 러너는 저장소 상대 경로를 사용한다. 이전 `C:\startcoding\GUKTO`는 별도 레거시 경로/옵션에 남아 있으며, 현재 CSV 경로 실행에 필요한 기본 경로가 아니다. 실제 원본 위치를 모른 채 일괄 치환하지 않았다.
- `scripts/monthly/verify_monthly_checklist_ready.py`: PASS. 필수 경로·3/5/7년·캐시 정리·보강 opt-in 설정을 검사했다. 실제 월간 갱신이나 데이터 품질 검증 배치는 실행하지 않았다.
- 일반 월간 덤프 `dump_db_for_promote.py`의 PostgreSQL 18 실행 파일은 현재 컴퓨터에 존재한다. 이미 수정 중이던 `dump_land_for_promote.py`는 추가 수정하지 않았다.
- 옛 `deploy/scripts/dump_built_stats_local.ps1`은 PostgreSQL 실행 파일 자동 탐색·저장소 기준 backups·사용자 OutDir 존중으로 수정했다. `-DryRun`을 추가했다.
- 기본 경로와 사용자 지정 경로 dry-run을 확인했다. PostgreSQL 18 및 D:의 backups가 선택되며, dry-run은 폴더·덤프를 만들지 않는다. 실제 덤프·복원은 실행하지 않았다.

## 5. 다시 실행하는 방법

어느 폴더에서든 PowerShell에서:

```powershell
pwsh -File D:\ch2\ch2_Macro\scripts\local\start-land.ps1
```

API 8000과 토지 5173을 숨김 프로세스로 시작하며 이미 응답하는 서버는 재사용한다. 로그는 `logs/local-land/`에 둔다. 외부 브라우저를 열지 않으려면 `-NoBrowser`를 붙인다.

개발 터미널 환경만 준비하려면:

```powershell
. D:\ch2\ch2_Macro\scripts\local\use-env.ps1
```

프론트 빌드:

```powershell
Set-Location D:\ch2\ch2_Macro\frontend
npm.cmd run build
```

HTTP 검증 재실행:

```powershell
Set-Location D:\ch2\ch2_Macro
backend\.venv\Scripts\python.exe -B scripts/local/check-land.py --as-of 2026-09-01
```

## 6. 남은 사항

- 사용자가 브라우저를 새로고침해 9월 말 기준 표시와 실제 클릭·지도 타일 렌더링을 확인하면 된다. 자동 시각 검증의 한계는 위에 명시했다.
- 과거 컴퓨터와 파일 해시·전체 DB 건수의 일치, 백업 복구 재연은 별도 검증이다.
- Cursor가 진행 중인 전국 대장 구축은 이번 검토와 독립적으로 계속할 수 있다.
- `ch2_platform`, `parcel_master`, `macro_ts_stats` 복원/구축은 필요 기능별 별도 작업이다. 이번에 새로 만들지 않았다.
- 기존 워킹트리의 다른 수정과 이번 변경을 구분해 검토·커밋해야 한다. 이번 작업으로 커밋·push는 하지 않았다.
