# V2 Step 3 소규모 검증 보고 (잠정)

> 실행일: 로컬 DB 기준으로 `build_stats_v2.py` + 검증 스크립트 수행.  
> 주의: **v1 운영 테이블·파이프라인은 변경하지 않음** (`land_basic_stats`만 참조 조회).

---

## 1. 수행 내용

| 단계 | 결과 |
|------|------|
| `db/007_land_basic_stats_v2.sql` 적용 | 성공 (`land_basic_stats_v2` 생성) |
| 소규모 빌드 | `python build_stats_v2.py --as-of 2024-04-01 --windows 3,5 --region 4311311300` (청주시 일대 법정동 코드 예시) |
| UPSERT 재실행 | 동일 인자 + 다른 `--batch-id` 로 2회차 실행 → **중복 그레인 0건** 유지 |
| 검증 스크립트 | `pipeline/verify_stats_v2_sample.py` |

---

## 2. 설계 문서 대비 검증

| 검증 항목 | 결과 |
|-----------|------|
| `as_of_month=2024-04-01` 저장 | 정상 (월 1일) |
| `window_years=3` 구간 | `period_start=2021-05-01`, `period_end=2024-04-30` ✅ (§4 예시와 동일 패턴) |
| `window_years=5` 구간 | `period_start=2019-05-01`, `period_end=2024-04-30` ✅ |
| 행 수 (해당 동·창) | 3년 창 조합 48행, 5년 창 조합 60행 (용도×지목×ALL 그리드) |
| ALL×ALL `count` vs 원장 | 3년: 원장 77 = 저장 77 / 5년: 원장 214 = 저장 214 ✅ |
| `contract_date IS NULL` | 집계 SQL에서 제외 (설계와 동일) |
| UPSERT | 동일 키 중복 없음, 재실행 후에도 건수 동일 |

---

## 3. v1 대비 차이 (비교 검증)

동일 법정동 `4311311300` 기준 **v1 `land_basic_stats` ALL×ALL** 일부:

- `year_from=2022, year_to=2025`, `count=147`
- `year_from=2021, year_to=2025`, `count=331`

v2 **5년 롤링** (`2019-05-01`~`2024-04-30`) ALL×ALL `count=214` 등으로 **숫자가 v1과 다름** → 정상.

**원인 요약**

1. **시간 축**: v1은 **계약연도** 범위(`year_from`~`year_to`), v2는 **계약일** 날짜 구간.  
2. **창 정의**: v1은 “원장 MAX 연도 기준 최근 N개 **연도**”, v2는 기준월 말일까지의 **롤링 N×12개월**.  
3. **포함 범위**: 연도만 자르면 연초·연말이 경계에서 v2와 어긋날 수 있음.  
4. **NULL `contract_date`**: v2는 제외; v1은 `contract_year`로 잡혀 포함될 수 있어 추가 차이 가능.

→ **값이 맞다고 보려면 동일 구간·동일 필터로 원장을 한 번 더 세어 교차검증**하면 됨(이번 검증에서 ALL×ALL 건수 일치 확인).

---

## 4. 성능 (아주 러프)

- **본 테스트**: 단일 `beopjungri`, 창 2개, 약 **1~2초대** (로컬·데이터량에 따라 변동).
- **전국 단위 추정**:  
  - 장점: 원장은 **긴 창(최대 5년)** 기준 **1회 조회** 후 창별로 메모리 슬라이스.  
  - 부담: 창마다 법정동 루프 + 조합 수만큼 `compute_stats` 호출 → **지역 수·거래 밀도에 비례해 선형~초선형 증가**.  
  - 거칠게 **수 분 ~ 수십 분 이상** 여지 있음(실측 필요). 메모리는 **최대 창 구간 원장 DF 크기**에 좌우.

---

## 5. 운영 리스크 (요약)

| 리스크 | 완화 |
|--------|------|
| v2 테이블만 추가해도 디스크 사용 증가 | 창·지역 단계적 적재, 보관 정책(as_of 보존 기간) |
| 전국 배치 장시간·메모리 | 청크(시군구별) 배치, 인덱스 `contract_date` 점검 |
| v1/v2 수치 혼동 | UI에 **“v2 기준월 + 날짜 구간”** 고정 표기 |
| `contract_date` NULL 비율 | 정제 파이프라인에서 비율 모니터링 |

---

## 6. 발견 이슈 / 후속 수정 제안

- **인코딩**: Windows 콘솔에서 `build_stats_v2.py` 로그 한글이 깨질 수 있음(기능에는 무관). UTF-8 콘솔 또는 영문 로그 옵션 검토.
- **검증 스크립트**: 지역·`as_of` 가 하드코딩 → argparse 추가하면 재사용성 좋음.
- **전국 실행 전**: `contract_date` 인덱스 존재 여부·`EXPLAIN` 으로 조회 구간 스캔 비용 확인 권장.

---

## 7. 첨부·재실행 명령

```powershell
# DDL (최초 1회)
cd c:\ch2\ch2_Macro\pipeline
.\.venv\Scripts\python.exe -c "from db_utils import get_engine, execute_sql_file; execute_sql_file(get_engine(), r'c:\ch2\ch2_Macro\db\007_land_basic_stats_v2.sql')"

# 소규모 빌드
.\.venv\Scripts\python.exe build_stats_v2.py --as-of 2024-04-01 --windows 3,5 --region 4311311300

# 검증
.\.venv\Scripts\python.exe verify_stats_v2_sample.py
```
