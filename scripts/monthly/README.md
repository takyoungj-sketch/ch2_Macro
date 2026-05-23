# `scripts/monthly/` — 월간 토지 반자동 배치

실제 운영 절차·용어는 **`docs/MONTHLY_UPDATE_SOP.md`** 를 본편으로 둔다.

## 진입점

- **통합 실행:**  
  `py scripts/monthly/run_monthly_cycle.py --cycle-id YYYYMM`  
  또는 `pwsh scripts/monthly/run_monthly_cycle.ps1 -CycleId YYYYMM`
- **평탄화만:** `py scripts/monthly/flatten_raw_xlsx.py`
- **시도별 건수 스냅샷:** `py scripts/monthly/snapshot_land_tx_counts.py`
- **스냅샷 비교:** `py scripts/monthly/compare_count_snapshots.py`
- **`cycle_id` ↔ V2 `--as-of` 매핑(기본 규칙):** `scripts/monthly/cycle_utils.py`

`DATABASE_URL`(및 선택 `STATS_*`)은 기존과 같이 **`pipeline/.env`** 또는 환경 변수를 사용한다.  
`flatten`/`snapshot*` 은 레포 루트에서 실행해도 `pipeline/` 을 `sys.path` 에 넣어 `db_utils` 를 로드한다.

## 국토부 엑셀 수집 (Selenium · 토지 매매)

- `py -m pip install "selenium>=4.15"`
- 전국 확장 전 1연치 검증 예:  
  `py scripts/monthly/download_molit_land_xlsx.py --cycle-id 202605 --limit-regions 1`

## 참고 노트북 규격 통합·정제 (템플릿용 산출)

- 설계·폴더 구조: `docs/LAND_NOTEBOOK_EXCEL_PREP.md`
- 일괄 실행:  
  `py scripts/monthly/run_land_notebook_excel_prep.py --cycle-id YYYYMM`
