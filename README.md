# 토지 실거래 통계 웹서비스 MVP

감정평가사를 **1차 사용자**로 두되, 향후 **부동산 투자자·개발자 등**으로 사용자층을 넓힐 수 있도록 설계한 프로젝트입니다.  
선택 지역의 토지 실거래 가격 수준을 빠르게 판단할 수 있게, 기존 엑셀 분석표(용도지역 × 지목 통계)를 웹서비스로 옮깁니다.

## 사용자·경험 목표

- **주 사용자**: MVP·검증 단계에서는 감정평가사 중심으로 두고, 이후 투자·개발 등으로 확장한다.
- **속도**: 별도 수치 SLA는 두지 않으며, 사용자가 **답답하지 않을 정도**의 응답 체감을 목표로 한다.
- **데이터 신선도 SLA**: 매월 **1일~5일** 사이에 **직전 월 말까지의 거래**를 반영해 갱신한다. 화면 우상단의 **「YYYY년 M월 말 기준」** 이 갱신 일자를 의미한다. (자세한 결정 배경: [`docs/DECISIONS.md`](docs/DECISIONS.md) D-002)

## 생태계 (ch2data)

`ch2_Macro`는 **`ch2_FieldNote`**, **`ch2_Viewer`** 와 함께 **`ch2data.com`** 을 구성하는 서비스 중 하나이다.  
도메인은 같이 쓸 수 있으나 **제품·결제는 서비스별로 분리**한다. 포털·DNS·허브 배포: [`deploy/08-ch2data-portal.md`](deploy/08-ch2data-portal.md).

## 제품 롤아웃 전략

MVP·초기 검증 단계에서는 **전국 데이터를 한 번에 목표로 두지 않고**, 먼저 한정된 지역(예: 충청북도 등 시도 단위)에서 수집·집계·웹 서비스를 End-to-End로 완성하고 작동 여부를 검증한다.

스키마(`sido_code`, `beopjungri_code` 등)와 파이프라인 단계(`collect → clean → build_stats`)는 처음부터 **전국 규모를 수용할 수 있는 형태**로 유지한다. 지역 한정은 코드 분기가 아니라 **설정·환경 변수**(허용 시도 코드, 수집 대상 필터 등)로 표현해, 전국 확장 시 데이터량·스케줄·리소스 조정만으로 가능하게 한다.

> 수집 원천이 전국 단위로만 제공되는 경우, 원자료 적재는 전체를 받되 **집계·서비스 노출은 파일럿 지역으로만** 제한하는 방식으로 운영할 수 있다.

## 진행 계획 (합의)

다음 순서로 제품·데이터 작업을 진행한다. **큰 결정은 [`docs/DECISIONS.md`](docs/DECISIONS.md) 참조** (V1·V2 단일화, 폐기 일정, 신선도 SLA 등).

1. **충청북도 기준 유료 화면 완성**: 복수 법정동·연도/필터·동적 집계·용도지역×지목 매트릭스를 **충북만** 허용하여 End-to-End 검증·안정화한다. 지역 한정은 **설정·허용 시도 코드** 등으로 두고, DB 스키마와 파이프라인은 전국 규모를 수용할 수 있는 형태를 유지한다.
2. **전국 base DB**: 보유 원본(예: **2021~2025년** 전국 토지 거래 엑셀 등)으로 **단일 베이스 DB**를 구축·적재한다. 이후 서비스 노출 범위는 위 설정으로 단계적으로 넓힌다.
3. **운영 전제일·갱신 루틴**: 예컨대 **2026-01-01**을 현재 일자 전제로 두고, 그 시점에 맞춘 **수집 → 정제 → 사전집계** 업데이트를 정기 배치로 굳인다. 운영 단일 SOP: [`docs/V2_OPERATOR_CHECKLIST.md`](docs/V2_OPERATOR_CHECKLIST.md). **전국 원장 로컬 월 재생성**(반자동·재현 가능) 절차: [`docs/MONTHLY_UPDATE_SOP.md`](docs/MONTHLY_UPDATE_SOP.md).

아래 「데이터 수집 전략」에서 정한 Selenium(또는 Playwright)·API 보조·`collect → clean → build_stats` 흐름은 그대로 따른다.

## 데이터 수집 전략

