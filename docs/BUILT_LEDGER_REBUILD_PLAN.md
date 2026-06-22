# 복합부동산(일반 3유형) 원장 전면 재구축 계획

> **작성:** 2026-06-21  
> **상태:** Phase A 완료 (2026-06-22) — 전국 ingest 419,040건  
> **범위:** **Phase A — 원장 DB만** — `commercial` · `factory` · `detached` (MOLIT `유형=일반` 또는 단독 전량)  
> **비범위 (Phase B 이후):** UI/UX, 회귀 API·엔진 변경, 통합 유형(`all`), twin cross-region, 사전통계 mart  
> **관련:** [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) · [`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](./COLLECTIVE_LEDGER_REBUILD_PLAN.md) · [`DECISIONS.md`](./DECISIONS.md) D-024 · [`BUILT_HANDOFF_AND_ROADMAP.md`](./BUILT_HANDOFF_AND_ROADMAP.md) · D-001 `as_of_month`

---

## 1. 목표

| # | 목표 | Phase |
|---|------|-------|
| G1 | `raw/raw base/{상업업무\|공장창고\|단독다가구}_2021_2026` CSV 기준 **`built_transactions` 전량 재적재** | A |
| G2 | **GUKTO 정제 xlsx 경로 폐기** — ingest SSOT = MOLIT raw base only | A |
| G3 | **도로조건 원문** 저장 (`road_width_label`), 기존 **`road_code` 정수 변환 삭제** | A |
| G4 | **주소 표시용 컬럼** — 법정리(`addr5`)·번지(마스킹)·도로명까지 ingest (`display_address` 규칙 B) | A |
| G5 | **해제 거래 제외**, **semantic hash dedupe** 유지 (`ON CONFLICT DO NOTHING`) | A |
| G6 | **`region_codes`** — 토지·집합 재구축과 동일 **`land_stats` → sync** + `attach_beopjungri_codes` | A |
| G7 | **`contract_year` / `contract_month` / `contract_date`** 완전 채움 (향후 `as_of_month`·3·5년 mart 대비) | A |
| G8 | Promote는 **로컬 검증 후** — VPS `built_stats` 교체는 운영자 지시 시 | A 이후 |

---

## 2. 의사결정 요약 (2026-06-21 확정)

### 2.1 데이터·적재

| 항목 | 결정 |
|------|------|
| 재적재 방식 | **전량 재적재** — `built_transactions` TRUNCATE(또는 유형별 DELETE) 후 raw base ingest |
| 입력 SSOT | `raw/raw base/` MOLIT CSV **만**. `C:\startcoding\GUKTO\` 및 legacy xlsx **무시** |
| 유형 필터 | 상업·공장: **`유형 = 일반`** (`집합` → `collective_commercial_*`, D-018). 단독: **전량** |
| 연도 범위 | **2021~2026** (폴더 내 시도별 CSV 전부) |
| 해제 | **`해제사유발생일`** 이 유효 날짜 패턴인 행 **제외** (집합 `refine.py` cancel regex 패턴 참고) |
| dedupe | **semantic `transaction_hash`** — 기존 `import_refined._tx_hash` 공식 **유지** |
| 도로 | MOLIT **`도로조건`** → `road_width_label` (원문). **`road_code` = NULL** (컬럼 deprecated, DDL 유지·회귀 Phase B에서 더미 전환) |
| GUKTO fallback | **제거** (코드 default `molit` only) |

### 2.2 주소·표시 (ingest 시점 — UI는 Phase B)

| 항목 | 결정 |
|------|------|
| 표시 규칙 **B** | **읍면동 + 법정리(`addr5`) + 번지(마스킹 유지) + 도로명** |
| `display_address` | ingest 조합 SSOT (Phase B 목록 1열) |
| 번지 | MOLIT `8**` 등 **마스킹 그대로** `lot_number` |
| addr 정규화 | **D-015** — 리는 항상 `addr5`, 구(區) 없는 시 구조 반영 |

**`display_address` 조합 (SSOT):**

```
{addr3} {addr4} {addr5} {lot_number} ({road_name})
```

- `addr4`/`addr5`/`road_name` 없으면 해당 토큰 생략 (연속 공백 정리)
- 괄호 `(도로명)` — 도로명 없으면 괄호 전체 생략

### 2.3 회귀·분석 (Phase B — 이번 작업 **비범위**, 방향만 기록)

| 항목 | 결정 |
|------|------|
| 집합부동산 회귀 | **참고하지 않음** (단가·cluster grain·효용지수 패턴 이식 **금지**) |
| 복합부동산 회귀 | **기존 `backend/app/built/regression`** 큰 틀 유지 |
| 종속변수 | **총액(만원)** — 단가(㎡당) **아님** |
| 기본 추정 | **선형 OLS (총액)** |
| 옵션 (후속) | **log(총액) semi-log** — UI 토글은 Phase B |
| 도로 변수 (후속) | `road_width_label` **범주 더미** (연속 `road_code` **폐기**) |
| 통합 회귀 (후속) | `asset_type` 더미 + 단독 `zone_type` 결측 처리 — [`BUILT_HANDOFF_AND_ROADMAP.md`](./BUILT_HANDOFF_AND_ROADMAP.md) 백로그 |

### 2.4 시간 축 — Macro 공통 정책 (D-001)

ch2_Macro 전역: **`as_of_month` + `window_years`(3·5)** 롤링.

| 개념 | 동작 |
|------|------|
| `as_of_month` | “이 데이터가 **어느 시점까지** 반영됐는지” (예: `2026-05-01` = 2026년 4월 말 거래까지) |
| `window_years=3` | 분석·표본 = **`contract_date` ∈ [as_of − 36개월, as_of]** 구간 |
| `window_years=5` | 동일, 60개월 |
| 연도 from/to (UI) | **달력 연도 필터** — `as_of`와 별개 (D-001 부록) |
| 2026 CSV | **원장에는 전량 보관**; mart·live 분석 시 `as_of` **이후 월** 거래는 롤링 창에서 **제외** (집합·토지와 동일) |

**Phase A:** mart 테이블(`built_*_stats`)은 **아직 없음**. 원장에 **`contract_date`** 를 정확히 넣어 두면 Phase B에서 집합 `collective_building_rolling_stats` 패턴으로 mart 추가 가능.

운영 `as_of` 정상값·Promote 타이밍: [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) §12 · [`MONTHLY_UPDATE_SOP.md`](./MONTHLY_UPDATE_SOP.md).

---

## 3. 전략 요약

```
[입력]  raw/raw base/상업업무_2021_2026/*.csv   → asset_type=commercial, 유형=일반
        raw/raw base/공장창고_2021_2026/*.csv   → asset_type=factory,   유형=일반
        raw/raw base/단독다가구_2021_2026/*.csv → asset_type=detached

[DB]    built_stats
        built_transactions  ← 전량 재적재
        region_codes        ← land_stats sync (집합과 동일)

[파이프라인 — Phase A]
  sync region_codes from land
  → molit ingest (3유형)
  → attach_beopjungri_codes + D-015 addr
  → semantic hash INSERT
  → log_mapping_coverage

[미구현 — Phase B]
  built rolling mart (3·5y) · API · frontend-built · 회귀 road_width 더미 · 통합 유형
```

**DB 전략:** 집합 주거 재구축처럼 로컬 **`built_stats` 직접 TRUNCATE** 후 재적재. VPS Promote 전 **`pg_dump` 백업** 필수. (토지 `built_stats_next` 병렬 패턴은 old/new diff 필요 시에만 선택.)

**토지·집합 파이프라인은 건드리지 않음.**

---

## 4. 입력 데이터

### 4.1 폴더·파일

| 폴더 | `asset_type` | 파일 패턴 | 행 필터 |
|------|--------------|-----------|---------|
| `raw/raw base/상업업무_2021_2026/` | `commercial` | `{시도}_상업업무_매매_{2021..2026}.csv` | `유형 == 일반` |
| `raw/raw base/공장창고_2021_2026/` | `factory` | `{시도}_공장창고_매매_{2021..2026}.csv` | `유형 == 일반` |
| `raw/raw base/단독다가구_2021_2026/` | `detached` | `{시도}_단독다가구_매매_{2021..2026}.csv` | 없음 |

- 인코딩: **CP949**
- 헤더: **skiprows=15** (면책 15행 — [`MOLIT_CSV_COLLECTOR_WARNINGS.md`](./MOLIT_CSV_COLLECTOR_WARNINGS.md))
- 장기(2010~2020): **v1 제외** — 필요 시 Phase 2 `built_annual_stats` backfill (토지·집합 long term 패턴)

### 4.2 MOLIT 컬럼 매핑 (iloc — `pipeline/built/molit_schemas.py` SSOT 예정)

**상업업무 · 공장창고** (동일 스키마, 21열):

| iloc | CSV 헤더 | DB 컬럼 |
|------|----------|---------|
| 1 | 시군구 | 파싱 → `addr1`~`addr5` |
| 2 | 유형 | 필터 (`일반`) |
| 3 | 번지 | `lot_number` |
| 4 | 도로명 | `road_name` |
| 5 | 용도지역 | `zone_type` (detached ingest N/A) |
| 6 | 건축물주용도 | `building_use` |
| 7 | 도로조건 | **`road_width_label`** |
| 8 | 연면적(㎡) | `gross_area` |
| 9 | 대지면적(㎡) | `land_area` |
| 10 | 거래금액(만원) | `price` |
| 11 | 층 | `floor` |
| 14 | 계약년월 | `contract_year`, `contract_month`, `contract_date` |
| 15 | 건축년도 | `building_age` / `building_year` 파생 |
| 16 | 해제사유발생일 | **drop if matched** |
| 17 | 거래유형 | `deal_type` (선택) |

**단독다가구** (17열):

| iloc | CSV 헤더 | DB 컬럼 |
|------|----------|---------|
| 1 | 시군구 | `addr1`~`addr5` |
| 2 | 번지 | `lot_number` |
| 3 | 주택유형 | `building_use` |
| 4 | 도로조건 | **`road_width_label`** |
| 5 | 건물면적(㎡) | `gross_area` |
| 6 | 대지면적(㎡) | `land_area` |
| 7 | 계약년월 | `contract_*` |
| 8 | 건축년도 | `building_age` |
| 13 | 도로명 | `road_name` |
| 14 | 해제사유발생일 | **drop** |
| — | (없음) | `zone_type = NULL` |

**`road_width_label` 값 예:** `8m이하`, `12m미만`, `25m미만`, `25m이상`, `-` → `-`/빈값은 **NULL**.

### 4.3 선행 마스터 — `region_codes`

| 테이블 | 조치 |
|--------|------|
| `region_codes` | **`sync_region_codes_from_land(built_engine, land_engine)`** — [`pipeline/built/import_refined.py`](../pipeline/built/import_refined.py) 기존 함수, **`--refresh-region-codes`** 시 TRUNCATE+복사 |
| 전제 | `land_stats.region_codes` 가 최신 (`seed_region_codes.py` 또는 토지 재구축 반영본) |

집합 재구축([`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](./COLLECTIVE_LEDGER_REBUILD_PLAN.md) §4.3)과 **동일 정책**.

---

## 5. 산출물 — DB·스키마

### 5.1 DDL migration (신규)

파일 예: **`db/028_built_ledger_rebuild.sql`**

| 컬럼 | 타입 | 비고 |
|------|------|------|
| `road_width_label` | VARCHAR(32) | MOLIT 도로조건 원문 |
| `road_name` | VARCHAR(64) | 도로명 |
| `display_address` | VARCHAR(256) | §2.2 조합 B |
| `deal_type` | VARCHAR(40) | 거래유형 (선택) |
| `needs_review` | BOOLEAN DEFAULT FALSE | 매핑 실패 |
| `mapping_notes` | VARCHAR(128) | D-012 스타일 |

**변경·폐기:**

| 컬럼 | Phase A |
|------|---------|
| `road_code` | **항상 NULL** — COMMENT `deprecated, use road_width_label` |
| `housing_type` | 단독 `building_use`와 중복 시 **`building_use` SSOT** |

기존 `015_built_transactions.sql` grain 유지: `asset_type` ∈ {`commercial`,`factory`,`detached`}, `deal_form='general'`.

### 5.2 `transaction_hash` (semantic dedupe)

기존 공식 **유지** ([`pipeline/built/import_refined.py`](../pipeline/built/import_refined.py) `_tx_hash`):

```
SHA-256(
  asset_type | addr1 | addr2 | addr3 | addr4 | addr5 | lot_number |
  contract_year | price | gross_area | building_use
)
```

- `INSERT … ON CONFLICT (transaction_hash) DO NOTHING`
- 파일·행번호 **미포함** (토지 semantic dedupe와 동일 철학, 집합 주거 **행번호 hash와 다름**)

### 5.3 ingest 후 검증 로그

| 지표 | 목표 |
|------|------|
| `log_mapping_coverage` | beopjungri 매칭률 — manifest 기록 |
| 해제 제외 건수 | 유형별 before/after |
| `road_width_label` NULL률 | `-` 처리 확인 |
| `display_address` non-null | >95% (도로명 결측 허용) |
| `contract_date` non-null | >99% |
| 유형별 건수 | commercial / factory / detached 스냅샷 JSON |

---

## 6. 작업 Phase (Phase A만)

### Phase 0 — 준비

| # | 작업 |
|---|------|
| 0-1 | `pg_dump` 현행 `built_stats` → `backups/built_stats_pre_rebuild.dump` |
| 0-2 | DDL `028` 적용 |
| 0-3 | `pipeline/built/molit_schemas.py` + `refine_built.py` (해제·유형 필터·주소 파싱) |
| 0-4 | `pipeline/built/import_molit.py` (또는 `import_refined.py` molit 전환) |
| 0-5 | `pipeline/rebuild_built_ledger.py` 오케스트레이터 |

### Phase 1 — smoke

| # | 작업 |
|---|------|
| 1-1 | 서울 2021 CSV 1파일 × 3유형 ingest |
| 1-2 | hash dedupe·해제·road_width_label spot check |
| 1-3 | `display_address` 샘플 20건 육안 |

### Phase 2 — 전국 ingest

| # | 작업 |
|---|------|
| 2-1 | `TRUNCATE built_transactions` (또는 3유형 DELETE) |
| 2-2 | 3폴더 × 17시도 × 6연도 ingest |
| 2-3 | coverage manifest → `logs/built_rebuild_manifest.json` |

### Phase 3 — 검증 (API/UI 없이 SQL)

| # | 작업 |
|---|------|
| 3-1 | 유형·연도·시도별 COUNT |
| 3-2 | legacy GUKTO 대비 건수 order-of-magnitude (참고만, SSOT 불일치 정상) |
| 3-3 | `contract_date` max vs 2026 CSV — as_of 정책 문서화 |

**Promote (VPS):** [`BUILT_MONTHLY_UPDATE_SOP.md`](./BUILT_MONTHLY_UPDATE_SOP.md) · `promote_built_restore.sh` — **Phase A 완료 + Phase B UI 최소 smoke 후** 권장.

---

## 7. Phase B 백로그

| 항목 | 상태 | 내용 |
|------|------|------|
| UI 거래목록 | [x] | `display_address` 컬럼, `road_width_label` |
| 회귀 | [x] | `road_width_label` dummy, linear + log 옵션 |
| 통합 유형 | [x] | `asset_type=all`, 유형 dummy (단독 zone 제외) |
| mart | [x] | `built_scope_stats` @ `(as_of_month, window_years)` |
| twin cross-region | [ ] | 쌍둥이 beopjungri scope 확장 (후속) |
| 월간 cycle | [x] | `run_built_monthly_cycle.py` → `import_molit.py` |
| Promote VPS | [ ] | **의도적 보류** — 로컬 smoke 후 별도 |

---

## 8. 리스크·완화

| 리스크 | 완화 |
|--------|------|
| GUKTO vs MOLIT 건수 불일치 | **MOLIT SSOT** — manifest에 legacy count 참고만 |
| `road_code` API·UI 깨짐 | Phase A 후 API는 old NULL 허용; Phase B에서 dummy 전환 |
| beopjungri 매칭률 | `needs_review` + [`FOLLOW_UP_LAND_TX_MAPPING.md`](./FOLLOW_UP_LAND_TX_MAPPING.md) |
| TRUNCATE 실수 | ingest 전 **pg_dump**; VPS는 Promote 전까지 old dump 유지 |
| 집합 commercial과 유형 중복 | 상업·공장 **일반만** — D-018 분리 유지 |

---

## 9. 체크리스트 (운영자)

```
Phase 0  [x] backup dump  [x] DDL 028  [x] molit_schemas  [x] refine_built  [x] orchestrator
Phase 1  [x] Seoul smoke ×3  [x] hash/cancel/road spot
Phase 2  [x] TRUNCATE  [x] national ingest  [x] manifest → logs/built_rebuild_manifest.json
Phase 3  [x] SQL counts  [x] contract_date  [x] mapping coverage log
Phase B  [x] UI display_address  [x] regression road_width/log/all  [x] scope_stats mart  [x] monthly→molit
Promote  [ ] (later) VPS dump/restore  [ ] built API smoke
```

---

## 10. 관련 경로

| 경로 | 역할 |
|------|------|
| `db/015_built_transactions.sql` | 현행 원장 DDL |
| `db/028_built_ledger_rebuild.sql` | *(예정)* Phase A migration |
| `pipeline/built/import_refined.py` | legacy GUKTO — **Phase A 후 default 비활성** |
| `pipeline/built/import_molit.py` | *(예정)* MOLIT ingest |
| `pipeline/rebuild_built_ledger.py` | *(예정)* 오케스트레이터 |
| `backend/app/built/regression/engine.py` | Phase B — 총액 OLS (현행 유지) |
| `frontend-built/` | Phase B |

---

## 11. 다음 액션

1. DDL `028` 초안 + `molit_schemas.py` / `refine_built.py` 구현  
2. 서울 smoke ingest  
3. 전국 재적재 + manifest  
4. Phase B 착수 전 — 본 문서 §7 항목 별도 티켓
