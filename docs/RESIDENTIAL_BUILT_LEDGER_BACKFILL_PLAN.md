# 주거 집합 · 복합부동산 원장 백필 계획 (보류)

> **작성:** 2026-06-25  
> **상태:** **보류 (deferred)** — UI·API 컬럼 선반영 완료, **DB 재적재·Promote는 추후 일괄 수행**  
> **범위:**  
> - **주거 집합 4유형** — `apartment` · `rowhouse` · `officetel` · `presale`  
> - **복합(일반) 3유형** — `commercial` · `factory` · `detached`  
> **관련:** [`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](./COLLECTIVE_LEDGER_REBUILD_PLAN.md) · [`BUILT_LEDGER_REBUILD_PLAN.md`](./BUILT_LEDGER_REBUILD_PLAN.md) · [`DECISIONS.md`](./DECISIONS.md) D-027

---

## 1. 배경 — UI는 준비됐으나 원장이 비어 있음

2026-06-25 프로덕션(`built_stats`·`collective_stats`) 점검 결과, 거래목록 UI/API에 노출하는 컬럼 중 **상당수가 원장에 0% 채움** 상태다. UI 결함이 아니라 **legacy ingest 경로**(GUKTO xlsx·구 `import_refined`)로 적재된 데이터에 해당 필드가 없기 때문이다.

| 영역 | 테이블 | 약 건수 | 비어 있는 필드 (valid 행 기준) |
|------|--------|---------|--------------------------------|
| 주거 집합 | `collective_transactions` | ~325만 | `buyer_type`, `seller_type`, `deal_type` **0%** |
| 복합 | `built_transactions` | ~416k | `display_address`, `road_name`, `road_width_label`, `deal_type` **0%** |

**이번 세션에서 선반영한 UI (배포 전):**

| 화면 | 변경 |
|------|------|
| 복합 거래목록 (`BuiltTransactionListModal`) | `연식` → **건축연도** · 계약일 **YYYY-MM-DD** · **도로명·매수·매도·거래유형** 컬럼 추가 |
| 복합 API/CSV | `building_year` 파생(계약연도−연식) · CSV 헤더 동기화 |
| 주거 집합 거래목록 | 기존 UI에 컬럼 있음 — 데이터만 백필 대기 |

데이터가 채워지기 전까지 해당 셀은 **`—`** 로 표시된다.

---

## 2. 공통 원칙

| 항목 | 결정 |
|------|------|
| 실행 시점 | **별도 운영 창** — 월간 갱신·Profile 작업과 겹치지 않게 |
| ingest SSOT | **`raw/raw base/{유형}_2021_2026`** MOLIT CSV only (GUKTO xlsx **금지**) |
| DB 전략 | 작업 DB에서 **유형별 TRUNCATE → 재적재** → mart 재빌드 → **`pg_dump` Promote** |
| Promote | 로컬 fill-rate 검증 **통과 후** VPS 교체 (운영자 지시) |
| UI | **재적재 전에도 배포 가능** — 컬럼·API 스키마 선반영 |

---

## 3. 주거 집합 4유형 — 재적재 계획

상세 설계는 [`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](./COLLECTIVE_LEDGER_REBUILD_PLAN.md) 를 따른다. 여기서는 **백필 목적·실행 순서·검증**만 요약한다.

### 3.1 목표 필드

| 컬럼 | 출처 (MOLIT) | DDL |
|------|--------------|-----|
| `buyer_type` | 유형별 col index — `molit_schemas.py` | `db/026_collective_tx_display_columns.sql` ✅ |
| `seller_type` | 동일 | ✅ |
| `deal_type` | 동일 | ✅ |
| `contract_date` | 계약년월일 | 기존 컬럼 — raw ingest 시 완전 채움 |
| `road_name` | 도로명 | 기존 |

### 3.2 파이프라인 경로

```
raw/raw base/{아파트|연립다세대|오피스텔|분양입주권}_2021_2026/*.csv
  → pipeline/collective/refine.py (_extract_raw, molit_schemas)
  → pipeline/collective/import_refined.py  (또는 raw 직접 ingest 경로)
  → collective_transactions
```

