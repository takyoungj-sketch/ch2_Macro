# 토지 원장·사전통계 전면 재구축 계획

> **작성:** 2026-06-17  
> **상태:** 착수 대기  
> **범위:** **토지(`land_stats`)만** — 원장 `land_transactions` + 사전통계 + (선택) 모달 API 풍부화  
> **비범위:** 복합(`built_stats`)·집합(`collective_stats`) — 동일 패턴으로 **후속**  
> **관련:** [`NEXT_STEPS.md`](../NEXT_STEPS.md) §4-2 · [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md) · [`V2_OPERATOR_CHECKLIST.md`](./V2_OPERATOR_CHECKLIST.md) · 지역선택 재구축(별도 plan, 완료/병행 무관)

---

## 1. 목표

| # | 목표 |
|---|------|
| G1 | `raw\raw base\토지_2021_2026` CSV(21~26) 기준 **원장 전량 재적재** |
| G2 | 모달·거래 목록용 컬럼 **`contract_date`, `lot_display`, `partial_ownership_label`, `deal_type`** 채움률 확보 |
| G3 | **사전통계(V1·V2·상위·장기)** 를 새 원장 기준으로 **재빌드** |
| G4 | 기존 `land_stats` 와 **병렬 비교** 후 검증 통과 시 Promote |
| G5 | 운영 중단 최소 — 로컬·검증 기간 동안 **old/new 2체제** 유지 |

---

## 2. 전략 요약

```
[Git]  main (현행)          feature/land-ledger-rebuild (DDL·API·모달)
[DB]   land_stats (old)     land_stats_next (new)
[API]  :8000 → old          :8001 → new
[UI]   :5173/land/ → old    :5176/land/ → new  (선택, UI 변경 시 worktree)
```

- **코드**는 브랜치, **데이터**는 병렬 DB — 둘 다 쓴다.
- Promote 전까지 **프로덕션(VPS)은 `land_stats` 유지**.
- 복합·집합 DB/API는 **손대지 않음**.

---

## 3. 입력 데이터

### 3.1 1차 소스 (이번 재구축)

