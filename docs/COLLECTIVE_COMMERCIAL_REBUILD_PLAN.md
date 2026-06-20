# 집합부동산(비주거 — 상가·공장) 원장·UI 재구축 계획

> **작성:** 2026-06-19  
> **상태:** **Phase 0~4 완료** (2026-06-20) — ingest·mart·회귀/효용지수·코호트·장기 추세  
> **범위:** `collective_shop` · `collective_factory` — **집합(`유형=집합`)만**  
> **비범위:** `일반` 행(→ `built_stats`), 주거 4유형(`collective_transactions`), **건물 grain(`building_key`) — 계획 제외 (D-020)**  
> **관련:** [`COLLECTIVE_COMMERCIAL_DESIGN.md`](./COLLECTIVE_COMMERCIAL_DESIGN.md) · [`COLLECTIVE_LEDGER_REBUILD_PLAN.md`](./COLLECTIVE_LEDGER_REBUILD_PLAN.md) · [`COLLECTIVE_HANDOFF.md`](./COLLECTIVE_HANDOFF.md) · [`DECISIONS.md`](./DECISIONS.md) D-018

---

## 1. 목표

| # | 목표 | 상태 |
|---|------|------|
| G1 | `raw/raw base/{상업업무\|공장창고}_2021_2026` CSV 기준 **집합 행만** 재적재 | ✅ |
| G2 | **도로명(`cluster_key`) grain** — 유일 분석 단위 (건물 grain **미계획**) | ✅ |
| G3 | 주거 재구축과 동일 **as_of_month + 롤링 3·5년** 통계 철학 (cluster mart) | ✅ |
| G4 | UI·고급분석(효용지수·회귀)은 주거와 **동일 UX 패턴**, grain만 도로 cluster | ✅ |
| G5 | 주거 P0~P1-B 개선(시점 더미·HC3·VIF·로그/선형 비교)을 **commercial 회귀·효용지수에 이식** | ✅ |
| G6 | **장기 추세 탭·2010~ annual backfill** | ✅ Phase 4 |
| G7 | Promote는 로컬 검증 후 — VPS 교체는 별도 | ✅ (로컬 finish 스크립트) |

---

## 2. 주거 vs 비주거 — 핵심 차이

| 항목 | 주거 (`collective_transactions`) | 비주거 (`collective_commercial_*`) |
|------|----------------------------------|-------------------------------------|
| **원본 SSOT** | `raw/raw base/{아파트\|연립\|오피스텔\|분양}_2021_2026` | `raw/raw base/{상업업무\|공장창고}_2021_2026` |
| **집합 식별** | 다운로드 유형 자체가 집합 (유형 컬럼 없음) | **`유형 == 집합`** 필터 (일반 → built) |
| **분석 grain** | `building_key` (단지/건물) | **`cluster_key` = hash(addr1~4 + road_name)** |
| **목록 단위** | 건물(유형×building_key) | **도로 cluster** |
| **코호트** | 다중 건물(최대 10) | **다중 도로 cluster** (통합분석·회귀·효용지수·장기 추세) |
| **mart** | `building_stats` · `rolling_stats` · `annual_stats` | `cluster_stats` · `cluster_rolling_stats` · **`cluster_annual_stats`** |
| **장기 추세** | long term CSV → annual mart | long term CSV → **`collective_cluster_annual_stats`** (집합만) |

설계 SSOT(도로 cluster 1단계): [`COLLECTIVE_COMMERCIAL_DESIGN.md`](./COLLECTIVE_COMMERCIAL_DESIGN.md) §2~3.

---

## 3. 전략 요약

```
[입력]  raw/raw base/상업업무_2021_2026/*.csv
        raw/raw base/공장창고_2021_2026/*.csv
        ※ 유형=집합만 · 도로명 필수 · 해제 거래 제외

[DB]    collective_stats (기존 commercial_* 테이블)
        commercial_clusters + collective_commercial_transactions

[파이프라인]
  probe_molit_raw.py (집합/일반 비율)
  → import_refined.py --source molit [--truncate]
  → region_sigungu_meta (--collective)
  → build_collective_cluster_stats.py + rolling + annual (2021~)
  → ingest_collective_commercial_long_term_annual.py (2010~2020)

[UI]    frontend-collective/CommercialApp.tsx
        grain=cluster_key · 모달 탭 주거와 정렬(장기 추세 = 마지막 탭)
```

