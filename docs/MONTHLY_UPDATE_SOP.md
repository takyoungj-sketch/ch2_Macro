# 월간 전국 토지 데이터 업데이트 SOP

> **목표:** 매월 초 **전국 토지** 원장·정제·V2 사전통계를 **재현 가능한 절차**로 갱신하고, 검증·승인 후 외부에 반영한다.  
> **전제:** 완전 무인·증분 갱신 최적화는 후순위. 우선 **단순성·재현성·검증·롤백**을 만족한다.  
> **기준 루트:** `C:\ch2\ch2_Macro` (다른 PC면 `--repo-root` 로 동일 구조를 맞춘다.)

---

## 1. 용어

| 용어 | 설명 |
|------|------|
| **cycle_id** | 월간 작업 번들 ID. **`YYYYMM`** (예: `202605` = 2026년 5월에 수행하는 이번 배치). |
| **수집 연월 범위** | 합의 예: `202605` 배치 시 **계약연월 `202505`~`202604`**(직전 12개월). 파일·국토부 UI 기준으로 조정 가능. |
| **`as_of_month` (V2)** | `build_stats_v2.py --as-of YYYY-MM-01` — 해당 **달 말일까지**가 통계 기간 끝으로 해석된다 (`build_stats_v2` 주석·`V2_STATS_DESIGN` 참고). |
| **기본 `--as-of` 매핑** | *수집 끝 연월이 `cycle`의 **직전 달**과 같다*고 가정할 때: `cycle_id=202605` → 마지막 월 `202604` → **`--as-of 2026-04-01`**. 자동화: `scripts/monthly/cycle_utils.stats_as_of_iso_from_cycle_id`. **실제 수집 끝 월이 다르면 `--v2-as-of`로 수동 지정.** |

> **토지 원장 재구축 중 (2026-06):** `land_stats_next` 는 재구축 배치로 `as_of_month=2026-06-01` 이 올라가 있을 수 있다. 6월 중순 **운영 정상값은 `2026-05-01`** 이다. **Promote·as_of 정상화는 `cycle_id=202607`(7월 초)에 `run_monthly_cycle` 로 일괄 처리** — 상세 [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) **§12**.  
> **D-026 지목군:** 기본=용도×지목 · 옵션=용도×지목군. Master 재적재 불필요; group mart는 **원장 단가 재집계**.  
> **월간 필수 후속:** 표준 `run_monthly_cycle`(category V2) **이후** §7.1「용도×지목군」을 반드시 수행한다.  
> SSOT: [`LAND_JIMOK_GROUP_DESIGN.md`](./LAND_JIMOK_GROUP_DESIGN.md) · [`DECISIONS.md`](./DECISIONS.md) D-026. Profile·Twin 연결은 후속.

---

## 2. 디렉터리 구조 (권장)

저장소 루트 기준:

```
C:\ch2\ch2_Macro\
  raw\토지\{cycle_id}\          # 시·도별 xlsx (하위 폴더 허용 — 평탄화 단계에서 처리)
  clean_snapshots\{cycle_id}\   # manifest, flat_in, land_tx_counts_after.json 등
  stats_snapshots\{cycle_id}\    # V2 요약 JSON (스크립트가 기록)
  logs\                          # 월간 실행 로그(선택)
  backups\                       # pg_dump 등
  scripts\monthly\               # 본 SOP 자동화 스크립트
  pipeline\                       # 기존 수집·정제·통계 파이프라인
  docs\                          # 본 문서
```

### 2.1 raw 예시

```
raw\토지\202605\
  서울.xlsx
  경기.xlsx
  충북.xlsx
  ...
```