| 경로 | 내용 |
|------|------|
| `raw\raw base\토지_2021_2026\` | 시도별 `*_토지_매매_2021.csv` … `2026.csv` |

- 형식: Molit CSV (`collect.py --format csv` / `run_pipeline.py --excel-format auto`)
- `collect.py` 가 면책·헤더 skiprows 처리 ([`MOLIT_CSV_COLLECTOR_WARNINGS.md`](./MOLIT_CSV_COLLECTOR_WARNINGS.md) 준수)

### 3.2 (선택) 장기 추세·2010~ 구간

| 경로 | 용도 |
|------|------|
| `raw\raw long term\토지_2010_2020\` | `land_annual_stats` backfill 시 **2차 ingest** |

**v1 재구축**은 2021~26 원장 + V2(3·5년) 우선.  
2010~ annual 은 원장·V2 안정 후 **Phase 2** 로 분리 권장.

### 3.3 선행 마스터

| 테이블 | 조치 |
|--------|------|
| `region_codes` | `seed_region_codes.py` 로 **new DB에** 최신 법정동 코드 적재 (또는 old에서 dump 후 검증) |

---

## 4. 산출물 — DB 객체

### 4.1 원장 (핵심)

**`land_transactions`** — 정제 거래 Fact (약 25 컬럼)

| 그룹 | 컬럼 | 비고 |
|------|------|------|
| 식별 | `transaction_hash`, `raw_id` | UPSERT 키 |
| 시점 | `contract_year`, `contract_month`, `contract_date` | 모달 풍부화: **일 단위** |
| 행정 | `beopjungri_code`, `sido_code`, `sigungu_code` | 이름은 `region_codes` JOIN |
| 속성 | `land_category`, `zone_type`, `road_condition`, `area_sqm`, `area_category` | 매트릭스 축 |
| 가격 | `total_price_10k`, `unit_price_per_sqm` | 만원 / 만원·㎡ |
| **표시** | `lot_display`, `partial_ownership_label`, `deal_type` | **§4-2 모달 목표** |
| 플래그 | `is_partial_ownership`, `is_cancelled`, `is_valid` | 통계 포함 규칙 |
| 매핑 | `needs_review`, `mapping_notes` | D-012 검수 |

**`land_transactions_raw`** — JSONB 원천 보존 (선택이지만 재구축 시 **권장**).

DDL: `db/001_init.sql`, `db/009_*`, `db/011_*`, `db/008_*`(배치 인덱스).

### 4.2 사전통계 (원장 재빌드 후 필수)

| 테이블 | 스크립트 | 용도 |
|--------|----------|------|
| `land_basic_stats` | `build_stats.py` | V1 (legacy, sunset 예정) |
| `land_basic_stats_v2` | `build_stats_v2.py` | **무료·유료 V2** (3·5년 창) |
| `land_upper_stats_v2` | `build_upper_stats_v2.py` | 시도·시군구·읍면동 상위 |
| `land_annual_stats` | `build_land_annual*.py` | 장기 추세 모달 (Phase 2) |

### 4.3 캐시 (재적재 후 비움)

- `analysis_cache`, `analysis_base_cache` — `clean.py` / pipeline 종료 시 TRUNCATE ([`DECISIONS.md`](./DECISIONS.md) D-012 부록)

---

## 5. 작업 Phase

### Phase 0 — 준비 (반나절)

| # | 작업 | 산출 |
|---|------|------|
| 0-1 | `main` 에서 `feature/land-ledger-rebuild` 분기 | Git |
| 0-2 | 태그 `backup-before-land-rebuild` | 복구 기준점 |
| 0-3 | `pg_dump -Fc land_stats` → `backups/` | old baseline |
| 0-4 | `CREATE DATABASE land_stats_next` + DDL 일괄 적용 (`001`~`011`, `007`, `008`, `009`, `014` 등) | empty schema |
| 0-5 | `pipeline/.env.rebuild` — `DATABASE_URL=.../land_stats_next` | ingest 전용 |
| 0-6 | (선택) `backend/.env.rebuild` — 동일 URL, 포트 8001 | API 비교용 |

**DDL 적용 예 (PowerShell):**

```powershell
$DB = "land_stats_next"
$DDL = @(
  "001_init.sql","002_indexes.sql","003_legacy_patch.sql",
  "007_land_basic_stats_v2.sql","008_land_transactions_v2_batch_index.sql",
  "009_land_transactions_mapping_review.sql","011_land_transactions_display_columns.sql",
  "010_land_upper_stats_v2.sql","014_land_annual_stats.sql"
)
foreach ($f in $DDL) {
  psql -U postgres -d $DB -f "c:\ch2\ch2_Macro\db\$f"
}
```

### Phase 1 — 마스터·원장 ingest (1~2일, 디스크·CPU 의존)

| # | 작업 | 명령·메모 |
|---|------|-----------|
| 1-1 | `region_codes` 시드 | `DATABASE_URL=...next python seed_region_codes.py` |
| 1-2 | CSV → raw | `collect.py --directory "..\raw\raw base\토지_2021_2026" --format csv --source-year 0` |
| 1-3 | raw → clean → upsert | `clean.py` (전량: `--reprocess-all --yes-i-am-sure` 또는 raw 비어 있으면 일반 clean) |
| 1-4 | 커버리지 로그 | 전국 `COUNT(*)`, `needs_review`, `beopjungri_code` NULL, **표시 컬럼 NULL 비율** |
| 1-5 | (권장) dedupe | [`TRANSACTION_HASH_DEDUPE.md`](./TRANSACTION_HASH_DEDUPE.md) — V2 배치 **전** |

**일괄 파이프라인 (대안):**

```powershell
cd c:\ch2\ch2_Macro\pipeline
$env:DATABASE_URL = (Get-Content .env.rebuild | Select-String DATABASE_URL).ToString().Split("=",2)[1]
python run_pipeline.py --excel-dir "..\raw\raw base\토지_2021_2026" --excel-format auto --skip-build-stats
python dedupe_land_transactions.py --execute --rehash   # 정책에 따라
```

> **주의:** `run_pipeline` 기본은 **증분**에 가깝다. **완전 갈아엎기**면 `land_transactions` TRUNCATE 후 collect→clean 또는 dedicated rebuild 스크립트(Phase 1.5에서 추가 검토).

### Phase 2 — 사전통계 재구축 (반나절~1일)

`as_of_month` 는 **데이터 기준일**에 맞게 고정 (예: `2026-05-01` = **2026년 5월 말**까지 반영 — [`V2_STATS_DESIGN.md`](./V2_STATS_DESIGN.md) §3).

| # | 작업 | 명령 |
|---|------|------|
| 2-1 | ANALYZE | `psql -d land_stats_next -f db/preflight_v2_national.sql` |
| 2-2 | V1 stats | `python build_stats.py` |
| 2-3 | **V2 stats** | `python build_stats_v2.py --as-of YYYY-MM-01 --windows 3,5` |
| 2-4 | 상위 stats | `python build_upper_stats_v2.py --as-of YYYY-MM-01 --windows 3,5` |
| 2-5 | 인구 (필요 시) | `seed_population_csv.py` |
| 2-6 | (Phase 2b) annual | 2010~20 CSV 추가 ingest 후 `land_annual_stats` 빌드 |

로그: `logs/rebuild_land_YYYYMMDD.log` 에 `tee` 저장.

### Phase 3 — old vs new 검증 (반나절)

| # | 검증 | 기준 |
|---|------|------|
| 3-1 | 전국·시도별 `land_transactions` 건수 | old 대비 ±허용치 문서화 (해제·dedupe 정책 차이 설명) |
| 3-2 | `needs_review` / 매핑률 | D-012 수준 유지 (~99% mapped) |
| 3-3 | 표시 컬럼 채움 | `lot_display`, `deal_type`, `partial_ownership_label`, `contract_date` — **목표 %** 설정 |
| 3-4 | V2 샘플 | `verify_v2_national_samples.py --base-url http://127.0.0.1:8001` |
| 3-5 | 월간 integrity | `verify_monthly_integrity.py` (golden 갱신 여부 별도 결정) |
| 3-6 | API 대조 | 동일 beopjungri·필터로 old/new `count` / 단가 비교 |

