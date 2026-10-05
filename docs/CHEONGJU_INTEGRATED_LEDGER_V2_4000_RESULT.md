# 청주 통합 대장 v2 — 4,000 PK 공급 체계

2026-10-05. 합의한 네 단계 중 **1단계 식별 규칙 v2.2와 2단계 4,000 PK 통합 공급·복구를 구현하고 검증했다.** 이어 [청주 전체 확대와 제품 공급 첫 비교](CHEONGJU_INTEGRATED_LEDGER_V2_CITY_RESULT.md)까지 진행했다. 운영 DB·기존 원장·제품 보강·회귀는 변경하지 않았다.

## 하나로 묶은 공급 경로

`data/research/cheongju_ledger/integrated_ledger_v2_4000.sqlite`에 건축 원문 선택 필드, 기존 가공 건물 속성, 주소 관측, 토지특성, 별도 공시지가 관측, 출처·해시·판본 레지스트리, 공개 배치와 current/last-seen을 함께 저장한다. 이전 v1·v2 DB와 고정 gzip 입력은 모두 그대로 보존했다.

`source`는 종류별 원천 manifest를 내용 해시로 식별하고, `release_source`는 어느 건축·토지·가공 입력을 함께 공개했는지 고정한다. 판본 월과 공개 순번은 별개다. 동일 배치의 입력 변경은 거절하며, 같은 원천 월의 정정은 별도의 배치 ID·공개 순번으로 보존할 수 있다. 구·신 PK 대응은 자동 적용하지 않는다.

건축 raw와 가공 속성은 별개 버전이다. 원문 면적 0을 기존 가공 경로가 결측으로 처리한 차이는 원문을 되살려 유효 면적으로 채우지 않고 `source_zero_processed_missing` 품질 상태로 함께 전달한다. 건축 전체 76/77열을 모두 복제한 것이 아니라 기존 검증 원문 필드와 원본 참조를 보존한 공급 체계다.

토지특성 내용 버전에서 가격을 분리했다. 가격만 달라지면 토지 속성 내용 버전을 불필요하게 복제하지 않는다. 기존에 확보한 27열 DBF payload는 그대로 저장하며, 나머지 캐시 필지 관측은 원본 ZIP 인벤토리·캐시 해시와 원문 19열로 추적한다. 모든 필지의 DBF 전체를 새로 스캔했다고 표시하지 않는다.

## 식별 규칙과 실제 영향

새 규칙은 `cheongju-source-identity-v2.2`다. 기존 `building_source_staging_v2.py`의 v2.1과 파일은 수정하지 않았다.

- 코드 0은 일반 대지, 코드 1은 산으로 구분한다. 법정동·본번·부번은 ASCII 숫자·자릿수·지역 일치를 검사한다. 빈 부번을 0으로 추정하지 않는다.
- 본번 0은 `noncanonical_zero_main_lot`으로 보류한다.
- 코드 2는 의미가 확인된 블록이며 `block_without_canonical_pnu`로 보존한다. 정식 지번으로 변환하지 않는다.
- 미상 구분·잘못된 코드·긴 지번·유니코드 숫자는 별도 식별 보류다. 이는 원천 주소 형식 판정이며 실재 필지·거래 소속 인증이 아니다.

원문 관측 **11,696개**는 모두 보존했다. 기존 대비 변화는 **67개 관측·34개 고유 PK**다. 본번 0의 44개는 주소 연결을 보류하고, 코드 2의 23개는 기존 PNU 보류를 유지하면서 블록 의미를 명시했다.

본번 0의 44개는 기존 공통 입력에서도 가격·토지특성이 미관측이었다. 이번 표본에서 기존 양수 가격을 제거한 변화는 없다. 이 영향 대조는 고정 입력 범위이며 운영 제품의 피해 여부를 조사한 결과는 아니다.

## 실제 적재와 소비 결과

건축 관측은 2024-09 **3,850개**, 2025-07 **3,933개**, 2026-07 **3,913개**다. 정식 주소는 각각 **3,818·3,916·3,895개**이며 합계 **11,629개**다. 원문 버전 7,986개, 건물 속성 버전 4,119개, 토지특성 버전 5,028개, 토지·가격 관측 각각 10,867개를 보존했다.

최신 공개 배치의 건물 소비 입력은 **4,000개**다. 3,913개는 해당 배치에서 관측됐고 **87개는 last-seen만 존재**한다. 87개를 현재 관측으로 표시하지 않으며 최신 토지·가격을 자동 연결하지 않는다.