- **ZIP/원본 다운로드 보존:** 디스크 여유가 있으면 `raw\토지\202605\_downloads\` 등에 두고 목록만 `raw_manifest.json`에 메모 가능. 레포에는 커밋하지 않음(`.gitignore`).

---

## 3. 로컬 DB vs staging/current (원칙)

본 레포 기본 패턴은 **`land_stats` 단일 PostgreSQL**에 적재하고, 버전 관리를 **통계 테이블의 `(as_of_month, window_years)`** 로 한다.

| 방식 | 설명 |
|------|------|
| **현실적 운영(권장, 단순)** | 로컬·서버 각각 같은 스키마. 갱신 전 **`pg_dump` 백업**으로 논리적 rollback. 통계 행은 `as_of_month`별로 공존. |
| **이중 DB (staging / prod)** | 로컬 `land_stats_staging` 으로 먼저 돌린 뒤 dump → prod 로칭복원. 초기에는 운영 부담만 커져 **후순위**. |

본 SOP 초안은 **단일 DB + 백업**을 표준으로 둔다.

---

## 4. 실행 흐름 (반자동)

1. 운영자: 국토부 등에서 **직전 12개월** 엑셀을 받아 `raw\토지\{cycle_id}\` 에 둔다 (하위 폴더 가능).
2. **Cursor / 운영자:** `CycleId`(예:`202605`) 지시 후 아래 명령 실행.
3. 스크립트: **평탄화 → `run_pipeline`(excel + V2 category, `--v2-as-of`) → 검증용 스냅샷 JSON**.
4. **에이전트/운영자:** **§7.1 용도×지목군** (V2 group + annual 당해 연도 both) — cycle에 미포함, **매월 필수**.
5. 운영자: **검증 체크리스트** 및 샘플 육안(category + group).
6. **OK** 후 **Promote** (§9) 로 외부 반영.

---

## 5. 수집 단계 (`raw`)

> **⚠ CSV Selenium 수집 치명적 주의:** 이전 다운로드 완료 전 rename·짧은 sleep(2초)은 **시도/연도 오염 CSV**를 만든다.  
> 반드시 `molit_csv_download_core` / `deploy/molit_csv_collector` **검증 포함 버전** 사용.  
> 상세: [`docs/MOLIT_CSV_COLLECTOR_WARNINGS.md`](MOLIT_CSV_COLLECTOR_WARNINGS.md)

- **실거래가 엑셀(토지 매매)** 는 국토교통부 페이지에서 브라우저로 받는 형태(**Selenium**)가 보통 안정적이다. 참고 레시피: `참고/0.수집.ipynb` 와 같은 흐름을 스크립트로 옮긴 것이 **`scripts/monthly/download_molit_land_xlsx.py`** 이다.  
  의존성: `py -m pip install "selenium>=4.15"` (Chrome 설치 필요, Selenium 4 가 드라이버를 관리한다).  
  예(2026년 5월 초 배치 가정 · **계약일 2025-05-01 ~ 2026-04-30** 전국):  
  `py scripts/monthly/download_molit_land_xlsx.py --cycle-id 202605`  
  검증만 할 때 한두 시도: `--limit-regions 1` 또는 `--regions "세종특별자치시"`  
  **시도당 `--start-date`~`--end-date` 구간을 한 번에 요청**(국토부 UI가 허용하는 범위에서 달력연도 분할 없음); 파일명에 구간 태그가 붙는다(`…_토지_매매_20250501_20260430.xlsx`).  
- **통합 · 정제(노트북 규격, 템플릿용)** 는 `docs/LAND_NOTEBOOK_EXCEL_PREP.md` 와  
  `py scripts/monthly/run_land_notebook_excel_prep.py --cycle-id …` 참고 (**DB 적재와 별도 디렉터리** 출력).
- **성공/실패 기록:** `clean_snapshots\{cycle_id}\raw_manifest.json` — `scripts/monthly/run_monthly_cycle.py` 가 `.xlsx` 목록과 개수 기록.

---

## 6. 통합·정제·DB 업데이트

### 6.1 하위폴더 탐색

- `pipeline/collect.py` 의 `--directory` 는 **직접 자식만** 스캔한다 (`resolve_excel_paths` → `root.iterdir()`).
- 따라서 깊게 두었으면 **`scripts/monthly/flatten_raw_xlsx.py`** 로 `clean_snapshots\{cycle_id}\flat_in\` 에 평탄화 후 파이프라인에 넘긴다.  
  **원스톱:** `run_monthly_cycle.py` 가 평탄화까지 수행한다( `--skip-flatten` 으로 생략 가능).

### 6.2 파이프라인

엑셀 기준 표준 실행(로컬, `pipeline` 디렉터리가 `DATABASE_URL` 을 읽음):

```powershell
cd C:\ch2\ch2_Macro
py scripts\monthly\run_monthly_cycle.py --cycle-id 202605
```

동작 요약:

1. `clean_snapshots\{cycle_id}\raw_manifest.json` 작성  
2. `flatten_raw_xlsx` → `clean_snapshots\{cycle_id}\flat_in\`  
3. `run_pipeline.py --excel-dir …\flat_in --excel-format auto --with-v2 --v2-windows 3,5 --v2-as-of <매핑>` **및 기본으로** `--with-upper-v2`(상위 행정 사전집계). 생략하려면 `run_monthly_cycle.py --skip-upper-v2`.  
4. `clean_snapshots\{cycle_id}\land_tx_counts_after.json` — 시도별 `land_transactions` 건수  
5. `stats_snapshots\{cycle_id}\land_basic_stats_v2_summary.json` — 해당 `as_of` V2 행수 요약  

> **통합 엑셀(`전국통합.xlsx`)** 은 선택. 필요 시 별도 수작업·추후 `COPY`/pandas export 스크립트 추가. 현재 스냅샷은 **JSON 요약 중심**.

### 6.3 `run_pipeline.py` 수정 사항

- **`--v2-as-of YYYY-MM-DD`** 를 지정하면 `build_stats_v2` 에 그대로 전달된다(환경 변수보다 우선).

---

## 7. 사전통계 생성 (V2 · 용도×지목)

- `--with-v2` 로 `build_stats_v2.py` 실행. **`--as-of` 는 반드시 이번 데이터에 맞게 고정**(CLI 또는 `--v2-as-of`).
- **상위 행정(시도·시군구·읍면동·city 버킷)** 은 `run_monthly_cycle.py` 가 **기본으로** `run_pipeline.py --with-upper-v2` 를 넣어 `build_upper_stats_v2.py` 까지 실행한다. **끄려면** `--skip-upper-v2`.
- 수동만 필요할 때: `python pipeline/build_upper_stats_v2.py --as-of … --windows 3,5` (전국; 시도 한정은 `--sido-code`).
- 기본 `--col-axis` 는 **`category`(용도×지목)**. 지목군은 **§7.1** 에서 별도 수행(cycle 스크립트에 아직 미통합).

---

## 7.1 용도×지목군 (D-026) — 월간 필수 · 에이전트 실행 가이드

> **목적:** 다른 에이전트/운영자가 매월 초 category V2 갱신 뒤 **용도×지목군 mart + 장기추세 annual(group)** 을 재현 가능하게 돌린다.  
> **전제:** §6 `run_monthly_cycle`(또는 동등한 원장·category V2) 가 이번 `as_of` 로 **성공**한 뒤 실행.  
> **금지:** 지목(category) mart 평균을 합쳐 지목군 평균을 만들지 말 것 — 반드시 **원장 단가 재집계** (`--col-axis group`).  
> **UI:** 통계 화면 기본은 항상 **용도×지목**. **용도×지목군**은 매트릭스 버튼을 눌렀을 때만. 지역을 바꾸면 자동으로 용도×지목으로 복귀.

### 7.1.0 운영 사고·주의 (2026-07-26)

배포판에서 「용도×지목군」조회 시  
`matrix_mode=group … V2 집계가 없습니다`(404) 가 난 사례가 있다.

| 원인 | 내용 |
|------|------|
| **부분 적재** | `land_basic_stats_v2` `col_axis=group` 이 일부 시도(예: 41·43)만 있고 **전국 미완료** |
| **upper 누락** | `land_upper_stats_v2` 에 `col_axis=group` **0행** → 시군구·읍면동 지목군 표 불가 |
| **월간 자동화 공백** | `run_monthly_cycle` 은 category만 수행 → **§7.1 group을 빼먹으면 재발** |

**조치(전국):** category와 **동일 as_of·windows** 로

1. `build_stats_v2.py --col-axis group`  
2. `build_upper_stats_v2.py --col-axis group`  

**VPS 실행 시:** `pipeline/.env` 의 `DATABASE_URL`(postgres 로컬 비번)과 `backend/.env`(ch2app)가 다를 수 있다.  
빌더는 **`backend/.env`를 source** 한 뒤 `backend/.venv` 파이썬으로 돌릴 것. (`STATS_V2_SIDO_CODE` 가 켜져 있으면 전국이 아니라 단일 시도만 돌므로 **unset**.)

검증은 “시도 샘플 몇 건”만 보지 말고, 아래처럼 **ALL×ALL 지역 수 category ≈ group** 을 맞출 것 (§7.1.4).

### 7.1.1 선행 DDL (최초 1회 · 스키마 확인)

로컬·VPS DB에 아래가 없으면 `pipeline/` 에서 적용:

| 파일 | 역할 |
|------|------|
| `db/037_land_jimok_group_map.sql` | 지목→지목군 맵 |
| `db/038_land_transactions_resolved_jimok_group.sql` | resolved VIEW + `jimok_group_*` |
| `db/040_land_stats_col_axis.sql` | V2 `col_axis` |
| `db/041_land_annual_col_axis.sql` | annual `col_axis` |

```powershell
cd C:\ch2\ch2_Macro\pipeline
python -c @"
from pathlib import Path
from sqlalchemy import text
from db_utils import get_engine
root = Path('..') / 'db'
for name in ('037_land_jimok_group_map.sql','038_land_transactions_resolved_jimok_group.sql','040_land_stats_col_axis.sql','041_land_annual_col_axis.sql'):
    p = root / name
    print('apply', p.name)
    with get_engine().begin() as c:
        c.execute(text(p.read_text(encoding='utf-8')))