**병렬 실행:**

```powershell
# Terminal A — old
cd backend; uvicorn app.main:app --port 8000   # DATABASE_URL=land_stats

# Terminal B — new
cd backend; $env:DATABASE_URL="postgresql+psycopg2://.../land_stats_next"
uvicorn app.main:app --port 8001

# Frontend (선택): vite 5173 → 8000, vite 5176 → 8001
```

스냅샷 JSON 저장: `clean_snapshots/rebuild_2021_2026/land_tx_counts.json`, `stats_snapshots/.../v2_summary.json`.

### Phase 4 — 모달·API 풍부화 (코드, Phase 1~3와 병행 가능)

[`NEXT_STEPS.md`](../NEXT_STEPS.md) §4-2:

| # | 작업 |
|---|------|
| 4-1 | `MatrixCellTransactionItem` + `paid.py` 쿼리에 `contract_date`, `lot_display`, `partial_ownership_label`, `deal_type` 추가 |
| 4-2 | `PaidMatrixYearlyModal` 거래 목록 UI 컬럼 확대 |
| 4-3 | (선택) 지분거래 표시·필터 정책 UI 명시 |

→ **feature 브랜치**에서 개발, **new DB + :8001** 로만 먼저 확인.

### Phase 5 — Promote (검증 OK 후)

