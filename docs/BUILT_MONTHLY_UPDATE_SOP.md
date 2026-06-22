# 월간 복합부동산(built) 데이터 업데이트 SOP

> **목표:** 매월 초 **토지 cycle 완료 후** 상업·공장·단독다가구 정제 xlsx → `built_stats.built_transactions` 갱신, 검증·승인 후 반영.  
> **전제:** 토지와 동일하게 **단순성·재현성·검증·롤백** 우선. 사전통계(V2)는 **당분간 없음** — 회귀는 실시간.  
> **기준 루트:** `C:\ch2\ch2_Macro`

관련: [`MONTHLY_UPDATE_SOP.md`](MONTHLY_UPDATE_SOP.md) (토지), [`BUILT_RESEARCH_MVP.md`](BUILT_RESEARCH_MVP.md) (로컬 실행)

---

## 1. 실행 순서 (월간)

```
1) 토지: run_monthly_cycle.py → 검증 → Promote
2) 복합부동산: run_built_monthly_cycle.py → 검증 → Promote (built_stats)
3) (선택) frontend-built / 백엔드 재기동 — 원장만 바뀌면 회귀 API 자동 반영
```

**토지를 먼저** 돌리는 이유: `region_codes` 행정코드가 land → built 로 동기화되기 때문.

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

- [ ] 토지 `run_monthly_cycle.py` 완료 (권장: `--require-land-cycle` 로 강제)
- [ ] `raw\복합부동산\{cycle_id}\` 에 3종 정제 xlsx (또는 `--use-legacy-defaults`)
- [ ] `BUILT_DATABASE_URL` 연결 확인

### 5.2 통합 실행

```powershell
cd C:\ch2\ch2_Macro
py scripts\monthly\run_built_monthly_cycle.py --cycle-id 202606 --require-land-cycle
```

동작:

1. xlsx 경로 해석 → `clean_snapshots\{cycle_id}\built\raw_manifest.json`
2. `pipeline/built/import_refined.py --refresh-region-codes` (유형별 **truncate 후 재적재**)
3. `built_tx_counts_after.json` (유형 × 시도 건수)

### 5.3 옵션

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
| **B** | 서버에서 동일 `run_built_monthly_cycle` 재실행 |

토지 Promote와 **독립** — `built_stats` 만 롤백 가능.

### 7.3 앱

- 백엔드 `BUILT_DATABASE_URL` 확인 후 재기동
- 회귀 API는 별도 `as_of` 없음 — 원장 갱신 즉시 반영

---

## 8. 롤백

Promote 이전 `pg_dump` 로 `built_stats` 복원 → 백엔드 재기동.

---

## 9. 로드맵 (미구현)

| 단계 | 내용 |
|------|------|
| B1 | 국토부 3종 xlsx **Selenium 수집** (토지 download 스크립트 패턴) |
| B2 | in-repo **정제** (`COL_MAP`·집합 제외·detached 처리) |
| B3 | `contract_month` / `contract_date` 적재 → 12개월 창 정밀화 |
| B4 | (선택) 무료용 canonical 회귀 preset 월배치 |

---

## 10. 빠른 참조

```powershell
# manifest만 (경로 확인)
py scripts\monthly\run_built_monthly_cycle.py --cycle-id 202606 --manifest-only

# 전환기 ingest (GUKTO 기본 경로)
py scripts\monthly\run_built_monthly_cycle.py --cycle-id 202606 --use-legacy-defaults --refresh-region-codes

# 건수 스냅샷만
py scripts\monthly\snapshot_built_tx_counts.py `
  --output clean_snapshots\202606\built\built_tx_counts_after.json `
  --cycle-id 202606
```