print('ddl ok')
"@
```

매월: 맵/VIEW가 이미 있으면 **스킵**. `jimok_key` 매핑 변경 시에만 037 재적용 후 **영향 연도·as_of group 재빌드**.

### 7.1.2 V2 지목군 mart (전국 · 이번 as_of)

`AS_OF` = 이번 cycle의 `--v2-as-of` (예: `2026-06-01`).  
category 를 이번 cycle에서 이미 돌렸으면 **`group`만** (중복 category 재빌드 회피).

```powershell
cd C:\ch2\ch2_Macro\pipeline
$env:PYTHONUNBUFFERED="1"
# 기본통계 V2 — 용도×지목군
python -u build_stats_v2.py --as-of $AS_OF --windows 3,5 --col-axis group
# 상위행정 V2 — 용도×지목군
python -u build_upper_stats_v2.py --as-of $AS_OF --windows 3,5 --col-axis group
```

- category 와 group을 한 번에: `--col-axis both` (시간↑).  
- 예상 시간(참고): 전국 group V2 는 환경에 따라 **수십 분~1시간대** (과거 로컬 ~40분대 사례).  
- 로그 권장: `Tee-Object` 또는 `> logs\jimok_group_v2_{cycle}.log`.

### 7.1.3 장기추세 annual (증분 · category + group)

| 정책 | 내용 |
|------|------|
| **매월** | **당해 달력 연도만** UPSERT 재집계 (`--years YYYY`). 전 기간(2010~) `--full` 재빌드 **금지**(초기/복구·맵 대변경 시에만). |
| **1월 또는 직전 연도 보정 반영 시** | `--years (YYYY-1)-YYYY` 로 직전+당해 연도. |
| **grain** | `(calendar_year, …, col_axis)` UPSERT — 지정 연도·축만 교체. |
| **축** | 월간은 `--col-axis both` (지목 + 지목군). group만 보강이면 `--col-axis group`. |

```powershell
cd C:\ch2\ch2_Macro\pipeline
$YEAR = (Get-Date).Year   # 또는 수집 계약이 걸친 달력 연도
python -u build_annual_stats.py --years $YEAR --full --col-axis both --with-upper
```

- `--full` = **전국 시도** (연도 범위는 `--years`로 제한).  
- 예상 시간(참고): 당해 연도 both+upper 전국은 **수 십분 이내**가 보통. 2010~전 기간 group은 **~2시간대**(과거 로컬 ~1.9h).

### 7.1.4 검증 (지목군)

```powershell
cd C:\ch2\ch2_Macro\pipeline
# as_of·window 는 verify 스크립트 상수 또는 인자 — 이번 AS_OF 와 맞출 것
python verify_jimok_group_integrity.py
```

수동/에이전트 체크:

- [ ] `land_basic_stats_v2` / `land_upper_stats_v2` 에 `col_axis='group'` 이고 `as_of_month=$AS_OF` 행 존재
- [ ] **전국성:** `window_years=5`·`zone_type=ALL`·`land_category=ALL` 기준  
      `COUNT(DISTINCT beopjungri_code)` (basic) 가 **category와 group이 같거나 거의 같음**  
      (부분 시도만 돌리면 UI에서 대부분 지역이 404)
- [ ] upper: `region_level='sigungu'` ALL×ALL group 행이 **전국 시군구 규모**로 존재
- [ ] `land_annual_stats` / `land_annual_upper_stats` 에 `col_axis='group'` 이고 `calendar_year=$YEAR` 행 존재
- [ ] API: free/upper `matrix_mode=group` · 필터분석 토글 · 장기추세 탭(지목군 셀) 404 아님
- [ ] UI: 기본=용도×지목 · 버튼으로만 지목군 · **지역 변경 시 용도×지목으로 복귀**
- [ ] integrity: zone×group `count` ≈ 소속 지목 category `count` 합 (스크립트 mismatch=0)

### 7.1.5 에이전트 체크리스트 (복붙용)

```
[ ] cycle_id / AS_OF 확인 (category V2 완료 후)
[ ] DDL 037·038·040·041 존재 확인 (없으면 적용)
[ ] build_stats_v2 --col-axis group --as-of AS_OF --windows 3,5   # 전국 · STATS_V2_SIDO_CODE unset
[ ] build_upper_stats_v2 --col-axis group --as-of AS_OF --windows 3,5
[ ] (VPS) DATABASE_URL = backend/.env (ch2app) 사용
[ ] basic ALL 지역수 category≈group · upper sigungu group 존재
[ ] build_annual_stats --years YEAR --full --col-axis both --with-upper
[ ] verify_jimok_group_integrity (또는 동등 count 합 검증)
[ ] UI/API matrix_mode=group 스모크 · 지역 변경 시 category 복귀 확인
[ ] (Promote 시) group mart·annual 이 dump/재실행에 포함되는지 확인
```

### 7.1.6 아직 자동화되지 않은 것

- `run_monthly_cycle.py` / `run_pipeline.py` 에 `--col-axis` · annual 단계 **미배선**.  
  → 매월 **본 절을 수동(또는 에이전트)으로 추가 실행**.  
- 통합 플래그 추가는 후속 이슈(J7 잔여).

---

## 8. 검증 (로컬, 최소)

### 8.1 자동/반자동

```powershell
cd C:\ch2\ch2_Macro\pipeline
py rehearse_v2_update.py --health-url http://127.0.0.1:8000/health
```

```powershell
py verify_monthly_integrity.py --as-of-month 2026-05-01
```

(`--as-of-month` 생략 시 `STATS_V2_DEFAULT_AS_OF_MONTH` 또는 DB `MAX(as_of_month)` 사용.  
`--base-url http://127.0.0.1:8000` 추가 시 API `total.count` ↔ DB 대조.  
배치 직후 golden count 갱신: `--update-golden`)