| # | 작업 |
|---|------|
| 5-1 | `pg_dump -Fc land_stats` 최종 old 백업 |
| 5-2 | `land_stats` rename → `land_stats_legacy_YYYYMMDD` 또는 dump restore로 **교체** |
| 5-3 | `land_stats_next` → `land_stats` rename **또는** dump restore |
| 5-4 | `backend/.env`, `pipeline/.env` URL 정리 |
| 5-5 | `analysis_cache` TRUNCATE, 백엔드·프론트 재시작 |
| 5-6 | VPS: [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md) §7 Promote 절차 |
| 5-7 | `feature/land-ledger-rebuild` → `main` merge |

**롤백:** `land_stats_legacy_*` restore 또는 `pg_dump` old 복원.

---

## 6. 완료 기준 (Definition of Done)

- [ ] `land_stats_next.land_transactions` — 2021~26 CSV 전량 반영, `is_valid` 건수 old와 설명 가능한 수준 일치
- [ ] 표시 컬럼: `lot_display` 채움 ≥ **95%** (valid 거래 기준, 목표치 착수 후 실측 조정)
- [ ] `needs_review` 비율 — old 대비 악화 없음
- [ ] `land_basic_stats_v2` — `--as-of` 스냅샷 전국 배치 성공
- [ ] `verify_v2_national_samples.py` errors=0 (new API)
- [ ] (Phase 4 포함 시) 모달 거래 목록에 **계약일·번지·지분·거래유형** 노출
- [ ] Promote 후 `/health.latest_as_of_month` 정책 일치

---

## 7. 리스크·완화

| 리스크 | 완화 |
|--------|------|
| CSV 시도·연도 오염 | 수집기 경고 문서 준수, ingest 전 파일명·행수 spot check |
| 전량 TRUNCATE 실수 | **old DB 건드리지 않음** — next만 ingest |
| V2 배치 장시간 | `008` 인덱스, `STATS_V2_SIDO_CODE` 시도별 분할 |
| old/new 건수 불일치 | dedupe·해제·연도 범위 차이를 **manifest**에 기록 |
| 모달만 먼저 merge | API는 additive — old DB에도 컬럼 있으면 harmless NULL |

---

## 8. 후속 (복합·집합)

