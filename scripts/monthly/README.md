# `scripts/monthly/` — 월간 토지 반자동 배치

실제 운영 절차·용어는 **`docs/MONTHLY_UPDATE_SOP.md`** 를 본편으로 둔다.

## 진입점

- **통합 실행:**  
  `py scripts/monthly/run_monthly_cycle.py --cycle-id YYYYMM` — **기본적으로** `run_pipeline` 에 `--with-upper-v2`(상위 행정 사전집계) 포함. 끄려면 `--skip-upper-v2`.  
  또는 `pwsh scripts/monthly/run_monthly_cycle.ps1 -CycleId YYYYMM` (상위 생략: `-SkipUpperV2`)
- **평탄화만:** `py scripts/monthly/flatten_raw_xlsx.py`
- **시도별 건수 스냅샷:** `py scripts/monthly/snapshot_land_tx_counts.py`
- **스냅샷 비교:** `py scripts/monthly/compare_count_snapshots.py`
- **`cycle_id` ↔ V2 `--as-of` 매핑(기본 규칙):** `scripts/monthly/cycle_utils.py`

`DATABASE_URL`(및 선택 `STATS_*`)은 기존과 같이 **`pipeline/.env`** 또는 환경 변수를 사용한다.  
`flatten`/`snapshot*` 은 레포 루트에서 실행해도 `pipeline/` 을 `sys.path` 에 넣어 `db_utils` 를 로드한다.

## 복합부동산 월간 배치

- **통합 실행:**  
  `py scripts/monthly/run_built_monthly_cycle.py --cycle-id YYYYMM --require-land-cycle`  
  (토지 cycle **이후** · `--use-legacy-defaults` 로 GUKTO 경로 전환기 ingest)
- **건수 스냅샷:** `py scripts/monthly/snapshot_built_tx_counts.py`
- **스냅샷 비교:** `py scripts/monthly/compare_built_count_snapshots.py`
- **beopjungri 매칭 품질:** `py scripts/monthly/verify_beopjungri_mapping.py --cycle-id YYYYMM` (토지·집합·복합 통합, 목표 ≥99.7%)
- **SOP:** `docs/BUILT_MONTHLY_UPDATE_SOP.md`

`BUILT_DATABASE_URL` 은 **`pipeline/.env.built`** (및 `import_refined` 의 built db_utils).

## 집합부동산 월간 배치

- **통합 실행:**  
  `py scripts/monthly/run_collective_monthly_cycle.py --cycle-id YYYYMM --require-land-cycle`  
  (`--use-legacy-defaults` GUKTO 경로)
- **건수 스냅샷:** `py scripts/monthly/snapshot_collective_tx_counts.py`
- **스냅샷 비교:** `py scripts/monthly/compare_collective_count_snapshots.py`
- **SOP:** `docs/COLLECTIVE_MONTHLY_UPDATE_SOP.md`

`COLLECTIVE_DATABASE_URL` 은 **`pipeline/.env.collective`**.

## 국토부 엑셀 수집 (Selenium · 토지 매매)

- `py -m pip install "selenium>=4.15"`
- 전국 확장 전 1연치 검증 예:  
  `py scripts/monthly/download_molit_land_xlsx.py --cycle-id 202605 --limit-regions 1`

## 국토부 CSV 수집 (Selenium · 토지 매매 · 2010~2020 backfill)

> **⚠ 필독:** [`docs/MOLIT_CSV_COLLECTOR_WARNINGS.md`](../docs/MOLIT_CSV_COLLECTOR_WARNINGS.md) — 시도/연도 오염 CSV 방지

- `scripts/monthly/download_molit_land_historical_csv.py` — `molit_csv_download_core` (검증·안정 대기)
- 충북·충남 pilot (wave 1, 2010~2020):  
  `py scripts/monthly/download_molit_land_historical_csv.py --regions "충청북도,충청남도" --start-year 2010 --end-year 2020`
- 충청 인접 5시도 (wave 2: 대전·세종·경기·경북·강원):  
  `py scripts/monthly/download_molit_land_historical_csv.py --regions "대전광역시,세종특별자치시,경기도,경상북도,강원특별자치도" --start-year 2010 --end-year 2020 --headless`  
  적재·연도 마트:  
  `py scripts/monthly/ingest_land_historical_csv.py --build-annual --years 2010-2026 --with-upper --sido-code 30,36,41,47,51`
- 잔여 10시도 (wave 3, unattended):  
  `py scripts/monthly/run_land_annual_wave3_after_wave2.py --skip-wait --headless --max-new-downloads 100`  
  (신규 CSV **최대 100건**/일 → **11년 CSV 완비 시도만** collect·annual. 미완 시도는 다음날 재실행)  
  **진행 상황·내일 재개:** `pipeline/logs/LAND_ANNUAL_BACKFILL_RESUME.md`
- 1연치 검증:  
  `py scripts/monthly/download_molit_land_historical_csv.py --regions "충청북도" --years 2010`

## 국토부 CSV 수집 (Selenium · 아파트 매매 · 2010~2020 backfill)

> **⚠** [`docs/MOLIT_CSV_COLLECTOR_WARNINGS.md`](../docs/MOLIT_CSV_COLLECTOR_WARNINGS.md)

- `scripts/monthly/download_molit_apartment_historical_csv.py` — `molit_csv_download_core`
- 사무실 GUI/EXE: `deploy/molit_csv_collector/` — 시도 선택·실패 로그(빨간색)·CSV 검증
- 전국 2010~2020 (일일 100건 제한, 2일 분할 예):  
  `py scripts/monthly/download_molit_apartment_historical_csv.py --start-year 2010 --end-year 2020 --headless --max-new-downloads 100`  
  (다음날 동일 명령 재실행 — 이미 있는 파일은 스킵)
- 1연치 검증:  
  `py scripts/monthly/download_molit_apartment_historical_csv.py --limit-regions 1 --years 2010 --headless`

## 국토부 CSV 수집 (Selenium · 오피스텔 매매)

- `scripts/monthly/download_molit_officetel_csv.py` — 시도×연도별 CSV → `원본/오피스텔/`
- 검증 예:  
  `py scripts/monthly/download_molit_officetel_csv.py --limit-regions 1 --years 2021 --headless`
- 전국 2021~2025:  
  `py scripts/monthly/download_molit_officetel_csv.py --start-year 2021 --end-year 2025 --headless`

## 국토부 CSV 수집 (Selenium · 연립·다세대 매매)

- `scripts/monthly/download_molit_rowhouse_csv.py` — 시도×연도별 CSV → `원본/연립다세대/`
- 검증 예:  
  `py scripts/monthly/download_molit_rowhouse_csv.py --limit-regions 1 --years 2021 --headless`
- 전국 2021~2025:  
  `py scripts/monthly/download_molit_rowhouse_csv.py --start-year 2021 --end-year 2025 --headless`
- 적재: `py pipeline/collective/import_refined.py --rowhouse-only` (대지권면적 `land_area` 포함)

## 참고 노트북 규격 통합·정제 (템플릿용 산출)

- 설계·폴더 구조: `docs/LAND_NOTEBOOK_EXCEL_PREP.md`
- 일괄 실행:  
  `py scripts/monthly/run_land_notebook_excel_prep.py --cycle-id YYYYMM`
