# 대장 원천 판본 접수·게시·복구 절차

2026-10-05. 통합 대장에 별도 로컬 운영 경로를 추가했다. 전체 스냅샷을 후보 DB로 적재하고 영향 결과를 확인한 뒤 원천 공개 포인터를 전환한다. 이전 판본은 보존하며 복구는 포인터만 되돌린다. 기존 4,000 PK·청주 전체 DB와 제품 DB는 수정하지 않았다.

## 실제 검증 결과

기존 통합 4,000 PK DB에서 보존 원문과 정규화 속성·토지특성을 추출해 실제 과거 판본 세 개를 순서대로 접수했다. 원본 ZIP·DBF 재파싱이나 2026-07 이후 새 자료 갱신은 아니다.

- 2024-09: 건물 관측 3,850개, 필지 관측 3,607개.
- 2025-07: 건물 3,933개, 필지 3,626개. 직전 대비 건물 신규 107개·미관측 24개.
- 2026-07: 건물 3,913개, 필지 3,634개. 직전 대비 신규 43개·미관측 63개. 누적 last_seen 건물 87개는 최신 관측으로 승계하지 않는다.

첫 실행 약 31초, 반복 검증·이전/최신 복구 약 13초였다. 운영 API 지연 시간이나 청주 전체 처리 속도가 아니다. 첫 실행의 23개 검사를 모두 통과했다. 반복 실행은 이미 게시된 후보의 적재 실패 주입을 생략하며 첫 실행 증거를 `execution_records`에 보존한다.

적재 sources/traits/buildings/published 네 단계 실패, 공개 포인터 전환 실패, 복구 포인터 전환 실패에서 활성 판본이 유지됐다. 이전·최신 복구 후 모든 건물 소비 출력의 정렬된 SHA-256이 각각 원래 결과와 일치했다. 원본/공개 DB 해시, SQLite 무결성·외래키를 확인했다. 관련 테스트 161개가 통과했다.

상세 증거: [운영 재연 결과](lab/cheongju_ledger_operations_rehearsal.json), [제품 전환 조건](lab/cheongju_product_transition_gate.json). 재연 위치는 `data/research/cheongju_ledger/operations_rehearsal_v1`, 최종 활성 판본은 `ops-4000-2026-07`이다. 반복 복구에 따라 registry revision은 증가한다.

## 접수 계약과 공개 단위

`ledger-normalized-full-snapshot-v1`은 `package.json`, `buildings.json.gz`, `traits.json.gz`로 구성한다. 규칙·PK namespace·소비 계약·범위 해시·전체 관측 수·파일/내용 해시·증거 종류를 선언한다. 중복 JSON 키, 경로 이탈, 해시/개수 불일치, 부분 증분 입력을 거절한다. 같은 관측 범위와 규칙에서 기준월이 증가하는 전체 스냅샷만 추가한다.

`export-historical`은 검증된 DB의 과거 판본을 내보내는 재연 도구다. 실제 새 원천 생산자는 원본 스키마·해시·PK 공간을 확인하고 동일 범위의 정규화 전체 스냅샷을 만들어야 한다. 과거 패키지의 날짜나 증거 종류만 바꿔 새 갱신을 인증할 수 없다. 신규 원본 추출기의 계약 연결은 아직 수행하지 않았다.

후보 적재는 활성 DB를 복제한 별도 `candidates/<batch>/ledger.sqlite` 안에서 실행한다. `impact.json`에 관측·누락·변경·식별/가격 상태·last_seen 영향이 기록된다. `stage.json`은 입력·후보·영향 해시와 기준 포인터/revision을 묶는다. 후보 내부 current와 registry 활성 공개 판본을 구별한다.

공개 시 영향 SHA-256과 예상 revision을 명시한다. 해시는 검토한 산출물 지정 수단이며 전자 서명이나 사용자 승인 대체물이 아니다. registry의 한 트랜잭션에서 판본 등록·활성/최신 포인터·revision·이벤트를 함께 변경한다. 다른 게시가 먼저 끝나거나 후보/입력이 바뀌면 차단한다. 파일 불변성은 해시로 검사하며 OS 읽기 전용 속성을 설정하지 않는다.