| 영역 | 계획서 | 상태 |
|------|--------|------|
| 주거 집합 4유형 | [`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](./COLLECTIVE_LEDGER_REBUILD_PLAN.md) | 진행/완료 |
| 복합 일반 3유형 | [`BUILT_LEDGER_REBUILD_PLAN.md`](./BUILT_LEDGER_REBUILD_PLAN.md) | Phase A 착수 (D-024) |

공통 패턴: `raw/raw base/{유형}_2021_2026` → ingest → **`region_codes` sync from land** → (Phase B) mart·UI.

**토지 Promote 완료 후** 복합 Phase A 착수 권장 (병행 시 `built_stats` 백업 필수).

---

## 9. 체크리스트 (운영자용)

```
Phase 0  [ ] 브랜치  [ ] backup tag  [ ] pg_dump old  [ ] land_stats_next DDL
Phase 1  [ ] region_codes  [ ] collect CSV  [ ] clean  [ ] coverage log  [ ] dedupe
Phase 2  [ ] build_stats  [ ] build_stats_v2  [ ] build_upper_stats_v2  [ ] ANALYZE
Phase 3  [ ] old/new count  [ ] verify_v2  [ ] verify_integrity  [ ] UI spot check
Phase 4  [ ] API modal fields  [ ] frontend columns
Phase 5  [ ] Promote  [ ] merge main  [ ] VPS
```

---

## 10. 관련 문서·경로

| 문서 | 역할 |
|------|------|
| [`NEXT_STEPS.md`](../NEXT_STEPS.md) §4-2 | 모달 거래 목록 확장 의도 |
| [`V2_OPERATOR_CHECKLIST.md`](./V2_OPERATOR_CHECKLIST.md) | V2 배치 SOP |
| [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md) | Promote·월간 갱신 |
| [`TRANSACTION_HASH_DEDUPE.md`](./TRANSACTION_HASH_DEDUPE.md) | dedupe |
| [`FOLLOW_UP_LAND_TX_MAPPING.md`](./FOLLOW_UP_LAND_TX_MAPPING.md) | 매핑 검증 |
| `pipeline/clean.py` | 원장 정제 SSOT |
| `db/011_land_transactions_display_columns.sql` | 표시 컬럼 DDL |

---

## 11. 다음 액션 (즉시)

1. Phase 0 실행 — `land_stats_next` 생성 + DDL  
2. `토지_2021_2026` 1개 시도 CSV로 **smoke ingest** (전국 전에)  
3. smoke OK → 전국 collect/clean → Phase 2 V2 배치  
4. 병렬 API `:8001` 로 old/new 비교 시작

### 로컬 dev (old vs new 병렬)

| 구분 | API | UI |
|------|-----|-----|
| **현행** | `:8000` (`backend/.env` → `land_stats`) | http://127.0.0.1:5173/land/ |
| **재구축** | `:8001` (`land_stats_next`) | http://127.0.0.1:5176/land/ |

**재구축 API (PowerShell):**

```powershell
cd c:\ch2\ch2_Macro\backend
$env:DATABASE_URL = "postgresql+psycopg2://postgres:8972@localhost:5432/land_stats_next"
$env:STATS_V2_DEFAULT_AS_OF_MONTH = "2026-06-01"   # ⚠ 중간 상태 — §12 참고. 운영 정상값은 2026-05-01(6월 중순) / Promote 후 202607에서 2026-06-01
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

**재구축 프론트:**

```powershell
cd c:\ch2\ch2_Macro\frontend
$env:VITE_DEV_API_TARGET = "http://127.0.0.1:8001"
$env:VITE_DEV_PORT = "5176"
npm run dev -- --host 127.0.0.1
```

`frontend/vite.config.ts` — `VITE_DEV_API_TARGET`, `VITE_DEV_PORT` 로 프록시·포트 분기.

---

## 12. `as_of_month` 중간 상태 — 2026-06 중순 (에이전트·운영자 필독)

> **기록일:** 2026-06-18  
> **결정:** **`as_of_month` 별도 수정은 하지 않고, 202607 월간 cycle에서 정상화한다.**

### 12.1 배경

| 항목 | 값 |
|------|-----|
| 달력 | **2026년 6월 중순** |
| **운영상 정상 `as_of_month`** | **`2026-05-01`** (= 5월 31일까지 반영, UI 기준일 2026-06-01) |
| `land_stats` (현행) | V2 mart **`2026-05-01`** — 정상 |
| `land_stats_next` (재구축) | V2 mart **`2026-06-01`** — **월간 SOP보다 1달 앞섬 (의도적 수정 보류)** |

6월 중순 **원장 전면 재구축**(`finish_land_rebuild.py`, `AS_OF = 2026-06-01`) 과정에서 사전통계 키가 **7월 cycle에 해당하는 as_of**로 올라갔다.  
이는 **원장·매핑·모달 검증용**이며, **지금 달 운영 기준과 같다고 보면 안 된다.**

집합·현행 토지·`backend/.env` 의 `STATS_V2_DEFAULT_AS_OF_MONTH=2026-05-01` 과 **재구축 DB만 불일치**하는 상태가 **의도된 중간 상태**다.

### 12.2 왜 지금 `2026-05-01`로 되돌리지 않나

| 지금 수정 (`--as-of 2026-05-01` 재배치) | 7월 초 정상화 (`cycle_id=202607`)까지 대기 |
|----------------------------------------|-------------------------------------------|
| Promote 전 **집합·현행과 as_of 맞춤** 가능 | **V2 전국 배치 2회** 방지 (5월 → 6월) |
| 재구축 **수용 테스트**에 유리 | **월간 SOP 한 번**으로 원장 12개월 갱신 + mart 재구축 |
| 7월 cycle **직전 Promote** 시 필수 | **Promote = 202607 완료 후**가 자연스러운 cutover |

**권장:** 재구축 DB를 현행 `land_stats` 자리에 **교체(Promote)할 계획**이면, **7월 초 `run_monthly_cycle.py --cycle-id 202607`** 을 **`land_stats_next`(또는 Promote 직후 `land_stats`)** 에 돌려 **`as_of_month=2026-06-01`** 로 **한 번에** 정상화한다.

**지금 당장 `2026-05-01` 재배치가 필요한 경우 (예외):**

- **7월 cycle 전**에 재구축 DB를 **운영/VPS에 Promote**해야 할 때
- as_of **수치 비교**가 Promote 게이트인데, 집합·현행과 **동일 스냅샷**이어야 할 때

예외 시: `build_stats_v2` / `build_upper_stats_v2` **`--as-of 2026-05-01`**, env `STATS_V2_DEFAULT_AS_OF_MONTH=2026-05-01`, `:8001` 검증 API도 동일.

### 12.3 202607 cycle (7월 초) — 정상화 절차

[`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md) · [`scripts/monthly/cycle_utils.py`](../scripts/monthly/cycle_utils.py):

| 항목 | 값 |
|------|-----|
| `cycle_id` | **`202607`** |
| 수집 연월 (12개월) | **`202507` ~ `202606`** |
| `--v2-as-of` | **`2026-06-01`** (= 6월 30일까지 반영) |
| Promote | cycle·검증 OK 후 `land_stats_next` → `land_stats` 교체 (§Phase 5) |

```powershell
# 재구축 DB URL 로 pipeline/.env 또는 .env.rebuild 설정 후
py scripts\monthly\run_monthly_cycle.py --cycle-id 202607
# Promote 후 backend/.env:
#   STATS_V2_DEFAULT_AS_OF_MONTH=2026-06-01
#   DATABASE_URL → land_stats (교체 완료 DB)
```

집합: [`COLLECTIVE_MONTHLY_UPDATE_SOP.md`](./COLLECTIVE_MONTHLY_UPDATE_SOP.md) — 토지 Promote **이후** `run_collective_monthly_cycle.py --cycle-id 202607`.

### 12.4 에이전트·로컬 dev 주의 (오해 방지)

1. **`:8001` / `land_stats_next` 의 `2026-06-01` ≠ “지금 운영 최신”** — 6월 중순 기준 운영 최신은 **`2026-05-01`**.
2. **재구축 vs 현행 count/단가 비교** 시 as_of가 다르면 **기간 창이 달라** 숫자가 어긋난다. 원장·매핑 검증은 OK, **V2 수치 1:1 비교는 `--as-of` 맞춘 뒤** 또는 **202607 이후**.
3. **Promote 전** VPS·`:8000` 에 재구축 DB를 붙이지 말 것 — `latest_as_of_month` 가 집합·복합과 **한 달 어긋남**.
4. `pipeline/finish_land_rebuild.py` 의 `AS_OF = "2026-06-01"` 은 **재구축 마무리 스크립트 고정값**이며, 월간 SOP 기본값이 **아님**. 202607 이후에는 cycle_utils 매핑을 따른다.

### 12.5 체크리스트 (202607 전)

```
[ ] 재구축 원장·모달·매핑 검증 (as_of 불일치 인지한 채)
[ ] 7월 초 전 Promote 금지 (또는 §12.2 예외 시 2026-05-01 재배치)
[ ] 202607 run_monthly_cycle on land_stats_next
[ ] verify_monthly_integrity / verify_v2_national_samples (--as-of-month 2026-06-01)
[ ] Promote + STATS_V2_DEFAULT_AS_OF_MONTH=2026-06-01 + collective 202607
```