```powershell
py verify_v2_national_samples.py --base-url http://127.0.0.1:8000 --as-of-month 2026-04-01
```

(`--as-of-month` 는 **이번에 선택한 `--v2-as-of` 와 같은 달의 1일**)

- **전월 대비 거래량 휴리스틱:** 이전 배치에서 저장해 둔 `land_tx_counts_after.json` 을 복사해 두었다면  

  ```powershell
  py scripts\monthly\compare_count_snapshots.py --before clean_snapshots\202604\land_tx_counts_after.json --after clean_snapshots\202605\land_tx_counts_after.json
  ```

### 8.2 수동 체크리스트 (최소)

- [ ] **`verify_monthly_integrity.py`** exit 0 (Promote 게이트)  
- [ ] **거래량 급변** 시도 없음 (`compare_*` 또는 `--count-before`/`--after`)  
- [ ] **`raw_manifest`** 의 기대 행정구역 파일 수와 실제 제공 범위 일치  
- [ ] **평균 단가 급변** 이슈 — 대표 동 2~3곳 재조회 (프론트·API)  
- [ ] **`/health.latest_as_of_month`** 의 정책과 `--v2-as-of` 의도 일치 확인  
- [ ] **`land_transactions` 행폭증·급감** — 직전 월 배치 요약 파일과 비교  
- [ ] **§7.1 지목군** — `col_axis=group` V2·annual 당해 연도 존재 + integrity/스모크  

