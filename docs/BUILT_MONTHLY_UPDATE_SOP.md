# 월간 복합부동산(built) 데이터 업데이트 SOP

> **목표:** 매월 초 **토지 cycle 완료 후** 상업·공장·단독다가구 → `built_stats.built_transactions` 갱신, 검증·승인 후 반영.  
> **전제:** 토지와 동일하게 **단순성·재현성·검증·롤백** 우선. 사전통계(V2)는 **당분간 없음** — 회귀는 실시간.  
> **기준 루트:** 저장소 루트. 예: `C:\ch2\ch2_Macro` · `E:\ch2\ch2_Macro`.
>
> **SSOT:** `scripts/monthly/run_built_cycle_csv.py`. 1페이지: [`MONTHLY_UPDATE_CHECKLIST.md`](./MONTHLY_UPDATE_CHECKLIST.md).  
> 축약·보강 달력: [`PARCEL_MASTER_MONTHLY_UPDATE.md`](./PARCEL_MASTER_MONTHLY_UPDATE.md) — 실거래 달 skip-enrich 기본. 이 SOP의 xlsx 러너 이름으로 월간을 돌리지 말 것.  
> xlsx/`run_built_monthly_cycle` 은 복구·레거시. git deploy ≠ 월갱신.

관련: [`MONTHLY_UPDATE_SOP.md`](MONTHLY_UPDATE_SOP.md) (토지), [`BUILT_RESEARCH_MVP.md`](BUILT_RESEARCH_MVP.md) (로컬 실행)

---

## 1. 실행 순서 (월간)

```
1) 토지: run_land_cycle_csv.py → 검증 → Promote (land_stats)
2) 복합: run_built_cycle_csv.py → 검증 → Promote (built_stats)
3) 집합: run_collective_cycle_csv.py (체크리스트 §3)
```

xlsx `run_built_monthly_cycle.py` 는 **복구**. 토지를 먼저 — `region_codes` 정본이 land.

---

## 2. 용어

| 용어 | 설명 |
|------|------|
| **cycle_id** | 월간 작업 번들 ID. **`YYYYMM`** (토지와 **동일 ID** 사용 권장). |
| **수집 연월 범위** | 토지와 동일 가정: `cycle_id=202606` → **`202507`~`202605`** (직전 12개월). `built_cycle_utils.collection_yyyymm_range_from_cycle_id` 참고. |
| **asset_type** | `commercial` · `factory` · `detached` |

> **참고:** 현재 ingest는 `contract_year` 위주. 월 단위 12개월 창은 **`contract_month`/`contract_date` 적재 후** 정밀화 예정.

---

## 3. 디렉터리 구조 (권장)

```
C:\ch2\ch2_Macro\
  raw\복합부동산\{cycle_id}\
    commercial\일반상가_정제.xlsx
    factory\공장창고_매매_정제.xlsx
    detached\단독다가구_매매_정제.xlsx
  clean_snapshots\{cycle_id}\built\
    raw_manifest.json
    built_tx_counts_after.json
  backups\
    built_stats_pre_promote_{cycle_id}.dump
  scripts\monthly\
    run_built_monthly_cycle.py
  pipeline\built\
    import_refined.py
```

서브폴더명은 `commercial` / `상업` / `일반상가` 등 **별칭 허용** (`built_cycle_utils.SUBDIR_ALIASES`).

### 전환기 (raw 미구축)

GUKTO 정제 xlsx를 기존 경로에 두고:

```powershell
py scripts\monthly\run_built_monthly_cycle.py --cycle-id 202606 --use-legacy-defaults --require-land-cycle
```

---

## 4. DB

| DB | 용도 |
|----|------|
| `land_stats` | 토지 원장 + region_codes **정본** |
| `built_stats` | 복합부동산 원장 (토지와 **분리**) |

환경: `pipeline/.env.built` → `BUILT_DATABASE_URL`

월간 ingest 시 **`--refresh-region-codes`** (기본 ON): land → built `region_codes` 전량 동기화.

---

## 5. 실행

### 5.1 사전 조건

- [ ] 토지 `run_land_cycle_csv.py` 완료 (권장: `--require-land-cycle`)
- [ ] MOLIT 복합 CSV (`molit_csv_collector` / 체크리스트 경로)
- [ ] `BUILT_DATABASE_URL` 연결 확인