가격 상태는 양수·연도 확인 **3,688개**, 최신 토지/가격 미관측 **199개**, 식별 보류 **18개**, 결측/비양수 **8개**, 건물 최신 미관측 **87개**다. 건물 기준 입력 수이며 고유 가격 필지 수나 회귀 표본 수가 아니다.

DB 용량은 **37,801,984바이트(약 37.8MB)**다. 재실행·입력 해시·롤백·복구·소비 출력 검사를 포함한 로컬 러너 실행은 약 27초였다. 신규 최초 적재 비용이나 청주 전체 성능으로 일반화하지 않는다.

## 소비 계약 고정

[기계 판독 계약](LEDGER_SOURCE_CONSUMER_CONTRACT_V2_2.json)에 각 값의 **원천 / 기준시점 / 신뢰상태 / 마지막 관측 / 사용 허용**을 고정했다. 실제 `consumer()` 출력은 각 값에 이 다섯 항목을 함께 반환한다.

`published_release`는 로컬 원천 공급 배치를 뜻한다. 운영 제품 사용 승인이나 객체 소속 인증이 아니다. 원문 조회와 형식이 유효한 후보 연구는 구분해서 허용하고, 새 제품 보강·수량 합산·회귀 채택은 모두 기본 false다. 기존 Macro의 승인된 결과를 해제한다는 뜻이 아니라 이번 공급 입력에 새 사용 권한을 부여하지 않는다는 뜻이다.

`selected_source_snapshot`과 `last_seen_source_snapshot`, `observed_in_selected_release`를 분리한다. 최신 토지 원천에 값이 없으면 과거 가격으로 채우지 않으며, 독립 필지 관측의 마지막 배치는 metadata로만 남긴다. 원천 기준일·입수일을 모르면 null이고 파일 월을 법적 효력일로 복사하지 않는다.

## 재현·공개 배치 복구·내보내기

```powershell
pipeline\.venv\Scripts\python.exe pipeline/parcel_master/run_cheongju_integrated_ledger_v2.py

pipeline\.venv\Scripts\python.exe pipeline/parcel_master/ledger_release_cli.py `
  --db data/research/cheongju_ledger/integrated_ledger_v2_4000.sqlite

pipeline\.venv\Scripts\python.exe pipeline/parcel_master/ledger_release_cli.py `
  --db data/research/cheongju_ledger/integrated_ledger_v2_4000.sqlite `
  --restore cheongju-4000-2024-09-identity-2.2

pipeline\.venv\Scripts\python.exe pipeline/parcel_master/ledger_release_cli.py `
  --db data/research/cheongju_ledger/integrated_ledger_v2_4000.sqlite `
  --restore cheongju-4000-2026-07-identity-2.2 `
  --export data/research/cheongju_ledger/ledger_supply_export.json.gz
```

일반 확인·내보내기는 읽기 전용이다. 복구만 기존 통합 연구 DB의 공개 포인터를 변경한다. CLI는 연구 폴더 밖의 DB와 통합 스키마가 없는 이전 v1·v2 DB를 거절한다. 공개 포인터를 과거로 돌려도 원문·속성·가격 관측은 지우지 않는다. 새 배치를 추가하려면 최신 배치로 먼저 복구해야 한다.

## 검증과 다음 단계

관련 테스트 **139개** 통과. 실제 자료의 세 배치 멱등 재실행, 출처 적재·토지/가격·건물·공개 직후의 네 실패 지점 롤백, 최초 배치 복구, 최신 배치의 전체 테이블·소비 결과 정확 복구, 원본 입력 해시 유지, 외래키·무결성, 본번 0의 정식 주소 차단을 확인했다.

[실측 집계](lab/cheongju_integrated_ledger_v2_4000.json)에 조건·행수·해시·검증 결과를 보존했다. 식별자가 있는 영향 목록과 4,000개 소비 입력은 연구 폴더 gzip에만 저장한다. 이 SQLite와 대용량 원천은 커밋하지 않는다.

후속 [청주 전체 실행](CHEONGJU_INTEGRATED_LEDGER_V2_CITY_RESULT.md)에서 동일 구조의 지역 전체 고정 판본 적재·용량·반복·누락·복구를 측정하고 기존 이름 키의 병행 공급을 생성했다. 실제 새 월 증분 갱신과 숫자 속성·복합 입력·회귀 결과의 병행 비교는 남아 있다. 회귀 모형 채택·추가 원천 탐색·운영 전환은 이 기술적 마일스톤과 분리한다.