**사전 확인 (착수 전 30분):**

1. `refine.py` / `REFINED_COL_MAP` 이 **raw base CSV** 를 default로 쓰는지 확인  
2. **유형 1개·시도 1개·최근 연도(예: 2025)** 스모크 ingest → §3.4 **매핑 검증(import fidelity) ≥ 95%** 확인  
3. legacy xlsx 경로가 default가 아니면 **코드 수정 후** 본 작업 착수

> **원문 한계:** MOLIT CSV에 매수·매도 컬럼이 있어도 **2021~2023대는 값이 `-`인 행이 대부분**이고, **2024~2025는 `개인`/`법인` 등으로 채워지는** 연도가 있다. 전체 재적재 후 DB `buyer_type` 절대 채움률(예: ~40–50%)은 **ingest 실패가 아니라 원문 미공개 구간**일 수 있다.

### 3.3 실행 순서

| Step | 작업 | 명령·스크립트 (예) |
|------|------|-------------------|
| 1 | DDL 확인 | `psql … -f db/026_collective_tx_display_columns.sql` (이미 적용 시 skip) |
| 2 | **유형별 TRUNCATE** | `apartment` → `rowhouse` → `officetel` → `presale` 순 |
| 3 | ingest 4유형 | `import_refined.py` (raw base, 2021–2026 전국) |
| 4 | region sync | `sync_region_codes` · `attach_beopjungri_codes` (SOP) |
| 5 | mart | `build_collective_building_stats.py` · rolling buckets · market_stats |
| 6 | fill-rate SQL | §3.4 |
| 7 | Promote | `pg_dump` → VPS `collective_stats` 교체 |

### 3.4 검증 — 두 가지 지표 (혼동 금지)

| 지표 | 질문 | 합격 기준 | 용도 |
|------|------|-----------|------|
| **A. 매핑 검증 (import fidelity)** | 원문에 값이 있는 셀을 DB에 제대로 넣었는가? | **≥ 95%** | 스모크·Promote **게이트** |
| **B. 절대 채움률 (population coverage)** | 전체 valid 거래 중 몇 %에 값이 있는가? | **원문 CSV와 동일 수준** (목표치 없음) | 기대치·UI 안내용 |

**95%는 A만 해당한다.** B는 MOLIT가 `-`/공란으로 두었거나 legacy ingest 행이 섞이면 **재적재만으로 95%에 도달하지 않는다.**

#### 3.4.1 A — 매핑 검증 (스모크·Promote 게이트)

**대상 파일:** 유형별 **최근 연도 1개** (예: `서울특별시_아파트_매매_2025.csv`). 구(2021) 파일은 원문 `-` 비율이 높아 매핑 검증용으로 부적합.

**방법:** 스모크 ingest 후, **같은 파일**을 `refine.py`로 파싱한 raw non-empty 건수와 DB 적재 건수를 비교.

```powershell
# ch2_Macro 루트
py pipeline/collective/verify_import_fidelity.py apartment `
  "raw/raw base/아파트_2021_2026/서울특별시_아파트_매매_2025.csv"
```

또는 `verify_import_fidelity.py` 내부와 동일하게 `refine_dataframe(..., input_kind="raw")` 적용 **후 생존 행** 기준으로 `work[col].notna()` vs `refined[col].notna()` 를 비교한다 (취소·면적 필터로 빠진 행은 분모에서 제외).

**합격:** `buyer_type` · `seller_type` · `deal_type` 각각 **import fidelity ≥ 95%**.  
`src_nonempty=0` 이면 원문에 값이 없어 100%로 통과하지만 **매핑 검증으로는 무의미** — 반드시 **최근 연도** 파일 사용.  
Promote 전 **유형별 최근 연도 파일 1개씩** 실행.

#### 3.4.2 B — 절대 채움률 (정보용, Promote 게이트 아님)

```sql
-- 유형별 매수·매도·거래유형 절대 채움률 (전체 valid 거래)
SELECT asset_type,
       COUNT(*) AS n,
       ROUND(100.0 * COUNT(buyer_type)  / NULLIF(COUNT(*),0), 2) AS buyer_pct,
       ROUND(100.0 * COUNT(seller_type) / NULLIF(COUNT(*),0), 2) AS seller_pct,
       ROUND(100.0 * COUNT(deal_type)   / NULLIF(COUNT(*),0), 2) AS deal_pct