**Legacy:** 기존 ingest는 `C:\startcoding\GUKTO` xlsx (`--source gukto`). 재구축 SSOT는 **MOLIT raw base CSV**.

---

## 4. 입력 데이터

### 4.1 1차 소스 — 2021~2026

**probe 스캔 (2026-06-19, `probe_molit_raw.py`):**

| 유형 | 파일 | 전체 행 | 집합 | 일반 |
|------|------|---------|------|------|
| 상업업무 | 102 | 380,199 | **276,698** | 103,501 |
| 공장창고 | 102 | 78,371 | **34,098** | 44,273 |

**Phase 1 ingest 결과 (2026-06-19, `rebuild_collective_commercial.py`):**

| asset_type | 거래 | cluster | 비고 |
|------------|------|---------|------|
| `collective_shop` | **241,508** | 19,194 | raw 집합 대비 −35,190 (도로명 없음·해제·가격/면적 invalid) |
| `collective_factory` | **31,132** | 1,000 | raw 집합 대비 −2,966 |
| **합계** | **272,640** | **20,194** | contract_year 2021~2026 |

| 폴더 | asset_type | 파일 패턴 | MOLIT preamble |
|------|------------|-----------|----------------|
| `raw/raw base/상업업무_2021_2026/` | `collective_shop` | `{시도}_상업업무_매매_{2021..2026}.csv` | `실거래구분 : 상업업무용(매매)` |
| `raw/raw base/공장창고_2021_2026/` | `collective_factory` | `{시도}_공장창고_매매_{2021..2026}.csv` | `실거래구분 : 공장창고등(매매)` |

- **skiprows=16** (주거와 동일 preamble)
- **20 columns** — 주거와 달리 **`유형`(iloc 2)** 존재

### 4.2 집합 선별 규칙

```python
df = read_csv(..., skiprows=16)
collective = df[df["유형"].astype(str).str.strip() == "집합"]
# 일반 → built_stats (별도 파이프라인, 본 재구축 범위 밖)
```

**품질 게이트 (ingest):**

| 조건 | 처리 |
|------|------|
| `도로명` 비어 있음 | **제외** (cluster_key 불가) |
| `전용/연면적` ≤ 0 또는 `거래금액` ≤ 0 | 제외 |
| `해제사유발생일` 유효 날짜 | 제외 (주거와 동일) |
| `failed/` 하위 파일 | 스캔·ingest **제외** (예: 제주 2023 오류 파일) |

### 4.3 2차 소스 — 장기 추세 ✅ (Phase 4, 2026-06-20)

| 폴더 | 용도 | mart |
|------|------|------|
| `raw/raw long term/상업업무_2010_2020/` | cluster annual backfill (`유형=집합`) | `collective_cluster_annual_stats` |
| `raw/raw long term/공장창고_2010_2020/` | 동일 | 동일 |

- ingest: `pipeline/ingest_collective_commercial_long_term_annual.py` — **contract_year < 2021** 만 upsert
- 2021~: `pipeline/build_collective_cluster_annual_stats.py` — transactions 기준
- API: `GET .../stats/by-year` — 필터 없으면 mart-first (`data_source: mart`)
- UI: `CommercialClusterDetailModal` **장기 추세** 탭 (마지막 탭) + 코호트 병렬 fetch

**로컬 적재 (2026-06-20):** annual **154,466행** (2010~2020: 105,590 · 2021~: 48,876)

---

## 5. MOLIT 컬럼 매핑 (주거 대비)

| iloc | MOLIT 컬럼 | DB / UI | 주거 대응 |
|------|------------|---------|-----------|
| 1 | 시군구 | addr1~5 split | 동일 |
| 2 | **유형** | (필터만) | **없음** |
| 3 | 지번 | lot_number | 번지 |
| 4 | 도로명 | road_name, **cluster_key** | 도로명 |
| 5 | 용도지역 | zone_type | — |
| 6 | 건축물주용도 | building_use | — |
| 7 | 도로조건 | road_width_label | — |
| 8 | 전용/연면적(㎡) | gross_area | exclusive_area |
| 9 | 대지면적(㎡) | land_area | land_area(연립) |
| 10 | 거래금액(만원) | price | price |
| 11 | 층 | floor | floor |
| 12–13 | 매수·매도 | (Phase 1b DDL) buyer/seller | buyer/seller |
| 14–15 | 계약년월·일 | contract_year/month | 동일 |
| 17 | 건축년도 | building_year | building_year |
| 18 | 해제사유발생일 | cancel filter | 동일 |
| 19 | 거래유형 | deal_type | deal_type |