## 명령 실행

저장소 루트에서 새로운 재연용 `operations_local` 경로를 사용하는 예시다. 운영 경로는 연구 디렉터리의 직계 하위 `operations_*`로 제한한다. `stage --package` 상대 경로는 운영 경로 기준이다.

```powershell
pipeline\.venv\Scripts\python.exe pipeline/parcel_master/ledger_operations_cli.py --root data/research/cheongju_ledger/operations_local export-historical --source data/research/cheongju_ledger/integrated_ledger_v2_4000.sqlite --release cheongju-4000-2024-09-identity-2.2 --batch-id local-4000-2024-09
pipeline\.venv\Scripts\python.exe pipeline/parcel_master/ledger_operations_cli.py --root data/research/cheongju_ledger/operations_local stage --package inbox/local-4000-2024-09/package.json
pipeline\.venv\Scripts\python.exe pipeline/parcel_master/ledger_operations_cli.py --root data/research/cheongju_ledger/operations_local status
```

영향 결과의 누락·보류·변경을 확인한 뒤 stage에 기록된 해시와 예상 revision을 사용한다. 아래 자리표시자는 실제 값으로 바꾼다.

```powershell
pipeline\.venv\Scripts\python.exe pipeline/parcel_master/ledger_operations_cli.py --root data/research/cheongju_ledger/operations_local publish --batch-id local-4000-2024-09 --impact-sha256 <impact_sha256> --expected-revision <expected_revision>
pipeline\.venv\Scripts\python.exe pipeline/parcel_master/ledger_operations_cli.py --root data/research/cheongju_ledger/operations_local restore --batch-id <게시된_판본_ID> --expected-revision <status의_revision>
```

게시 전 실패는 기존 활성 포인터를 유지한다. 게시 후 복구는 알려진 판본 DB 해시를 확인한 뒤 포인터만 변경한다. 최신 판본·이력은 삭제하지 않는다. 과거 판본으로 복구된 동안은 새 적재를 차단하므로 추가 적재 전에 최신으로 복구한다. 현재 활성 판본의 동일 게시 재실행은 변경 없이 종료한다.

접수 중단으로 일부 파일이 남으면 파일 존재만으로 완료로 간주하지 않는다. 내용을 조사하고 별도 batch ID로 접수하거나 보존 후보의 검증 절차를 이용한다. 해시 오류를 무시하거나 강제 게시하는 옵션은 없다. SQLite·정규화 원문 등 연구 대용량 산출물은 Git에 넣지 않는다.

## 제품 전환과 다음 작업

원천 게시 후에도 새 제품 보강·수량 합산·회귀 권한은 false다. 기존 공급·마트·실제 SQL/ASGI 검증의 코드/산출물 해시는 확인했지만 제품 전환은 다음 네 조건으로 보류된다.

1. 목적·값 범위를 정한 소비 계약의 새 제품 사용 허용.
2. 실제 다음 원천 자료의 접수·갱신 검증.
3. TCP·프록시·브라우저 경로 검증.
4. 선택 원천 공개 판본에 결합된 제품 공급 인계 증거.

수량 합산·새 회귀 모형 채택은 제한된 보강 공급 전환의 필수 조건으로 두지 않는다. 각각 별도 검증 트랙이다. 전환 판정 성공도 운영 반영 자동 실행을 뜻하지 않는다.

다음 구현은 선택 원천 판본·소비 계약·기존 제품 키 결합·출력 해시를 묶는 공급 어댑터와 병행 산출물 인계다. 이어 같은 운영 경로를 청주 전체에 적용해 공간·시간·누락·복구 비용을 측정한다. 실제 새 원천 확보와 브라우저/프록시 확인은 해당 증거가 필요한 시점에 수행한다.

후보마다 전체 SQLite 복제본을 보존하므로 공간이 판본 수에 따라 증가한다. 기존 청주 전체 실험 성능은 새 운영 래퍼 실측으로 대신할 수 없다. 이번 완료 범위는 4,000 PK 과거 자료의 원천 접수·게시·복구이며 실제 다음 월 갱신·청주 전체 운영 래퍼·제품 운영 전환은 남아 있다.