국토부 실거래 관련 **공공데이터포털 OpenAPI에는 서비스키 단위 일일 트래픽(호출 한도)** 가 있으며, **시군구 코드 × 계약연월** 단위 호출에 **페이지네이션**까지 더해지면 전국·다년치 **전량을 API만으로** 받기 어렵거나 며칠에 나눠 호출·운영계정·증설 신청이 필요해지기 쉽다.

**합의된 방향**

- **대량 초기·전국 적재**: **Selenium**(또는 검증 후 **Playwright**) 기반으로 브라우저·파일 다운로드 등 **대량 수집을 중심**에 둔다. 기존 Selenium 자산을 정리·안정화하는 것이 MVP 속도에 유리하다.
- **API**: 호출 수가 적게 나가는 구간(증분 검증, 소량 보정, 특정 구간 보조 등)에 **보조**로 사용한다.
- **실행 로드맵(요약)**  
  1. Selenium 코드 정리 및 **전국 토지 초기 적재(예: 5개년)** 안정화  
  2. DB 구축·적재 프로세스 자동화  
  3. API를 활용한 갱신 보조  
  4. 필요 시 **Playwright** 로 전환 검토  

**현재 레포**

- `pipeline/collect.py`: **`api`**(REST XML), **`excel`**(국토부 원본/통합 xlsx) 모드를 지원한다. API만 사용할 때는 건수 상한·**page 루프** 등으로 누락이 없게 할 것.
- 원천 데이터는 **주기적으로 자체 DB에 적재**한 뒤, 서비스는 DB를 조회하는 패턴을 따른다.

수집 구현·약관 준수·실패 재시도·UI 변경 대응은 운영 정책에 맞게 별도 문서화할 수 있다.

## 구조

```
ch2_macro/
├── db/                  # DB 스키마 및 마이그레이션 SQL
├── pipeline/            # 수집·정제·사전집계 배치 파이프라인
├── backend/             # FastAPI 백엔드
├── frontend/            # React 프론트엔드
└── deploy/              # dev/test VPS (AWS Lightsail) 배포 가이드·템플릿
```

**dev/test VPS 이전:** [`deploy/README.md`](deploy/README.md) (Lightsail·PostgreSQL·Nginx·Promote 절차).

## 빠른 시작

### 1. DB 초기화

```bash
psql -U postgres -c "CREATE DATABASE land_stats;"
psql -U postgres -d land_stats -f db/001_init.sql
psql -U postgres -d land_stats -f db/002_indexes.sql
# 유료 필터 분석 속도 향상(선택): psql ... -f db/002_paid_analyze_index.sql
# 백엔드 venv에서 적용 스크립트: cd backend && .venv\\Scripts\\python scripts/run_paid_index.py
# 이미 예전 001만 적용한 DB라면: psql ... -f db/003_legacy_patch.sql
# 기존 DB에 표준편차 컬럼이 없다면: psql ... -f db/004_add_basic_stats_std.sql
# 도로조건 문자열 명칭 이전 반영 시: psql ... -f db/005_road_condition_labels.sql
# 대량 raw → clean 시 미처리 조회 속도: psql ... -f db/006_land_tx_raw_id_index.sql
```

### 2. 파이프라인 실행

```bash
cd pipeline
pip install -r requirements.txt
python collect.py          # 국토부 데이터 수집
python clean.py            # 정제 및 DB 적재
python build_stats.py      # 사전 집계 테이블 생성

# 한 번에 실행 (초기 5년 적재 후 정제·집계)
python run_pipeline.py --initial --years 5

# 매월 갱신: 최근 3개월 재수집(해제·정정 반영) → 정제 → 사전집계 전체 재계산
python run_pipeline.py --refresh --months 3
```

#### 전국 엑셀으로 base DB 초기 적재 (파일럿 DB에서 확장할 때)

1. **법정동 마스터(전국)**  
   행정안전부·공공데이터포털 등에서 법정동코드 전체 파일을 받은 뒤, `DATABASE_URL` 이 있는 환경에서:  
   `python seed_region_codes.py --file 법정동코드_전체.txt`  
   (`--sido` 를 생략하면 전 시도가 들어갑니다. 강원·전북 특별자치도 등은 파일에 쓰인 시도명과 `seed_region_codes.py` 의 `SIDO_CODE_MAP` 이 맞아야 합니다.)
