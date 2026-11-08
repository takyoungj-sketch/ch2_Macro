# collective 범위 운영 배포 결과 — 2026-11-09

제품 소스 기준 main: **`6c6b35d811038dfbdb99ca9ad05db8e0d60f47cd`**.

집합 코드 전송·프런트 빌드·백엔드 재시작을 완료했다. **자동 검증 전체 성공 또는 브라우저 수동 검증 완료 상태는 아니다.** 자동 검증의 마지막 비로그인 복합 회귀는 정상 로그인 제한인 401로 중단됐고, 브라우저는 컴퓨터 사용 도구의 URL 검증 제한으로 확인하지 못했다. 이를 서버 데이터·정적 산출물·별도 API 검증과 구분해 아래에 기록한다.

## 배포 전 확인

1. 실제 작업 위치는 `D:\ch2\ch2_Macro\.release-worktree-20261108`, 브랜치는 `main`, `git status --porcelain`은 비어 있었다. 추가 미커밋 보고서는 없었다.
2. `git diff --stat 6f8ed2b main -- backend frontend-collective shared pipeline`은 14파일, 580줄 추가·186줄 삭제였다. 앱 실행 코드 변경은 `backend/app/collective`와 `frontend-collective/src` 안에만 있었다. `backend/app/ai` 등 다른 앱 실행 코드는 변경되지 않았다.
3. 범위 밖 `pipeline/apply_kb_complex_fill.py`와 `backend/tests`는 운영 복사 대상이 아니라는 운영자 예외 승인을 받았다. KB 스크립트·CSV는 수정하거나 실행하지 않았다.
4. `fcbd9af`와 `a7295c3`은 새 DB 테이블·컬럼·뷰를 만들 필요가 없다. 운영에서 READ ONLY로 기존 `collective_transactions`, `collective_building_annual_stats`, `collective_building_attributes`의 필요한 컬럼을 확인했으며 누락은 0개였다. DB 스키마·데이터 변경은 하지 않았다.
5. 직전 전체 백엔드 기준선은 1,123 통과·12 실패·수집 오류 1·건너뜀 3이다. 이번 배포를 위해 기존 실패를 숨기거나 제품 코드를 추가 변경하지 않았다.

## 4번: main push

- `git fetch origin main`으로 확인 후 fast-forward 가능한 상태임을 검사했다.
- `git push origin main`: 기존 `6c62404` → `6c6b35d` 성공.
- 아래 배포 스크립트 안의 재차 push도 `Everything up-to-date`였다.
- 이 배포 결과 문서의 후속 docs 전용 커밋은 별도로 push한다. 문서 커밋이 추가돼도 배포 제품 소스 기준과 서버 `DEPLOYED_COMMIT`은 위 `6c6b35d`다.

## 5번: 서버 백업

백업 파일:

```text
/opt/ch2_release_backups/20261108-155913-collective/code-and-static.tar.gz
```

- 폴더 시각은 서버 UTC 기준이며 한국 시각으로 2026-11-09 00:59:13이다.
- 요청한 `backend/app`, `frontend-collective/dist`를 포함한다. 복구 일관성을 위해 `frontend-collective/src`와 기존 `DEPLOYED_COMMIT`도 함께 보존했다.
- 크기: **6,472,461 bytes**.
- 권한: **600**.
- SHA256: `62a61421d733d0f6d101f4a3d443d56c6351986afeca33e752baecad7ee35502`.
- DB 백업은 만들지 않았다. 이번 승인은 앱 코드 배포이며 DB 변경이 없었다.

## 6번: 지정 스크립트 실행

정확히 다음 경로·옵션으로 실행했다. 스크립트는 수정하지 않았다.

```powershell
& 'D:\ch2\ch2_Macro\.release-worktree-20261108\deploy\scripts\deploy-from-windows.ps1' -Scope collective -SkipCommit
```

- collective 범위의 백엔드·공유 모듈·집합 프런트를 전송했다.
- `pipeline/apply_kb_complex_fill.py`, CSV, `backend/tests`는 전송하지 않았다.
- VPS에서 `tsc && vite build` 성공: 319개 모듈.
- 생성 JS: `/collective/assets/index-Bxgj-ECG.js`.
- 생성 CSS: `/collective/assets/index-DC8wnu7Y.css`.
- `ch2-macro-backend` 재시작 성공, `/health` 정상.
- 기존 번들 크기·Browserslist 데이터 경고는 빌드를 막지 않았다.

자동 검증 결과:

- health 정상.
- 토지 가경동 검색 1건 정상.
- 주거 집합 및 비주거 집합 메타 조회 정상.
- 마지막 복합 회귀 요청은 **HTTP 401, `로그인이 필요합니다.`**였다. 이 요청은 로그인 쿠키 없이 실행되므로 기존 접근 제한에 걸린다. 배포 스크립트는 `VPS smoke verify failed`, 종료 코드 1로 끝났다. 자동 검증이 전부 통과했다고 처리하지 않았다.
- 빌드·재시작은 그 이전에 완료됐으며, 별도 검사에서 실제 회귀 계산과 접근 제한이 정상임을 확인했다. 권한을 우회하도록 제품 코드를 바꾸지 않았다.

