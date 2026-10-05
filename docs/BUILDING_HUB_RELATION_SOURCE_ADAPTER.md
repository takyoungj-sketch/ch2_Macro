# 건축HUB 명시적 관계 원천 검증기

2026-10-05. `pipeline/parcel_master/building_hub_relation_source.py`는 기본개요의 상위 대장 PK와 부속지번의 명시적 필지를 읽는 로컬 도구다. 현재 실자료를 수집한 결과가 아니라 공식 스키마에 맞춘 입력 검증 구현이다. 거래 소속·대표 주소·보강 승계는 확정하지 않는다.

## 확인한 공식 공급 경로

[국토교통부 건축HUB 건축물대장정보 서비스](https://www.data.go.kr/data/15134735/openapi.do)의 API 스키마에서 다음을 확인했다.

- `getBrBasisOulnInfo`: `mgmBldrgstPk`, `mgmUpBldrgstPk`, `bldgId`. 기본개요의 명시적 상위 관계를 제공한다.
- `getBrAtchJibunInfo`: 대장 PK와 `atchSigunguCd`, `atchBjdongCd`, `atchPlatGbCd`, `atchBun`, `atchJi` 등의 부속지번 필드를 제공한다. 원래 대장 주소와 부속 필지 주소를 혼용하지 않는다.
- API 안내에는 건축HUB 이관에 따른 PK 변경과 변환 안내가 있다. 기존 TXT 관리 PK와 새 API PK를 문자열 일치만으로 결합하지 않는다. 이번 도구의 PK 공간은 `building_hub_api_1613000`으로 제한하며 구 PK 대응표 적용 기능은 없다.

[건축HUB 기본개요](https://www.hub.go.kr/portal/opn/tyb/idx-bdrg.do)와 [부속지번 메타정보](https://www.hub.go.kr/portal/opn/tyb/idx-bdrg-anx.do)에서 대지구분 `2`는 **블록**임을 확인했다. 의미가 확인돼도 정식 지번과 동일하지 않으므로 PNU를 생성하지 않는다. 기존 v2의 `unknown_land_type` 판정은 당시 실험 결과로 보존하고 이 도구에서 별도 `block_without_canonical_pnu` 상태를 사용한다.

## 입력과 실행

입력 JSON은 아래 형식의 묶음들을 담은 배열이다. 두 endpoint 각각 주소 조회별 묶음을 만든다. `pages`에는 원래 응답을 페이지 순서와 관계없이 모두 넣는다. `query`는 인증키·페이지 번호를 제외한 공개 주소 필터다. 시군구·법정동은 각 5자리, 본번·부번은 각 4자리 문자열로 보존한다.

```json
{
  "endpoint": "getBrBasisOulnInfo",
  "query": {"sigunguCd": "43111", "bjdongCd": "12000"},
  "pages": [
    {"response": {"header": {"resultCode": "00"}, "body": {
      "pageNo": 1, "numOfRows": 100, "totalCount": 0, "items": ""
    }}}
  ]
}
```

위 예시는 응답 구조 설명용이며 청주 실자료나 관계 인증 결과가 아니다. 실자료는 `data/research/cheongju_ledger/` 아래 보관한다. 인증키가 든 요청 URL·헤더는 입력에 저장하지 않는다.

```powershell
pipeline\.venv\Scripts\python.exe pipeline/parcel_master/building_hub_relation_source.py `
  data/research/cheongju_ledger/hub_relation_input.json `
  --observed-at "2026-10-05T12:00:00+09:00" `
  --output data/research/cheongju_ledger/hub_relation_admission.json
```

`observed-at`은 실제 수집 배치의 관측 시각이다. 거래일·관계 유효 시작일이 아니다. 서로 다른 수집 시점의 응답을 한 배치로 섞지 않는다. 도구는 파일 작성 시각에서 실제 수집 시점을 추정하지 않는다.

## 검증 범위

응답 성공, 총건수·페이지 크기 일관성, 모든 페이지와 페이지별 건수, 조회 주소 범위, 한 조회 내 중복, 같은 PK의 충돌, 두 원천의 대장 주소 충돌, 부모 관계 순환을 검사한다. 소스 묶음·원본 행 해시와 원문을 보존한다. 부속필지의 누락·잘못된 숫자·미상 구분을 PNU로 채우지 않는다.

명시적 부모 PK의 대상이 같은 배치에 존재하면 `explicit_parent_resolved_in_batch`, 없으면 `explicit_parent_target_missing`이다. 부속지번은 대장 PK의 대상 존재와 부속 PNU 정규화 성공을 함께 확인한다. 이 상태들은 **수집 배치 안에서 원천의 관계를 해석한 결과**다. 실제 관계 유효기간, 거래 소속, 분석 객체 동일성, 예전 TXT PK 대응을 인증하는 상태가 아니다.

출력의 `membership_verified`, `production_apply`, `representative_selected`는 항상 false다. 현재 선택기는 이 출력으로 보류를 해제하거나 보강을 승계하지 않는다.

## 실자료 확보와 후속 순서

이 절은 **명시적 부모·부속필지 관계를 추가 확보하는 경로**다. API 신청·추가 다운로드는 공통 대장 통합 전체의 선행 조건이 아니다. [청주 건축·토지 통합 검토](CHEONGJU_BUILDING_PARCEL_INTEGRATION_REVIEW.md)와 [일원화 로드맵](LEDGER_UNIFICATION_ROADMAP.md)에 따라 기존 `parcel_master` 건축물 판본과 확보한 토지특성·가격 이력의 정규화·갱신·복구 통합은 계속 진행한다. 직접 관계 원천이 필요한 소속 판정만 미검증으로 남긴다.

현재 저장소의 `raw`·`참고` 파일명을 재확인했으며 기본개요·부속지번 파일은 찾지 못했다. 다만 [과거 원자료 조사](DATA_ENRICHMENT_RAW_ADDITION_PLAN.md) §1·§2.3에는 `mart_djy_01` 기본개요 보유 기록이 있다. 과거 보유 기록과 현재 경로 확인 결과를 구분하며, 저장소 밖 보관본까지 없다고 단정하지 않는다. 기존 기록의 보관 위치 확인을 추가 신청보다 먼저 한다.

프로세스와 루트·pipeline·backend `.env`에서 `MOLIT_API_KEY`가 설정돼 있지 않았다. 인증키 값은 출력하거나 문서에 저장하지 않았다. API 권한 유무를 서버에서 검증한 것은 아니다. 이 설정 확인은 로컬 대장 DB 통합의 중단 사유가 아니다.

1. 기존 보유 기록과 보관 위치를 확인한다. 명시적 관계 실험에 필요한 파일이 없을 때 공식 서비스의 조회 권한을 확보하거나 건축HUB 공개 파일을 내려받는다. 공개 파일은 해당 파일의 실제 열 명세에 맞춘 별도 변환기가 필요하다. 키는 대화에 전달하지 않는다.
2. 청주 검토 대상의 조회를 페이지 누락 없이 수집한다. 소스 관측 시각과 PK 공간을 보존한다.
3. 검증기를 실행하고 구 TXT↔HUB PK 변환 규칙·대응표를 별도로 확인한다. 서로 다른 판본을 임의 연결하지 않는다.
4. 객체 범위와 거래 소속의 독립 근거를 검증한 뒤 대표 주소 선택, 보강 승계, 키 전환 대응표를 구현한다.

실자료 입력이 없는 상태에서 관계 건수나 소속 인증 건수를 만들지 않았다. 기존 85개 키 병행 결과는 그대로 보류 상태다.

조회 목록은 `prepare_cheongju_hub_relation_queries.py`로 생성한다. 고정 입력 85개 키·177개 주소 후보에서 중복 주소를 합친 조회 범위 172개와 두 endpoint의 조회 항목 344개를 준비했다. 페이지 수나 실제 API 호출 횟수는 아니다. 비정규 주소 후보 4개는 PNU나 대지구분을 추정하지 않고 법정동 범위로 조회하도록 남겼다. 응답에서 부모 PK 대상이 부족하면 추가 조회가 필요하다.

목록 파일 `data/research/cheongju_ledger/hub_relation_query_manifest.json`은 실제 조회를 수행하지 않으며 기존 키 대응 참조를 보존한다. 이 목록의 `candidate_refs`는 수집 계획용이다. 검증기 입력에는 `endpoint`, `query`, `pages`만 전달한다.