2. **`pipeline` 쪽 DB 접속**  
   `pipeline/` 에서도 `DATABASE_URL` 을 읽습니다. `pipeline/.env` 에 백엔드와 동일한 URL을 두거나, 같은 셸에서 `set DATABASE_URL=...` 후 실행하세요.
3. **원본 엑셀 경로**  
   국토부 토지 거래 **원본 xlsx**(또는 통합 xlsx)만 `원본폴더/토지` 같은 **한 폴더**에 모읍니다 (하위 폴더는 검색하지 않습니다. 필요하면 평면으로 복사).
4. **한 번에 실행** (수집 후 `clean.py`·`build_stats.py` 자동):  

```bash
cd pipeline
python run_pipeline.py --excel-dir "절대/경로/원본폴더/토지" --excel-format auto
```

통합 xlsx만 있으면 `--excel-format merged`, 국토부 다운로드 원본만 있으면 보통 `auto` 또는 `raw` 입니다.

**시도별 폴더로만 넣을 때(예: `원본/토지_경기`)**  
`collect.py`는 지정한 폴더 **바로 아래**의 `.xlsx`만 읽습니다(하위 폴더 미검색). 해당 시도 엑셀만 두고 `--excel-dir`에 그 폴더 절대 경로를 주면 됩니다.

**`region_codes` 선행 적재(필수에 가깝게 권장)**  
`clean.py`는 `시군구` 주소 문자열을 `region_codes`로 조회해 `beopjungri_code`·`sido_code`·`sigungu_code`를 채웁니다. 적재할 시도가 테이블에 없으면 코드가 비어 들어갑니다. 시도 단위로만 확장할 때는 같은 법정동 마스터 파일로  
`python seed_region_codes.py --file ... --sido 경기도`  
처럼 넣거나, 처음부터 전국을 넣습니다(`--sido` 생략).

**같은 거래에 대해 정제를 다시 돌릴 때**  
`land_transactions`는 `transaction_hash` 기준 UPSERT입니다. `clean.py`는 충돌 시에도 **`beopjungri_code`, `sido_code`, `sigungu_code`를 갱신**하도록 되어 있어, `region_codes`를 나중에 채운 뒤 `python clean.py --reprocess-all`로 주소 매핑을 다시 반영할 수 있습니다(집계는 이어서 `build_stats.py`).

전량 갈아엎을 때는 적재 전에 `land_transactions_raw`, `land_transactions`, `land_basic_stats` 등 비우기(TRUNCATE)·백업 여부를 결정하세요(FK·캐시 테이블 순서 주의).

#### 법정동 연말 인구 CSV (`population_stats`)

행안부 형식 「지역별(법정동) 성별 연령별 주민등록 인구수_YYYYMMDD.csv」(헤더에 `법정동코드`, `계` 등)를 `data/population/` 등에 두고:

```bash
cd pipeline
# 충북(코드 접두 43)만 적재·교체 (기본)
python seed_population_csv.py --file ../data/population/지역별(법정동) 성별 연령별 주민등록 인구수_20221231.csv
# 경기도만 (법정동코드 접두 41)
python seed_population_csv.py --file ...csv --codes-prefix 41
# 충청남도만 (법정동코드 접두 44)
python seed_population_csv.py --file ...csv --codes-prefix 44
# 경상북도만 (법정동코드 접두 47)
python seed_population_csv.py --file ...csv --codes-prefix 47
# 검증만
python seed_population_csv.py --file ...csv --dry-run
# 해당 연도·월 전국 행 삭제 후 전량 재적재 (주의)
python seed_population_csv.py --file ...csv --all-sido
```

연도별 통계 표의 「연말 인구(명)」 행은 같은 DB의 `population_stats`(연말 월=`stats_month`)와 선택 법정동 코드를 맞춰 합산합니다. 적재 연도가 없는 해는 빈 칸입니다.  
**기본 `--codes-prefix`는 `43`(충북)** 이라 같은 CSV라도 경기·충남 등은 **`--codes-prefix 41`** / **`44`** 로 연도별로 한 번씩 더 적재해야 표에 나옵니다(또는 시도 무관하게 `--all-sido`).

### 파이프라인 설계 요약