xlsx 복구만: `raw\복합부동산\{cycle_id}\` 3종 정제 xlsx 또는 `--use-legacy-defaults`.

### 5.2 통합 실행 (CSV · SSOT)

```powershell
py scripts\monthly\run_built_cycle_csv.py --cycle-id YYYYMM
```

동작: CSV UPSERT → stale hash purge → `build_scope_stats`(원장만) → skip-enrich 기본 → 동결 검증. `--enrich` 는 D-051 전 운영에 쓰지 않음.

### 5.2b xlsx 복구

```powershell
py scripts\monthly\run_built_monthly_cycle.py --cycle-id YYYYMM --require-land-cycle
```

동작:

1. xlsx 경로 해석 → `clean_snapshots\{cycle_id}\built\raw_manifest.json`
2. `pipeline/built/import_refined.py --refresh-region-codes` (유형별 **truncate 후 재적재**)
3. `built_tx_counts_after.json` (유형 × 시도 건수)

### 5.3 옵션 (xlsx `run_built_monthly_cycle` 복구)

CSV 러너 옵션은 `run_built_cycle_csv.py --help` (`--dry-run`, `--enrich` 등).

| 옵션 | 설명 |
|------|------|
| `--manifest-only` | manifest 만 생성 |
| `--skip-ingest` | 스냅샷만 (DB 변경 없음) |
| `--no-refresh-region-codes` | region_codes 동기화 생략 |
| `--commercial-only` 등 | 한 유형만 |
| `--commercial-path` 등 | xlsx 직접 지정 |
| `--use-legacy-defaults` | GUKTO 기본 경로 |

---

## 6. 검증

### 6.1 전월 대비 건수

```powershell
py scripts\monthly\compare_built_count_snapshots.py `
  --before clean_snapshots\202605\built\built_tx_counts_after.json `
  --after  clean_snapshots\202606\built\built_tx_counts_after.json
```

### 6.2 수동 체크리스트

- [ ] `compare_built_count_snapshots` exit 0 (또는 급변 사유 확인)
- [ ] `commercial` / `factory` / `detached` total > 0
- [ ] UI: 대표 시군구 2~3곳 — 거래 n·회귀 실행 sanity
- [ ] **beopjungri 매칭 품질 게이트** (토지·집합·복합, 목표 ≥99.7%):
  `py scripts\monthly\verify_beopjungri_mapping.py --cycle-id YYYYMM` → exit 0
  (리포트: `clean_snapshots/YYYYMM/beopjungri_mapping_report.json`)

---

## 7. Promote (built_stats)

### 7.1 백업 (필수)

```powershell
$env:PGPASSWORD="…"
pg_dump -h localhost -U postgres -d built_stats -Fc `
  -f C:\ch2\ch2_Macro\backups\built_stats_pre_promote_202606.dump
```

### 7.2 승격

| 방식 | 절차 |
|------|------|
| **A (권장)** | 검증된 dump → 서버 restore |
| **B** | 서버에서 동일 `run_built_cycle_csv` 재실행 (xlsx 복구면 `run_built_monthly_cycle`) |

토지 Promote와 **독립** — `built_stats` 만 롤백 가능.

### 7.3 앱

- 백엔드 `BUILT_DATABASE_URL` 확인 후 재기동
- 회귀 API는 별도 `as_of` 없음 — 원장 갱신 즉시 반영

---

## 8. 롤백

Promote 이전 `pg_dump` 로 `built_stats` 복원 → 백엔드 재기동.

---

## 9. 로드맵 (xlsx 경로 · 참고)

MOLIT **CSV 수집기**가 월간 SSOT다. 아래 B1–B3는 옛 xlsx 러너 잔여.

| 단계 | 내용 |
|------|------|
| B1 | (레거시) 국토부 3종 xlsx Selenium |
| B2 | (레거시) in-repo 정제 |
| B3 | `contract_month` / `contract_date` 적재 → 12개월 창 정밀화 |
| B4 | (선택) 무료용 canonical 회귀 preset 월배치 |

---

## 10. 빠른 참조

```powershell
# SSOT
py scripts\monthly\run_built_cycle_csv.py --cycle-id YYYYMM --dry-run
py scripts\monthly\run_built_cycle_csv.py --cycle-id YYYYMM

# xlsx 복구
py scripts\monthly\run_built_monthly_cycle.py --cycle-id YYYYMM --manifest-only
py scripts\monthly\run_built_monthly_cycle.py --cycle-id YYYYMM --use-legacy-defaults --refresh-region-codes
```

## 11. 미구현 — 축약·enrich

CSV 러너는 마트 뒤 **skip-enrich 기본**. `--enrich`는 D-051 전 운영 적재에 쓰지 않는다. 동결 검증·purge FK는 [`PARCEL_MASTER_MONTHLY_UPDATE.md`](PARCEL_MASTER_MONTHLY_UPDATE.md).