파서 SSOT: `pipeline/collective_commercial/molit_raw_common.py`  
Legacy xlsx 파서: `gukto_raw_shop.py` (동일 iloc)

---

## 6. 산출물 — DB

### 6.1 기존 테이블 (유지)

- `commercial_clusters` — grain: `cluster_key`
- `collective_commercial_transactions` — `cluster_id` FK

DDL: `db/019_collective_commercial.sql`, `db/020_collective_commercial_road_width.sql`

### 6.2 Phase 1b — 표시 컬럼 (주거 026 패턴) ✅

| 컬럼 | 출처 | 비고 |
|------|------|------|
| `buyer_type` | 매수 | `029_collective_commercial_display.sql` |
| `seller_type` | 매도 | |
| `deal_type` | 거래유형 | |

### 6.3 Phase 2 — cluster mart ✅

주거 `collective_building_stats` 대응:

| 테이블 | grain | 용도 |
|--------|-------|------|
| `collective_cluster_stats` | cluster_key × as_of × window(3,5) | **목록** 기본 통계 |
| `collective_cluster_rolling_stats` | cluster × as_of × window × bucket | 모달 **롤링 추세** (장기 탭 대신 1차 핵심) |

1차 ingest 직후에는 **기존처럼 live 쿼리**로도 UI 가능 → mart는 성능·as_of 일관성용.

---

## 7. 산출물 — 백엔드·UI

### 7.1 재사용 (변경 최소)

| 모듈 | 역할 |
|------|------|
| `backend/app/collective_commercial/router.py` | cluster CRUD·stats |
| `cluster_keys.py` | `make_road_cluster_key` — **규칙 유지** |
| `collective/floor_index.py` | 층·면적 효용지수 엔진 |
| `frontend-collective/CommercialApp.tsx` | 목록·필터 |
| `CommercialClusterDetailModal.tsx` | 모달 탭 |

### 7.2 주거에서 이식 (Phase 3)

| 주거 (완료) | commercial 대응 |
|-------------|-----------------|
| 시점(반기) 더미 | `floor_index_regression.py` · `regression/engine.py` |
| HC3 강건 SE | 동일 |
| VIF·조건수 진단 | `CommercialFloorIndexPanel` 표시 |
| 로그/선형 + Duan + MAPE 비교 | `CommercialRegressionPanel` |
| 코호트 유도 메시지 | **다중 도로 cluster** 안내 문구 |
| Analysis gates (n≥50 등) | cluster 단위 동일 threshold |

### 7.3 UI 탭

| 탭 | API | 상태 |
|----|-----|------|
| 추세·요약 (롤링) | `.../stats/rolling` | ✅ mart |
| 단가 분포 | histogram (+ 연도 필터 시 live by-year) | ✅ |
| 거래 목록 | transactions | ✅ (+ buyer/seller/deal_type) |
| 번지별 요약 | addresses (shop) | ✅ |
| 층·면적 효용지수 | floor-index | ✅ + VIF |
| 회귀 | regression/run + predict | ✅ + model compare |
| 장기 추세 | by-year (mart-first) | ✅ annual mart 2010~ |

---

## 8. 구현 Phase

### Phase 0 — 준비 ✅ (2026-06-19)

- [x] 본 계획서
- [x] `molit_raw_common.py` · `molit_raw_shop.py` · `molit_raw_factory.py`
- [x] `import_refined.py --source molit|gukto` (default **molit**)
- [x] `rebuild_collective_commercial.py` 오케스트레이터 골격
- [x] `probe_molit_raw.py` — 집합/일반 건수 스캔
- [x] D-018 결정 기록

### Phase 1 — ingest ✅ (2026-06-19)

```powershell
cd c:\ch2\ch2_Macro\pipeline\collective_commercial
py probe_molit_raw.py

cd c:\ch2\ch2_Macro\pipeline
py rebuild_collective_commercial.py
# 또는
py collective_commercial/import_refined.py --source molit --truncate
```