---

## 9. 승인 (Promote) 및 외부 서버 반영

### 9.1 반영 전 **필수: 백업**

```powershell
$env:PGPASSWORD="…"
pg_dump -h 호스트 -U 유저 -d land_stats -Fc -f C:\ch2\ch2_Macro\backups\land_stats_pre_promote_202605.dump
```

### 9.2 승격 방식 (택 1을 팀 규약으로 고정)

| 선택 | 절차 | 비고 |
|------|------|------|
| **안 A** | 검증된 DB dump를 서버로 restore | 프로덕션이 검증 상태와 바이트 동일하게 맞춰짐. 전송·복원 시간 큼. |
| **안 B** | 서버에 동일 월 원본 폴더·동일 명령(`run_monthly_cycle` 상당) 재실행 | 원본 파일 전송 필요. 재현성 좋음, 서버·로컬 환경 차이 시 편차 가능. |

**초기 권장:** 팀에 DB 운영 경험이 있으면 **A**, 동일 스크립트를 서버에도 두고 싶으면 **B**. **한 팀은 한 가지로 고정**해 Playbook을 줄인다.

### 9.4 코드 배포 ≠ DB Promote (2608 교훈)

**`deploy-from-windows.ps1` 은 backend·frontend 코드만 반영한다.** `land_stats` 원장·V2 mart 는 **별도 월간 cycle + Promote** 없이는 운영 DB에 7월(또는 이번 `as_of_month`)이 나타나지 않는다.