## 7번: 배포 해시 기록

`/opt/ch2_Macro/DEPLOYED_COMMIT`:

```text
6c6b35d811038dfbdb99ca9ad05db8e0d60f47cd
```

실제 변경된 제품 소스 8개의 줄바꿈 정규화 SHA256을 운영과 main에서 비교해 모두 일치함을 확인했다.

## 8번: 추가 검증과 한계

### 분양권 비교 목록

- 운영의 실제 `presale_catalog` 라우트 함수를 READ ONLY 세션으로 호출해 DTO 직렬화까지 확인했다.
- 대상: **가로수마을호반베르디움**.
- 원 단지 법정동: **가경동**.
- 분양권 비교 목록: **9개**, 전부 `dong == source_dong`, `same_dong == true`.
- 실제 브라우저에서 장기추세 탭을 클릭한 검증은 완료하지 못했다.

### KB 속성·출처

- 운영에는 앞선 읽기 전용 확인대로 KB 시공사·주차 값이 이미 있다. ‘아직 운영에 없을 수 있음’이라는 가정 대신 실제 KB 시공사 플래그가 있는 단지 1곳을 조회했다.
- 시공사 원문과 주차대수가 운영 테이블 값과 응답에서 일치했다.
- 응답에 내부 `kb_internet_*` 플래그가 노출되지 않음을 확인했다.
- 배포 소스와 JS에 `AttributeSourceHelp`, `속성 출처` 도움말 및 일반 `시공사` 열 표시가 포함돼 있음을 확인했다.
- **실제 화면에서 물음표를 클릭해 여는 동작이나 시각적 배치는 미검증**이다. 서버 응답·정적 코드 확인을 브라우저 검증으로 간주하지 않았다.

### 토지·복합 및 공통 공개 기능

- 토지 지역 검색, 5년 기본통계·매트릭스 롤링 5구간 정상.
- 주거·비주거 집합 5년 기본통계·롤링 정상.
- 주거 면적형 롤링 3유형, 비주거 면적형 롤링 4유형 정상.
- 7년 조회와 유료 분석의 비로그인 제한 유지.
- 복합 회귀를 운영 DB의 READ ONLY 연결로 직접 계산해 가경동 초점, 표본 **67건** 정상 확인.
- 토지·복합 기존 dist의 HTML과 참조 JS/CSS 파일이 존재함을 확인했다. collective 배포는 이 두 앱을 빌드하지 않았다.
- 외부 `/land/`, `/built/`, `/collective/residential/`는 기존 사이트 비밀번호 보호에 따라 HTTP 401을 반환한다. 이를 실제 화면 표시 성공으로 기록하지 않았다.
- 백엔드 정상 가동, 최종 검사 시 최근 10분 서비스 로그의 Traceback 0건.

### 브라우저 확인을 완료하지 못한 이유

Windows Chrome을 선택하는 과정에서 컴퓨터 사용 도구가 현재 브라우저 URL을 정책 적용에 충분한 확신으로 확인할 수 없다며 해당 턴의 UI 제어를 중단했다. 이후 UI 조작은 하지 않았다. 내장 브라우저의 운영 탭도 비밀번호 인증 제한 상태였다. 따라서 요청한 화면 수동 확인은 운영자 브라우저에서 별도로 확인해야 한다.

## 9번: 필요 시 복구 방법

현재 확인된 빌드·데이터·계산 오류가 없어 롤백은 실행하지 않았다. 필요하면 다음과 같이 **서버에서** 5번 백업을 복원한다:

```bash
sudo systemctl stop ch2-macro-backend
sudo tar -xzf /opt/ch2_release_backups/20261108-155913-collective/code-and-static.tar.gz -C /opt/ch2_Macro
sudo systemctl start ch2-macro-backend
curl -fsS http://127.0.0.1:8000/health
cat /opt/ch2_Macro/DEPLOYED_COMMIT
```

백업에 기존 배포 마커·집합 소스·정적 결과가 함께 있어 같이 복구된다. DB는 이번에 바뀌지 않았으므로 DB 복원은 하지 않는다. 복구 후 API·자산 파일·브라우저 새로고침 검증을 다시 수행한다. 이 명령은 보고용이며 실행하지 않았다.

## 단계별 원본 기록

Git 제외 `logs/collective-deploy-20261109/`:

- `schema-check.log`: DB 구조 사전 확인.
- `backup.log`: 백업 경로·크기·권한·SHA256.
- `deploy.log`: 지정 스크립트의 실제 출력과 자동 검증 중단.
- `deployed-commit.log`, `source-hashes.log`: 배포 해시 및 8개 제품 파일 일치.
- `manual-data-checks.log`: 동일 법정동 목록·KB 응답·배포 JS·페이지 응답.
- `cross-app-checks.log`: 공개 기능·접근제어·복합 계산·정적 파일·서비스 확인.

KB 보강 스크립트·CSV 수정/실행, 운영 DB DDL·UPDATE, pipeline 배포는 수행하지 않았다.