| 단계 | 스크립트 | 출력 |
|------|-----------|------|
| 수집 | `collect.py` | `land_transactions_raw` (JSONB 원본 행) |
| 정제 | `clean.py` | `land_transactions` (`transaction_hash` 기준 UPSERT) |
| 사전집계 | `build_stats.py` | `land_basic_stats` (동/리 × 용도지역 × 지목) |

- **초기**: `--years 5` 로 전 기간(연·월 조합) 수집 후 적재.
- **정기**: `--months 3` 으로 최근 분기 재수집 후 같은 키로 UPSERT 해 해제·변경분을 반영한다.
- 노트북(`0.수집`, `7.토지 통합 정제`)의 로직은 각각 `collect.py`, `clean.py`의 매핑·정제 규칙으로 이관한다.

### 통계 산식·필터 확정

구현 상세는 `pipeline/constants.py`, `pipeline/stats.py`를 따르되, 아래는 **제품 스펙**이다. 코드와 다르면 README 우선으로 정합을 맞춘다.

- **단가 표시·집계 단위**: **만원/㎡** 로 통일한다.  
  산식: `거래금액(만원) / 계약면적(㎡)` 이며, `land_transactions.unit_price_per_sqm`에도 이 엑셀 단가를 저장한다.
- **정제 기준**: `참고/7.토지 통합 정제.ipynb`를 기준으로 해제거래 제외, 면적구분 생성, 용도지역·지목·도로조건 축약을 수행한다. 상세 기준은 `LAND_CLEANING.md`를 따른다.
- **해제 신고 처리**: 동일 물건에 정상 신고와 해제 신고가 함께 있어도 정상 신고는 보존한다. 정제 테이블은 신고 행 단위로 저장하고, 통계 집계에서 `is_cancelled = FALSE`, `is_valid = TRUE`만 사용한다.
- **신뢰구간**
  - **무료**: **95%** 신뢰구간 (Student `t`, `n≥2`일 때만 계산 등 세부는 구현과 동일하게 맞춘다).
  - **유료**: 사용자가 **신뢰구간 수준을 선택**할 수 있게 한다. 캐시 키 폭발을 막기 위해 90/95/99 등 **단계적 선택**을 권장한다.
- 분위수: 25/50/75%, 최소·최대
- 표본 충분: `n ≥ 15` (엑셀 강조 기준과 동일)
- 면적구분: 광소(<30㎡), 정상(30~3000㎡), 광대(≥3000㎡)

### 표 정렬·표시 우선순위

- 목표는 **거래 건수가 많은 용도지역·지목 조합이 먼저 보이게** 하는 것이다.
- 성능·구현 부담이 있으면 **동 단위·리 단위** 등에 따라 순서 규칙을 다르게 가져갈 수 있다.
- 기본 구현은 **건수 기준 내림차순**(예: 용도지역별 건수 → 그 안에서 지목별 건수)을 우선한다.

### 성능 전략 및 확장 기준 (PostgreSQL MVP)

**현재**

- 무료 API는 `land_basic_stats`만 조회한다 (원자료 스캔 없음). **복수 동·리 기본통계**(유료 화면 「기본 통계 보기」)는 같은 응답 형식으로 `POST /api/free/stats/bulk` 가 `land_transactions`를 한 번 재집계한다 (도로 미적용 매트릭스와 표시 차이는 구현 참고).
- 유료 「필터 분석」(이상치 제외 **미사용**)은 `WHERE` 에 맞는 행만 `WITH base AS MATERIALIZED (...)` 에 올린 뒤 전체합·법정별·매트릭스 집계를 한 라운드트립으로 돌린다. PostgreSQL percentile 정렬이 `work_mem` 에 민감해 `paid_analyze_work_mem_mb`(기본 192)·`SET LOCAL work_mem` 을 적용한다. 부분 인덱스는 `db/002_paid_analyze_index.sql`.
- **2단계 행ID 캐시 (`analysis_base_cache`)**: 「기본 통계 보기」(`/free/stats/...`, `/free/stats/bulk`) 가 선택 지역·연도 윈도우에서 유효 거래행 id 배열을 `analysis_base_cache` 에 적재하고 `analysis_base_key` 를 돌려준다. 이어지는 「필터 분석 실행」이 이 키를 함께 보내면 `paid/analyze` 는 region 재확장·`beopjungri_code` 재스캔 없이 `lt.id IN (SELECT unnest(row_ids) ...)` 만으로 출발해 추가 필터를 얹는다. 키가 없거나 만료된 경우 자동 fallback (legacy region_codes 경로) 으로 동작한다.
- 응답 캐시(`analysis_cache`) 로 같은 페이로드 재조회 비용도 줄인다. 통계 산출의 `NaN`(표본 1건일 때의 CI 등) 은 직렬화 전 `None` 으로 정규화해 `jsonb` 저장 실패를 막는다.
- 행정구역 코드 (`beopjungri_code` 등 `CHAR(N)`) 비교는 `btrim(cast(... AS text)) = ANY(:codes)` 로 통일해 패딩으로 인한 매칭 누락을 막는다.
- 필요 시 `land_transactions`를 `sido_code` 등으로 파티션하는 것을 우선 검토한다.