FROM collective_transactions
WHERE is_valid = true
GROUP BY 1 ORDER BY 1;
```

**기대:** 2021–2026 전국 재적재 후 `buyer_pct`는 **유형·연도 혼합에 따라 ~40–60%대**일 수 있다 (2026-06 실측: 아파트 ~50%, 연립·오피스텔·분양은 유형별 상이).  
**합격/불합격 판정에 쓰지 않는다.** UI는 결측 시 `—` 표시.

**참고 (원문 CSV 실측, 서울):**

| 파일 | buyer | seller |
|------|-------|--------|
| 아파트 2021 | ~0% (`-`) | ~0% |
| 아파트 2025 | ~100% | ~100% |

### 3.5 소요 시간 (추정)

| 단계 | 시간 |
|------|------|
| ingest 4유형 (~325만 행) | **1–1.5h** |
| building_stats · rolling · market | **2–3h** |
| Promote·스모크 | **0.5–1h** |
| **합계** | **약 4–6h** |

---

## 4. 복합(일반) 3유형 — 재적재 계획

Phase A ingest는 2026-06-22 로컬 완료([`BUILT_LEDGER_REBUILD_PLAN.md`](./BUILT_LEDGER_REBUILD_PLAN.md))했으나, **프로덕션 VPS는 legacy 원장**이거나 Promote 미반영으로 표시 컬럼이 비어 있다. **MOLIT 경로로 전량 재적재 + Promote** 가 필요하다.

### 4.1 목표 필드

| 컬럼 | MOLIT 매핑 | DDL | ingest |
|------|------------|-----|--------|
| `display_address` | 규칙 B (addr3·4·5·번지·도로명) | `db/028` ✅ | `import_molit.py` ✅ |
| `road_name` | 도로명 col | `db/028` ✅ | ✅ |
| `road_width_label` | 도로조건 원문 | `db/028` ✅ | ✅ |
| `deal_type` | 거래유형 col | `db/028` ✅ | ✅ |
| `contract_date` | 계약년월일 | 기존 | ✅ |
| `building_year` | 건축년도 col | **신규 `db/029` (보류)** | `refine_built.py` 파생 → persist |
| `buyer_type` | **MOLIT 일반 3유형 CSV에 없음** | **신규 nullable (보류)** | 소스 확인 후 |
| `seller_type` | **동일** | **신규 nullable (보류)** | 소스 확인 후 |

**UI `건축연도`:** 재적재 전까지 API·프론트에서 `contract_year − building_age` 로 **파생 표시**. 재적재 시 `building_year` 컬럼 persist 권장.

**매수·매도:** 현재 `pipeline/built/molit_schemas.py` 에 col index **없음**. UI·API 컬럼만 선반영; MOLIT 컬럼 추가·매핑 확인 후 DDL·ingest 확장.

### 4.2 파이프라인 경로

```
raw/raw base/{상업업무|공장창고|단독다가구}_2021_2026/*.csv
  → pipeline/built/refine_built.py
  → pipeline/built/import_molit.py    ← import_refined.py 사용 금지
  → built_transactions
```

상업·공장: **`유형 = 일반`** 필터. 단독: 전량.

### 4.3 착수 전 DDL (1회)

```sql
-- db/029_built_tx_display_backfill.sql (작성·적용은 재적재 착수 시)
ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS building_year SMALLINT;

ALTER TABLE built_transactions
    ADD COLUMN IF NOT EXISTS buyer_type  VARCHAR(20),
    ADD COLUMN IF NOT EXISTS seller_type VARCHAR(20);

COMMENT ON COLUMN built_transactions.building_year IS 'MOLIT 건축년도 (건축연도 UI SSOT)';
```

`import_molit.py` INSERT 목록에 `building_year` 추가 (buyer/seller는 소스 확인 후).

### 4.4 실행 순서

| Step | 작업 |
|------|------|
| 1 | `db/028` · `db/029` 적용 |
| 2 | `built_transactions` TRUNCATE (또는 3유형 DELETE) |
| 3 | `py pipeline/rebuild_built_ledger.py` 또는 유형별 `import_molit.py` |
| 4 | `log_mapping_coverage` — display·road·deal fill-rate |
| 5 | (Phase B) built rolling mart — 필요 시 |
| 6 | Promote → VPS `built_stats` |

### 4.5 검증 SQL

```sql
SELECT asset_type,
       COUNT(*) AS n,
       ROUND(100.0 * COUNT(display_address)   / NULLIF(COUNT(*),0), 2) AS addr_pct,
       ROUND(100.0 * COUNT(road_name)         / NULLIF(COUNT(*),0), 2) AS road_pct,
       ROUND(100.0 * COUNT(road_width_label)  / NULLIF(COUNT(*),0), 2) AS road_w_pct,
       ROUND(100.0 * COUNT(deal_type)         / NULLIF(COUNT(*),0), 2) AS deal_pct,
       ROUND(100.0 * COUNT(building_year)     / NULLIF(COUNT(*),0), 2) AS bld_yr_pct
FROM built_transactions
GROUP BY 1 ORDER BY 1;
```

**합격 기준:** `display_address`·`road_width_label`·`deal_type` **≥ 90%** (단독은 `zone_type` 없음 — addr·road 위주).

### 4.6 소요 시간 (추정)

| 단계 | 시간 |
|------|------|
| ingest 3유형 (~416k 행) | **20–40분** |
| mart (필요 시) | **1–2h** |
| Promote·스모크 | **0.5h** |
| **합계** | **약 2–3h** |

---

## 5. 권장 실행 순서 (통합 창)

두 영역은 **독립 DB**(`collective_stats` / `built_stats`)이므로 **병렬 가능**. 다만 디스크·CPU 부하를 고려해 **순차** 권장:

```
[1] 복합 3유형 재적재 (짧음, ~416k)  → fill-rate OK → Promote
[2] 주거 4유형 재적재 (~325만)      → mart           → Promote
[3] 프로덕션 스모크 — 거래목록 UI에서 매수·매도·도로명·건축연도 확인
```

**총 wall-clock (순차):** **약 6–9h** (mart 범위에 따라 변동).

---

## 6. 배포 (UI — 재적재와 분리)

재적재 **이전에** 복합 프론트·백엔드 배포 가능:

```powershell
.\deploy\scripts\deploy-from-windows.ps1 -Scope built -SkipPush   # push 후
```

주거 집합 거래목록 UI는 이미 컬럼 존재 — **collective scope 배포만** 필요 시 `-Scope collective`.

---

## 7. 완료 체크리스트

- [ ] 주거: 4유형 ingest smoke — **최근 연도** 파일 기준 buyer/seller/deal **import fidelity ≥ 95%** (§3.4.1)
- [ ] 주거: 전량 재적재 후 §3.4.2 절대 채움률 기록 (Promote 게이트 아님)
- [ ] 주거: mart 재빌드 · Promote
- [ ] 복합: `import_molit` 전량 · display/road/deal ≥ 90%
- [ ] 복합: `db/029` + `building_year` persist (선택)
- [ ] 프로덕션 거래목록 — 계약일 전체 일자 · 건축연도 · 도로명 · 거래유형 표시
- [ ] [`DECISIONS.md`](./DECISIONS.md) D-027 상태 → **완료** 로 갱신

---

## 8. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-06-25 | 초안 — 보류 결정, UI 선반영, 주거·복합 백필 절차 통합 문서화 |
| 2026-06-25 | §3.4 — 95%를 **매핑 검증(import fidelity)** 으로 명확화; 절대 채움률은 원문 한계 반영·정보용으로 분리 |
