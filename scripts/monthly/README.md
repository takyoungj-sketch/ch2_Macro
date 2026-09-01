# `scripts/monthly/` — 월간 배치

운영 1페이지: [`docs/MONTHLY_UPDATE_CHECKLIST.md`](../../docs/MONTHLY_UPDATE_CHECKLIST.md)  
토지 SOP: [`docs/MONTHLY_UPDATE_SOP.md`](../../docs/MONTHLY_UPDATE_SOP.md)  
xlsx / `run_monthly_cycle*` 는 **복구·레거시**. 매월 아래 CSV 러너로 시작한다.

## SSOT 러너 (매월)

```
py scripts/monthly/run_land_cycle_csv.py --cycle-id YYYYMM
py scripts/monthly/run_built_cycle_csv.py --cycle-id YYYYMM
py scripts/monthly/run_collective_cycle_csv.py --cycle-id YYYYMM
```

- 토지: V2 windows **3,5,7** · §7.1 group · `analysis_cache` TRUNCATE. `--skip-jimok-group` / `--skip-cache-clear` 비권장.
- 복합: UPSERT + stale purge + 원장 mart. skip-enrich 기본. `--enrich` 는 D-051 전 운영 적재에 쓰지 않음.
- 집합: skip-enrich 기본. 신규 키만 `--enrich-new-keys`.
- `cycle_id` ↔ V2 `--as-of`: `cycle_utils.py`. 수집 끝 월이 직전 달과 다르면 `--v2-as-of`.
- `DATABASE_URL` / `BUILT_DATABASE_URL` / `COLLECTIVE_DATABASE_URL`: `pipeline/.env` · `.env.built` · `.env.collective`.

건수 스냅샷: `snapshot_land_tx_counts.py` · `snapshot_built_tx_counts.py` · `snapshot_collective_tx_counts.py`  
비교: `compare_count_snapshots.py` · `compare_built_count_snapshots.py` · `compare_collective_count_snapshots.py`  
beopjungri 품질: `verify_beopjungri_mapping.py --cycle-id YYYYMM` (목표 ≥99.7%)  
분양권 키: [`COLLECTIVE_PRESALE_BUILDING_KEY.md`](../../docs/COLLECTIVE_PRESALE_BUILDING_KEY.md)

## 용도×지목군 (D-026)

CSV 토지 러너가 **기본으로** 수행. 빼먹으면 배포 UI `matrix_mode=group` 404.

xlsx `run_monthly_cycle` 만 돌린 복구에서만 SOP **§7.1** 수동 (`--windows 3,5,7`). 설계: [`LAND_JIMOK_GROUP_DESIGN.md`](../../docs/LAND_JIMOK_GROUP_DESIGN.md).  
UI: 기본=용도×지목 · 지목군은 버튼만 · 지역 변경 시 용도×지목으로 복귀.

## 레거시 (xlsx · 복구만)

- 토지: `run_monthly_cycle.py` / `run_monthly_cycle.ps1` — category V2만. 이후 §7.1 수동.
- 복합: `run_built_monthly_cycle.py` (`--use-legacy-defaults` GUKTO)
- 집합: `run_collective_monthly_cycle.py`
- 평탄화: `flatten_raw_xlsx.py`
- 토지 엑셀 수집: `download_molit_land_xlsx.py` (`selenium>=4.15`)

SOP: [`BUILT_MONTHLY_UPDATE_SOP.md`](../../docs/BUILT_MONTHLY_UPDATE_SOP.md) · [`COLLECTIVE_MONTHLY_UPDATE_SOP.md`](../../docs/COLLECTIVE_MONTHLY_UPDATE_SOP.md)

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