**ClickHouse·DuckDB 등 분리 검토 시점 (예시 기준)**

- 단일 복잡 유료 쿼리가 인덱스·캐시에도 불구하고 목표 응답시간을 반복적으로 초과할 때.
- 전국 단위 ad-hoc 집계·동시 사용자가 RDB CPU/IO 한계를 넘을 때.
- 보관 주기·컬럼이 늘어나 풀스캔 비용이 지속적으로 커질 때.

DuckDB는 로컬/분석용 부속 저장소, ClickHouse는 서비스용 컬럼형 집계 보조에 적합한 편이다.

### 3. 백엔드 실행

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env       # DB 접속 정보 입력
uvicorn app.main:app --reload
```

### 4. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

## 무료/유료 기능 구분 (제품 경계)

### 유료 웹 UI 흐름 (두 단계)

1. **기본 통계 보기**: 지역을 선택한 뒤 무료 패널과 같은 형식으로 요약 표시한다. 무료 탭에서는 법정단위가 1곳일 때만, 유료에서는 **복수 동·면 합산**이 가능하다 (`/api/free/stats/bulk`).
2. **필터 분석 실행**: 연도·도로·면적 등 추가 필터 후 `/api/paid/analyze` 로 용도×지목 매트릭스를 조회한다. 복수 지역일 때는 지역별 부분통계 표를 함께 볼 수 있다.

API·화면 설계 기준이다. 인증·과금 연동 전에는 엔드포인트가 모두 열려 있을 수 있으나, 기능 범위는 아래로 고정한다.

| 기능 | 무료 (`/api/free/...`) | 유료 (`/api/paid/...`) |
|------|------|------|
| 단일 동/리 기본 통계 (사전집계) | ✅ | 동일 데이터를 동적 집계로도 조회 가능 |
| 복수 동·리 선택 (합산 기본 통계) | ❌ (법정코드 정확히 1곳만) | ✅ (`/api/free/stats/bulk` — 유료 화면 「기본 통계 보기」) |
| 연도/기간 필터 | ❌ (무료는 아래「무료 사전집계 분석 기간 정책」 범위로 고정) | ✅ |
| 도로조건 필터 | ❌ | ✅ |
| 면적형 필터 (광소/정상/광대) | ❌ | ✅ |
| 지목/용도지역 선택 필터 | ❌ (매트릭스 전체 표시) | ✅ |
| 지분거래 제외 | ❌ (무료 집계에는 지분 포함) | ✅ |
| 이상치 제외 (IQR) | ❌ | ✅ |
| 신뢰구간 | 95% 고정 | 수준 선택 가능 |

### 무료 사전집계 분석 기간 정책

- **원칙**: 거래가 많은 **동(읍면동)** 단위는 **최근 3개년**, 표본이 상대적으로 적은 **법정리** 단위는 **최근 5개년**을 우선 고려한다.
- **통일 옵션**: 구현·속도·운영 부담이 크면 **동·리 모두 최근 4개년**으로 통일할 수 있다.
- 집계 테이블의 실제 기간·컷오프는 `build_stats.py` 및 환경 설정과 맞춘다.

- **무료** 데이터 소스: `land_basic_stats` 만. 필터: 해제 제외·`is_valid`·정상 단가, 기간은 위 정책에 따른 사전집계 범위.
- **유료** 데이터 소스: `land_transactions` + 요청 파라미터 필터 + 선택적 캐시.

## 통계 항목

- 거래건수 (n)
- 평균 단가 (**만원/㎡**)
- 무료: **95%** 신뢰구간 / 유료: **선택 신뢰구간**
- 최솟값, 25% 분위, 중위값, 75% 분위, 최댓값
- 거래건수 15건 이상 시 노란색 강조

## 향후 확장 (MVP 필수 아님)

- **장기 연도별 추세 (2010~)** : 유료 필터분석 매트릭스 모달·복수 지역 지역별 추세선 — [`docs/LONG_TERM_TREND_DESIGN.md`](docs/LONG_TERM_TREND_DESIGN.md) (D-013).
- **용도지역×지목별 연도별 평균 변화** 등 시계열·피벗형 화면: 제품적으로 중요하나 **MVP에 반드시 넣지 않아도 된다**.
- **행정구역 인구 데이터**: `population_stats` 스키마는 준비되어 있으나, **제공·연동은 추후** 검토한다.

## DB 구조 (PostgreSQL)

- `land_transactions_raw` : 정제 전/후 원자료 보존
- `land_transactions` : 분석용 정규화 테이블 (transaction_hash UNIQUE, ~9.6M건)
- `region_codes` : 시도·시군구·읍면동·법정리 코드/명칭 (SSOT = land_stats)
- `land_basic_stats_v2` : V2 무료·유료용 법정동/리 단위 사전집계 (as_of_month + window_years)
- `land_upper_stats_v2` : 상위 행정구역(시도·시군구·읍면동) 사전집계
- `land_annual_stats` : 장기 연도별 추세 집계
- `twin_neighbor_v8` : Twin v8 쌍둥이 지역 (충청권 현재, 전국 예정)
- `regional_profile` : Regional Profile 피처 벡터 (JSONB)
- `paid_analysis_logs` : 유료 분석 사용 기록
- `analysis_cache` : 유료 분석 응답 캐시 (요청 페이로드 해시 키 기반, 24h TTL)
- `analysis_base_cache` : 「기본 통계 보기」가 만든 후보 거래행 id 배열 캐시 (TTL 4h; 갱신 직후 TRUNCATE 필수)
- `population_stats` : 행정구역 인구 레이어 (행안부 CSV 기반)

> **상세 스키마**: [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md)

---

## 기술 문서 (docs/)

| 문서 | 내용 |
|------|------|
| [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) | 전체 시스템 아키텍처 (레이어·배포·API·파이프라인) |
| [`docs/DATA_FLOW.md`](docs/DATA_FLOW.md) | 데이터 흐름 (수집→정제→집계→API) |
| [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) | DB 테이블·컬럼·인덱스 상세 |
| [`docs/MONTHLY_UPDATE_PIPELINE.md`](docs/MONTHLY_UPDATE_PIPELINE.md) | 월간 갱신 단계별 가이드 및 실패 시나리오 |
| [`docs/DATA_INTEGRITY_CHECKLIST.md`](docs/DATA_INTEGRITY_CHECKLIST.md) | 무결성 검증 체크리스트 (Level 0~4) |
| [`docs/RISK_REGISTER.md`](docs/RISK_REGISTER.md) | 위험 요소 레지스터 (CRITICAL~LOW) |
| [`docs/ARCHITECTURE_REVIEW_REPORT.md`](docs/ARCHITECTURE_REVIEW_REPORT.md) | 아키텍처 비판적 검토 및 1년 확장 예상 문제 |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 설계 결정 이력 (D-001~D-024b) |
| [`docs/MONTHLY_UPDATE_SOP.md`](docs/MONTHLY_UPDATE_SOP.md) | 운영 SOP (상세 절차) |
| [`docs/TRANSACTION_HASH_DEDUPE.md`](docs/TRANSACTION_HASH_DEDUPE.md) | transaction_hash 중복제거·rehash 배경 |
| [`docs/TWIN_V8_DESIGN.md`](docs/TWIN_V8_DESIGN.md) | Twin v8 알고리즘 설계 |
| [`docs/REGIONAL_PROFILE_ARCHITECTURE.md`](docs/REGIONAL_PROFILE_ARCHITECTURE.md) | Regional Profile 5-Layer 아키텍처 |