검증: API `GET /api/collective/commercial/meta/filters` → `contract_years: 2021~2026` · `GET .../clusters?addr1=서울특별시&addr2=강남구`

### Phase 1b — 표시 컬럼 DDL + 거래목록 UI ✅

- DDL `db/029_collective_commercial_display.sql` — `buyer_type`, `seller_type`, `deal_type`
- ingest·API·`CommercialClusterDetailModal` 거래목록 컬럼

### Phase 2 — cluster mart (3·5y + rolling bucket) ✅

- DDL `db/030_collective_cluster_stats.sql`
- `build_collective_cluster_stats.py` · `build_collective_cluster_rolling_stats.py`
- 목록 mart-first (`window_years`), `GET .../stats/rolling`, UI `StatsWindowToggle`

### Phase 3 — 회귀·효용지수 주거 패리티 ✅

- 시점(반기) 더미 · HC3 · VIF/조건수 · log/linear + `model_comparison`
- `CommercialRegressionPanel` · `CommercialFloorIndexPanel`

### Phase 4 — 장기 추세 ✅ (2026-06-20)

- DDL `db/031_collective_cluster_annual_stats.sql`
- `ingest_collective_commercial_long_term_annual.py` — `raw/raw long term`, **집합만**
- `build_collective_cluster_annual_stats.py` — 2021~ from transactions
- API mart-first + `data_source`; UI **장기 추세** 탭 + 코호트
- `rebuild_collective_commercial.py` 연동

---

## 9. 명령 Quick reference

```powershell
# raw base 집합/일반 비율
py pipeline/collective_commercial/probe_molit_raw.py

# 전량 재구축 (MOLIT SSOT + long-term annual)
py pipeline/rebuild_collective_commercial.py

# finish 검증 (Promote 전)
py pipeline/finish_collective_commercial.py --api-base http://127.0.0.1:8000

# legacy GUKTO xlsx (비교·fallback)
py pipeline/collective_commercial/import_refined.py --source gukto --truncate

# UI dev
cd frontend-collective; npm run dev
# http://localhost:5175/collective/commercial/
```

---

## 10. 기존 구현과의 관계

| 자산 | 상태 | 조치 |
|------|------|------|
| Stage 1 MVP (GUKTO xlsx) | 운영/로컬 혼재 가능 | `--source molit --truncate`로 **교체** |
| `building_key` 컬럼 | nullable, 미사용 | **유지(스키마 호환)** — 건물 grain 미구현 |
| `make_cluster_key()` | dead code | 재구축 중 정리 검토 |
| Residential rebuild | **완료** (main) | 패턴·게이트·회귀 UX **템플릿** |
| Regional Profile | 추후 | `commercial_market` · `factory_market` domain |

---

## 11. 리스크·주의

1. **경기 등 혼합 파일** — 집합/일반 비율 지역별 상이 → `probe_molit_raw` 후 ingest
2. **마스킹 번지** — 건물 단위 아님; UI 라벨 유지 ([`COLLECTIVE_COMMERCIAL_DESIGN.md`](./COLLECTIVE_COMMERCIAL_DESIGN.md) §3.4)
3. **as_of_month** — 주거·토지와 동일 `2026-05-01`; 7월 cycle 정상화는 [`LAND_LEDGER_REBUILD_PLAN.md`](./LAND_LEDGER_REBUILD_PLAN.md) §12 참조
4. **일반 행** — 본 ingest에서 제외; built 파이프라인과 **이중 적재 금지** 확인

---

## 12. Promote 전 완료 기준 (로컬)

- [x] 272,640건 ingest · 20,194 clusters
- [x] `collective_cluster_stats` / `rolling_stats` @ as_of `2026-05-01`, windows 3·5
- [x] `collective_cluster_annual_stats` 2010~2026 (long-term + transactions)
- [x] 모달: 롤링 추세 / 분포(기간 필터) / 장기 추세(만년력) 분리
- [x] 코호트: 롤링·히스토그램·거래·회귀·장기 추세
- [x] 회귀 예측구간(PI) · `finish_collective_commercial.py` PASS
- [ ] VPS Promote (운영자 지시 시 — [`deploy/AGENT_DEPLOY_RUNBOOK.md`](../deploy/AGENT_DEPLOY_RUNBOOK.md))

---

*최종 갱신: 2026-06-20 · D-018 Phase 0~4 완료 · D-020 건물 grain 제외*