| 단계 | 무엇이 바뀌는가 | 2608(`cycle_id=202608`) |
|------|----------------|-------------------------|
| **① ingest** | `land_transactions` 에 **신규 계약연월** 거래 적재 | `raw/2608 업데이트/토지_202508_202607/*.csv` → `run_land_cycle_csv.py --cycle-id 202608` |
| **② mart** | `land_basic_stats_v2` 등 **`as_of_month=2026-07-01`** 행 생성 | cycle 스크립트 내 V2·§7.1 group·annual |
| **③ Promote** | 검증된 **`land_stats` DB** 를 VPS에 restore | 로컬 dump → VPS `promote_restore.sh` (§9.2 안 A) |
| **④ env** | `STATS_V2_DEFAULT_AS_OF_MONTH=2026-07-01` | Promote 직후 backend 재기동 |

**mart만 재계산(ingest 생략)하면** 원장에 7월 거래가 없을 때 화면에 7월이 **절대** 보이지 않는다.

**Promote dump 호환 (2026-08-09):**

- Windows PG18 **custom `-Fc` dump** → VPS 기본 `/usr/bin/pg_restore`(PG16) **실패** → `/usr/lib/postgresql/18/bin/pg_restore` 사용 또는 **plain SQL `.sql.gz`** ( `transaction_timeout` 등 PG18 전용 GUC 줄 제거 후 `psql` ).
- 스크립트: `scripts/monthly/dump_land_for_promote.py` → `backups/land_stats_promote_{cycle}.sql.gz`
- VPS: `deploy/scripts/promote_restore.sh` (PG18 bin·`as_of` 자동·pre-backup은 `/tmp` 경유)

**2608 Promote 완료 (2026-08-09):** 로컬 검증 DB(`as_of=2026-07-01`, 7월 거래 17,985건) → VPS `land_stats` restore → `/health.latest_as_of_month=2026-07-01`.

---

## 10. 백업 및 롤백

- **백업:** Promote 직전 `pg_dump` (`backups\`).  
- **롤백:** 문제 발견 시 Promote 이전 dump 로 DB 복원 후 백엔드 재기동.  
- **부분 롤백:** `land_basic_stats_v2` 특정 `as_of_month` 행만 삭제 등은 설계·FK에 따라 위험 — **가능하면 전체 restore** 우선.

---

## 11. 빠른 참조 — 명령 모음

| 목적 | 명령 |
|------|------|
| 월간 로컬 한 번에 (category V2) | `py scripts\monthly\run_monthly_cycle.py --cycle-id 202605` |
| 상위통계 생략(드물게) | `… run_monthly_cycle.py --cycle-id 202605 --skip-upper-v2` |
| **지목군 V2 (매월 §7.1)** | `py pipeline\build_stats_v2.py --as-of YYYY-MM-01 --windows 3,5 --col-axis group` |
| **지목군 upper V2** | `py pipeline\build_upper_stats_v2.py --as-of YYYY-MM-01 --windows 3,5 --col-axis group` |
| **annual 당해연도 both** | `py pipeline\build_annual_stats.py --years YYYY --full --col-axis both --with-upper` |
| 지목군 integrity | `py pipeline\verify_jimok_group_integrity.py` |
| 수집 목록만 | `py scripts\monthly\run_monthly_cycle.py --cycle-id 202605 --manifest-only` |
| 평탄화만 | `py scripts\monthly\flatten_raw_xlsx.py --source raw\토지\202605 --dest clean_snapshots\202605\flat_in` |
| 시도 건수 스냅샷 | `py scripts\monthly\snapshot_land_tx_counts.py --output clean_snapshots\202605\land_tx_counts_after.json` |
| 스냅샷 비교 | `py scripts\monthly\compare_count_snapshots.py --before … --after …` |
| **Promote 게이트** | `py pipeline\verify_monthly_integrity.py --as-of YYYY-MM-01` |
| **Promote dump (VPS 호환)** | `py scripts\monthly\dump_land_for_promote.py` → `backups\land_stats_promote_{cycle}.sql.gz` |

PowerShell 래퍼: `scripts\monthly\run_monthly_cycle.ps1 -CycleId 202605` (상위 생략: `-SkipUpperV2`)

---

## 12. 관련 문서

- `docs/V2_OPERATOR_CHECKLIST.md` — 월초 갱신 단일 SOP(전국·검증·백엔드)  
- `docs/V2_STATS_PRODUCTION.md` — `build_stats_v2` 운영  
- `docs/LAND_JIMOK_GROUP_DESIGN.md` — 지목군 7분류 · mart/API 정책 (D-026)  
- `docs/LONG_TERM_TREND_DESIGN.md` — 장기추세 annual · 월간은 **당해 연도 UPSERT**  
- `docs/DECISIONS.md` — D-007 `API_TOKEN`, D-003 캐시, **D-026 지목군**  
- `NEXT_STEPS.md` — 백로그(알림·백업 자동화 등)

---

## 13. 개정 이력

| 날짜 | 내용 |
|------|------|
| 2026-08-09 | **§9.4 코드 배포 vs DB Promote** — 2608 토지 7월 미노출 원인·ingest→mart→dump→VPS restore 체크리스트·PG18 dump 호환 |
| 2026-07-26 | **§7.1.0** 배포 404 사고(부분 group·upper 0) · VPS `backend/.env` · 전국성 검증 · UI 기본=용도×지목·지역 변경 시 category 복귀 |
| 2026-07-17 | **§7.1 용도×지목군 월간 필수** — 에이전트용 DDL·V2 group·annual 증분·검증 체크리스트. 실행 흐름·빠른 참조 반영 |
| 2026-05-24 | `run_monthly_cycle` 기본에 `build_upper_stats_v2`(상위통계) 포함, `--skip-upper-v2` 로 생략 |
